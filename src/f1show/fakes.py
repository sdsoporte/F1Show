"""Deterministic, in-memory test doubles for every injection boundary.

These are **deliberately shipped**, not test-local: every unit's tests and the
offline replay harness share one implementation instead of re-inventing a fake
per module. Each fails loudly rather than inventing an answer, and nothing here
touches the network, the wall clock or the disk.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

from f1show.events import EventEnvelope
from f1show.ports import ModelRequest, ModelResponse


class FrozenClock:
    """A clock stopped at one aware instant, movable only by hand."""

    def __init__(self, start: dt.datetime) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("FrozenClock needs a timezone-aware instant; naive time is ambiguous")
        self._now = start

    def now(self) -> dt.datetime:
        """Return the frozen instant. Always timezone-aware and UTC."""
        return self._now

    def advance(self, seconds: float) -> dt.datetime:
        """Move the clock forward by ``seconds`` and return the new instant."""
        self._now += dt.timedelta(seconds=seconds)
        return self._now


class FakeHttpClient:
    """Answers only registered URLs and logs every call.

    An unregistered URL raises, so an accidental network call cannot go unnoticed.
    """

    def __init__(self) -> None:
        self._responses: dict[tuple[str, tuple[tuple[str, str], ...]], object] = {}
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def register(
        self, url: str, payload: object, *, params: Mapping[str, str] | None = None
    ) -> None:
        """Register ``payload`` as the answer for ``url`` with exactly ``params``."""
        self._responses[(url, self._key(params))] = payload

    async def get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> object:
        """Return the registered payload or raise; the URL-``params`` pair is the key."""
        self.calls.append((url, dict(params) if params is not None else None))
        key = (url, self._key(params))
        if key not in self._responses:
            raise LookupError(f"FakeHttpClient has no registered response for {url!r} with {params!r}")
        return self._responses[key]

    @staticmethod
    def _key(params: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((params or {}).items()))


class InMemoryBus:
    """An append-only bus with a cursor and an ack set per group.

    ``read`` never moves the cursor past an unacked message, so delivery is
    at-least-once; one group's reads and acks are invisible to every other.
    """

    def __init__(self) -> None:
        self._streams: dict[str, list[tuple[str, EventEnvelope]]] = {}
        self._cursors: dict[tuple[str, str], int] = {}
        self._acked: dict[tuple[str, str], set[str]] = {}

    async def publish(self, stream: str, event: EventEnvelope) -> str:
        entries = self._streams.setdefault(stream, [])
        message_id = str(len(entries) + 1)
        entries.append((message_id, event))
        return message_id

    async def read(
        self, stream: str, group: str, consumer: str, *, count: int = 10
    ) -> tuple[tuple[str, EventEnvelope], ...]:
        entries = self._streams.get(stream, [])
        acked = self._acked.get((stream, group), set())
        index = self._cursors.get((stream, group), 0)
        delivered: list[tuple[str, EventEnvelope]] = []
        while index < len(entries) and len(delivered) < count:
            message_id, event = entries[index]
            if message_id not in acked:
                delivered.append((message_id, event))
            index += 1
        return tuple(delivered)

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        entries = self._streams.get(stream, [])
        self._acked.setdefault((stream, group), set()).add(message_id)
        cursor = self._cursors.get((stream, group), 0)
        while cursor < len(entries) and entries[cursor][0] in self._acked[(stream, group)]:
            cursor += 1
        self._cursors[(stream, group)] = cursor


class InMemoryStore:
    """A dict-backed store: records isolate by ``family`` and ``session_key``, the
    watermark is per ``(endpoint, session_key)``, and ``close`` marks it closed so
    further use raises.
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, int], list[tuple[dt.datetime, dict[str, object]]]] = {}
        self._watermarks: dict[tuple[str, int], dt.datetime] = {}
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("InMemoryStore is closed")

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: dt.datetime,
    ) -> int:
        self._require_open()
        bucket = self._records.setdefault((family, session_key), [])
        for record in records:
            bucket.append((observed_at, dict(record)))
        return len(records)

    async def read_source_records(
        self,
        family: str,
        session_key: int,
        *,
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
    ) -> Sequence[Mapping[str, object]]:
        """Return copies of records whose observation time is in the inclusive window.

        Each record is stamped with the ``observed_at`` of its write batch.
        """
        self._require_open()
        found: list[dict[str, object]] = []
        for stamped_at, record in self._records.get((family, session_key), []):
            if since is not None and stamped_at < since:
                continue
            if until is not None and stamped_at > until:
                continue
            found.append(dict(record))
        return tuple(found)

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: dt.datetime
    ) -> int:
        self._require_open()
        self._watermarks[(endpoint, session_key)] = observed_at
        return 1

    async def get_watermark(self, endpoint: str, session_key: int) -> dt.datetime | None:
        self._require_open()
        return self._watermarks.get((endpoint, session_key))

    async def close(self) -> None:
        self._closed = True


class ScriptedModelClient:
    """Returns exactly the queued responses, in order, and records every request.

    It raises when the queue is exhausted rather than inventing a response.
    """

    def __init__(self, responses: Sequence[ModelResponse] = ()) -> None:
        self._queue = list(responses)
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError(
                "ScriptedModelClient queue is exhausted; a silent fallback is forbidden"
            )
        return self._queue.pop(0)
