"""F1Show: replay-testable, real-time Formula 1 commentary system.

The package public surface is the typed configuration and the secret-safe
logging helpers. Shared contracts and injection boundaries land in F02b.
"""

from __future__ import annotations

from f1show.config import (
    DEFAULT_OPENF1_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    BoothSettings,
    CredentialsSettings,
    Mode,
    ModelProvider,
    ReplaySettings,
    Settings,
    SourceSettings,
    TimeWindowSettings,
)
from f1show.redaction import REDACTED, RedactingFilter, attach_redacting_filter, redact

__all__ = [
    "DEFAULT_OPENF1_BASE_URL",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS",
    "REDACTED",
    "BoothSettings",
    "CredentialsSettings",
    "Mode",
    "ModelProvider",
    "RedactingFilter",
    "ReplaySettings",
    "Settings",
    "SourceSettings",
    "TimeWindowSettings",
    "attach_redacting_filter",
    "redact",
]
