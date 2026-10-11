"""F1Show: replay-testable, real-time Formula 1 commentary system.

The public surface is the typed configuration, the secret-safe logging helpers,
the shared contracts (events, enrichment and dialogue), the injection boundaries
(the ports plus their shipped in-memory test doubles), the session fixtures
(immutable parquet snapshots plus the deterministic replay source that reads them)
and, from F08, the Gemini gateway: the thin SDK adapter, the safeguards over any
model client, the measured usage record and the typed model failures. Measured
model usage is reported, never enforced: it is not a hard spend limit and no cost
stop exists before F13.
"""

from __future__ import annotations

from f1show.auth import (
    DEFAULT_OPENF1_TOKEN_URL,
    TOKEN_REFRESH_SKEW_SECONDS,
    AccessToken,
    AuthenticatedHttpClient,
    AuthError,
    OpenF1TokenProvider,
    TokenDecodeError,
    TokenExchangeError,
    TokenPayload,
    TokenPayloadError,
    TokenTransportError,
    parse_token_payload,
)
from f1show.collector import (
    DetectedEvent,
    GapKind,
    GapReading,
    classify_gap,
    collect_session_events,
)
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
    FakeMonotonicClock,
    FrozenClock,
    InMemoryBus,
    InMemoryStore,
    ScriptedModelClient,
)
from f1show.gemini import (
    GoogleGenAIClient,
    ModelError,
    ModelRateLimitedError,
    ModelResponseError,
    ModelServerError,
    ModelTimeoutError,
    ModelTransportError,
    ModelUsage,
    SafeguardedModelClient,
)
from f1show.http import HttpxJsonClient
from f1show.ingest import (
    EndpointOutcome,
    SessionSyncResult,
    ingest_endpoint,
    sync_session,
)
from f1show.ports import (
    Bus,
    Clock,
    HttpClient,
    HttpDecodeError,
    HttpError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
    ModelClient,
    ModelRequest,
    ModelResponse,
    MonotonicClock,
    Store,
)
from f1show.redaction import REDACTED, RedactingFilter, attach_redacting_filter, redact
from f1show.replay import SessionMismatchError, SnapshotReplaySource
from f1show.request_policy import (
    PacingPolicy,
    RateLimiter,
    RetryingHttpClient,
    RetryPolicy,
)
from f1show.session import (
    RunNotActiveError,
    RunState,
    SessionRun,
    SessionRunIdentity,
    StaleRunError,
    StoreOwnershipError,
)
from f1show.snapshot import SnapshotResult, write_session_snapshot
from f1show.store import SQLiteStore

__all__ = [
    "DEFAULT_OPENF1_BASE_URL", "DEFAULT_REQUEST_TIMEOUT_SECONDS", "DEFAULT_STORE_PATH", "REDACTED",
    "Attribution", "BoothSettings", "Bus", "Clock", "CredentialsSettings", "DriverRecord",
    "EndpointOutcome",
    "EnrichmentKind", "EnrichmentRecord", "EventEnvelope", "EventType", "FakeHttpClient",
    "FakeMonotonicClock", "FrozenClock", "HttpClient", "HttpDecodeError", "HttpError", "HttpResponse",
    "HttpResponseTooLargeError", "HttpTimeoutError", "HttpTransportError", "HttpxJsonClient",
    "InMemoryBus", "InMemoryStore", "Mode", "ModelClient",
    "ModelProvider", "ModelRequest", "ModelResponse", "MonotonicClock", "PacingPolicy", "Provenance",
    "RateLimiter", "RedactingFilter",
    "ReplaySettings", "RetryPolicy", "RetryingHttpClient", "SQLiteStore", "ScriptedModelClient",
    "SessionMismatchError", "SessionRecord",
    "RunNotActiveError", "RunState", "SessionRun", "SessionRunIdentity", "StaleRunError",
    "StoreOwnershipError",
    "Settings", "SnapshotReplaySource", "SnapshotResult", "SourceSettings", "Speaker", "Store",
    "StoreSettings", "TimeWindowSettings", "Transcript", "Turn", "attach_redacting_filter",
    "SessionSyncResult", "ingest_endpoint", "redact", "sync_session", "write_session_snapshot",
    "DEFAULT_OPENF1_TOKEN_URL", "TOKEN_REFRESH_SKEW_SECONDS", "AccessToken", "AuthError",
    "AuthenticatedHttpClient", "OpenF1TokenProvider", "TokenDecodeError", "TokenExchangeError",
    "TokenPayload", "TokenPayloadError", "TokenTransportError", "parse_token_payload",
    "DetectedEvent", "GapKind", "GapReading", "classify_gap", "collect_session_events",
    # F08: the Gemini gateway, its safeguards, its usage record and its typed failures.
    "GoogleGenAIClient", "SafeguardedModelClient", "ModelUsage", "ModelError",
    "ModelTimeoutError", "ModelRateLimitedError", "ModelServerError", "ModelTransportError",
    "ModelResponseError",
]
