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

import datetime as dt

import pytest

from f1show.collector import DetectedEvent
from f1show.events import EventType
from f1show.fakes import FakeMonotonicClock
from f1show.pacing import PacingSpec, pacing_origin, release_at_offsets

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
