"""F1Show: replay-testable, real-time Formula 1 commentary system.

The public surface is the typed configuration, the secret-safe logging helpers,
and the shared contracts: events, enrichment and dialogue. Injection boundaries
land in F02b-2.
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
from f1show.dialogue import Speaker, Transcript, Turn
from f1show.enrichment import Attribution, EnrichmentKind, EnrichmentRecord
from f1show.events import (
    DriverRecord,
    EventEnvelope,
    EventType,
    Provenance,
    SessionRecord,
)
from f1show.redaction import REDACTED, RedactingFilter, attach_redacting_filter, redact

__all__ = [
    "DEFAULT_OPENF1_BASE_URL", "DEFAULT_REQUEST_TIMEOUT_SECONDS", "REDACTED", "Attribution",
    "BoothSettings", "CredentialsSettings", "DriverRecord", "EnrichmentKind",
    "EnrichmentRecord", "EventEnvelope", "EventType", "Mode", "ModelProvider", "Provenance",
    "RedactingFilter", "ReplaySettings", "SessionRecord", "Settings", "SourceSettings",
    "Speaker", "TimeWindowSettings", "Transcript", "Turn", "attach_redacting_filter", "redact",
]
