"""Deterministic, in-memory test doubles for every injection boundary.

These are **deliberately shipped**, not test-local: every unit's tests and the
offline replay harness share one implementation instead of re-inventing a fake
per module. Each fails loudly rather than inventing an answer, and nothing here
touches the network, the wall clock or the disk.
"""

from __future__ import annotations

import copy
import datetime as dt
from collections.abc import Mapping, Sequence

from f1show.events import EventEnvelope
from f1show.ports import (
    HttpResponse,
    ModelRequest,
    ModelResponse,
    copy_form_fields,
    copy_request_headers,
)


class FrozenClock:
    """A clock stopped at one aware instant, movable only by hand."""

    def __init__(self, start: dt.datetime) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("FrozenClock needs a timezone-aware instant; naive time is ambiguous")
        self._now = start.astimezone(dt.timezone.utc)

    def now(self) -> dt.datetime:
        """Return the frozen instant. Always timezone-aware and UTC."""
        return self._now

    def advance(self, seconds: float) -> dt.datetime:
        """Move the clock forward by ``seconds`` and return the new instant.

        A negative value is rejected: a test clock that can silently run
        backwards is a hazard, not a feature.
        """
        if seconds < 0:
            raise ValueError(
                f"FrozenClock cannot advance by a negative number of seconds; got {seconds!r}"
            )
        self._now += dt.timedelta(seconds=seconds)
        return self._now


class FakeMonotonicClock:
    """A virtual monotonic clock that moves only when someone sleeps on it.

    Deliberately independent from :class:`FrozenClock`: pacing measures elapsed
    duration, not the UTC instant an observation is stamped with, and the two must
    not be able to move each other. Every ``sleep`` advances the clock by exactly
    the requested duration and records it, so a test can assert the precise waits a
    policy asked for. A negative sleep is refused rather than silently rewinding.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        """Return the virtual instant; only differences between calls matter."""
        return self._now

    async def sleep(self, seconds: float) -> None:
        """Advance the virtual clock by exactly ``seconds`` and record the wait."""
        if seconds < 0:
            raise ValueError(
                "FakeMonotonicClock cannot sleep for a negative number of seconds; "
                f"got {seconds!r}"
            )
        self.sleeps.append(seconds)
        self._now += seconds


class FakeHttpClient:
    """Answers registered URLs, or the outcomes scripted for them, and logs every call.

    Three guarantees make it usable as a policy double rather than a stub:

    * An unregistered URL raises, so an accidental network call cannot go unnoticed.
    * A registered payload and its headers are copied in both directions, so mutating
      what was passed in, or what came back, cannot poison a later answer.
    * Scripted outcomes are delivered strictly in order and never repeat; once the
      queue is drained the fake refuses instead of falling back to a static answer.

    F03d adds the additive form-POST surface. Every existing observable stays exactly
    as it was - the ``calls`` list shape, the registration keys, the exhaustion rule and
    the deep copies - and the new surface is observed separately through
    ``post_calls`` and ``request_headers``. A form registration never collides with a
    GET registration for the same URL, and request header names are recorded verbatim,
    never lower-cased: observing them is the fake's job, rewriting them is not.
    """

    def __init__(self) -> None:
        self._responses: dict[tuple[str, tuple[tuple[str, str], ...]], HttpResponse] = {}
        self._scripts: dict[
            tuple[str, tuple[tuple[str, str], ...]], list[HttpResponse | BaseException]
        ] = {}
        self._form_responses: dict[tuple[str, tuple[tuple[str, str], ...]], HttpResponse] = {}
        self._form_scripts: dict[
            tuple[str, tuple[tuple[str, str], ...]], list[HttpResponse | BaseException]
        ] = {}
        self._closed = False
        self.calls: list[tuple[str, dict[str, str] | None]] = []
        #: Additive F03d observability: the request headers of every request, in call
        #: order, or ``None`` when the call passed none.
        self.request_headers: list[dict[str, str] | None] = []
        #: Additive F03d observability: ``(url, form, headers)`` for every form POST.
        self.post_calls: list[tuple[str, dict[str, str], dict[str, str] | None]] = []

    def register(
        self,
        url: str,
        payload: object,
        *,
        params: Mapping[str, str] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Register the answer for ``url`` with exactly ``params``.

        The default is a success response wrapping ``payload``. A non-2xx status with
        ``payload=None`` models a source failure whose status and headers the caller
        must inspect; a ``headers`` mapping is copied so a mutable fixture cannot
        change an already-registered answer.
        """
        self._responses[(url, self._key(params))] = HttpResponse(
            status_code=status_code,
            headers=dict(headers) if headers is not None else {},
            payload=copy.deepcopy(payload),
        )

    def enqueue(
        self,
        url: str,
        outcome: HttpResponse | BaseException,
        *,
        params: Mapping[str, str] | None = None,
    ) -> None:
        """Append one scripted outcome for the ``url``/``params`` pair.

        A queued outcome wins over any static registration and is consumed in order:
        an ``HttpResponse`` is returned, an exception instance is raised, and
        exhausting the queue raises instead of repeating or falling back. Nothing here
        retries, so a policy test sees exactly the sequence it scripted.
        """
        if not isinstance(outcome, (HttpResponse, BaseException)):
            raise TypeError(
                "a scripted outcome must be an HttpResponse or an exception instance, "
                f"got {type(outcome).__name__}"
            )
        self._scripts.setdefault((url, self._key(params)), []).append(outcome)

    def register_form(
        self,
        url: str,
        payload: object,
        *,
        form: Mapping[str, str] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Register the answer for a form POST to ``url`` with exactly ``form``.

        Additive to :meth:`register`: the two key spaces are separate, so a form
        registration neither shadows nor is shadowed by a GET registration on the same
        URL. The payload and headers are copied exactly as :meth:`register` copies them.
        """
        self._form_responses[(url, self._key(form))] = HttpResponse(
            status_code=status_code,
            headers=dict(headers) if headers is not None else {},
            payload=copy.deepcopy(payload),
        )

    def enqueue_form(
        self,
        url: str,
        outcome: HttpResponse | BaseException,
        *,
        form: Mapping[str, str] | None = None,
    ) -> None:
        """Append one scripted outcome for the form-POST ``url``/``form`` pair."""
        if not isinstance(outcome, (HttpResponse, BaseException)):
            raise TypeError(
                "a scripted outcome must be an HttpResponse or an exception instance, "
                f"got {type(outcome).__name__}"
            )
        self._form_scripts.setdefault((url, self._key(form)), []).append(outcome)

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Return the next answer for the ``url``/``params`` pair, or raise.

        The call is recorded before the outcome is delivered, including when the
        outcome is a scripted exception, so an exhausted queue still shows the attempt.
        ``headers`` is validated by the shared port rule and recorded verbatim.
        """
        if self._closed:
            raise RuntimeError("FakeHttpClient is closed")
        copied_headers = copy_request_headers(headers)
        self.calls.append((url, dict(params) if params is not None else None))
        self.request_headers.append(copied_headers)
        key = (url, self._key(params))
        if key in self._scripts:
            queue = self._scripts[key]
            if not queue:
                raise RuntimeError(
                    f"FakeHttpClient scripted outcomes for {url!r} with {params!r} are exhausted"
                )
            outcome = queue.pop(0)
            if not isinstance(outcome, HttpResponse):
                raise outcome
            return self._copy(outcome)
        if key not in self._responses:
            raise LookupError(f"FakeHttpClient has no registered response for {url!r} with {params!r}")
        return self._copy(self._responses[key])

    async def post_form_json(
        self,
        url: str,
        *,
        form: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Return the next answer for the form-POST ``url``/``form`` pair, or raise.

        The mirror of :meth:`get_json` for the additive form surface: the same recording
        discipline, the same scripted-then-static-then-refuse order, and the same deep
        copies. The form and headers are validated by the shared port rule before the
        call is recorded.
        """
        if self._closed:
            raise RuntimeError("FakeHttpClient is closed")
        copied_form = copy_form_fields(form)
        copied_headers = copy_request_headers(headers)
        self.post_calls.append((url, copied_form, copied_headers))
        self.request_headers.append(copied_headers)
        key = (url, self._key(copied_form))
        if key in self._form_scripts:
            queue = self._form_scripts[key]
            if not queue:
                raise RuntimeError(
                    f"FakeHttpClient scripted form outcomes for {url!r} with "
                    f"{copied_form!r} are exhausted"
                )
            outcome = queue.pop(0)
            if not isinstance(outcome, HttpResponse):
                raise outcome
            return self._copy(outcome)
        if key not in self._form_responses:
            raise LookupError(
                f"FakeHttpClient has no registered form response for {url!r} with "
                f"{copied_form!r}"
            )
        return self._copy(self._form_responses[key])

    async def close(self) -> None:
        """Mark the fake closed; safe to call repeatedly."""
        self._closed = True

    @classmethod
    def _copy(cls, response: HttpResponse) -> HttpResponse:
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            payload=copy.deepcopy(response.payload),
        )

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

    Reads mirror the real store's ``ORDER BY observed_at, rowid``: ascending by
    batch observation time, stable for equal times. Records are held in an
    insertion-ordered mapping keyed by identity, so a replacement updates the
    value in place and keeps its original position, exactly as an upsert keeps
    its ``rowid``.
    """

    def __init__(self) -> None:
        self._records: dict[
            tuple[str, int], dict[str, tuple[dt.datetime, dict[str, object]]]
        ] = {}
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
        # Validate and copy the whole batch before touching stored state, exactly
        # as the real store prepares every row before executing: one invalid
        # record rejects the batch without a partial write.
        prepared: list[tuple[str, dict[str, object]]] = []
        for record in records:
            identity = record.get("record_id")
            if not isinstance(identity, str) or not identity.strip():
                raise ValueError(
                    f"source record for family {family!r} must carry a non-empty string "
                    "'record_id'; deriving an identity belongs to the sync writer"
                )
            prepared.append((identity, copy.deepcopy(dict(record))))
        bucket = self._records.setdefault((family, session_key), {})
        for identity, payload in prepared:
            # Reassign an existing key, which keeps its position: a replacement
            # stays where it was instead of moving to the back. The real store
            # upserts on (family, session_key, record_id); a double that appended
            # would let tests pass that the real store would not.
            bucket[identity] = (observed_at, payload)
        return len(records)

    async def read_source_records(
        self,
        family: str,
        session_key: int,
        *,
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
    ) -> Sequence[tuple[dt.datetime, Mapping[str, object]]]:
        """Return ``(observed_at, record)`` pairs in the inclusive window, oldest first.

        Each pair carries the instant of its write batch, and the result is sorted
        stably by that time, matching the real store. Both the instant and the
        payload are fresh copies, so a caller cannot reach stored state.
        """
        self._require_open()
        found = [
            (stamped_at, copy.deepcopy(record))
            for stamped_at, record in self._records.get((family, session_key), {}).values()
            if (since is None or stamped_at >= since) and (until is None or stamped_at <= until)
        ]
        found.sort(key=lambda row: row[0])
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
