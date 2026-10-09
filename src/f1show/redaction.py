"""Secret-safe logging.

The application handles credentials that must never reach a log sink. Pydantic's
``SecretStr`` protects the *model* surfaces (``repr``, ``str``, ``model_dump``),
but a secret can still be interpolated into a log message. This module closes
that hole at the logging boundary, including values that arrive through
``%``-style arguments rather than the pre-formatted message.

The filter is deliberately the right place for this work, not the formatter:

* A formatter runs *after* the filter, so it sees whatever the record already
  holds. Redacting there would mean every formatter has to cooperate. Doing it
  here means the record itself is clean before any formatter or handler runs.
* ``record.exc_info`` is rendered by the formatter itself, so a filter that
  only rewrites ``record.exc_text`` still leaks a secret inside an exception
  message or traceback. This filter renders ``exc_info`` to text with a
  :class:`logging.Formatter`, redacts that text, stores it back on
  ``record.exc_text`` and clears ``record.exc_info``. Once cleared, the
  formatter can only append the already-redacted text.
* Log arguments are walked recursively: mappings (keys and values), lists,
  tuples, sets and frozensets are descended into, with a depth cap and visited
  identities so a self-referential structure can neither hang nor overflow the
  stack. A ``str`` is a leaf and is never iterated.
* Bytes secrets are decoded as UTF-8 (``errors="replace"``) and kept in their
  ``repr`` form as well, so a secret supplied as bytes is removed whether the
  output shows the plain text or ``b'…'``.
* Two consequences are accepted trade-offs of this technique, not defects, and
  must not be "fixed" into a leak. Rendering ``exc_info`` inside the filter runs
  ``Formatter.formatException`` for every record that carries exception info,
  including records a later filter or level test may drop before they are ever
  emitted. And clearing ``record.exc_info`` means a consumer that wanted the
  structured exception object no longer receives it; all that remains is the
  redacted text on ``record.exc_text``. Both are the price of guaranteeing the
  formatter can never re-render a raw traceback.

Installation is also part of the contract. A filter attached to a *logger* does
not run for records that a child logger propagates into that logger's handlers;
only filters on the *handlers* are applied. :func:`attach_redacting_filter`
therefore attaches to the logger and to each of its handlers, and is idempotent
so repeated calls cannot stack duplicate filters.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, cast

#: The fixed placeholder that replaces every registered secret.
REDACTED = "[REDACTED]"

#: How deep the argument walker descends before it gives up on a branch. Any
#: container beyond this is replaced by :data:`REDACTED`, never passed through.
MAX_REDACTION_DEPTH = 8

SecretLike = object


def _secret_texts(value: SecretLike) -> tuple[str, ...]:
    """Return the text forms of one candidate secret.

    ``SecretStr`` values are unwrapped first. Bytes contribute both the decoded
    text (``errors="replace"``) and the Python ``repr``, so ``b"abc"`` removes
    both ``abc`` and ``b'abc'``. Everything else is matched by its text form.
    """
    if value is None:
        return ()
    get_secret_value = getattr(value, "get_secret_value", None)
    if callable(get_secret_value):
        value = get_secret_value()
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        if not raw:
            return ()
        decoded = raw.decode("utf-8", errors="replace")
        # The repr comes first so a rendered ``b'…'`` is replaced as a whole
        # rather than becoming ``b'[REDACTED]'``.
        return tuple(text for text in (repr(raw), decoded) if text)
    if not isinstance(value, str):
        value = str(value)
    return (value,) if value else ()


def _normalize(secrets: Iterable[SecretLike] | SecretLike | None) -> tuple[str, ...]:
    """Return the unique, non-empty secret strings to redact."""
    if secrets is None:
        return ()
    if isinstance(secrets, (str, bytes, bytearray)) or hasattr(secrets, "get_secret_value"):
        candidates: Iterable[SecretLike] = (secrets,)
    else:
        candidates = cast("Iterable[SecretLike]", secrets)
    seen: dict[str, None] = {}
    for candidate in candidates:
        for text in _secret_texts(candidate):
            seen.setdefault(text, None)
    return tuple(seen)


def redact(text: str, secrets: Iterable[SecretLike] | SecretLike | None = None) -> str:
    """Replace every supplied secret in ``text`` with :data:`REDACTED`."""
    if not text:
        return text
    result = text
    for secret in _normalize(secrets):
        if secret in result:
            result = result.replace(secret, REDACTED)
    return result


class RedactingFilter(logging.Filter):
    """A logging filter that removes registered secrets from every record.

    The filter rewrites ``record.msg``, ``record.args`` and ``record.exc_info``
    in place, so a formatter always renders redacted output. Handlers downstream
    see no secret, whatever formatting style the caller used.
    """

    def __init__(self, secrets: Iterable[SecretLike] | SecretLike | None = None, name: str = "") -> None:
        super().__init__(name)
        self._secrets: tuple[str, ...] = _normalize(secrets)

    @property
    def secrets(self) -> tuple[str, ...]:
        """The registered secret values. Never log or dump this."""
        return self._secrets

    def add_secret(self, secret: SecretLike) -> None:
        """Register one more secret value to redact."""
        for text in _secret_texts(secret):
            if text not in self._secrets:
                self._secrets = (*self._secrets, text)

    def redact(self, text: str) -> str:
        """Redact the filter's registered secrets from ``text``."""
        return redact(text, self._secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._redact_value(value) for value in record.args)
        elif isinstance(record.args, dict):
            # Mapping-style args are format placeholders: only the values may
            # be walked, because rewriting a key would break "%(key)s".
            record.args = {key: self._redact_value(value) for key, value in record.args.items()}
        if record.exc_info is not None:
            if not record.exc_text:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_info = None
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        return True

    def _redact_value(
        self,
        value: object,
        _visited: set[int] | None = None,
        _depth: int = 0,
    ) -> object:
        """Return ``value`` with every secret removed, descending containers.

        ``_visited`` holds the identities on the current descent path, so a
        container that references itself is replaced by :data:`REDACTED` rather
        than recursed into forever. A plain ``str`` is returned through
        :meth:`redact` as a leaf before any container check runs.
        """
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, (dict, list, tuple, set, frozenset)):
            visited = set() if _visited is None else _visited
            marker = id(value)
            if marker in visited or _depth >= MAX_REDACTION_DEPTH:
                return REDACTED
            visited.add(marker)
            try:
                if isinstance(value, dict):
                    return {
                        self._redact_value(key, visited, _depth + 1): self._redact_value(
                            item, visited, _depth + 1
                        )
                        for key, item in value.items()
                    }
                items = [self._redact_value(item, visited, _depth + 1) for item in value]
            finally:
                visited.discard(marker)
            try:
                if isinstance(value, tuple) and hasattr(value, "_fields"):
                    return cast("Any", type(value))(*items)
                return type(value)(items)
            except Exception:
                # ``type(value)(items)`` is false for some container types.
                # Fail closed: replace the whole container rather than raising
                # or letting it through, so no secret can survive unanswered.
                return REDACTED
        return value


def attach_redacting_filter(
    logger: logging.Logger,
    secrets: Iterable[SecretLike] | SecretLike | None = None,
) -> RedactingFilter:
    """Attach a :class:`RedactingFilter` to ``logger`` and to its handlers.

    Filters attached to a *logger* only see records logged through that logger.
    A record propagated from a child logger is delivered straight to the
    parent's handlers, where the parent's logger-level filter never runs, so a
    logger-only installation still lets a child's secret reach the sink.
    Attaching to each handler is what actually protects the sink; the
    logger-level filter additionally covers records logged through the logger
    itself.

    The call is idempotent: reusing it returns the already-installed filter and
    adds no duplicate handler filters. Handlers that were attached before the
    call are covered. Secrets passed on a later call are registered on the
    existing filter.
    """
    log_filter = next((f for f in logger.filters if isinstance(f, RedactingFilter)), None)
    if log_filter is None:
        log_filter = RedactingFilter(secrets)
        logger.addFilter(log_filter)
    else:
        for secret in _normalize(secrets):
            log_filter.add_secret(secret)
    for handler in logger.handlers:
        if not any(existing is log_filter for existing in handler.filters):
            handler.addFilter(log_filter)
    return log_filter
