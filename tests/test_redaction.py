"""Offline acceptance tests for secret redaction."""

from __future__ import annotations

import logging

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
