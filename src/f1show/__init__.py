"""F1Show: replay-testable, real-time Formula 1 commentary system.

The public surface is the typed configuration, the secret-safe logging helpers,
the shared contracts (events, enrichment and dialogue) and the injection
boundaries: the ports plus their shipped in-memory test doubles.
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
from f1show.fakes import (
    FakeHttpClient,
    FrozenClock,
    InMemoryBus,
    InMemoryStore,
    ScriptedModelClient,
)
from f1show.ports import (
    Bus,
    Clock,
    HttpClient,
    ModelClient,
    ModelRequest,
    ModelResponse,
    Store,
)
from f1show.redaction import REDACTED, RedactingFilter, attach_redacting_filter, redact

__all__ = [
    "DEFAULT_OPENF1_BASE_URL", "DEFAULT_REQUEST_TIMEOUT_SECONDS", "REDACTED", "Attribution",
    "BoothSettings", "Bus", "Clock", "CredentialsSettings", "DriverRecord",
    "EnrichmentKind", "EnrichmentRecord", "EventEnvelope", "EventType", "FakeHttpClient",
    "FrozenClock", "HttpClient", "InMemoryBus", "InMemoryStore", "Mode", "ModelClient",
    "ModelProvider", "ModelRequest", "ModelResponse", "Provenance", "RedactingFilter",
    "ReplaySettings", "ScriptedModelClient", "SessionRecord", "Settings", "SourceSettings",
    "Speaker", "Store", "TimeWindowSettings", "Transcript", "Turn", "attach_redacting_filter",
    "redact",
]
