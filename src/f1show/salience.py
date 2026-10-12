"""The window's salience projection: what the race so far is actually about (F09g U1).

This module is **pure**. It reads no file, opens no store, reads no clock and draws no
random number: a summary is a function of the sequence of detected events it is handed, so
the same events always produce an equal summary. It is what lets the colour seat answer
*why* - who is gaining, who is losing, who stopped, which sector is flagged, who set the
fastest lap - instead of reciting one event's telemetry at a time.

**The window, and why it starts where it does.** The projection is a function of the
sequence of events up to and including the current event, and the **window** is the part of
that sequence from the race start onward: it begins at the **first ``LAP_COMPLETED``
event** and runs to the current event. The recorded corpus opens with a pre-race grid
snapshot (Austin 2024: twenty position rows at ``18:06:48``, more than an hour before the
lights), and lap 1's rows are emitted at the session-start instant. Including the grid is
not a detail: measured both ways over the recorded session's start-to-lap-5 window, the
whole-prefix reading gives Ocon 12 to 18 (**+6**) and Zhou 18 to 14, while the race-window
reading gives Zhou 19 to 14 (**-5**), Alonso 5 to 10 and Ocon 13 to 18 (**+5** each) - the
design's measured table. The window therefore starts at the race, and a prefix that holds
no completed lap has **no window and no story**, which is stated rather than invented from
the grid.

**The salience rule, declared here so it is not inherited.** A driver or moment is salient
by **magnitude of position change**, **involvement in a flagged sector or a race-control
message**, **a pit stop** and **a lap-time outlier either way**. The rule deliberately
**excludes nationality, team affiliation and championship standing**, which this projection
does not read.

**Positions, measured as the design measured them.** ``position.json`` carries no
``lap_number``, so a driver's change is the difference between their **first observed**
position inside the window and their latest one at the current event, and the biggest gain
and the biggest loss are the extremes of that signed difference with **every tie reported**
(the recorded window's biggest loss is a two-way tie). A driver whose position does not
move is in neither extreme. The **busiest** driver is the one with the most
``POSITION_CHANGE`` events in the window; a tied count is broken by the **earliest first
observation**, then by driver number. That counting is declared and its alternative is
measured and disclosed: the recorded window's busiest has 13 recorded position updates and
12 adjacent transitions, and the design's ``13 position changes`` matches the former, so
the count is of recorded updates. Every metric is window-local; no pre-window reading is
used.

**Pit stops and flags.** A pit reading carries the three recorded durations
(``pit_duration``, ``lane_duration``, ``stop_duration``) with explicit ``None`` where the
record has none. A **flag** is a race-control row whose ``flag`` field is a non-empty
string; rows that carry only a category and a message (``SAFETY CAR DEPLOYED``, ``DRS
ENABLED``) are not flags, and a flag reading carries its sector when the record has one and
an explicit ``None`` when it does not.

**The lap-time story, including a derived fastest lap.** No ``fastest*`` field exists
anywhere in the corpus, so the fastest lap is **derived** as the minimum ``lap_duration``
among laps with ``lap_number >= 2``: lap 1 is a standing start and never a time comparison,
and a null or non-numeric duration is skipped rather than coerced. The **declared outlier
rule** is one sentence: *a lap is a fast outlier when its duration is below 0.75 times the
median duration of the window's valid laps, and a slow outlier when it is above 1.25 times
that median; a duration exactly on a fence is inside it.* The multiplier is declared rather
than derived, and the rule is applied to the report only - it never filters the fastest-lap
derivation.

**What that rule measures on the design's window, and what it cannot express.** An earlier
draft of this docstring claimed the median was chosen rather than the mean "so a safety-car
period cannot drag it". That claim was measured on the very window this module is anchored
to and it is **false**. Over the window's **76** valid laps the median is **141.1955 s**,
while lap 2 ran at about **102 s** (99.923 s to 104.544 s): the safety-car period covers
laps 3 to 5, and all **57** of the laps after lap 2 sit between **122.849 s and 168.785 s**,
so they carry the median up with them. The fences therefore land at **105.896625 s** (fast) and
**176.494375 s** (slow), and this window classifies **19** fast outliers - every lap-2 time -
and **0** slow outliers, even though the design's own narrative is lap 5 dropping to 166 s
to 168 s. **The rule as written cannot express a safety-car period as slow outliers**,
because the safety-car laps are the bulk of this window and so define its own centre. That
is a declared **limitation, not a fix**: expressing a safety-car period would need a
different declared baseline (a per-driver or green-flag reference, say), which is a later
unit's decision rather than a silent repair here.

**The rendered block is plain prose and structurally uncitable.** :func:`render_salience`
renders the summary with driver names joined from the session directory, and it **removes
every bracket character** (``[](){}``) from any recorded text it interpolates, so a hostile
message cannot smuggle a ``family[index].field``-shaped token into the prompt. That is
deliberate: the prompt's reference net is the guarantee that nothing new becomes citable,
and the CONTEXT block refuses the characters that net is built from rather than trusting
that no recorded message happens to carry one.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from f1show.collector import DetectedEvent
from f1show.events import EventType

__all__ = [
    "FAST_OUTLIER_FACTOR",
    "MAX_OUTLIERS_RENDERED",
    "SLOW_OUTLIER_FACTOR",
    "FlagReading",
    "LapReading",
    "PitReading",
    "PositionMove",
    "SalienceSummary",
    "render_salience",
    "salience_summary",
]

#: The declared fast fence: a lap below ``FAST_OUTLIER_FACTOR`` times the window's median
#: valid duration is a fast outlier. Declared, not derived.
FAST_OUTLIER_FACTOR = 0.75

#: The declared slow fence: a lap above ``SLOW_OUTLIER_FACTOR`` times the window's median
#: valid duration is a slow outlier. Declared, not derived.
SLOW_OUTLIER_FACTOR = 1.25

#: How many outliers of one direction the rendered block lists before it counts the rest.
#: The summary itself is never truncated; only the prose is bounded.
MAX_OUTLIERS_RENDERED = 3

#: Every bracket character, refused in the rendered block.
_BRACKETS = frozenset("[](){}")

#: What the block states when the window holds no story. Explicit absence, never invention.
_EMPTY_CONTEXT = (
    "CONTEXT - the race story so far: the window holds no story yet, because no completed "
    "lap and no race datum have been observed."
)


class _Value(BaseModel):
    """One internal value: strict and frozen, like every other record in this project."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PositionMove(_Value):
    """One driver's position movement inside the window.

    ``change`` is ``last_position - first_position``, so a **negative** change is a gain:
    the driver's position number got smaller because they moved up the order.
    """

    driver_number: int
    first_position: int
    last_position: int
    change: int


class PitReading(_Value):
    """One pit stop, with each recorded duration kept separate and honest.

    ``pit_duration``, ``lane_duration`` and ``stop_duration`` are three different recorded
    measurements; a missing one stays ``None`` and is never borrowed from another.
    """

    driver_number: int | None
    lap_number: int | None
    pit_duration: float | None
    lane_duration: float | None
    stop_duration: float | None


class FlagReading(_Value):
    """One race-control flag, with its sector only when the record has one."""

    flag: str
    sector: int | None
    message: str | None
    lap_number: int | None


class LapReading(_Value):
    """One valid lap time: ``lap_number >= 2`` and a finite numeric duration."""

    driver_number: int | None
    lap_number: int
    duration_seconds: float


class SalienceSummary(_Value):
    """One small, immutable statement of what the window is about."""

    event_count: int
    latest_lap: int | None
    biggest_gains: tuple[PositionMove, ...]
    biggest_losses: tuple[PositionMove, ...]
    busiest_driver: int | None
    busiest_changes: int
    pit_stops: tuple[PitReading, ...]
    flags: tuple[FlagReading, ...]
    fastest_lap: LapReading | None
    lap_median: float | None
    fast_outliers: tuple[LapReading, ...]
    slow_outliers: tuple[LapReading, ...]

    @property
    def is_empty(self) -> bool:
        """Whether the window holds no story at all, stated rather than invented."""
        return not (
            self.biggest_gains
            or self.biggest_losses
            or self.busiest_driver is not None
            or self.pit_stops
            or self.flags
            or self.fastest_lap is not None
            or self.fast_outliers
            or self.slow_outliers
        )


def _as_int(value: object) -> int | None:
    """Return ``value`` when it is a real integer, otherwise an explicit unknown."""
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _as_number(value: object) -> float | None:
    """Return ``value`` as a finite number, refusing ``bool`` and every non-number.

    A value too large to represent as a float (a corrupt payload can carry a Python ``int``
    of arbitrary width) is an explicit unknown rather than an ``OverflowError`` that aborts
    the whole projection, mirroring :func:`f1show.collector.classify_gap`.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _as_text(value: object) -> str | None:
    """Return a non-blank string, otherwise an explicit unknown."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def salience_summary(events: Sequence[DetectedEvent]) -> SalienceSummary:
    """Project the window of ``events`` into one immutable summary.

    ``events`` is the sequence of detected events **up to and including the current
    event**; the window is its tail from the first completed lap onward. The function is
    pure: no file, no clock, no random source, so equal sequences always yield an equal
    summary. A window with no story returns an explicitly empty summary.
    """
    start = _window_start(events)
    return _project(events, start)


def _window_start(events: Sequence[DetectedEvent]) -> int:
    """The index of the window's first event: the first completed lap, or the end.

    Returning ``len(events)`` for a prefix with no completed lap is what makes a pre-race
    prefix an empty window with no story, rather than one measured from the grid.
    """
    for index, event in enumerate(events):
        if event.event_type is EventType.LAP_COMPLETED:
            return index
    return len(events)


def _project(events: Sequence[DetectedEvent], start: int) -> SalienceSummary:
    """Walk the window once and build the summary."""
    first_position: dict[int, int] = {}
    last_position: dict[int, int] = {}
    first_seen: dict[int, int] = {}
    changes: dict[int, int] = {}
    pit_stops: list[PitReading] = []
    flags: list[FlagReading] = []
    laps: list[LapReading] = []
    latest_lap: int | None = None
    for index in range(start, len(events)):
        event = events[index]
        kind = event.event_type
        if kind is EventType.POSITION_CHANGE:
            number = event.driver_number
            position = _as_int(event.evidence.get("position"))
            if number is None or position is None:
                continue
            if number not in first_seen:
                first_seen[number] = index
                first_position[number] = position
            last_position[number] = position
            changes[number] = changes.get(number, 0) + 1
        elif kind is EventType.PIT_STOP:
            pit_stops.append(
                PitReading(
                    driver_number=event.driver_number,
                    lap_number=_as_int(event.evidence.get("lap_number")),
                    pit_duration=_as_number(event.evidence.get("pit_duration")),
                    lane_duration=_as_number(event.evidence.get("lane_duration")),
                    stop_duration=_as_number(event.evidence.get("stop_duration")),
                )
            )
        elif kind is EventType.RACE_CONTROL:
            flag = _as_text(event.evidence.get("flag"))
            if flag is None:
                continue
            flags.append(
                FlagReading(
                    flag=flag,
                    sector=_as_int(event.evidence.get("sector")),
                    message=_as_text(event.evidence.get("message")),
                    lap_number=_as_int(event.evidence.get("lap_number")),
                )
            )
        elif kind is EventType.LAP_COMPLETED:
            lap_number = _as_int(event.evidence.get("lap_number"))
            if lap_number is None:
                continue
            latest_lap = (
                lap_number if latest_lap is None else max(latest_lap, lap_number)
            )
            duration = _as_number(event.evidence.get("lap_duration"))
            if lap_number >= 2 and duration is not None:
                laps.append(
                    LapReading(
                        driver_number=event.driver_number,
                        lap_number=lap_number,
                        duration_seconds=duration,
                    )
                )
    moves = [
        PositionMove(
            driver_number=number,
            first_position=first_position[number],
            last_position=last_position[number],
            change=last_position[number] - first_position[number],
        )
        for number in first_position
    ]
    order = _first_observation_order(first_seen)
    biggest_gains = _extremes(
        [move for move in moves if move.change < 0], pick=min, order=order
    )
    biggest_losses = _extremes(
        [move for move in moves if move.change > 0], pick=max, order=order
    )
    busiest_driver, busiest_changes = _busiest(changes, first_seen)
    fastest_lap, lap_median, fast_outliers, slow_outliers = _lap_story(laps)
    return SalienceSummary(
        event_count=max(0, len(events) - start),
        latest_lap=latest_lap,
        biggest_gains=biggest_gains,
        biggest_losses=biggest_losses,
        busiest_driver=busiest_driver,
        busiest_changes=busiest_changes,
        pit_stops=tuple(pit_stops),
        flags=tuple(flags),
        fastest_lap=fastest_lap,
        lap_median=lap_median,
        fast_outliers=fast_outliers,
        slow_outliers=slow_outliers,
    )


def _first_observation_order(
    first_seen: Mapping[int, int],
) -> Callable[[PositionMove], tuple[int, int]]:
    """A total ordering of moves by first observation, then by driver number."""

    def order(move: PositionMove) -> tuple[int, int]:
        return (first_seen[move.driver_number], move.driver_number)

    return order


def _extremes(
    moves: Sequence[PositionMove],
    *,
    pick: Callable[[Iterable[int]], int],
    order: Callable[[PositionMove], tuple[int, int]],
) -> tuple[PositionMove, ...]:
    """Every tied extreme, in first-observation order; empty when nothing moved that way."""
    if not moves:
        return ()
    extreme = pick(move.change for move in moves)
    return tuple(sorted((move for move in moves if move.change == extreme), key=order))


def _busiest(
    changes: Mapping[int, int], first_seen: Mapping[int, int]
) -> tuple[int | None, int]:
    """The driver with the most recorded position changes, tied by first observation."""
    if not changes:
        return None, 0
    top = max(changes.values())
    winner = min(
        (number for number, count in changes.items() if count == top),
        key=lambda number: (first_seen[number], number),
    )
    return winner, top


def _lap_order(lap: LapReading) -> tuple[float, int, int]:
    """A total order over laps, so equal durations never resolve by input order."""
    return (
        lap.duration_seconds,
        lap.lap_number,
        -1 if lap.driver_number is None else lap.driver_number,
    )


def _lap_story(
    laps: Sequence[LapReading],
) -> tuple[
    LapReading | None, float | None, tuple[LapReading, ...], tuple[LapReading, ...]
]:
    """Derive the fastest lap and split the valid laps across the two declared fences."""
    if not laps:
        return None, None, (), ()
    fastest = min(laps, key=_lap_order)
    median = statistics.median([lap.duration_seconds for lap in laps])
    fast = tuple(
        sorted(
            (
                lap
                for lap in laps
                if lap.duration_seconds < FAST_OUTLIER_FACTOR * median
            ),
            key=_lap_order,
        )
    )
    slow = tuple(
        sorted(
            (
                lap
                for lap in laps
                if lap.duration_seconds > SLOW_OUTLIER_FACTOR * median
            ),
            key=lambda lap: (
                -lap.duration_seconds,
                lap.lap_number,
                -1 if lap.driver_number is None else lap.driver_number,
            ),
        )
    )
    return fastest, median, fast, slow


def render_salience(
    summary: SalienceSummary,
    driver_directory: Mapping[int, tuple[str, str]],
) -> str:
    """Render one summary as the CONTEXT block: plain prose, no bracket, no reference.

    Driver names and teams are joined from the session directory; a driver the directory
    cannot resolve renders ``driver <number>`` rather than a half-join. Every recorded
    string interpolated here is stripped of bracket characters, so the block can never
    carry a ``family[index].field``-shaped token.
    """
    if summary.is_empty:
        return _EMPTY_CONTEXT
    window = (
        f"{summary.event_count} events through lap {summary.latest_lap}"
        if summary.latest_lap is not None
        else f"{summary.event_count} events"
    )
    lines = [f"CONTEXT - the race story so far, {window}:"]
    if summary.biggest_gains:
        lines.append(
            _move_line("gain", "gains", summary.biggest_gains, driver_directory)
        )
    if summary.biggest_losses:
        lines.append(
            _move_line("loss", "losses", summary.biggest_losses, driver_directory)
        )
    if summary.busiest_driver is not None:
        label = _label(summary.busiest_driver, driver_directory)
        plural = "change" if summary.busiest_changes == 1 else "changes"
        lines.append(f"- busiest: {label}, {summary.busiest_changes} position {plural}")
    if summary.pit_stops:
        lines.append(
            "- pit stops: "
            + "; ".join(_pit_phrase(pit, driver_directory) for pit in summary.pit_stops)
        )
    else:
        lines.append("- pit stops: none in the window")
    if summary.flags:
        lines.append(
            "- race control: " + "; ".join(_flag_phrase(f) for f in summary.flags)
        )
    else:
        lines.append("- race control: no flags in the window")
    if summary.fastest_lap is not None:
        lines.append(
            f"- fastest lap: {_lap_phrase(summary.fastest_lap, driver_directory)}"
        )
    else:
        lines.append("- fastest lap: none in the window")
    if summary.lap_median is not None:
        lines.append(
            "- lap-time fence: median "
            f"{_seconds(summary.lap_median)} seconds; slow above "
            f"{_seconds(SLOW_OUTLIER_FACTOR * summary.lap_median)} seconds and fast below "
            f"{_seconds(FAST_OUTLIER_FACTOR * summary.lap_median)} seconds"
        )
    lines.append(
        "- fast laps below the declared fence: "
        + _outliers_phrase(summary.fast_outliers, driver_directory)
    )
    lines.append(
        "- slow laps above the declared fence: "
        + _outliers_phrase(summary.slow_outliers, driver_directory)
    )
    return "\n".join(lines)


def _move_line(
    singular: str,
    plural: str,
    moves: Sequence[PositionMove],
    directory: Mapping[int, tuple[str, str]],
) -> str:
    heading = singular if len(moves) == 1 else plural
    return f"- biggest {heading}: " + "; ".join(
        _move_phrase(move, directory) for move in moves
    )


def _move_phrase(move: PositionMove, directory: Mapping[int, tuple[str, str]]) -> str:
    label = _label(move.driver_number, directory)
    if move.change < 0:
        places = "place" if move.change == -1 else "places"
        return (
            f"{label}, from P{move.first_position} to P{move.last_position}, "
            f"up {-move.change} {places}"
        )
    places = "place" if move.change == 1 else "places"
    return (
        f"{label}, from P{move.first_position} to P{move.last_position}, "
        f"down {move.change} {places}"
    )


def _pit_phrase(pit: PitReading, directory: Mapping[int, tuple[str, str]]) -> str:
    label = (
        "an unidentified car"
        if pit.driver_number is None
        else _label(pit.driver_number, directory)
    )
    lap = f"lap {pit.lap_number}" if pit.lap_number is not None else "lap unknown"
    phrase = f"{label}, {lap}"
    pit_lane = pit.pit_duration if pit.pit_duration is not None else pit.lane_duration
    if pit_lane is not None:
        phrase += f", {_seconds(pit_lane)} seconds in the pit lane"
    if pit.stop_duration is not None:
        phrase += f", {_seconds(pit.stop_duration)} seconds stationary"
    return phrase


def _flag_phrase(flag: FlagReading) -> str:
    phrase = _clean(flag.flag)
    if flag.sector is not None:
        phrase += f", sector {flag.sector}"
    if flag.message is not None:
        phrase += f", {_clean(flag.message)}"
    return phrase


def _lap_phrase(lap: LapReading, directory: Mapping[int, tuple[str, str]]) -> str:
    label = (
        "an unidentified car"
        if lap.driver_number is None
        else _label(lap.driver_number, directory)
    )
    return f"{label}, lap {lap.lap_number}, {_seconds(lap.duration_seconds)} seconds"


def _outliers_phrase(
    laps: Sequence[LapReading], directory: Mapping[int, tuple[str, str]]
) -> str:
    if not laps:
        return "none"
    shown = laps[:MAX_OUTLIERS_RENDERED]
    text = "; ".join(_lap_phrase(lap, directory) for lap in shown)
    hidden = len(laps) - len(shown)
    if hidden:
        text += f"; and {hidden} more"
    noun = "lap" if len(laps) == 1 else "laps"
    return f"{len(laps)} {noun}: {text}"


def _label(number: int, directory: Mapping[int, tuple[str, str]]) -> str:
    """The driver's joined identity, or the one declared fallback for an unknown number."""
    identity = directory.get(number)
    if identity is None:
        return f"driver {number}"
    full_name, team_name = identity
    cleaned_name = _clean(full_name)
    cleaned_team = _clean(team_name)
    if not cleaned_name:
        return f"driver {number}"
    if not cleaned_team:
        return cleaned_name
    return f"{cleaned_name}, {cleaned_team}"


def _clean(text: str) -> str:
    """Strip every bracket character and collapse whitespace, so no token can survive."""
    without_brackets = "".join(
        " " if character in _BRACKETS else character for character in text
    )
    return " ".join(without_brackets.split())


def _seconds(value: float) -> str:
    """A declared rendering of a duration: at most three decimals, trailing zeros cut."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"
