"""F1Show: replay-testable, real-time Formula 1 commentary system.

The public surface is the typed configuration, the secret-safe logging helpers,
the shared contracts (events, enrichment and dialogue), the injection boundaries
(the ports plus their shipped in-memory test doubles) and the session fixtures:
immutable parquet snapshots plus the deterministic replay source that reads them.
"""

from __future__ import annotations

from f1show.config import (
    DEFAULT_OPENF1_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_STORE_PATH,
    BoothSettings,
    CredentialsSettings,
    Mode,
    ModelProvider,
    ReplaySettings,
    Settings,
    SourceSettings,
    StoreSettings,
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
from f1show.replay import SessionMismatchError, SnapshotReplaySource
from f1show.snapshot import write_session_snapshot
from f1show.store import SQLiteStore

__all__ = [
    "DEFAULT_OPENF1_BASE_URL", "DEFAULT_REQUEST_TIMEOUT_SECONDS", "DEFAULT_STORE_PATH", "REDACTED",
    "Attribution", "BoothSettings", "Bus", "Clock", "CredentialsSettings", "DriverRecord",
    "EnrichmentKind", "EnrichmentRecord", "EventEnvelope", "EventType", "FakeHttpClient",
    "FrozenClock", "HttpClient", "InMemoryBus", "InMemoryStore", "Mode", "ModelClient",
    "ModelProvider", "ModelRequest", "ModelResponse", "Provenance", "RedactingFilter",
    "ReplaySettings", "SQLiteStore", "ScriptedModelClient", "SessionMismatchError", "SessionRecord",
    "Settings", "SnapshotReplaySource", "SnapshotResult", "SourceSettings", "Speaker", "Store",
    "StoreSettings", "TimeWindowSettings", "Transcript", "Turn", "attach_redacting_filter",
    "redact", "write_session_snapshot",
]
