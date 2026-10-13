"""Offline tests for the wall-clock playback policy.

The unit under test is pure: it decides **how long to wait** before releasing the next
event, and it never waits itself — the wait goes to the injected monotonic clock. Every
test therefore runs on ``FakeMonotonicClock``, which advances only when someone sleeps
on it, so a ninety-minute race costs no real time and each wait can be asserted exactly.
A test that slept for real would be a defect of the test.

The rule these tests pin, and the two measured properties of the corpus behind its
edges:

* an event's target offset is ``timestamp_value - origin`` divided by the declared
  scale, so a run consumes a recorded session at the rate it happened;
* an event whose own timestamp is unknown is released with **no wait**, because the
  corpus holds such members — the null-timestamp lap-1 orphan, and a family whose
  records carry no timestamp field at all — and inventing "now" for them would assert
  a fact the data does not have.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re

import pytest

from f1show.collector import DetectedEvent, collect_session_events
from f1show.config import BoothSettings
from f1show.events import EventType
from f1show.fakes import FakeMonotonicClock, FrozenClock
from f1show.pacing import Pacer, PacingSpec, pacing_origin, release_at_offsets
from f1show.ports import ModelRequest, ModelResponse
from f1show.run import load_recorded_session, run_session

UTC = dt.timezone.utc
SESSION_KEY = 9617
T0 = dt.datetime(2024, 3, 2, 15, 0, 5, tzinfo=UTC)


def event(*, index: int, offset_seconds: float, driver_number: int = 1) -> DetectedEvent:
    """One event stamped ``offset_seconds`` after ``T0``, as the collector would derive it."""
    return DetectedEvent(
        event_type=EventType.LAP_COMPLETED,
        family="laps",
        session_key=SESSION_KEY,
        record_index=index,
        driver_number=driver_number,
        timestamp_field="date_start",
        timestamp_value=T0 + dt.timedelta(seconds=offset_seconds),
        timestamp_unknown_reason=None,
        evidence={"lap_number": 1},
    )


def unknown(*, index: int, driver_number: int = 1) -> DetectedEvent:
    """One event whose family carries no timestamp field, which is a recorded shape."""
    return DetectedEvent(
        event_type=EventType.STINT_START,
        family="stints",
        session_key=SESSION_KEY,
        record_index=index,
        driver_number=driver_number,
        timestamp_field=None,
        timestamp_value=None,
        timestamp_unknown_reason="family_carries_no_timestamp_field",
        evidence={"stint_number": 1},
    )


async def released(
    events: tuple[DetectedEvent, ...], *, scale: float, clock: FakeMonotonicClock | None = None
) -> tuple[list[DetectedEvent], FakeMonotonicClock]:
    """Release ``events`` on a fake monotonic clock and return them with the waits asked."""
    clock = FakeMonotonicClock() if clock is None else clock
    out = [item async for item in release_at_offsets(events, clock=clock, spec=PacingSpec(scale))]
    return out, clock


@pytest.mark.anyio
async def test_every_event_is_released_in_the_recorded_order() -> None:
    """Pacing changes when an event is released, never which one or in what order."""
    events = (event(index=0, offset_seconds=0.0), event(index=1, offset_seconds=10.0))
    out, _ = await released(events, scale=1.0)
    assert [item.record_index for item in out] == [0, 1]


@pytest.mark.anyio
async def test_the_first_known_event_is_released_at_the_origin_without_waiting() -> None:
    events = (event(index=0, offset_seconds=0.0), event(index=1, offset_seconds=30.0))
    _, clock = await released(events, scale=1.0)
    assert clock.sleeps[0] == 0.0


@pytest.mark.anyio
async def test_a_wait_is_the_offset_over_the_declared_scale() -> None:
    """Scale 1 is real time; a bigger scale is faster, and the waits scale exactly."""
    events = (
        event(index=0, offset_seconds=0.0),
        event(index=1, offset_seconds=10.0),
        event(index=2, offset_seconds=25.0),
    )
    _, real = await released(events, scale=1.0)
    assert real.sleeps == [0.0, 10.0, 15.0]

    _, fast = await released(events, scale=10.0)
    assert fast.sleeps == [0.0, 1.0, 1.5]
    # The waits sum to the scaled span: the run lasts the session divided by the scale.
    assert sum(fast.sleeps) == pytest.approx(2.5)


@pytest.mark.anyio
async def test_a_wait_is_never_negative() -> None:
    """An event recorded behind the schedule waits nothing rather than rewinding time."""
    events = (
        event(index=0, offset_seconds=0.0),
        event(index=1, offset_seconds=10.0),
        event(index=2, offset_seconds=5.0),
    )
    _, clock = await released(events, scale=1.0)
    assert clock.sleeps == [0.0, 10.0, 0.0]
    assert all(wait >= 0 for wait in clock.sleeps)


@pytest.mark.anyio
async def test_an_event_with_an_unknown_timestamp_is_released_without_waiting() -> None:
    """A member the data cannot place is released with the previous event, not invented."""
    events = (
        event(index=0, offset_seconds=0.0),
        unknown(index=1),
        event(index=2, offset_seconds=10.0),
    )
    out, clock = await released(events, scale=1.0)
    assert [item.record_index for item in out] == [0, 1, 2]
    assert clock.sleeps == [0.0, 0.0, 10.0]


@pytest.mark.anyio
async def test_the_origin_is_the_earliest_known_instant_not_the_first_record() -> None:
    """A run paces from its own earliest known instant, so a mid-session start works."""
    events = (
        event(index=0, offset_seconds=5.0),
        event(index=1, offset_seconds=0.0),
        event(index=2, offset_seconds=10.0),
    )
    assert pacing_origin(events) == T0
    _, clock = await released(events, scale=1.0)
    # Each wait is the **gap** to its target, not the target itself: the third event's
    # target is 10 s but 5 s have already elapsed, so it waits 5. The waits sum to the
    # last target, which is the run's scaled span -- the property the next assertion
    # pins, so a future edit cannot quietly turn these back into absolute offsets.
    assert clock.sleeps == [5.0, 0.0, 5.0]
    assert sum(clock.sleeps) == pytest.approx(10.0)


@pytest.mark.anyio
async def test_a_run_with_no_known_instant_waits_for_nothing() -> None:
    """With nothing to place, the run is as fast as an unpaced one, not an error."""
    events = (unknown(index=0), unknown(index=1))
    assert pacing_origin(events) is None
    out, clock = await released(events, scale=1.0)
    assert [item.record_index for item in out] == [0, 1]
    assert clock.sleeps == [0.0, 0.0]


@pytest.mark.parametrize("scale", [0.0, -1.0, float("inf"), float("nan")])
def test_the_scale_must_be_a_positive_finite_number(scale: float) -> None:
    with pytest.raises(ValueError):
        PacingSpec(scale)


@pytest.mark.anyio
async def test_equal_inputs_produce_equal_waits() -> None:
    """Determinism: the same events, scale and clock yield the same waits, twice."""
    events = (
        event(index=0, offset_seconds=0.0),
        unknown(index=1),
        event(index=2, offset_seconds=7.5),
    )
    _, first = await released(events, scale=2.0)
    _, second = await released(events, scale=2.0)
    assert first.sleeps == second.sleeps

# --- T2: the pacer the booth and the paced release share --------------------------------


def test_the_pacer_places_one_event_against_the_runs_own_origin() -> None:
    """The same rule the paced release uses, callable for one event at a time.

    The booth walks its events internally and so cannot consume a paced stream; it asks
    the same pacer instead. Two copies of a timing rule would drift, so this pins the one
    the booth calls and the next test pins that the stream agrees with it.
    """
    events = (
        event(index=0, offset_seconds=5.0),
        event(index=1, offset_seconds=0.0),
        event(index=2, offset_seconds=10.0),
    )
    pacer = Pacer(events, PacingSpec(scale=1.0))
    assert pacer.wait_seconds(events[0], elapsed_seconds=0.0) == pytest.approx(5.0)
    assert pacer.wait_seconds(events[1], elapsed_seconds=5.0) == pytest.approx(0.0)
    assert pacer.wait_seconds(events[2], elapsed_seconds=5.0) == pytest.approx(5.0)


def test_the_pacer_cannot_place_an_event_the_data_does_not() -> None:
    """Zero when the event carries no instant, and zero when the whole run carries none."""
    placed = Pacer(
        (unknown(index=0), event(index=1, offset_seconds=10.0)), PacingSpec(scale=1.0)
    )
    assert placed.wait_seconds(unknown(index=0), elapsed_seconds=0.0) == 0.0
    placeless = Pacer((unknown(index=0), unknown(index=1)), PacingSpec(scale=1.0))
    assert placeless.wait_seconds(unknown(index=0), elapsed_seconds=0.0) == 0.0


@pytest.mark.anyio
async def test_the_paced_release_waits_exactly_what_the_pacer_says() -> None:
    """One rule, two callers: the stream and the pacer must never disagree."""
    events = (event(index=0, offset_seconds=0.0), event(index=1, offset_seconds=4.0))
    pacer = Pacer(events, PacingSpec(scale=2.0))
    first = pacer.wait_seconds(events[0], elapsed_seconds=0.0)
    second = pacer.wait_seconds(events[1], elapsed_seconds=first)
    _, clock = await released(events, scale=2.0)
    assert clock.sleeps == [pytest.approx(first), pytest.approx(second)]


# --- T4: the end-to-end measurement, over the whole recorded session --------------------

FIELD_REFERENCE = re.compile(r"^-\s+([a-z_]+\[\d+\]\.[a-z0-9_]+)\s*$", re.MULTILINE)
IDENTITY_REFERENCE = re.compile(r"^-\s+([a-z_]+\[\d+\])\s*$", re.MULTILINE)


class CitesTheFirstOfferedReference:
    """Answer every turn with the first reference that turn's own prompt offered.

    A corpus run needs one answer per aired turn -- 1,629 over the recorded session -- and
    each answer must cite a reference that turn actually supplied, so the answer is derived
    from the prompt instead of written by hand. It is a scripted double, not a measurement:
    it makes no model call and claims nothing about a real model's behaviour.
    """

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        match = FIELD_REFERENCE.search(request.prompt) or IDENTITY_REFERENCE.search(
            request.prompt
        )
        if match is None:
            raise AssertionError("the prompt offered no reference to cite")
        return ModelResponse(
            model_id=request.model_id,
            text=f"EVIDENCE: {match.group(1)}\nCommentary on {match.group(1)}.",
            input_tokens=1,
            output_tokens=1,
        )


@pytest.mark.anyio
async def test_a_paced_run_over_the_recorded_session_costs_no_real_time() -> None:
    """At scale 1 the waits sum to ninety minutes of race, and the run still finishes.

    The hazard bound is the proof that nothing slept for real: a booth that really waited
    would still be inside its first gap when the bound expired. The two runs also have to
    agree turn for turn, which is S3 checked over the whole corpus rather than three events.
    """
    payloads = load_recorded_session(SESSION_KEY)
    events = collect_session_events(SESSION_KEY, payloads)
    monotonics = FakeMonotonicClock()

    def a_run(*, paced: bool) -> object:
        cadence = {"monotonic": monotonics, "pacing": PacingSpec(scale=1.0)} if paced else {}
        return run_session(
            payloads=payloads,
            session_key=SESSION_KEY,
            model=CitesTheFirstOfferedReference(),
            clock=FrozenClock(T0),
            settings=BoothSettings(model_id="test-model", language="en"),
            **cadence,
        )

    async with asyncio.timeout(60):
        paced = await a_run(paced=True)
        unpaced = await a_run(paced=False)

    known = [event.timestamp_value for event in events if event.timestamp_value is not None]
    span = (max(known) - min(known)).total_seconds()
    # One wait per event, in order, and their sum is the session's own span at scale 1.
    assert len(monotonics.sleeps) == len(events)
    assert all(wait >= 0.0 for wait in monotonics.sleeps)
    assert sum(monotonics.sleeps) == pytest.approx(span, abs=1.0)
    # Ninety minutes of race, paced, and not one of them spent waiting for real.
    assert span > 3000.0
    # S3 over the whole corpus: the cadence changed when, and nothing else.
    assert [turn.text for turn in paced.transcript.turns] == [
        turn.text for turn in unpaced.transcript.turns
    ]
    assert len(paced.transcript.turns) == len(unpaced.transcript.turns) > 0
    assert [(item.kind, item.reason) for item in paced.outcomes] == [
        (item.kind, item.reason) for item in unpaced.outcomes
    ]
