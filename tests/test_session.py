"""Offline acceptance tests for the per-session run lifecycle.

The lifecycle is a thin coordinator over the already published ``sync_session``
composition: a run fixes one session identity, repeats a single bounded sync at
whatever cadence the caller wants, and can be ended, cancelled or superseded
without ever reaching into the caller's task, client or store.

Every test is fully offline. The lifecycle adds no entropy, no clock read and no
network of its own, so a ``run_id`` is always handed in by the test, the store is
the shipped in-memory double (wrapped to count calls and close requests), and the
scripted ``FakeHttpClient`` answers every request.

Two invariants are worth naming because they are easy to fake:

* A response that arrives after the run became non-active is **refused** at the
  store boundary, not silently committed and not swallowed into a success.
* Refusal is typed data. No exception or outcome produced here repeats a
  payload, URL, header, secret, session identifier or message text.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest

from f1show import session as session_module
from f1show.fakes import FakeHttpClient, InMemoryStore
from f1show.ingest import SessionSyncResult, sync_session
from f1show.ports import HttpTransportError, Store
from f1show.session import (
    RunNotActiveError,
    RunState,
    SessionRun,
    SessionRunIdentity,
    StaleRunError,
    StoreOwnershipError,
)

UTC = dt.timezone.utc
SESSION_KEY = 9462
OBSERVED = dt.datetime(2024, 3, 2, 20, 0, 0, tzinfo=UTC)
BASE = "https://example.invalid/v1"
SESSIONS_URL = f"{BASE}/sessions"
DRIVERS_URL = f"{BASE}/drivers"
PARAMS = {"session_key": str(SESSION_KEY)}


def session_row(**overrides: object) -> dict[str, object]:
    """A source-shaped ``sessions`` row; dates arrive as JSON strings."""
    row: dict[str, object] = {
        "session_key": SESSION_KEY,
        "session_name": "Race",
        "session_type": "Race",
        "date_start": "2024-03-01T11:00:00+00:00",
        "date_end": "2024-03-01T13:00:00+00:00",
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


def driver_row(driver_number: int = 1) -> dict[str, object]:
    """A source-shaped ``drivers`` row."""
    return {
        "driver_number": driver_number,
        "broadcast_name": f"DRIVER {driver_number}",
        "first_name": "First",
        "last_name": "Last",
        "full_name": f"First Last {driver_number}",
        "name_acronym": f"D{driver_number:02d}",
        "country_code": "NED",
        "headshot_url": f"https://example.invalid/{driver_number}.png",
        "meeting_key": 1236,
        "session_key": SESSION_KEY,
        "team_colour": "3671C6",
        "team_name": "Red Bull Racing",
    }


def make_run(run_id: str = "run-1", generation: int = 1) -> SessionRun:
    return SessionRun(SessionRunIdentity(run_id, SESSION_KEY), generation)


def register_both(fake: FakeHttpClient, *, drivers_status: int = 200) -> None:
    """Register one successful sessions answer and one drivers answer."""
    fake.register(SESSIONS_URL, [session_row()], params=PARAMS)
    fake.register(
        DRIVERS_URL,
        [driver_row()],
        params=PARAMS,
        status_code=drivers_status,
    )


class CountingClock:
    """A clock stopped at one instant that counts how often it was read."""

    def __init__(self, instant: dt.datetime = OBSERVED) -> None:
        self._instant = instant
        self.calls = 0

    def now(self) -> dt.datetime:
        self.calls += 1
        return self._instant


class TrackingStore:
    """Delegates to a real store, recording call order and close requests.

    ``write_error``/``checkpoint_error`` make a call fail before it reaches the
    wrapped store, so a test can observe an attempted write that never committed.
    ``close_calls`` is the ownership proof: the run layer must never close, swap
    or replace the store it borrowed.
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
        self.close_calls = 0

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: dt.datetime,
    ) -> int:
        self.calls.append("write")
        if self.write_error is not None:
            raise self.write_error
        return await self._inner.write_source_batch(
            family, session_key, records, observed_at=observed_at
        )

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: dt.datetime
    ) -> int:
        self.calls.append("checkpoint")
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
        self.close_calls += 1
        await self._inner.close()


class HookedHttpClient:
    """Wraps a ``FakeHttpClient``; runs ``hook`` on the first fetch of one URL.

    The hook runs *before* the wrapped fetch, which is how a test drives the
    race the lifecycle must survive: the run becomes non-active while the
    response is still in flight. ``fetches`` and ``close_calls`` are the effect
    counters; the real client is never closed here.
    """

    def __init__(
        self,
        inner: FakeHttpClient,
        *,
        hook: Callable[[], None] | None = None,
        trigger_url: str | None = None,
    ) -> None:
        self._inner = inner
        self._hook = hook
        self._trigger_url = trigger_url
        self._fired = False
        self.fetches = 0
        self.close_calls = 0

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> Any:
        self.fetches += 1
        if self._hook is not None and not self._fired and url == self._trigger_url:
            self._fired = True
            self._hook()
        return await self._inner.get_json(url, params=params)

    async def close(self) -> None:
        self.close_calls += 1
        await self._inner.close()


class ExplodingHttpClient:
    """A client whose every fetch raises the injected ``BaseException``."""

    def __init__(self, error: BaseException) -> None:
        self._error = error
        self.fetches = 0

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> Any:
        self.fetches += 1
        raise self._error

    async def close(self) -> None:
        """Nothing to release."""


# --- identity admission -----------------------------------------------------


@pytest.mark.parametrize("run_id", ["", 0, None, b"run", ["run"]])
def test_identity_rejects_a_run_id_that_is_not_a_non_empty_string(run_id: object) -> None:
    with pytest.raises(ValueError):
        SessionRunIdentity(run_id, SESSION_KEY)  # type: ignore[arg-type]


@pytest.mark.parametrize("session_key", [0, -1, True, "9462", 1.5, None])
def test_identity_rejects_a_session_key_without_the_shared_admission_rule(
    session_key: object,
) -> None:
    with pytest.raises(ValueError):
        SessionRunIdentity("run-1", session_key)  # type: ignore[arg-type]


def test_a_run_starts_active_at_the_caller_supplied_generation() -> None:
    run = make_run("run-alpha", generation=3)

    assert run.identity == SessionRunIdentity("run-alpha", SESSION_KEY)
    assert run.identity.run_id == "run-alpha"
    assert run.identity.session_key == SESSION_KEY
    assert run.generation == 3
    assert run.state is RunState.ACTIVE
    # The vocabulary is data, comparable without a lookup table.
    assert run.state == "active"


@pytest.mark.parametrize("generation", [0, -1, True, "1", None])
def test_a_run_rejects_a_generation_that_is_not_a_positive_int(generation: object) -> None:
    with pytest.raises(ValueError):
        SessionRun(
            SessionRunIdentity("run-1", SESSION_KEY), generation  # type: ignore[arg-type]
        )


# --- the active cadence -----------------------------------------------------


@pytest.mark.anyio
async def test_an_active_run_syncs_repeatedly_and_returns_sync_session_unchanged() -> None:
    run = make_run("run-cadence")
    store = TrackingStore(InMemoryStore())
    clock = CountingClock()
    fake = FakeHttpClient()
    fake.register(SESSIONS_URL, [session_row()], params=PARAMS)
    fake.register(DRIVERS_URL, None, params=PARAMS, status_code=404)
    http = HookedHttpClient(fake)

    first = await run.sync(http, store, clock, base_url=BASE)

    # Exactly one bounded pass: one fetch per endpoint, one write + checkpoint.
    assert http.fetches == 2
    assert store.calls == ["write", "checkpoint"]
    assert isinstance(first, SessionSyncResult)
    assert first.session_key == SESSION_KEY
    assert [outcome.endpoint for outcome in first.outcomes] == ["sessions", "drivers"]
    assert first.outcomes[0].status == "ok"
    assert first.outcomes[0].records_written == 1
    assert first.outcomes[1].status == "failed"
    assert first.outcomes[1].failure_stage == "fetch"
    assert first.outcomes[1].failure_type == "HTTPStatus404"
    assert run.state is RunState.ACTIVE

    # Not re-invented: a direct composition call on identical inputs is equal.
    direct_store = TrackingStore(InMemoryStore())
    direct_fake = FakeHttpClient()
    direct_fake.register(SESSIONS_URL, [session_row()], params=PARAMS)
    direct_fake.register(DRIVERS_URL, None, params=PARAMS, status_code=404)
    direct = await sync_session(
        direct_fake, direct_store, CountingClock(), session_key=SESSION_KEY, base_url=BASE
    )
    assert first == direct

    # Repeat calls are the live cadence, not an error.
    second = await run.sync(http, store, clock, base_url=BASE)

    assert second == first
    assert http.fetches == 4
    assert store.calls == ["write", "checkpoint", "write", "checkpoint"]
    assert run.state is RunState.ACTIVE


@pytest.mark.anyio
async def test_a_run_sync_reports_unknown_and_zero_counts_honestly() -> None:
    run = make_run()
    store = TrackingStore(InMemoryStore(), write_error=RuntimeError("store is down"))
    fake = FakeHttpClient()
    fake.register(SESSIONS_URL, None, params=PARAMS, status_code=500)
    fake.register(DRIVERS_URL, [driver_row()], params=PARAMS)

    result = await run.sync(HookedHttpClient(fake), store, CountingClock(), base_url=BASE)

    # A fetch-stage failure knows nothing was written: a real zero.
    assert result.outcomes[0].status == "failed"
    assert result.outcomes[0].failure_stage == "fetch"
    assert result.outcomes[0].failure_type == "HTTPStatus500"
    assert result.outcomes[0].records_written == 0
    # A failed write cannot claim a committed count: unknown, not zero.
    assert result.outcomes[1].status == "failed"
    assert result.outcomes[1].failure_stage == "write"
    assert result.outcomes[1].records_written is None
    assert store.calls == ["write"]


# --- terminal transitions ---------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("terminate", ["end", "cancel", "reset"])
async def test_sync_on_a_non_active_run_is_refused_before_any_effect(
    terminate: str,
) -> None:
    run = make_run()
    store = TrackingStore(InMemoryStore())
    clock = CountingClock()
    fake = FakeHttpClient()
    register_both(fake)
    http = HookedHttpClient(fake)

    if terminate == "reset":
        run.reset(SESSION_KEY, "run-2")
    else:
        getattr(run, terminate)()

    with pytest.raises(RunNotActiveError) as caught:
        await run.sync(http, store, clock, base_url=BASE)

    # Typed data with no message: nothing to leak.
    assert caught.value.args == ()
    assert str(caught.value) == ""
    # Refused before any fetch, clock read or store call.
    assert http.fetches == 0
    assert store.calls == []
    assert store.close_calls == 0
    assert clock.calls == 0


def test_end_and_cancel_are_terminal_and_idempotent() -> None:
    ended = make_run()
    ended.end()
    ended.end()
    assert ended.state is RunState.ENDED
    # The first terminal transition wins; the second method cannot rewrite it.
    ended.cancel()
    assert ended.state is RunState.ENDED

    cancelled = make_run()
    cancelled.cancel()
    cancelled.cancel()
    assert cancelled.state is RunState.CANCELLED
    cancelled.end()
    assert cancelled.state is RunState.CANCELLED


# --- supersede --------------------------------------------------------------


@pytest.mark.anyio
async def test_reset_supersedes_in_memory_without_touching_committed_rows() -> None:
    run = make_run("run-1", generation=1)
    store = TrackingStore(InMemoryStore())
    fake = FakeHttpClient()
    register_both(fake)
    await run.sync(HookedHttpClient(fake), store, CountingClock(), base_url=BASE)

    committed = await store.read_source_records("sessions", SESSION_KEY)
    watermark = await store.get_watermark("sessions", SESSION_KEY)
    calls_before = list(store.calls)

    successor = run.reset(SESSION_KEY, "run-2")

    assert run.state is RunState.ENDED  # the superseded run is no longer active
    assert run.generation == 1  # its own generation is not rewritten
    assert successor is not run
    assert successor.identity.run_id == "run-2"
    assert successor.identity.session_key == SESSION_KEY
    assert successor.generation == 2  # one greater than the superseded run's
    assert successor.state is RunState.ACTIVE

    # Superseding is an in-memory transition: the store was not called at all.
    assert store.calls == calls_before
    assert await store.read_source_records("sessions", SESSION_KEY) == committed
    assert await store.get_watermark("sessions", SESSION_KEY) == watermark
    assert store.close_calls == 0


def test_reset_with_an_invalid_identity_leaves_the_current_run_active() -> None:
    run = make_run()

    with pytest.raises(ValueError):
        run.reset(SESSION_KEY, "")

    assert run.state is RunState.ACTIVE


def test_reset_does_not_rewrite_a_terminal_state() -> None:
    run = make_run()
    run.cancel()

    successor = run.reset(SESSION_KEY, "run-2")

    assert run.state is RunState.CANCELLED  # history is preserved, not relabelled
    assert successor.state is RunState.ACTIVE


# --- late-response isolation ------------------------------------------------


@pytest.mark.anyio
async def test_a_late_response_for_a_cancelled_run_never_commits() -> None:
    run = make_run("run-marker-xyz")
    store = TrackingStore(InMemoryStore())
    fake = FakeHttpClient()
    register_both(fake)
    http = HookedHttpClient(fake, hook=run.cancel, trigger_url=SESSIONS_URL)

    result = await run.sync(http, store, CountingClock(), base_url=BASE)

    assert run.state is RunState.CANCELLED
    assert isinstance(result, SessionSyncResult)
    assert [outcome.status for outcome in result.outcomes] == ["failed", "failed"]
    assert [outcome.failure_stage for outcome in result.outcomes] == ["write", "write"]
    assert [outcome.failure_type for outcome in result.outcomes] == [
        "StaleRunError",
        "StaleRunError",
    ]
    assert [outcome.records_written for outcome in result.outcomes] == [None, None]
    # The view refused before the wrapped store ever saw a call.
    assert store.calls == []
    assert await store.read_source_records("sessions", SESSION_KEY) == ()
    assert await store.get_watermark("sessions", SESSION_KEY) is None
    assert store.close_calls == 0
    assert "run-marker-xyz" not in repr(result)


@pytest.mark.anyio
async def test_a_late_response_for_a_superseded_run_cannot_advance_the_next_run() -> None:
    run = make_run("run-1")
    store = TrackingStore(InMemoryStore())
    fake = FakeHttpClient()
    register_both(fake)
    superseded: list[SessionRun] = []

    def supersede() -> None:
        superseded.append(run.reset(SESSION_KEY, "run-2"))

    http = HookedHttpClient(fake, hook=supersede, trigger_url=SESSIONS_URL)

    stale = await run.sync(http, store, CountingClock(), base_url=BASE)

    successor = superseded[0]
    assert run.state is RunState.ENDED
    assert successor.state is RunState.ACTIVE
    assert [outcome.failure_type for outcome in stale.outcomes] == [
        "StaleRunError",
        "StaleRunError",
    ]
    # The in-flight response advanced neither the superseded run nor the next one.
    assert store.calls == []
    assert await store.read_source_records("drivers", SESSION_KEY) == ()
    assert await store.get_watermark("drivers", SESSION_KEY) is None

    fresh = await successor.sync(http, store, CountingClock(), base_url=BASE)

    assert [outcome.status for outcome in fresh.outcomes] == ["ok", "ok"]
    assert await store.get_watermark("sessions", SESSION_KEY) == OBSERVED
    assert await store.get_watermark("drivers", SESSION_KEY) == OBSERVED
    assert len(await store.read_source_records("drivers", SESSION_KEY)) == 1


@pytest.mark.anyio
async def test_a_stale_run_keeps_the_endpoint_already_committed_before_the_transition() -> None:
    run = make_run()
    store = TrackingStore(InMemoryStore())
    fake = FakeHttpClient()
    register_both(fake)
    http = HookedHttpClient(fake, hook=run.end, trigger_url=DRIVERS_URL)

    result = await run.sync(http, store, CountingClock(), base_url=BASE)

    # No cross-endpoint rollback is claimed: sessions committed before the end.
    assert run.state is RunState.ENDED
    assert result.outcomes[0].status == "ok"
    assert result.outcomes[0].records_written == 1
    assert result.outcomes[0].checkpoint_written is True
    assert result.outcomes[1].status == "failed"
    assert result.outcomes[1].failure_stage == "write"
    assert result.outcomes[1].failure_type == "StaleRunError"
    # The refused endpoint reports an unknown count and no checkpoint, never a fabricated
    # zero or an invented success; the observation stamp still exists because the clock was
    # read before the write was refused.
    assert result.outcomes[1].records_written is None
    assert result.outcomes[1].checkpoint_written is False
    assert result.outcomes[1].observed_at is not None
    assert store.calls == ["write", "checkpoint"]
    assert await store.get_watermark("sessions", SESSION_KEY) == OBSERVED
    assert await store.get_watermark("drivers", SESSION_KEY) is None
    assert await store.read_source_records("drivers", SESSION_KEY) == ()


# --- cancellation and ownership ---------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("error", [asyncio.CancelledError(), KeyboardInterrupt()])
async def test_base_exceptions_propagate_without_a_fabricated_result(
    error: BaseException,
) -> None:
    run = make_run()
    store = TrackingStore(InMemoryStore())
    http = ExplodingHttpClient(error)

    with pytest.raises(type(error)):
        await run.sync(http, store, CountingClock(), base_url=BASE)

    # The run was not silently retired and nothing was written or closed.
    assert run.state is RunState.ACTIVE
    assert http.fetches == 1
    assert store.calls == []
    assert store.close_calls == 0


@pytest.mark.anyio
async def test_a_run_never_closes_or_swaps_the_caller_owned_client_and_store() -> None:
    run = make_run()
    store = TrackingStore(InMemoryStore())
    fake = FakeHttpClient()
    register_both(fake)
    http = HookedHttpClient(fake)

    result = await run.sync(http, store, CountingClock(), base_url=BASE)

    assert [outcome.status for outcome in result.outcomes] == ["ok", "ok"]
    assert http.close_calls == 0
    assert store.close_calls == 0
    # The same borrowed store is still usable for the next cadence tick.
    assert await store.get_watermark("sessions", SESSION_KEY) == OBSERVED
    follow_up = await run.sync(http, store, CountingClock(), base_url=BASE)
    assert [outcome.records_written for outcome in follow_up.outcomes] == [1, 1]
    assert http.close_calls == 0
    assert store.close_calls == 0


# --- the run-scoped store view ----------------------------------------------


@pytest.mark.anyio
async def test_the_run_scoped_store_view_refuses_to_close_the_callers_store() -> None:
    run = make_run()
    store = TrackingStore(InMemoryStore())
    view = session_module._RunScopedStore(store, run)

    assert isinstance(view, Store)
    # No deletion, truncation or transaction surface is added.
    assert {name for name in dir(view) if not name.startswith("_")} == {
        "close",
        "get_watermark",
        "read_source_records",
        "set_watermark",
        "write_source_batch",
    }

    with pytest.raises(StoreOwnershipError) as caught:
        await view.close()

    assert caught.value.args == ()
    assert str(caught.value) == ""
    assert store.close_calls == 0
    assert StaleRunError().args == ()


@pytest.mark.anyio
async def test_the_run_scoped_store_refuses_a_superseded_generation() -> None:
    class StandInRun:
        """A stand-in whose generation can move without a state change."""

        def __init__(self) -> None:
            self.state = RunState.ACTIVE
            self.generation = 1

    store = TrackingStore(InMemoryStore())
    stand_in = StandInRun()
    view = session_module._RunScopedStore(store, stand_in)  # type: ignore[arg-type]
    stand_in.generation = 2

    with pytest.raises(StaleRunError):
        await view.write_source_batch(
            "sessions", SESSION_KEY, [session_row()], observed_at=OBSERVED
        )
    with pytest.raises(StaleRunError):
        await view.set_watermark("sessions", SESSION_KEY, observed_at=OBSERVED)
    # Reads are never refused: only the two write methods are scoped.
    assert await view.read_source_records("sessions", SESSION_KEY) == ()
    assert store.calls == []


# --- text safety ------------------------------------------------------------


@pytest.mark.anyio
async def test_no_secret_or_identity_text_reaches_a_refusal_or_failure_type() -> None:
    run = make_run("run-marker-xyz")
    store = TrackingStore(InMemoryStore())
    fake = FakeHttpClient()
    fake.enqueue(SESSIONS_URL, HttpTransportError("token=SUPERSECRET"), params=PARAMS)
    fake.register(DRIVERS_URL, [driver_row()], params=PARAMS)

    result = await run.sync(HookedHttpClient(fake), store, CountingClock(), base_url=BASE)

    assert result.outcomes[0].failure_type == "HttpTransportError"
    serialized = repr(result)
    assert "SUPERSECRET" not in serialized
    assert "SUPERSECRET" not in str(result.outcomes[0])
    assert "run-marker-xyz" not in serialized

    run.end()
    with pytest.raises(RunNotActiveError) as caught:
        await run.sync(HookedHttpClient(fake), store, CountingClock(), base_url=BASE)

    assert caught.value.args == ()
    assert caught.value.__cause__ is None
    assert "run-marker-xyz" not in repr(caught.value)
