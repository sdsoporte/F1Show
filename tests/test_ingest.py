"""Offline acceptance tests for single-endpoint historical ingestion.

Every test is fully offline: no network, no model call and no wall clock. The
observation stamp always comes from an injected clock, and one parameterized
body drives the same assertions against the shipped in-memory double and a real
temporary ``SQLiteStore``, so a divergence between them cannot hide behind a
second, hand-written assertion.

The engine's contract is deliberately narrow: it validates and prepares the
entire endpoint before touching the store, writes records and only then writes
the matching observation checkpoint, and it reports partial outcomes honestly
instead of inventing an aggregate success.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import datetime as dt
import pathlib
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx
import pytest

from f1show.config import DEFAULT_OPENF1_BASE_URL
from f1show.fakes import FakeHttpClient, FakeMonotonicClock, FrozenClock, InMemoryStore
from f1show.http import HttpxJsonClient
from f1show.ingest import (
    EndpointOutcome,
    SessionSyncResult,
    ingest_endpoint,
    sync_session,
)
from f1show.ports import (
    HttpClient,
    HttpDecodeError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
    Store,
)
from f1show.request_policy import (
    PacingPolicy,
    RateLimiter,
    RetryingHttpClient,
    RetryPolicy,
)
from f1show.store import SQLiteStore

UTC = dt.timezone.utc
#: Event start/end come from the source payload; the observation stamp is
#: deliberately a different instant, several hours later, so a test can prove
#: the source's own dates never become the observation time.
SESSION_START = dt.datetime(2024, 3, 1, 11, 0, 0, tzinfo=UTC)
SESSION_END = dt.datetime(2024, 3, 1, 13, 0, 0, tzinfo=UTC)
OBSERVED = dt.datetime(2024, 3, 2, 20, 0, 0, tzinfo=UTC)
EARLIER = OBSERVED - dt.timedelta(hours=3)


def session_row(session_key: int = 9462, **overrides: object) -> dict[str, object]:
    """A source-shaped ``sessions`` row; dates arrive as JSON strings."""
    row: dict[str, object] = {
        "session_key": session_key,
        "session_name": "Race",
        "session_type": "Race",
        "date_start": SESSION_START.isoformat(),
        "date_end": SESSION_END.isoformat(),
        "meeting_key": 1236,
        "circuit_key": 63,
        "circuit_short_name": "Sakhir",
        "country_key": 7,
        "country_code": "BHR",
        "country_name": "Bahrain",
        "location": "Sakhir",
        "gmt_offset": "03:00:00",
        "year": 2024,
        "is_cancelled": False,
    }
    row.update(overrides)
    return row


def driver_row(
    session_key: int = 9462, driver_number: int = 1, **overrides: object
) -> dict[str, object]:
    """A source-shaped ``drivers`` row."""
    row: dict[str, object] = {
        "driver_number": driver_number,
        "broadcast_name": f"DRIVER {driver_number}",
        "first_name": "First",
        "last_name": "Last",
        "full_name": f"First Last {driver_number}",
        "name_acronym": f"D{driver_number:02d}",
        "country_code": "NED",
        "headshot_url": f"https://example.invalid/{driver_number}.png",
        "meeting_key": 1236,
        "session_key": session_key,
        "team_colour": "3671C6",
        "team_name": "Red Bull Racing",
    }
    row.update(overrides)
    return row


def open_store(tmp_path: pathlib.Path) -> SQLiteStore:
    """Open a real store on a fresh path inside the test's temporary directory."""
    return SQLiteStore(tmp_path / "ingest.sqlite3")


#: One factory per implementation. One shared body runs against both; a
#: hand-written assertion per implementation is exactly how a divergence
#: survived the last review.
STORE_FACTORIES = [
    pytest.param(lambda path: SQLiteStore(path / "parity.sqlite3"), id="sqlite"),
    pytest.param(lambda path: InMemoryStore(), id="in-memory"),
]


class CountingClock:
    """A clock stopped at one instant that also counts how often it was read."""

    def __init__(self, instant: dt.datetime) -> None:
        self._instant = instant
        self.calls = 0

    def now(self) -> dt.datetime:
        self.calls += 1
        return self._instant


class FixedReadingClock:
    """Returns whatever the test handed it, contract-valid or not."""

    def __init__(self, reading: object) -> None:
        self._reading = reading
        self.calls = 0

    def now(self) -> dt.datetime:  # type: ignore[return-value]
        self.calls += 1
        return self._reading  # type: ignore[return-value]


class RaisingClock:
    """A clock that fails the way a real clock boundary can."""

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls = 0

    def now(self) -> dt.datetime:
        self.calls += 1
        raise self._error


class TrackingStore:
    """Delegates to a real store while recording call order and arguments.

    The record is what proves the two orderings the contract demands: the whole
    batch is written before the checkpoint, and both calls carry the very same
    observation stamp object. Optional ``write_error``/``checkpoint_error`` make
    that call fail before it reaches the wrapped store, so a test can observe an
    attempted call that never committed.
    """

    def __init__(
        self,
        inner: Store,
        *,
        write_error: Exception | None = None,
        checkpoint_error: Exception | None = None,
    ) -> None:
        self._inner = inner
        self.write_error = write_error
        self.checkpoint_error = checkpoint_error
        self.calls: list[str] = []
        self.writes: list[tuple[str, int, list[Mapping[str, object]], dt.datetime]] = []
        self.checkpoints: list[tuple[str, int, dt.datetime]] = []

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: dt.datetime,
    ) -> int:
        self.calls.append("write")
        self.writes.append((family, session_key, list(records), observed_at))
        if self.write_error is not None:
            raise self.write_error
        return await self._inner.write_source_batch(
            family, session_key, records, observed_at=observed_at
        )

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: dt.datetime
    ) -> int:
        self.calls.append("checkpoint")
        self.checkpoints.append((endpoint, session_key, observed_at))
        if self.checkpoint_error is not None:
            raise self.checkpoint_error
        return await self._inner.set_watermark(endpoint, session_key, observed_at=observed_at)

    async def read_source_records(
        self,
        family: str,
        session_key: int,
        *,
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
    ) -> Sequence[tuple[dt.datetime, Mapping[str, object]]]:
        return await self._inner.read_source_records(
            family, session_key, since=since, until=until
        )

    async def get_watermark(self, endpoint: str, session_key: int) -> dt.datetime | None:
        return await self._inner.get_watermark(endpoint, session_key)

    async def close(self) -> None:
        await self._inner.close()


class ParkingStore(InMemoryStore):
    """A store whose write parks until the task is cancelled."""

    def __init__(self) -> None:
        super().__init__()
        self.write_entered = asyncio.Event()
        self.calls: list[str] = []

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: dt.datetime,
    ) -> int:
        self.calls.append("write")
        self.write_entered.set()
        await asyncio.Event().wait()  # never completes; cancellation must propagate
        raise AssertionError("unreachable")  # pragma: no cover

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: dt.datetime
    ) -> int:
        self.calls.append("checkpoint")
        return await super().set_watermark(endpoint, session_key, observed_at=observed_at)


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_ingest_endpoint_shared_contract(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    """One body, both stores: persistence, checkpoint order, refusal, idempotency."""
    store = TrackingStore(build_store(tmp_path))
    clock = CountingClock(OBSERVED)

    # --- sessions: the whole batch, derived identity, one stamp, write first.
    payload = [session_row(9462, provider_note="ignored", record_id="attacker")]
    snapshot = copy.deepcopy(payload)
    outcome = await ingest_endpoint(
        store, clock, endpoint="sessions", session_key=9462, payload=payload
    )
    assert outcome == EndpointOutcome(
        endpoint="sessions",
        family="sessions",
        status="ok",
        records_written=1,
        observed_at=OBSERVED,
        checkpoint_written=True,
        failure_stage=None,
        failure_type=None,
    )
    assert clock.calls == 1
    assert store.calls == ["write", "checkpoint"]
    assert store.writes[0][0] == "sessions"
    assert store.writes[0][1] == 9462
    assert store.writes[0][3] == OBSERVED
    assert store.writes[0][3].utcoffset() == dt.timedelta(0)
    # The checkpoint carries the exact same stamp object the write carried.
    assert store.writes[0][3] is store.checkpoints[0][2]
    assert store.checkpoints == [("sessions", 9462, OBSERVED)]
    # The caller's payload is untouched.
    assert payload == snapshot

    stored = await store.read_source_records("sessions", 9462)
    assert [moment for moment, _ in stored] == [OBSERVED]
    row = stored[0][1]
    # Derived identity wins over whatever the provider payload claimed.
    assert row["record_id"] == "9462"
    assert row["session_key"] == 9462
    # Canonical JSON projection of the model, plus the derived identity.
    assert row["year"] == 2024
    assert row["is_cancelled"] is False
    assert isinstance(row["date_start"], str)
    assert dt.datetime.fromisoformat(str(row["date_start"])) == SESSION_START
    # The source's own event date is not the observation time.
    assert row["date_start"] != OBSERVED.isoformat()
    # Unknown provider fields are ignored, and the claimed identity is not kept.
    assert "provider_note" not in row
    # The caller's payload is untouched: it still carries the provider's claim.
    assert snapshot[0]["record_id"] == "attacker"
    assert store.writes[0][2][0] == row
    assert await store.get_watermark("sessions", 9462) == OBSERVED

    # --- drivers: two rows, one stamp, one write before one checkpoint.
    drivers = [driver_row(9462, 1), driver_row(9462, 11)]
    outcome = await ingest_endpoint(
        store, clock, endpoint="drivers", session_key=9462, payload=drivers
    )
    assert outcome == EndpointOutcome(
        endpoint="drivers",
        family="drivers",
        status="ok",
        records_written=2,
        observed_at=OBSERVED,
        checkpoint_written=True,
        failure_stage=None,
        failure_type=None,
    )
    assert clock.calls == 2
    assert store.calls == ["write", "checkpoint", "write", "checkpoint"]
    assert store.writes[1][3] is store.checkpoints[1][2]
    assert [
        record["record_id"] for _, record in await store.read_source_records("drivers", 9462)
    ] == ["9462-1", "9462-11"]

    # --- a valid empty list is a successful observation that advances the checkpoint.
    clock.calls = 0
    calls_before_empty = len(store.calls)
    outcome = await ingest_endpoint(
        store, clock, endpoint="drivers", session_key=9462, payload=[]
    )
    assert outcome == EndpointOutcome(
        endpoint="drivers",
        family="drivers",
        status="empty",
        records_written=0,
        observed_at=OBSERVED,
        checkpoint_written=True,
        failure_stage=None,
        failure_type=None,
    )
    assert clock.calls == 1
    assert store.calls[calls_before_empty:] == ["write", "checkpoint"]
    assert await store.get_watermark("drivers", 9462) == OBSERVED

    # --- a malformed later item rejects the whole batch with zero store calls.
    watermark_before = await store.get_watermark("sessions", 9462)
    sessions_before = len(await store.read_source_records("sessions", 9462))
    calls_before = len(store.calls)
    malformed = [session_row(9462), session_row(9462, session_name=None)]
    outcome = await ingest_endpoint(
        store, clock, endpoint="sessions", session_key=9462, payload=malformed
    )
    assert outcome.status == "failed"
    assert outcome.failure_stage == "validation"
    assert outcome.failure_type == "ValidationError"
    assert outcome.records_written == 0
    assert outcome.observed_at is None
    assert outcome.checkpoint_written is False
    assert len(store.calls) == calls_before
    assert len(await store.read_source_records("sessions", 9462)) == sessions_before
    assert await store.get_watermark("sessions", 9462) == watermark_before

    # --- a mixed-session batch is a local session mismatch, refused whole.
    mixed = [session_row(9462), session_row(9999)]
    outcome = await ingest_endpoint(
        store, clock, endpoint="sessions", session_key=9462, payload=mixed
    )
    assert outcome.status == "failed"
    assert outcome.failure_stage == "validation"
    assert outcome.failure_type == "SourceValidationError"
    assert outcome.records_written == 0
    assert len(store.calls) == calls_before
    assert await store.get_watermark("sessions", 9462) == watermark_before

    # --- non-list and structurally bad payloads fail before any store call.
    for bad_payload in (None, {"session_key": 9462}, "sessions", [123], [["x"]], [None]):
        calls_before = len(store.calls)
        outcome = await ingest_endpoint(
            store, clock, endpoint="sessions", session_key=9462, payload=bad_payload
        )
        assert outcome.status == "failed"
        assert outcome.failure_stage == "validation"
        assert outcome.failure_type == "SourceValidationError"
        assert outcome.records_written == 0
        assert outcome.observed_at is None
        assert outcome.checkpoint_written is False
        assert len(store.calls) == calls_before

    # --- re-ingesting the same payload converges by upsert, not duplication.
    again = await ingest_endpoint(
        store, clock, endpoint="drivers", session_key=9462, payload=drivers
    )
    assert again.status == "ok"
    assert again.records_written == 2
    assert len(await store.read_source_records("drivers", 9462)) == 2

    # --- the caller owns the store: it is still usable and was never closed.
    direct = await store.write_source_batch(
        "laps", 9462, [{"record_id": "lap-1"}], observed_at=EARLIER
    )
    assert direct == 1
    assert len(await store.read_source_records("laps", 9462)) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "endpoint",
    ["laps", "pit_stops", "https://api.openf1.org/v1/sessions", "", None, 9462],
)
async def test_unsupported_endpoint_is_an_argument_error(endpoint: object) -> None:
    clock = CountingClock(OBSERVED)
    with pytest.raises(ValueError):
        # A deliberately out-of-contract endpoint: the test exists to prove the
        # guard refuses it, so the argument-level finding is expected right here.
        await ingest_endpoint(  # type: ignore[arg-type]
            InMemoryStore(), clock, endpoint=endpoint, session_key=9462, payload=object()  # pyright: ignore[reportArgumentType]
        )
    # The guard runs before any clock read or store call.
    assert clock.calls == 0


@pytest.mark.anyio
@pytest.mark.parametrize("session_key", [0, -1, True, False, "9462", 9462.0, None])
async def test_bad_session_key_is_an_argument_error(session_key: object) -> None:
    clock = CountingClock(OBSERVED)
    with pytest.raises(ValueError):
        # A deliberately invalid session key: the guard must refuse it, so the
        # argument-level finding is expected right here.
        await ingest_endpoint(  # type: ignore[arg-type]
            InMemoryStore(), clock, endpoint="sessions", session_key=session_key, payload=[]  # pyright: ignore[reportArgumentType]
        )
    assert clock.calls == 0


@pytest.mark.anyio
async def test_argument_errors_do_not_echo_the_rejected_value() -> None:
    with pytest.raises(ValueError) as excinfo:
        # A deliberately unsupported endpoint that doubles as a secret marker:
        # the expected finding sits on this argument, not file-wide.
        await ingest_endpoint(  # type: ignore[arg-type]
            InMemoryStore(),
            CountingClock(OBSERVED),
            endpoint="SECRET-MARKER",  # pyright: ignore[reportArgumentType]
            session_key=9462,
            payload=[],
        )
    assert "SECRET-MARKER" not in str(excinfo.value)


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
@pytest.mark.parametrize(
    "reading",
    [
        pytest.param(dt.datetime(2024, 3, 2, 20, 0, 0), id="naive"),
        pytest.param(
            dt.datetime(2024, 3, 2, 20, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30))),
            id="non-utc-offset",
        ),
        pytest.param("2024-03-02T20:00:00Z", id="not-a-datetime"),
        pytest.param(None, id="none"),
    ],
)
async def test_invalid_clock_reading_fails_before_any_store_call(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path, reading: object
) -> None:
    store = TrackingStore(build_store(tmp_path))
    outcome = await ingest_endpoint(
        store,
        FixedReadingClock(reading),
        endpoint="sessions",
        session_key=9462,
        payload=[session_row(9462)],
    )
    assert outcome == EndpointOutcome(
        endpoint="sessions",
        family="sessions",
        status="failed",
        records_written=0,
        observed_at=None,
        checkpoint_written=False,
        failure_stage="clock",
        failure_type="ObservationClockError",
    )
    assert store.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_raising_clock_fails_before_any_store_call(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    store = TrackingStore(build_store(tmp_path))
    outcome = await ingest_endpoint(
        store,
        RaisingClock(RuntimeError("boom SECRET-MARKER")),
        endpoint="sessions",
        session_key=9462,
        payload=[session_row(9462)],
    )
    assert outcome.status == "failed"
    assert outcome.failure_stage == "clock"
    assert outcome.failure_type == "RuntimeError"
    assert outcome.records_written == 0
    assert outcome.observed_at is None
    assert outcome.checkpoint_written is False
    assert store.calls == []
    assert "SECRET-MARKER" not in repr(outcome)


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_write_failure_keeps_count_unknown_and_skips_checkpoint(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    inner = build_store(tmp_path)
    await inner.set_watermark("sessions", 9462, observed_at=EARLIER)
    store = TrackingStore(inner, write_error=RuntimeError("boom SECRET-MARKER"))
    outcome = await ingest_endpoint(
        store,
        CountingClock(OBSERVED),
        endpoint="sessions",
        session_key=9462,
        payload=[session_row(9462)],
    )
    assert outcome.status == "failed"
    assert outcome.failure_stage == "write"
    assert outcome.failure_type == "RuntimeError"
    # The committed count is unknown, not a pretend zero.
    assert outcome.records_written is None
    assert outcome.observed_at == OBSERVED
    assert outcome.checkpoint_written is False
    assert store.calls == ["write"]  # no checkpoint attempt
    assert await inner.get_watermark("sessions", 9462) == EARLIER
    assert await inner.read_source_records("sessions", 9462) == ()
    assert "SECRET-MARKER" not in repr(outcome)


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_checkpoint_failure_keeps_committed_records_then_retry_converges(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    inner = build_store(tmp_path)
    await inner.set_watermark("sessions", 9462, observed_at=EARLIER)
    store = TrackingStore(inner, checkpoint_error=RuntimeError("boom SECRET-MARKER"))
    payload = [session_row(9462)]
    outcome = await ingest_endpoint(
        store, CountingClock(OBSERVED), endpoint="sessions", session_key=9462, payload=payload
    )
    assert outcome.status == "failed"
    assert outcome.failure_stage == "checkpoint"
    assert outcome.failure_type == "RuntimeError"
    # The acknowledged write count and the valid stamp survive the failure.
    assert outcome.records_written == 1
    assert outcome.observed_at == OBSERVED
    assert outcome.checkpoint_written is False
    assert "SECRET-MARKER" not in repr(outcome)
    # The records really were committed; only the checkpoint is missing.
    committed = await inner.read_source_records("sessions", 9462)
    assert [record["record_id"] for _, record in committed] == ["9462"]
    assert [moment for moment, _ in committed] == [OBSERVED]
    assert await inner.get_watermark("sessions", 9462) == EARLIER

    # Retrying after the checkpoint recovers re-upserts instead of duplicating.
    store.checkpoint_error = None
    retry = await ingest_endpoint(
        store, CountingClock(OBSERVED), endpoint="sessions", session_key=9462, payload=payload
    )
    assert retry.status == "ok"
    assert retry.checkpoint_written is True
    assert await inner.get_watermark("sessions", 9462) == OBSERVED
    assert len(await inner.read_source_records("sessions", 9462)) == 1


@pytest.mark.anyio
async def test_cancellation_while_the_store_write_parks_propagates_without_checkpoint() -> None:
    store = ParkingStore()
    clock = CountingClock(OBSERVED)
    task = asyncio.create_task(
        ingest_endpoint(
            store, clock, endpoint="sessions", session_key=9462, payload=[session_row(9462)]
        )
    )
    await asyncio.wait_for(store.write_entered.wait(), timeout=5)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Nothing is converted into an outcome and no checkpoint is attempted.
    assert store.calls == ["write"]
    assert await store.get_watermark("sessions", 9462) is None


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_existing_model_admission_policy_is_preserved(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    """A JSON-shaped source row is admitted by the existing models unchanged."""
    store = TrackingStore(build_store(tmp_path))
    row = session_row(9462)
    row["year"] = "2024"  # the models coerce the string the source actually sends
    outcome = await ingest_endpoint(
        store, CountingClock(OBSERVED), endpoint="sessions", session_key=9462, payload=[row]
    )
    assert outcome.status == "ok"
    stored = (await store.read_source_records("sessions", 9462))[0][1]
    assert stored["year"] == 2024
    assert stored["record_id"] == "9462"


# ---------------------------------------------------------------------------
# F03c-3b: bounded fixed sessions/drivers HTTP composition.
# ---------------------------------------------------------------------------

SYNC_BASE = "https://example.invalid/v1"
SYNC_SESSIONS_URL = f"{SYNC_BASE}/sessions"
SYNC_DRIVERS_URL = f"{SYNC_BASE}/drivers"
SYNC_PARAMS = {"session_key": "9462"}
#: A Retry-After HTTP-date is resolved against an injected UTC clock; this one
#: never needs to move, because the scripted advice is delta-seconds.
SYNC_MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=UTC)


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_sync_session_fetches_fixed_endpoints_in_canonical_order(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    """One body, both stores: fixed URLs, canonical order, one write per endpoint."""
    base = "https://example.invalid/v1/"
    normalized = base.rstrip("/")
    http = FakeHttpClient()
    http.register(f"{normalized}/sessions", [session_row(9462)], params=SYNC_PARAMS)
    http.register(f"{normalized}/drivers", [driver_row(9462, 1)], params=SYNC_PARAMS)
    store = TrackingStore(build_store(tmp_path))
    clock = CountingClock(OBSERVED)

    result = await sync_session(http, store, clock, session_key=9462, base_url=base)

    assert isinstance(result, SessionSyncResult)
    assert result.session_key == 9462
    assert isinstance(result.outcomes, tuple)
    assert [outcome.endpoint for outcome in result.outcomes] == ["sessions", "drivers"]
    assert [outcome.status for outcome in result.outcomes] == ["ok", "ok"]
    assert [outcome.records_written for outcome in result.outcomes] == [1, 1]
    assert [outcome.observed_at for outcome in result.outcomes] == [OBSERVED, OBSERVED]
    assert all(outcome.checkpoint_written for outcome in result.outcomes)
    # The caller's HttpClient saw exactly one call per fixed endpoint, in order.
    assert http.calls == [
        (f"{normalized}/sessions", SYNC_PARAMS),
        (f"{normalized}/drivers", SYNC_PARAMS),
    ]
    # One observation read per admitted endpoint: no extra ingestion retry.
    assert clock.calls == 2
    assert store.calls == ["write", "checkpoint", "write", "checkpoint"]

    stored = await store.read_source_records("sessions", 9462)
    assert [record["record_id"] for _, record in stored] == ["9462"]
    assert await store.get_watermark("sessions", 9462) == OBSERVED
    assert await store.get_watermark("drivers", 9462) == OBSERVED

    # Caller ownership: the store is still usable and was never closed.
    direct = await store.write_source_batch(
        "laps", 9462, [{"record_id": "lap-1"}], observed_at=EARLIER
    )
    assert direct == 1


@pytest.mark.anyio
async def test_sync_session_honors_the_default_base_url_and_empty_payloads() -> None:
    """The published default base URL is used, and ``[]`` is a valid checkpoint."""
    http = FakeHttpClient()
    http.register(f"{DEFAULT_OPENF1_BASE_URL}/sessions", [], params=SYNC_PARAMS)
    http.register(f"{DEFAULT_OPENF1_BASE_URL}/drivers", [], params=SYNC_PARAMS)
    store = InMemoryStore()

    result = await sync_session(http, store, CountingClock(OBSERVED), session_key=9462)

    assert result.session_key == 9462
    assert [outcome.status for outcome in result.outcomes] == ["empty", "empty"]
    assert [outcome.records_written for outcome in result.outcomes] == [0, 0]
    assert all(outcome.checkpoint_written for outcome in result.outcomes)
    assert http.calls == [
        (f"{DEFAULT_OPENF1_BASE_URL}/sessions", SYNC_PARAMS),
        (f"{DEFAULT_OPENF1_BASE_URL}/drivers", SYNC_PARAMS),
    ]
    assert await store.get_watermark("sessions", 9462) == OBSERVED
    assert await store.get_watermark("drivers", 9462) == OBSERVED


@pytest.mark.anyio
@pytest.mark.parametrize("session_key", [0, -1, True, False, "9462", 9462.0, None])
async def test_sync_session_rejects_a_bad_session_key_before_any_effect(
    session_key: object,
) -> None:
    http = FakeHttpClient()
    store = TrackingStore(InMemoryStore())
    clock = CountingClock(OBSERVED)
    with pytest.raises(ValueError):
        # A deliberately invalid identity: the guard must refuse it before any
        # effect, so the argument-level finding is expected right here.
        await sync_session(  # type: ignore[arg-type]
            http,
            store,
            clock,
            session_key=session_key,  # pyright: ignore[reportArgumentType]
            base_url=SYNC_BASE,
        )
    assert http.calls == []
    assert store.calls == []
    assert clock.calls == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "sessions_payload, drivers_payload",
    [
        pytest.param(None, None, id="json-null"),
        pytest.param({"session_key": 9462}, [123], id="non-list-and-non-mapping"),
        pytest.param([session_row(9999)], [driver_row(9999, 1)], id="wrong-session"),
    ],
)
async def test_sync_session_malformed_2xx_is_a_validation_failure(
    sessions_payload: object, drivers_payload: object
) -> None:
    """A 2xx with a bad shape is validation, never a fetch, failure."""
    http = FakeHttpClient()
    http.register(SYNC_SESSIONS_URL, sessions_payload, params=SYNC_PARAMS)
    http.register(SYNC_DRIVERS_URL, drivers_payload, params=SYNC_PARAMS)
    store = TrackingStore(InMemoryStore())

    result = await sync_session(
        http, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    assert [outcome.status for outcome in result.outcomes] == ["failed", "failed"]
    for outcome in result.outcomes:
        assert outcome.failure_stage == "validation"
        assert outcome.failure_type == "SourceValidationError"
        assert outcome.records_written == 0
        assert outcome.observed_at is None
        assert outcome.checkpoint_written is False
    assert store.calls == []


@pytest.mark.anyio
async def test_sync_session_non_2xx_is_a_fetch_failure_and_does_not_block_the_second() -> None:
    http = FakeHttpClient()
    http.register(SYNC_SESSIONS_URL, None, params=SYNC_PARAMS, status_code=404)
    http.register(SYNC_DRIVERS_URL, [driver_row(9462, 1)], params=SYNC_PARAMS)
    store = TrackingStore(InMemoryStore())
    clock = CountingClock(OBSERVED)

    result = await sync_session(http, store, clock, session_key=9462, base_url=SYNC_BASE)

    sessions, drivers = result.outcomes
    assert sessions.status == "failed"
    assert sessions.failure_stage == "fetch"
    assert sessions.failure_type == "HTTPStatus404"
    assert sessions.records_written == 0
    assert sessions.observed_at is None
    assert sessions.checkpoint_written is False
    assert drivers.status == "ok"
    assert drivers.records_written == 1
    # Only the admitted 2xx reached the ingestion clock, and only it wrote.
    assert clock.calls == 1
    assert store.calls == ["write", "checkpoint"]
    assert await store.get_watermark("sessions", 9462) is None
    assert await store.get_watermark("drivers", 9462) == OBSERVED


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error, expected_type",
    [
        pytest.param(HttpTransportError("boom SECRET-MARKER"), "HttpTransportError", id="transport"),
        pytest.param(HttpTimeoutError("boom SECRET-MARKER"), "HttpTimeoutError", id="timeout"),
        pytest.param(HttpDecodeError("boom SECRET-MARKER"), "HttpDecodeError", id="decode"),
        pytest.param(
            HttpResponseTooLargeError("boom SECRET-MARKER"),
            "HttpResponseTooLargeError",
            id="size",
        ),
        pytest.param(RuntimeError("boom SECRET-MARKER"), "RuntimeError", id="foreign"),
    ],
)
async def test_sync_session_ordinary_fetch_failure_keeps_only_the_safe_type(
    error: Exception, expected_type: str
) -> None:
    http = FakeHttpClient()
    http.enqueue(SYNC_SESSIONS_URL, error, params=SYNC_PARAMS)
    http.register(SYNC_DRIVERS_URL, [driver_row(9462, 1)], params=SYNC_PARAMS)
    store = TrackingStore(InMemoryStore())

    result = await sync_session(
        http, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    sessions, drivers = result.outcomes
    assert sessions.status == "failed"
    assert sessions.failure_stage == "fetch"
    assert sessions.failure_type == expected_type
    assert sessions.records_written == 0
    assert sessions.observed_at is None
    assert sessions.checkpoint_written is False
    # No message, URL, header or cause text is carried into the outcome.
    assert "SECRET-MARKER" not in repr(sessions)
    assert drivers.status == "ok"
    assert store.calls == ["write", "checkpoint"]


@pytest.mark.anyio
async def test_sync_session_reports_explicit_outcomes_when_both_endpoints_fail() -> None:
    http = FakeHttpClient()
    http.register(SYNC_SESSIONS_URL, None, params=SYNC_PARAMS, status_code=500)
    http.enqueue(SYNC_DRIVERS_URL, HttpTransportError("boom"), params=SYNC_PARAMS)

    result = await sync_session(
        http,
        TrackingStore(InMemoryStore()),
        CountingClock(OBSERVED),
        session_key=9462,
        base_url=SYNC_BASE,
    )

    assert [outcome.status for outcome in result.outcomes] == ["failed", "failed"]
    assert [outcome.failure_type for outcome in result.outcomes] == [
        "HTTPStatus500",
        "HttpTransportError",
    ]
    assert len(result.outcomes) == 2
    # There is deliberately no aggregate success flag to misread.
    assert not hasattr(result, "ok")


class FailingFamilyStore(InMemoryStore):
    """A store that can fail exactly one endpoint's write or checkpoint."""

    def __init__(
        self,
        *,
        fail_write_family: str | None = None,
        fail_checkpoint_endpoint: str | None = None,
    ) -> None:
        super().__init__()
        self._fail_write_family = fail_write_family
        self._fail_checkpoint_endpoint = fail_checkpoint_endpoint
        self.calls: list[str] = []

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: dt.datetime,
    ) -> int:
        self.calls.append("write")
        if family == self._fail_write_family:
            raise RuntimeError("write boom")
        return await super().write_source_batch(
            family, session_key, records, observed_at=observed_at
        )

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: dt.datetime
    ) -> int:
        self.calls.append("checkpoint")
        if endpoint == self._fail_checkpoint_endpoint:
            raise RuntimeError("checkpoint boom")
        return await super().set_watermark(endpoint, session_key, observed_at=observed_at)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "store, stage, records_written",
    [
        pytest.param(
            FailingFamilyStore(fail_write_family="sessions"), "write", None, id="write-failure"
        ),
        pytest.param(
            FailingFamilyStore(fail_checkpoint_endpoint="sessions"),
            "checkpoint",
            1,
            id="checkpoint-failure",
        ),
    ],
)
async def test_sync_session_preserves_core_write_and_checkpoint_partial_outcomes(
    store: FailingFamilyStore, stage: str, records_written: int | None
) -> None:
    """The ingestion core's honest partial counts survive the composition."""
    http = FakeHttpClient()
    http.register(SYNC_SESSIONS_URL, [session_row(9462)], params=SYNC_PARAMS)
    http.register(SYNC_DRIVERS_URL, [driver_row(9462, 1)], params=SYNC_PARAMS)

    result = await sync_session(
        http, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    sessions, drivers = result.outcomes
    assert sessions.status == "failed"
    assert sessions.failure_stage == stage
    assert sessions.failure_type == "RuntimeError"
    assert sessions.records_written == records_written
    assert sessions.observed_at == OBSERVED
    assert sessions.checkpoint_written is False
    assert await store.get_watermark("sessions", 9462) is None
    assert drivers.status == "ok"


def test_session_sync_result_is_frozen_and_coerces_to_a_tuple() -> None:
    sessions = EndpointOutcome(
        endpoint="sessions",
        family="sessions",
        status="empty",
        records_written=0,
        observed_at=None,
        checkpoint_written=False,
        failure_stage=None,
        failure_type=None,
    )
    drivers = EndpointOutcome(
        endpoint="drivers",
        family="drivers",
        status="empty",
        records_written=0,
        observed_at=None,
        checkpoint_written=False,
        failure_stage=None,
        failure_type=None,
    )
    result = SessionSyncResult(  # type: ignore[arg-type]
        9462,
        [sessions, drivers],  # pyright: ignore[reportArgumentType]
    )
    assert result.outcomes == (sessions, drivers)
    assert isinstance(result.outcomes, tuple)
    assert isinstance(hash(result), int)  # a mutable list field would have raised
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.session_key = 1  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


class CountingHttpClient:
    """Wraps an ``HttpClient`` and counts fetches and closes."""

    def __init__(self, inner: HttpClient) -> None:
        self._inner = inner
        self.fetches = 0
        self.close_calls = 0

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> HttpResponse:
        self.fetches += 1
        return await self._inner.get_json(url, params=params)

    async def close(self) -> None:
        self.close_calls += 1
        await self._inner.close()


@pytest.mark.anyio
async def test_sync_session_never_opens_or_closes_the_caller_owned_clients() -> None:
    inner = FakeHttpClient()
    inner.register(SYNC_SESSIONS_URL, [session_row(9462)], params=SYNC_PARAMS)
    inner.register(SYNC_DRIVERS_URL, [driver_row(9462, 1)], params=SYNC_PARAMS)
    http = CountingHttpClient(inner)
    store = TrackingStore(InMemoryStore())

    await sync_session(
        http, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    assert http.fetches == 2
    assert http.close_calls == 0
    # Both remain usable: neither was closed or rebuilt by the composition.
    assert (await http.get_json(SYNC_SESSIONS_URL, params=SYNC_PARAMS)).status_code == 200
    assert http.close_calls == 0
    assert await store.get_watermark("sessions", 9462) == OBSERVED


class ParkingHttpClient:
    """A client whose fetch for one endpoint parks until the task is cancelled."""

    def __init__(self, inner: HttpClient, *, park_on: str) -> None:
        self._inner = inner
        self._park_on = park_on
        self.entered = asyncio.Event()

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> HttpResponse:
        if url.endswith(self._park_on):
            self.entered.set()
            await asyncio.Event().wait()
        return await self._inner.get_json(url, params=params)

    async def close(self) -> None:
        await self._inner.close()


@pytest.mark.anyio
async def test_sync_session_cancellation_while_a_fetch_parks_propagates() -> None:
    http = ParkingHttpClient(FakeHttpClient(), park_on="/sessions")
    store = TrackingStore(InMemoryStore())
    clock = CountingClock(OBSERVED)

    task = asyncio.create_task(
        sync_session(http, store, clock, session_key=9462, base_url=SYNC_BASE)
    )
    await asyncio.wait_for(http.entered.wait(), timeout=5)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Nothing is converted into an outcome and no write was attempted.
    assert store.calls == []
    assert clock.calls == 0


@pytest.mark.anyio
async def test_sync_session_cancellation_during_the_second_fetch_leaves_the_first_committed() -> None:
    inner = FakeHttpClient()
    inner.register(SYNC_SESSIONS_URL, [session_row(9462)], params=SYNC_PARAMS)
    inner.register(SYNC_DRIVERS_URL, [driver_row(9462, 1)], params=SYNC_PARAMS)
    http = ParkingHttpClient(inner, park_on="/drivers")
    store = TrackingStore(InMemoryStore())

    task = asyncio.create_task(
        sync_session(http, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE)
    )
    await asyncio.wait_for(http.entered.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # No cross-request rollback is claimed: the first endpoint is committed.
    assert store.calls == ["write", "checkpoint"]
    assert await store.get_watermark("sessions", 9462) == OBSERVED
    assert await store.get_watermark("drivers", 9462) is None


class ExplodingHttpClient:
    """A client whose every fetch raises the injected ``BaseException``."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> HttpResponse:
        raise self._error

    async def close(self) -> None:
        """Nothing to release."""


@pytest.mark.anyio
async def test_sync_session_process_control_exception_propagates_without_an_outcome() -> None:
    store = TrackingStore(InMemoryStore())
    with pytest.raises(KeyboardInterrupt):
        await sync_session(
            ExplodingHttpClient(KeyboardInterrupt()),
            store,
            CountingClock(OBSERVED),
            session_key=9462,
            base_url=SYNC_BASE,
        )
    assert store.calls == []


@dataclasses.dataclass(frozen=True)
class Step:
    """One scripted HTTP step, served by both inner clients."""

    status: int = 200
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
    payload: Any = None
    error: BaseException | None = None
    raw_body: str | None = None
    oversized: bool = False


def _step_response(step: Step) -> HttpResponse:
    return HttpResponse(
        status_code=step.status, headers=dict(step.headers), payload=step.payload
    )


def build_sync_client(
    implementation: str,
    scripts: Mapping[str, Sequence[Step]],
    *,
    max_attempts: int = 3,
    max_response_bytes: int = 4096,
) -> tuple[RetryingHttpClient, Callable[[], int], FakeMonotonicClock]:
    """Build one retrying client over one shared limiter for the scripted steps."""
    monotonic = FakeMonotonicClock()
    limiter = RateLimiter(PacingPolicy(per_second=3, per_minute=30), monotonic)
    inner: HttpClient
    if implementation == "fake":
        fake = FakeHttpClient()
        for url, steps in scripts.items():
            for step in steps:
                if step.error is not None:
                    fake.enqueue(url, step.error, params=SYNC_PARAMS)
                else:
                    fake.enqueue(url, _step_response(step), params=SYNC_PARAMS)
        inner = fake

        def attempts() -> int:
            return len(fake.calls)

    else:
        queues = {url: list(steps) for url, steps in scripts.items()}
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            step = queues[str(request.url).split("?")[0]].pop(0)
            if step.error is not None:
                raise step.error
            if step.oversized:
                return httpx.Response(200, content=b"x" * (max_response_bytes + 1))
            if step.raw_body is not None:
                return httpx.Response(
                    step.status, headers=dict(step.headers), text=step.raw_body
                )
            return httpx.Response(step.status, headers=dict(step.headers), json=step.payload)

        def attempts() -> int:
            return len(seen)

        inner = HttpxJsonClient(
            timeout_seconds=5.0,
            max_response_bytes=max_response_bytes,
            transport=httpx.MockTransport(handler),
        )
    client = RetryingHttpClient(
        inner,
        limiter=limiter,
        retry_policy=RetryPolicy(max_attempts=max_attempts),
        clock=FrozenClock(SYNC_MOMENT),
    )
    return client, attempts, monotonic


@pytest.mark.anyio
@pytest.mark.parametrize("implementation", ["fake", "adapter"])
async def test_sync_session_retrying_client_recovers_from_429_then_fetches_the_other(
    implementation: str,
) -> None:
    client, attempts, monotonic = build_sync_client(
        implementation,
        {
            SYNC_SESSIONS_URL: [
                Step(status=429, headers={"retry-after": "1"}),
                Step(payload=[session_row(9462)]),
            ],
            SYNC_DRIVERS_URL: [Step(payload=[driver_row(9462, 1)])],
        },
    )
    store = TrackingStore(InMemoryStore())
    clock = CountingClock(OBSERVED)

    result = await sync_session(client, store, clock, session_key=9462, base_url=SYNC_BASE)

    assert [outcome.status for outcome in result.outcomes] == ["ok", "ok"]
    assert [outcome.records_written for outcome in result.outcomes] == [1, 1]
    assert attempts() == 3
    # Exactly the server's advice; the one shared limiter adds no wait of its own.
    assert monotonic.sleeps == [1.0]
    # The ingestion clock is read once per admitted endpoint, never per HTTP attempt.
    assert clock.calls == 2
    # No duplicate checkpoint: one write/checkpoint pair per endpoint.
    assert store.calls == ["write", "checkpoint", "write", "checkpoint"]


@pytest.mark.anyio
@pytest.mark.parametrize("implementation", ["fake", "adapter"])
@pytest.mark.parametrize(
    "session_steps, expected_type",
    [
        pytest.param([Step(status=503)], "HTTPStatus503", id="status-exhaustion"),
        pytest.param(
            [Step(error=HttpTransportError("boom"))], "HttpTransportError", id="transport-exhaustion"
        ),
    ],
)
async def test_sync_session_retry_exhaustion_is_a_fetch_failure_with_no_extra_wait(
    implementation: str, session_steps: Sequence[Step], expected_type: str
) -> None:
    client, attempts, monotonic = build_sync_client(
        implementation,
        {
            SYNC_SESSIONS_URL: session_steps,
            SYNC_DRIVERS_URL: [Step(payload=[driver_row(9462, 1)])],
        },
        max_attempts=1,
    )
    store = TrackingStore(InMemoryStore())

    result = await sync_session(
        client, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    sessions, drivers = result.outcomes
    assert sessions.failure_stage == "fetch"
    assert sessions.failure_type == expected_type
    assert sessions.records_written == 0
    assert sessions.observed_at is None
    assert sessions.checkpoint_written is False
    assert drivers.status == "ok"
    assert attempts() == 2
    assert monotonic.sleeps == []
    assert store.calls == ["write", "checkpoint"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error, expected_type",
    [
        pytest.param(HttpDecodeError("dropped"), "HttpDecodeError", id="decode"),
        pytest.param(
            HttpResponseTooLargeError("dropped"), "HttpResponseTooLargeError", id="size"
        ),
    ],
)
async def test_sync_session_deterministic_body_failure_is_not_retried_on_the_scripted_fake(
    error: Exception, expected_type: str
) -> None:
    client, attempts, monotonic = build_sync_client(
        "fake",
        {
            SYNC_SESSIONS_URL: [Step(error=error)],
            SYNC_DRIVERS_URL: [Step(payload=[driver_row(9462, 1)])],
        },
    )
    store = TrackingStore(InMemoryStore())

    result = await sync_session(
        client, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    assert result.outcomes[0].failure_type == expected_type
    assert result.outcomes[1].status == "ok"
    assert attempts() == 2  # one sessions attempt and one drivers attempt, no retry
    assert monotonic.sleeps == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "step, expected_type",
    [
        pytest.param(Step(raw_body="not json"), "HttpDecodeError", id="malformed-json"),
        pytest.param(Step(oversized=True), "HttpResponseTooLargeError", id="oversized-body"),
    ],
)
async def test_sync_session_deterministic_body_failure_is_not_retried_on_the_adapter(
    step: Step, expected_type: str
) -> None:
    client, attempts, monotonic = build_sync_client(
        "adapter",
        {
            SYNC_SESSIONS_URL: [step],
            SYNC_DRIVERS_URL: [Step(payload=[driver_row(9462, 1)])],
        },
        max_response_bytes=2048,
    )
    store = TrackingStore(InMemoryStore())

    result = await sync_session(
        client, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    assert result.outcomes[0].failure_type == expected_type
    assert result.outcomes[1].status == "ok"
    assert attempts() == 2
    assert monotonic.sleeps == []


@pytest.mark.anyio
async def test_sync_session_adapter_does_not_follow_a_redirect_and_reports_the_status() -> None:
    client, attempts, monotonic = build_sync_client(
        "adapter",
        {
            SYNC_SESSIONS_URL: [
                Step(status=302, headers={"location": "https://elsewhere.invalid/v1/sessions"})
            ],
            SYNC_DRIVERS_URL: [Step(payload=[driver_row(9462, 1)])],
        },
    )
    store = TrackingStore(InMemoryStore())

    result = await sync_session(
        client, store, CountingClock(OBSERVED), session_key=9462, base_url=SYNC_BASE
    )

    assert result.outcomes[0].failure_stage == "fetch"
    assert result.outcomes[0].failure_type == "HTTPStatus302"
    assert result.outcomes[1].status == "ok"
    assert attempts() == 2  # the redirected URL is never requested
    assert monotonic.sleeps == []
