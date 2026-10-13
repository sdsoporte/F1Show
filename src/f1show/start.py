"""The start aggregation's grouping rule, as a pure function of the recorded order.

The design asks for one thing of the start: **the twenty lap-1 events become one "start"
turn**, because twenty near-identical sentences are not a start. This module decides only
**which** events that group contains and **where** its single turn sits; it builds no
prompt, calls no model and reads no fixture, so the decision is testable on its own and
the booth keeps its own walk over the events.

**Why a scan and not a prefix, measured.** In the recorded session nineteen of the twenty
lap-1 rows carry ``date_start`` and interleave with the position changes, while exactly
one has a null timestamp; the collector's total order sends unknown timestamps last, so
that member lands **after every timestamped event and after every other member** --
measured at indices **25-43 and 1604**, with 43 null-timestamp ``stints`` events still
following it. (An earlier wording claimed it sorted after *every* other event; a verifier
measured the tail and that claim was too strong, so it is corrected here rather than
repeated.) A rule that took "the first twenty lap events" or a contiguous block would
therefore drop a real member, so the membership test is applied to every event in the
sequence and the group's turn sits at the **lowest index** among its members. Every other member is *covered*: its own turn is
never attempted, and the booth states that as a typed outcome rather than dropping it
silently.

**What is a lap-1 event, declared.** An event whose type is exactly the one the collector
derives from the ``laps`` family and whose own evidence says ``lap_number == 1``. The
field is read defensively -- ``True == 1`` in Python, and a boolean is not a recorded lap
number -- and a stream with fewer than two members has **no** group, so a single row keeps
the behaviour it already had.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from f1show.collector import DetectedEvent
from f1show.events import EventType

__all__ = [
    "LAP_ONE_EVENT_TYPE",
    "MINIMUM_START_MEMBERS",
    "START_LAP_NUMBER",
    "StartGroup",
    "group_start_events",
]

#: The one event type the collector derives from the ``laps`` family, which is what makes a
#: lap-1 row identifiable from the event alone instead of by re-reading the fixture.
LAP_ONE_EVENT_TYPE = EventType.LAP_COMPLETED

#: The lap whose events the start turn aggregates.
START_LAP_NUMBER = 1

#: Fewer members than this is not an aggregation: one row is already one turn, so grouping
#: it would change the disclosed reason without changing the transcript.
MINIMUM_START_MEMBERS = 2


@dataclass(frozen=True)
class StartGroup:
    """The lap-1 events of one stream, and where their single turn sits.

    ``positions`` and ``members`` are parallel and in recorded order, so ``position`` is
    the index of the first member and ``covered`` holds the indices of the rest. The two
    are kept apart because they answer different questions: ``position`` says *where the
    turn airs*, ``covered`` says *which events it absorbs*.
    """

    positions: tuple[int, ...]
    members: tuple[DetectedEvent, ...]

    @property
    def position(self) -> int:
        """The index the start turn airs at: the first member's."""
        return self.positions[0]

    @property
    def covered(self) -> frozenset[int]:
        """The indices whose own turn the start turn absorbs, excluding ``position``."""
        return frozenset(self.positions[1:])

    def covers(self, index: int) -> bool:
        """Whether the event at ``index`` is a member whose own turn is absorbed."""
        return index in self.covered


def group_start_events(events: Sequence[DetectedEvent]) -> StartGroup | None:
    """The stream's lap-1 group, or ``None`` when there is nothing to aggregate.

    A membership scan over the whole sequence, never a prefix: the recorded corpus puts one
    member after every other event of the race, and a prefix rule would silently leave it
    out. Order is the recorded order, so two runs over equal sequences agree.
    """
    positions: list[int] = []
    members: list[DetectedEvent] = []
    for index, event in enumerate(events):
        if _is_lap_one(event):
            positions.append(index)
            members.append(event)
    if len(members) < MINIMUM_START_MEMBERS:
        return None
    return StartGroup(positions=tuple(positions), members=tuple(members))


def _is_lap_one(event: DetectedEvent) -> bool:
    """Whether the collector derived ``event`` from a lap-1 row.

    Both halves are required: the event type the ``laps`` family maps to, and the event's
    own recorded lap number. The number is checked as a real integer, because ``True == 1``
    would otherwise let a boolean stand in for a lap.
    """
    if event.event_type is not LAP_ONE_EVENT_TYPE:
        return False
    value = event.evidence.get("lap_number")
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value == START_LAP_NUMBER
    )
