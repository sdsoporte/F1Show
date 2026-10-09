"""Offline acceptance tests for secret redaction."""

from __future__ import annotations

import io
import logging
import sys
from collections.abc import Iterable
from typing import Any

from f1show.redaction import REDACTED, RedactingFilter, attach_redacting_filter, redact


def test_redact_replaces_every_occurrence_of_every_secret() -> None:
    text = "user=alice token=tok-1 retry token=tok-1"
    assert redact(text, ["tok-1", "alice"]) == f"user={REDACTED} token={REDACTED} retry token={REDACTED}"


def test_redact_ignores_none_and_empty_secrets() -> None:
    assert redact("nothing to hide", [None, ""]) == "nothing to hide"


def test_redact_accepts_secretstr_values(make_settings) -> None:
    settings = make_settings(
        mode="replay",
        replay={"session_key": 1},
        booth={"model_id": "test-model", "language": "en"},
        credentials={"gemini_api_key": "fake-key"},
    )
    assert redact("key=fake-key", [settings.credentials.gemini_api_key]) == f"key={REDACTED}"


def _record(msg: str, args: Any = ()) -> logging.LogRecord:
    return logging.LogRecord(
        name="f1show.test.record",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def _rendered(msg: str, args: Any, secrets: Iterable[Any]) -> str:
    """Run the filter over a real record and render it with a real formatter."""
    record = _record(msg, args)
    assert RedactingFilter(secrets).filter(record) is True
    return logging.Formatter("%(levelname)s %(message)s").format(record)


def _bare_logger(name: str) -> logging.Logger:
    """Return a logger with no inherited handlers or filters."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
    for existing in list(logger.filters):
        logger.removeFilter(existing)
    return logger


def _logger(name: str, secrets) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = True
    attach_redacting_filter(logger, secrets)
    return logger


def test_filter_redacts_percent_style_args(caplog) -> None:
    logger = _logger("f1show.test.percent", ["s3cr3t-token"])
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        logger.info("auth token=%s", "s3cr3t-token")
    assert "s3cr3t-token" not in caplog.text
    assert REDACTED in caplog.text


def test_filter_redacts_mapping_style_args(caplog) -> None:
    logger = _logger("f1show.test.mapping", ["s3cr3t-token"])
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        logger.info("payload=%(token)s", {"token": "s3cr3t-token"})
    assert "s3cr3t-token" not in caplog.text


def test_filter_redacts_preformatted_message(caplog) -> None:
    logger = _logger("f1show.test.preformatted", ["s3cr3t-token"])
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        logger.info("literal value s3cr3t-token in message")
    assert "s3cr3t-token" not in caplog.text


def test_filter_redacts_secrets_inside_larger_arguments(caplog) -> None:
    logger = _logger("f1show.test.nested", ["s3cr3t-token"])
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        logger.info("url=%s", "https://user:s3cr3t-token@example.test/v1")
    assert "s3cr3t-token" not in caplog.text
    assert "example.test" in caplog.text


def test_attach_returns_the_filter_and_registers_it(caplog) -> None:
    logger = logging.getLogger("f1show.test.attach")
    logger.setLevel(logging.DEBUG)
    for existing in list(logger.filters):
        logger.removeFilter(existing)
    result = attach_redacting_filter(logger, ["top-secret"])
    assert isinstance(result, RedactingFilter)
    assert result in logger.filters
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        logger.warning("value=%s", "top-secret")
    assert "top-secret" not in caplog.text


def test_registering_more_secrets_after_construction(caplog) -> None:
    logger = logging.getLogger("f1show.test.late")
    logger.setLevel(logging.DEBUG)
    for existing in list(logger.filters):
        logger.removeFilter(existing)
    log_filter = attach_redacting_filter(logger, [])
    log_filter.add_secret("late-secret")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        logger.error("boom %s", "late-secret")
    assert "late-secret" not in caplog.text


def test_filter_redacts_secrets_inside_exception_info() -> None:
    try:
        raise RuntimeError("provider rejected key s3cr3t-token")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="f1show.test.exc",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="request failed",
        args=(),
        exc_info=exc_info,
    )
    assert RedactingFilter(["s3cr3t-token"]).filter(record) is True
    # The raw traceback must no longer be renderable by a formatter.
    assert record.exc_info is None
    rendered = logging.Formatter("%(levelname)s %(message)s").format(record)
    assert "s3cr3t-token" not in rendered
    assert REDACTED in rendered


def test_filter_redacts_a_dict_nested_inside_a_list_argument() -> None:
    rendered = _rendered("payload=%s", ([{"token": "s3cr3t-token"}],), ["s3cr3t-token"])
    assert "s3cr3t-token" not in rendered
    assert REDACTED in rendered


def test_filter_redacts_a_list_nested_inside_a_mapping_argument() -> None:
    # The list is one level below the top-level mapping argument, behind a
    # nested mapping, so the walker must descend through mappings to reach it.
    rendered = _rendered(
        "payload=%(data)s",
        ({"data": {"items": ["s3cr3t-token"]}},),
        ["s3cr3t-token"],
    )
    assert "s3cr3t-token" not in rendered
    assert REDACTED in rendered


def test_filter_redacts_a_nested_mapping_key_and_value() -> None:
    rendered = _rendered(
        "payload=%s",
        ({"inner": {"s3cr3t-key": "s3cr3t-value"}},),
        ["s3cr3t-key", "s3cr3t-value"],
    )
    assert "s3cr3t-key" not in rendered
    assert "s3cr3t-value" not in rendered


def test_filter_redacts_secrets_inside_sets_and_tuples() -> None:
    as_set = _rendered("payload=%s", ({"keep", "s3cr3t-token"},), ["s3cr3t-token"])
    assert "s3cr3t-token" not in as_set
    as_tuple = _rendered("payload=%s", (("keep", "s3cr3t-token"),), ["s3cr3t-token"])
    assert "s3cr3t-token" not in as_tuple


def test_redact_matches_bytes_secrets_in_plain_and_repr_form() -> None:
    assert redact("token=abcdef", [b"abcdef"]) == f"token={REDACTED}"
    assert redact("token=b'abcdef'", [b"abcdef"]) == f"token={REDACTED}"


def test_filter_redacts_bytes_secrets_from_rendered_output() -> None:
    plain = _rendered("token=abcdef", (), [b"abcdef"])
    assert "abcdef" not in plain
    assert REDACTED in plain

    repr_form = _rendered("token=b'abcdef'", (), [b"abcdef"])
    assert "abcdef" not in repr_form


def test_filter_handles_a_self_referential_argument_without_hanging() -> None:
    payload: list[object] = ["s3cr3t-token"]
    payload.append(payload)
    rendered = _rendered("payload=%s", (payload,), ["s3cr3t-token"])
    assert "s3cr3t-token" not in rendered


def test_installation_is_idempotent_and_covers_handlers() -> None:
    logger = _bare_logger("f1show.test.install")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    first = attach_redacting_filter(logger, ["install-secret"])
    second = attach_redacting_filter(logger, ["install-secret"])

    assert first is second
    assert sum(isinstance(f, RedactingFilter) for f in logger.filters) == 1
    for attached in logger.handlers:
        assert sum(isinstance(f, RedactingFilter) for f in attached.filters) == 1

    logger.warning("token=%s", "install-secret")
    assert "install-secret" not in stream.getvalue()
    assert REDACTED in stream.getvalue()


def test_installation_covers_handlers_for_records_from_child_loggers() -> None:
    parent = _bare_logger("f1show.test.propagation")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    parent.addHandler(handler)
    attach_redacting_filter(parent, ["propagated-secret"])

    child = logging.getLogger("f1show.test.propagation.child")
    child.setLevel(logging.DEBUG)
    child.propagate = True

    child.info("token=%s", "propagated-secret")
    assert "propagated-secret" not in stream.getvalue()
    assert REDACTED in stream.getvalue()


def test_filter_passes_records_through() -> None:
    record = logging.LogRecord(
        name="f1show.test.record",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=%s",
        args=("abc123",),
        exc_info=None,
    )
    log_filter = RedactingFilter(["abc123"])
    assert log_filter.filter(record) is True
    assert record.getMessage() == f"token={REDACTED}"
