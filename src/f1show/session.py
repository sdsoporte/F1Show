"""Run-scoped session lifecycle over the bounded two-endpoint sync.

:func:`f1show.ingest.sync_session` is deliberately stateless: it fetches and
ingests both fixed endpoints once and has no memory of whether a caller still
wants the answer. A live operator does have that memory, and that is the whole
reason this module exists.

A :class:`SessionRun` fixes one caller-supplied identity and one generation,
performs exactly one bounded sync per call - repeat calls are the ~3s live
cadence, not an error - and can be ended, cancelled or superseded. Nothing here
opens, closes, wraps, re-limits or retries anything: the caller owns the
``HttpClient``, the ``Store`` and its own task, and ``cancel()`` requests
isolation rather than reaching into that task.

**Late responses do not commit.** ``sync_session`` receives a run-scoped
``Store`` view that delegates reads and refuses the two write methods once the
run is no longer active, so the existing pipeline turns a write that raced an
``end``/``cancel``/``reset`` into an honest ``failed`` outcome carrying
``failure_type="StaleRunError"`` instead of a committed row. The view never
closes or replaces the caller's store and adds no delete or transaction surface.

**Refusal is typed data, not text.** A sync on a non-active run raises
:class:`RunNotActiveError` before the first fetch or store call, and no exception
or outcome produced here repeats a payload, URL, header, secret, session
identifier or provider text.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from f1show.config import DEFAULT_OPENF1_BASE_URL
from f1show.ingest import SessionSyncResult, _require_session_key, sync_session
from f1show.ports import Clock, HttpClient, Store


class RunState(str, Enum):
    """The closed lifecycle vocabulary of one run.

    A ``str`` enum so the value is plain data a caller can compare, log or
    serialize without a lookup table. There is deliberately no ``superseded``
    member: a superseded run is an ended one whose generation has been passed,
    and a fourth word would make that look like a different outcome.
    """

    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"


class RunNotActiveError(RuntimeError):
    """A sync was requested from a run that is no longer active.

    Carries no message on purpose: the failure is the type, and any text here
    would risk repeating a URL, header, payload or session identifier into a log.
    """


class StaleRunError(RuntimeError):
    """A write was refused because its run is no longer active.

    Raised by the run-scoped store view and reported by the existing pipeline as
    ``failure_type="StaleRunError"``. It also carries no message.
    """


class StoreOwnershipError(RuntimeError):
    """The run-scoped view was asked to close the caller's store.

    The caller owns the store; a run only borrows it. Refusing here is the
    explicit alternative to an ownership bug that would close a connection the
    caller still needs.
    """


@dataclass(frozen=True)
class SessionRunIdentity:
    """Fixed per-run identity: a caller label plus the session the run tracks.

    ``run_id`` is caller-supplied and validated as a non-empty string: this
    module never generates a uuid, reads entropy or consults a clock, so a run
    stays deterministic in a test. ``session_key`` uses the exact admission rule
    the endpoint writer already applies, imported rather than re-derived so the
    two cannot drift.
    """

    run_id: str
    session_key: int

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        _require_session_key(self.session_key)


class SessionRun:
    """One session's run: a fixed identity, a generation and a live state.

    The run coordinates; it owns no resources. ``sync`` borrows the caller's
    ``HttpClient``/``Store``/``Clock`` for one bounded pass and never closes,
    swaps or reconfigures them.
    """

    __slots__ = ("_generation", "_identity", "_state")

    def __init__(self, identity: SessionRunIdentity, generation: int = 1) -> None:
        if not isinstance(identity, SessionRunIdentity):
            raise TypeError("identity must be a SessionRunIdentity")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0:
            raise ValueError("generation must be a positive integer")
        self._identity = identity
        self._generation = generation
        self._state: RunState = RunState.ACTIVE

    @property
    def identity(self) -> SessionRunIdentity:
        return self._identity

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def state(self) -> RunState:
        return self._state

    async def sync(
        self,
        http: HttpClient,
        store: Store,
        clock: Clock,
        *,
        base_url: str = DEFAULT_OPENF1_BASE_URL,
    ) -> SessionSyncResult:
        """Fetch and ingest both endpoints once for this run's fixed session.

        The run's own ``identity.session_key`` is the only session argument, so
        a caller cannot accidentally sync a different session under this run's
        identity. A non-active run is refused before the first fetch or store
        call; a run that becomes non-active while the request is in flight has
        its writes refused by the run-scoped view. Either way the caller owns
        the client, the store and the task, and a ``CancelledError`` raised by
        the client propagates unchanged.
        """
        if self._state is not RunState.ACTIVE:
            raise RunNotActiveError
        view = _RunScopedStore(store, self)
        return await sync_session(
            http,
            view,
            clock,
            session_key=self._identity.session_key,
            base_url=base_url,
        )

    def end(self) -> None:
        """Move an active run to ``ended``; a repeat leaves the state unchanged."""
        if self._state is RunState.ACTIVE:
            self._state = RunState.ENDED

    def cancel(self) -> None:
        """Request isolation: an active run becomes ``cancelled`` and cannot commit.

        This does not reach into the caller's task; the caller still owns the
        task and any ``CancelledError`` it sees. A repeat leaves the state
        unchanged, and so does an ``end`` that follows a ``cancel``.
        """
        if self._state is RunState.ACTIVE:
            self._state = RunState.CANCELLED

    def reset(self, session_key: int, run_id: str) -> SessionRun:
        """Supersede this run and return a fresh one for ``session_key``.

        The successor is built - and its identity validated - before this run is
        marked terminal, so an invalid ``run_id``/``session_key`` leaves the
        current run active. An already terminal run keeps its terminal state
        instead of being relabelled. Superseding is purely in-memory: it never
        reads, rewrites, deletes or truncates committed store rows and makes no
        store call at all.
        """
        successor = SessionRun(
            SessionRunIdentity(run_id=run_id, session_key=session_key),
            generation=self._generation + 1,
        )
        if self._state is RunState.ACTIVE:
            self._state = RunState.ENDED
        return successor


class _RunScopedStore:
    """The caller's store seen through one run's lifecycle.

    Read methods delegate unchanged; ``write_source_batch`` and ``set_watermark``
    refuse with :class:`StaleRunError` once the run is not active or its
    generation no longer matches the one captured when the view was built. The
    view exposes no delete, truncate or transaction method, and ``close`` is an
    explicit refusal rather than a delegation, because the caller owns the store.
    """

    __slots__ = ("_generation", "_run", "_store")

    def __init__(self, store: Store, run: SessionRun) -> None:
        self._store = store
        self._run = run
        self._generation = run.generation

    def _require_current(self) -> None:
        # The state check is the observable guard for end/cancel/reset. The
        # generation check is a secondary invariant: it keeps a superseded
        # generation from ever writing even if a future implementation moved a
        # run's generation in place instead of returning a new object.
        if self._run.state is not RunState.ACTIVE or self._run.generation != self._generation:
            raise StaleRunError

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: datetime,
    ) -> int:
        self._require_current()
        return await self._store.write_source_batch(
            family, session_key, records, observed_at=observed_at
        )

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: datetime
    ) -> int:
        self._require_current()
        return await self._store.set_watermark(endpoint, session_key, observed_at=observed_at)

    async def read_source_records(
        self,
        family: str,
        session_key: int,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Sequence[tuple[datetime, Mapping[str, object]]]:
        return await self._store.read_source_records(
            family, session_key, since=since, until=until
        )

    async def get_watermark(self, endpoint: str, session_key: int) -> datetime | None:
        return await self._store.get_watermark(endpoint, session_key)

    async def close(self) -> None:
        """Refuse to close the caller's store: the caller owns its lifecycle."""
        raise StoreOwnershipError
