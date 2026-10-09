"""Secret-safe logging.

The application handles credentials that must never reach a log sink. Pydantic's
``SecretStr`` protects the *model* surfaces (``repr``, ``str``, ``model_dump``),
but a secret can still be interpolated into a log message. This module closes
that hole at the logging boundary, including values that arrive through
``%``-style arguments rather than the pre-formatted message.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import cast

#: The fixed placeholder that replaces every registered secret.
REDACTED = "[REDACTED]"

SecretLike = object


def _secret_text(value: SecretLike) -> str | None:
    """Normalise one candidate into text, unwrapping ``SecretStr`` values."""
    if value is None:
        return None
    get_secret_value = getattr(value, "get_secret_value", None)
    if callable(get_secret_value):
        value = get_secret_value()
    if not isinstance(value, str):
        value = str(value)
    return value or None


def _normalize(secrets: Iterable[SecretLike] | SecretLike | None) -> tuple[str, ...]:
    """Return the unique, non-empty secret strings to redact."""
    if secrets is None:
        return ()
    if isinstance(secrets, (str, bytes)) or hasattr(secrets, "get_secret_value"):
        candidates: Iterable[SecretLike] = (secrets,)
    else:
        candidates = cast("Iterable[SecretLike]", secrets)
    seen: dict[str, None] = {}
    for candidate in candidates:
        text = _secret_text(candidate)
        if text:
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

    The filter rewrites ``record.msg``, ``record.args`` and any cached
    ``record.exc_text`` in place, so a formatter always renders redacted output.
    Handlers downstream see no secret, whatever formatting style the caller used.
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
        text = _secret_text(secret)
        if text and text not in self._secrets:
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
            record.args = {key: self._redact_value(value) for key, value in record.args.items()}
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        return True

    def _redact_value(self, value: object) -> object:
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, (list, tuple)) and not hasattr(value, "_fields"):
            return type(value)(self._redact_value(item) for item in value)
        return value


def attach_redacting_filter(
    logger: logging.Logger,
    secrets: Iterable[SecretLike] | SecretLike | None = None,
) -> RedactingFilter:
    """Attach a :class:`RedactingFilter` to ``logger`` and return it.

    Filters attached to a *logger* only see records logged through that logger;
    attach the returned filter to a handler as well when it must cover records
    propagated from child loggers.
    """
    log_filter = RedactingFilter(secrets)
    logger.addFilter(log_filter)
    return log_filter
