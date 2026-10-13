"""Offline tests for the start aggregation's grouping rule.

The unit under test is pure: it decides **which events form the start group** and
**where that group's single turn sits** in the recorded order. It does not build a
prompt, call a model or read a fixture, so everything here is deterministic and free.

Two measured properties of the recorded stream shape this file, and both are why the
grouping is a scan rather than a prefix:

* nineteen of the twenty lap-1 rows carry ``date_start`` and interleave with the
  position changes, while **one has a null timestamp** and the collector's total order
  (`unknown timestamps last`) sends it to the **end** of the sequence;
* the collector maps exactly the ``laps`` family to ``LAP_COMPLETED``, so a lap-1 row
  is identifiable from the event alone, without re-reading the fixture.
"""

from __future__ import annotations

import datetime as dt

from f1show.collector import DetectedEvent
from f1show.events import EventType
from f1show.start import group_start_events

UTC = dt.timezone.utc
SESSION_KEY = 9617
T0 = dt.datetime(2024, 3, 2, 15, 0, 5, tzinfo=UTC)


def event(
    *,
    index: int,
    event_type: EventType = EventType.LAP_COMPLETED,
    family: str = "laps",
    evidence: dict[str, object] | None = None,
    driver_number: int | None = 1,
    timestamp: dt.datetime | None = T0,
) -> DetectedEvent:
    """One detected event, carrying exactly the fields the grouping reads."""
    return DetectedEvent(
        event_type=event_type,
        family=family,
        session_key=SESSION_KEY,
        record_index=index,
        driver_number=driver_number,
        timestamp_field="date_start" if timestamp is not None else None,
        timestamp_value=timestamp,
        timestamp_unknown_reason=(
            None if timestamp is not None else "family_carries_no_timestamp_field"
        ),
        evidence={"lap_number": 1} if evidence is None else evidence,
    )


def lap_one(
    index: int, *, driver: int, timestamp: dt.datetime | None = T0
) -> DetectedEvent:
    """A recorded lap-1 row: the family, type and evidence the collector derives for it."""
    return event(
        index=index,
        evidence={"lap_number": 1, "lap_duration": 90.0 + index},
        driver_number=driver,
        timestamp=timestamp,
    )


# --- When there is no start group -----------------------------------------------


def test_a_stream_without_lap_one_events_has_no_start_group() -> None:
    events = [
        event(index=3, evidence={"lap_number": 2}),
        event(index=4, evidence={"lap_number": 3}),
    ]

    assert group_start_events(events) is None


def test_a_single_lap_one_event_is_not_an_aggregation() -> None:
    """One row is already one turn: aggregating it would change nothing but the reason."""
    assert group_start_events([lap_one(7, driver=4)]) is None


def test_a_lap_two_row_is_never_a_member() -> None:
    events = [
        lap_one(1, driver=1),
        event(index=2, evidence={"lap_number": 2}, driver_number=2),
        lap_one(3, driver=3),
    ]

    group = group_start_events(events)

    assert group is not None
    assert [member.record_index for member in group.members] == [1, 3]


def test_only_the_lap_family_qualifies_even_when_its_evidence_says_lap_one() -> None:
    """The member rule is the collector's own mapping, not a bare field match."""
    events = [
        lap_one(1, driver=1),
        event(
            index=2,
            event_type=EventType.POSITION_CHANGE,
            family="position",
            evidence={"lap_number": 1, "position": 3},
            driver_number=2,
        ),
        lap_one(3, driver=3),
    ]

    group = group_start_events(events)

    assert group is not None
    assert [member.record_index for member in group.members] == [1, 3]


def test_a_non_integer_lap_number_is_not_a_member() -> None:
    """``True == 1`` in Python, and a boolean is not a recorded lap number."""
    events = [
        lap_one(1, driver=1),
        event(index=2, evidence={"lap_number": True}, driver_number=2),
        lap_one(3, driver=3),
    ]

    group = group_start_events(events)

    assert group is not None
    assert [member.record_index for member in group.members] == [1, 3]


# --- Where the group sits, and which members it covers ---------------------------


def test_the_group_sits_at_its_first_member_and_covers_every_other_one() -> None:
    events = [
        event(
            index=0,
            evidence={"position": 1},
            family="position",
            event_type=EventType.POSITION_CHANGE,
        ),
        lap_one(1, driver=1),
        event(
            index=2,
            evidence={"position": 2},
            family="position",
            event_type=EventType.POSITION_CHANGE,
        ),
        lap_one(3, driver=2),
        lap_one(4, driver=3),
    ]

    group = group_start_events(events)

    assert group is not None
    assert group.position == 1
    assert [member.record_index for member in group.members] == [1, 3, 4]
    assert group.covered == frozenset({3, 4})


def test_a_member_with_no_timestamp_that_sorts_last_is_still_a_member() -> None:
    """The measured shape of the corpus: the orphan belongs to the group it cannot sit in."""
    events = [
        lap_one(1, driver=1),
        event(
            index=2,
            evidence={"position": 5},
            family="position",
            event_type=EventType.POSITION_CHANGE,
        ),
        lap_one(3, driver=2),
        lap_one(4, driver=63, timestamp=None),
    ]

    group = group_start_events(events)

    assert group is not None
    assert group.position == 0
    assert [member.driver_number for member in group.members] == [1, 2, 63]
    assert group.covered == frozenset({2, 3})


def test_the_members_keep_the_recorded_order_and_the_grouping_is_deterministic() -> (
    None
):
    events = [lap_one(1, driver=1), lap_one(2, driver=2), lap_one(3, driver=3)]

    first = group_start_events(events)
    second = group_start_events(tuple(events))

    assert first is not None and second is not None
    assert [member.driver_number for member in first.members] == [1, 2, 3]
    assert first.position == second.position
    assert first.covered == second.covered
    assert [member.record_index for member in first.members] == [
        member.record_index for member in second.members
    ]
