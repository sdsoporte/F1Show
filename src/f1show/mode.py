"""The two declared per-turn commentary modes: build and climax (F09g U2).

**What the design asks for.** Live commentary has two prosodic modes, not one: a style
that *builds suspense* and a style that *presents a climax* (the prosody research the
registered design cites), and the design's own rule is that a routine lap is **build**
(one line of context) while a position change of two or more places, a flag or a pit stop
is **climax** (short and emphatic). This module decides that mode for one turn and renders
it as **instruction text** for the prompt. The mode is never evidence: it adds no citable
reference and no bracket, so it cannot move the acceptance that only the current event's
supplied references may air.

**The decision is pure.** :func:`turn_mode` reads no file, opens no store, reads no clock
and draws no random number: a mode is a function of the detected events up to and
including the current one, so equal sequences always yield an equal mode. It is called
with that prefix, exactly as :func:`f1show.salience.salience_summary` is.

**Positions, measured the same way U1 measured them.** ``position.json`` carries no
``lap_number``, so a driver's change cannot be read per lap. The mode therefore compares
the driver's **previous observed position** in the window with the position the current
event carries, and it uses the same window boundary U1 declared: the window begins at the
**first ``LAP_COMPLETED`` event**, so a pre-race grid snapshot is not a prior observation.
A change of ``CLIMAX_POSITION_DELTA`` (two) places or more, in either direction, is
climax; a driver whose first observation inside the window is the current event, or whose
driver number or position cannot be resolved, has no measured change and is build.

**The trigger is the step at this event, not U1's window measure - declared because the
reading drifts.** ``position.json`` supports two quantities and they are not
interchangeable: the **current step** (this event's position against the driver's previous
observed position, which is what this module uses) and U1's **cumulative**
first-observed-versus-latest ``PositionMove.change`` (which the CONTEXT block carries). A
climax is about the **moment** - the design's own framing is that *a magic moment must look
epic* - so the trigger measures what happened *at this event*, not how far a driver has
travelled since the window opened. Measured on the recorded session's 1,648 turns, the
single-step basis makes **46** turns climax and **1,602** build, broken down as **23 pit
stops**, **9 caution rows** and **14 position steps of two or more places**; the cumulative
reading would make **271** turns climax, which would turn the exception into a fifth of the
session. A driver whose cumulative change is two places but whose current step is one is
therefore **build**, and that case is pinned by test so the two readings cannot silently
swap places.

**The caution list is declared from measurement, not intuition.** The recorded
``race_control`` fixture holds **120** rows for session 9617, and their ``flag`` values
with counts are: ``None`` 78, ``BLUE`` 20, ``CLEAR`` 7, ``BLACK AND WHITE`` 5, ``YELLOW``
4, ``DOUBLE YELLOW`` 3, ``GREEN`` 2 and ``CHEQUERED`` 1. A race-control row **announces or
escalates a caution** - and so is climax - when it carries one of these:

* ``YELLOW`` (4 rows) - a caution starts; the recorded messages are ``YELLOW IN TRACK
  SECTOR 19`` and ``YELLOW IN TRACK SECTOR 3``;
* ``DOUBLE YELLOW`` (3 rows) - the caution escalates; the recorded messages are ``DOUBLE
  YELLOW IN TRACK SECTOR 19`` and ``DOUBLE YELLOW IN TRACK SECTOR 3``;
* ``category == "SafetyCar"`` (2 rows, ``flag`` is ``None``) - the caution escalates to the
  safety car; the recorded messages are ``SAFETY CAR DEPLOYED`` and ``SAFETY CAR IN THIS
  LAP``.

Every other recorded shape is **not** a caution and stays build: ``CLEAR`` (7 rows) clears
a caution; ``GREEN`` (2 rows) opens the pit exit; ``BLUE`` (20 rows) warns one driver about
lapped traffic; ``BLACK AND WHITE`` (5 rows) is a sporting warning; ``CHEQUERED`` (1 row)
ends the session; and the 76 remaining flag-less rows are DRS notices, deleted lap times,
stewards' decisions and similar - none of them a caution. That is **9 climax race-control
rows and 111 build rows** out of 120.

**The dead priority band, and this module's fix.** ``booth.PRIORITY_EVENT_TYPES`` was
``{FLAG, SAFETY_CAR, VIRTUAL_SAFETY_CAR}``, but the collector emits ``RACE_CONTROL`` for
**every** race-control record, so that band matched **no recorded event** and the seat
order on the corpus was plain alternation. The band now consults :func:`announces_caution`,
the same derived signal the mode uses, so a recorded flag or safety-car row is a priority
event. Measured on the recorded session (1,648 detected events, the 9 caution rows above),
consulting the signal changes the seat of **1,023** of the 1,648 aired turns (62%) against
the previous strict alternation. The number is large for a reason the source states
plainly: a band event hands the lead the next slot **unconditionally**, and the
non-priority seat follows the last turn that actually aired, so a forced lead **flips the
alternation phase for every later turn until the next band event**. Measured, not assumed:
of the nine recorded caution rows **six** land where the alternation would not already have
given the lead the turn, and the seat offset from strict alternation is therefore 1 for
1,023 turns (the three that coincide change nothing, and the six flips make the offset
piecewise constant, changing only at a band event). Only the seat changes: the turn count,
order, text and evidence are untouched, which is why this is the seat band and not a
transcript-shape change.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from f1show.collector import DetectedEvent
from f1show.events import EventType

__all__ = [
    "CAUTION_CATEGORIES",
    "CAUTION_EVENT_TYPES",
    "CAUTION_FLAGS",
    "CAUTION_MESSAGES",
    "CLIMAX_POSITION_DELTA",
    "TurnMode",
    "announces_caution",
    "render_mode_instruction",
    "turn_mode",
]

#: The incident event types this project declares as cautions. The collector never emits
#: them today (it emits ``RACE_CONTROL`` for every race-control record), so they are the
#: declared subset of the band; the recorded corpus reaches the band through the derived
#: signal below. ``booth.PRIORITY_EVENT_TYPES`` is this same set.
CAUTION_EVENT_TYPES: frozenset[EventType] = frozenset(
    {EventType.FLAG, EventType.SAFETY_CAR, EventType.VIRTUAL_SAFETY_CAR}
)

#: A recorded flag value that announces or escalates a caution. Measured on the corpus:
#: ``YELLOW`` 4 rows, ``DOUBLE YELLOW`` 3 rows.
CAUTION_FLAGS: frozenset[str] = frozenset({"YELLOW", "DOUBLE YELLOW"})

#: A recorded category that carries a caution with a null ``flag``. Measured on the corpus:
#: ``SafetyCar`` 2 rows (``SAFETY CAR DEPLOYED`` and ``SAFETY CAR IN THIS LAP``).
CAUTION_CATEGORIES: frozenset[str] = frozenset({"SafetyCar"})

#: The recorded safety-car messages, as a fallback when the category is missing. These are
#: the two messages the corpus carries under ``category == "SafetyCar"``.
CAUTION_MESSAGES: frozenset[str] = frozenset(
    {"SAFETY CAR DEPLOYED", "SAFETY CAR IN THIS LAP"}
)

#: How many places a driver must move, against their previous observed position, for the
#: turn to be a climax. Declared, not derived.
CLIMAX_POSITION_DELTA = 2


class TurnMode(str, Enum):
    """The prosody of one turn: a routine lap, or a moment of change."""

    BUILD = "build"
    CLIMAX = "climax"


#: The declared instruction text for each mode: a ``MODE:`` line plus one sentence of what
#: it asks for. Plain prose - no bracket, no reference-shaped token - so it stays
#: instruction text and can never make a new token citable.
_MODE_INSTRUCTIONS: dict[TurnMode, str] = {
    TurnMode.BUILD: (
        "MODE: build\nThis is a routine lap: one line of context, nothing more."
    ),
    TurnMode.CLIMAX: (
        "MODE: climax\nThis is a moment of change: keep it short and emphatic."
    ),
}


def _as_int(value: object) -> int | None:
    """Return ``value`` when it is a real integer, otherwise an explicit unknown."""
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _as_text(value: object) -> str | None:
    """Return a non-blank string, otherwise an explicit unknown."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def announces_caution(event: DetectedEvent) -> bool:
    """Whether this event is a race-control row that announces or escalates a caution.

    Pure: it reads only the event's own type and recorded evidence. The declared incident
    event types are cautions by their own name; a ``RACE_CONTROL`` row is a caution when it
    carries a caution ``flag``, a ``SafetyCar`` category, or one of the recorded safety-car
    messages. A caution **clearing** (``CLEAR``), a green flag, a blue flag, a black-and-white
    warning, the chequered flag and every other flag-less row are **not** cautions.
    """
    if event.event_type in CAUTION_EVENT_TYPES:
        return True
    if event.event_type is not EventType.RACE_CONTROL:
        return False
    flag = _as_text(event.evidence.get("flag"))
    if flag is not None and flag.upper() in CAUTION_FLAGS:
        return True
    category = _as_text(event.evidence.get("category"))
    if category is not None and category in CAUTION_CATEGORIES:
        return True
    message = _as_text(event.evidence.get("message"))
    return message is not None and message.upper() in CAUTION_MESSAGES


def turn_mode(events: Sequence[DetectedEvent]) -> TurnMode:
    """Decide the mode of the current event: ``events`` is its prefix, current event last.

    Pure and deterministic. The current event is a climax when it is a pit stop, when it
    announces or escalates a caution, or when it is a position change of
    ``CLIMAX_POSITION_DELTA`` or more places against that driver's previous observed
    position inside U1's window. A prefix with no events is build.
    """
    if not events:
        return TurnMode.BUILD
    event = events[-1]
    if event.event_type is EventType.PIT_STOP:
        return TurnMode.CLIMAX
    if announces_caution(event):
        return TurnMode.CLIMAX
    if event.event_type is EventType.POSITION_CHANGE and _changed_two_or_more(events):
        return TurnMode.CLIMAX
    return TurnMode.BUILD


def render_mode_instruction(mode: TurnMode) -> str:
    """Render one mode as the prompt's declared instruction text."""
    return _MODE_INSTRUCTIONS[mode]


def _changed_two_or_more(events: Sequence[DetectedEvent]) -> bool:
    """Whether the current position event moved its driver by two or more places."""
    current = events[-1]
    number = current.driver_number
    position = _as_int(current.evidence.get("position"))
    if number is None or position is None:
        return False
    previous = _previous_position(events, number)
    return previous is not None and abs(position - previous) >= CLIMAX_POSITION_DELTA


def _previous_position(
    events: Sequence[DetectedEvent], driver_number: int
) -> int | None:
    """The driver's latest observed position inside the window before the current event.

    The window begins at the first completed lap, exactly as U1's does, so the pre-race
    grid snapshot is not a previous observation. ``None`` means no observation inside the
    window, which is an explicit unknown rather than an invented zero.
    """
    start = _window_start(events)
    previous: int | None = None
    for event in events[start:-1]:
        if (
            event.event_type is EventType.POSITION_CHANGE
            and event.driver_number == driver_number
        ):
            position = _as_int(event.evidence.get("position"))
            if position is not None:
                previous = position
    return previous


def _window_start(events: Sequence[DetectedEvent]) -> int:
    """The index of the window's first event: the first completed lap, or the end."""
    for index, event in enumerate(events):
        if event.event_type is EventType.LAP_COMPLETED:
            return index
    return len(events)
