"""Single-endpoint historical ingestion: validate, persist, then checkpoint.

One call ingests **one endpoint for one session**: it validates and prepares the
entire payload before touching the store, asks the injected clock for exactly
one observation stamp, writes the whole batch, and only then advances the
matching observation checkpoint with that same stamp.

**What this module deliberately does not do.** It is not an HTTP client, it has
no session lifecycle, no retries, no paging and no cursor. The endpoint name is
the canonical family identifier (``sessions`` or ``drivers``), not a URL and not
a source-date filter, because only those two families have ever been observed.
Unknown provider fields are dropped by the existing record models
(``extra="ignore"``); this is a canonical projection of the known shape, **not**
a lossless raw-payload archive and not the F04 event normalization.

**Honest partial outcomes, not false rollback.** Records and the checkpoint are
two separate store calls, not one transaction. If the write succeeds and the
checkpoint then fails, the records are already committed; the outcome keeps the
acknowledged write count and the valid stamp and reports ``checkpoint_written``
as ``False``. A higher layer that retries re-upserts the same identities
idempotently, so a repeat converges instead of duplicating. Nothing here claims
a rollback that did not happen.

**Counts.** ``records_written`` is the count the store acknowledged for accepted
or upserted rows, not the number of newly inserted unique rows. It is ``None``
when a write failed and the committed count is therefore unknown, rather than a
pretended zero.

**Composition (F03c-3b).** :func:`sync_session` is the bounded two-endpoint layer
over the single-endpoint core: it asks a caller-provided ``HttpClient`` for the
fixed ``sessions`` and then ``drivers`` URLs for one session, and delegates each
admitted 2xx payload exactly once to :func:`ingest_endpoint`. It adds no retry,
timeout, pacing or rate policy of its own - those stay the caller's
``HttpClient`` - and it never opens, closes or wraps the client or the store. A
non-2xx status or an ordinary fetch failure becomes a ``fetch``-stage failed
outcome carrying only a safe exception class name or the stable
``HTTPStatus<code>`` token; the second endpoint is always attempted.
Cancellation and process-control ``BaseException`` propagate, and a cancellation
during the second request may leave the first endpoint committed, because there
is no cross-request transaction to roll back.

**Not swallowed.** Only regular exceptions from the clock, the write and the
checkpoint calls are converted into a failed outcome, and only around those
named calls. ``BaseException`` is never caught, so ``CancelledError``,
``KeyboardInterrupt`` and ``SystemExit`` propagate and no checkpoint is written
after a cancellation. The caller owns the store: this module never opens or
closes it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from f1show.config import DEFAULT_OPENF1_BASE_URL
from f1show.events import DriverRecord, SessionRecord
from f1show.ports import Clock, HttpClient, Store

EndpointName = Literal["sessions", "drivers"]
EndpointStatus = Literal["ok", "empty", "failed"]
FailureStage = Literal["validation", "clock", "write", "checkpoint", "fetch"]

#: The canonical family for each supported endpoint. Written out instead of
#: aliasing the endpoint so a future family rename stays a one-line change here.
_FAMILY_BY_ENDPOINT: Mapping[EndpointName, str] = {
    "sessions": "sessions",
    "drivers": "drivers",
}

#: The model that admits each endpoint's observed shape.
_MODEL_BY_ENDPOINT: Mapping[EndpointName, type[SessionRecord] | type[DriverRecord]] = {
    "sessions": SessionRecord,
    "drivers": DriverRecord,
}

#: The fixed composition order for one session sync: sessions first, then drivers.
_SYNC_ENDPOINTS: tuple[EndpointName, ...] = ("sessions", "drivers")


class SourceValidationError(ValueError):
    """A structural or session-scope problem in the caller's payload.

    Raised before any store mutation and reported only through
    ``EndpointOutcome.failure_type``, so it never carries provider data.
    """


class ObservationClockError(Exception):
    """The clock returned a reading that violates its own contract.

    A naive, timezone-free or non-UTC instant is refused by the caller of the
    port, so there is no library exception to name; this is the stable local
    type for that refusal.
    """


@dataclass(frozen=True)
class EndpointOutcome:
    """The honest result of one endpoint ingestion attempt.

    There is deliberately no aggregate success flag: ``status`` plus
    ``failure_stage`` says everything, and a boolean that ignored partial writes
    would be the one field a caller could trust wrongly.
    """

    endpoint: EndpointName
    family: str
    status: EndpointStatus
    records_written: int | None
    observed_at: dt.datetime | None
    checkpoint_written: bool
    failure_stage: FailureStage | None
    failure_type: str | None


@dataclass(frozen=True)
class SessionSyncResult:
    """The honest result of one two-endpoint session sync.

    ``outcomes`` is an immutable, ordered tuple - ``sessions`` then ``drivers`` -
    with exactly one :class:`EndpointOutcome` per requested endpoint, including the
    failed ones. Like the single-endpoint outcome there is deliberately no
    aggregate success flag: a boolean that flattened a partial result would be the
    one field a caller could trust wrongly.
    """

    session_key: int
    outcomes: tuple[EndpointOutcome, ...]

    def __post_init__(self) -> None:
        # A frozen record that could still hold a caller's mutable list would not
        # be immutable, so the sequence is copied into a tuple once.
        object.__setattr__(self, "outcomes", tuple(self.outcomes))


def _require_endpoint(endpoint: object) -> None:
    """Reject anything that is not a supported canonical endpoint name."""
    if not isinstance(endpoint, str) or endpoint not in _FAMILY_BY_ENDPOINT:
        raise ValueError("endpoint must be one of 'sessions' or 'drivers'")


def _require_session_key(session_key: object) -> None:
    """Reject a session key that is not a positive integer.

    ``bool`` is checked first because it is an ``int`` subclass; ``True`` is not
    a session.
    """
    if isinstance(session_key, bool) or not isinstance(session_key, int) or session_key <= 0:
        raise ValueError("session_key must be a positive integer")


def _derive_record_id(endpoint: EndpointName, session_key: int, row: Mapping[str, object]) -> str:
    """Derive the local record identity from the family's stable keys.

    ``sessions`` is one row per session; ``drivers`` is one row per
    session/driver pair. Any identity the provider payload happened to carry is
    ignored, so it can never override this derivation.
    """
    if endpoint == "sessions":
        return str(session_key)
    return f"{session_key}-{row['driver_number']}"


def _prepare_rows(
    endpoint: EndpointName, session_key: int, payload: object
) -> list[dict[str, object]]:
    """Validate the whole payload and project it to canonical store rows.

    Nothing is written until every item has been admitted, so one bad item
    rejects the entire batch before any store mutation. The caller's payload is
    never mutated: the rows are fresh dictionaries built from the model's JSON
    projection plus the derived identity.
    """
    if not isinstance(payload, list):
        raise SourceValidationError("payload must be a list of record mappings")
    model = _MODEL_BY_ENDPOINT[endpoint]
    rows: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise SourceValidationError("every payload item must be a record mapping")
        record = model.model_validate(item)
        if record.session_key != session_key:
            raise SourceValidationError("a payload record does not belong to the requested session")
        row = record.model_dump(mode="json")
        row["record_id"] = _derive_record_id(endpoint, session_key, row)
        rows.append(row)
    return rows


def _require_utc_instant(reading: object) -> dt.datetime:
    """Refuse a clock reading that is not an aware UTC datetime."""
    if not isinstance(reading, dt.datetime):
        raise ObservationClockError("clock did not return a datetime")
    if reading.tzinfo is None or reading.utcoffset() is None:
        raise ObservationClockError("clock returned a naive datetime")
    if reading.utcoffset() != dt.timedelta(0):
        raise ObservationClockError("clock returned a datetime that is not UTC")
    return reading


def _failed(
    endpoint: EndpointName,
    family: str,
    stage: FailureStage,
    failure_type: str,
    *,
    records_written: int | None,
    observed_at: dt.datetime | None = None,
) -> EndpointOutcome:
    """Build a failed outcome; the failure type is never a message or payload."""
    return EndpointOutcome(
        endpoint=endpoint,
        family=family,
        status="failed",
        records_written=records_written,
        observed_at=observed_at,
        checkpoint_written=False,
        failure_stage=stage,
        failure_type=failure_type,
    )


async def ingest_endpoint(
    store: Store,
    clock: Clock,
    *,
    endpoint: EndpointName,
    session_key: int,
    payload: object,
) -> EndpointOutcome:
    """Ingest one endpoint's payload for one session, then checkpoint it.

    ``store`` and ``clock`` are injected and caller-owned. The store is never
    opened or closed here. A valid empty payload is a successful observation:
    the zero-row write and the checkpoint both happen, and ``status`` is
    ``"empty"``.
    """
    _require_endpoint(endpoint)
    _require_session_key(session_key)
    family = _FAMILY_BY_ENDPOINT[endpoint]

    try:
        rows = _prepare_rows(endpoint, session_key, payload)
    except (SourceValidationError, ValidationError) as error:
        return _failed(
            endpoint, family, "validation", type(error).__name__, records_written=0
        )

    try:
        observed_at = _require_utc_instant(clock.now())
    except ObservationClockError as error:
        return _failed(
            endpoint, family, "clock", type(error).__name__, records_written=0
        )
    except Exception as error:
        return _failed(
            endpoint, family, "clock", type(error).__name__, records_written=0
        )

    try:
        written = await store.write_source_batch(
            family, session_key, rows, observed_at=observed_at
        )
    except Exception as error:
        # The committed count is unknown after a failed write; claiming zero
        # would be a fiction, and the checkpoint is not attempted.
        return _failed(
            endpoint,
            family,
            "write",
            type(error).__name__,
            records_written=None,
            observed_at=observed_at,
        )

    try:
        await store.set_watermark(endpoint, session_key, observed_at=observed_at)
    except Exception as error:
        # The records are already committed; only the checkpoint is missing.
        return _failed(
            endpoint,
            family,
            "checkpoint",
            type(error).__name__,
            records_written=written,
            observed_at=observed_at,
        )

    status: EndpointStatus = "ok" if rows else "empty"
    return EndpointOutcome(
        endpoint=endpoint,
        family=family,
        status=status,
        records_written=written,
        observed_at=observed_at,
        checkpoint_written=True,
        failure_stage=None,
        failure_type=None,
    )


async def sync_session(
    http: HttpClient,
    store: Store,
    clock: Clock,
    *,
    session_key: int,
    base_url: str = DEFAULT_OPENF1_BASE_URL,
) -> SessionSyncResult:
    """Fetch and ingest both fixed endpoints for one session.

    ``http``, ``store`` and ``clock`` are injected and caller-owned: this function
    never opens, closes, wraps or rate-limits them, and it makes exactly one
    ``get_json`` call per endpoint. Retries, pacing and timeouts are the caller's
    policy, applied through whatever ``HttpClient`` it passes (for example the
    published ``RetryingHttpClient`` over a shared ``RateLimiter``); none is added
    here.

    An admitted 2xx payload is delegated exactly once to :func:`ingest_endpoint`, so
    its validation/clock/write/checkpoint stages and its honest count and stamp
    survive unchanged. A non-2xx status or a regular fetch failure becomes a
    ``fetch``-stage failed outcome carrying only a safe class name or the stable
    status code, never a message, URL, header, cause or payload. The second
    endpoint is always attempted, even when the first failed. A cancellation or a
    process-control ``BaseException`` propagates with no manufactured result; a
    cancellation during the second request may leave the first endpoint committed,
    because the two endpoints are not one transaction.
    """
    _require_session_key(session_key)
    # The published base URL may or may not carry the trailing separator; the two
    # fixed paths are joined to whichever form arrived, with no new configuration.
    base = base_url.rstrip("/")
    params = {"session_key": str(session_key)}
    outcomes: list[EndpointOutcome] = []
    for endpoint in _SYNC_ENDPOINTS:
        family = _FAMILY_BY_ENDPOINT[endpoint]
        try:
            response = await http.get_json(f"{base}/{endpoint}", params=params)
        except Exception as error:
            # An ordinary fetch failure: the exception's own text may repeat a URL,
            # header or provider payload, so only its class name is kept.
            outcomes.append(
                _failed(endpoint, family, "fetch", type(error).__name__, records_written=0)
            )
            continue
        if not 200 <= response.status_code < 300:
            # A non-2xx answer is data, and only its stable status code is recorded.
            outcomes.append(
                _failed(
                    endpoint,
                    family,
                    "fetch",
                    f"HTTPStatus{response.status_code}",
                    records_written=0,
                )
            )
            continue
        outcomes.append(
            await ingest_endpoint(
                store,
                clock,
                endpoint=endpoint,
                session_key=session_key,
                payload=response.payload,
            )
        )
    return SessionSyncResult(session_key=session_key, outcomes=tuple(outcomes))
