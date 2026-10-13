"""The bounded championship context of one moment (F09g U3b).

**What the design asks for.** The championship picture of a race weekend reaches the booth
so the colour seat can answer *what is at stake* rather than only what happened. The
recorded corpus carries it as 53 rows over three families - ``championship_drivers`` (23),
``championship_teams`` (10) and ``session_result`` (20) - and the first two carry **both
checkpoints in one row**: ``position_start``/``points_start`` before the session and
``position_current``/``points_current`` after it. There is no in-race table anywhere in the
source, so an **in-race provisional** picture must be **derived**. This module derives a
**bounded** one for a single moment: the current driver's provisional season position,
points and gap to the leader, and their team's provisional position and points. It
deliberately carries no full table and no per-driver list, because the prompt block it
feeds is context, not evidence.

**Pure by construction.** It reads no file, opens no store, reads no clock and draws no
random number, so a context is a function of its inputs alone and equal inputs always give
an equal context. Inputs are read, never mutated. It adds no citable reference, no bracket
and no airing shape: everything it produces is prose for one prompt block.

The driver derivation, under the reviewed rules
-----------------------------------------------

:func:`f1show.standings.provisional_table` is the reviewed derivation this module wires,
not a second implementation of it. The module reads the current **running order** off the
event prefix using the same window boundary U1 and U2 declared - the window begins at the
first ``LAP_COMPLETED`` event, so the pre-race grid snapshot is not an in-race position -
takes each driver's **latest observed position** inside that window, and orders the field
first to last. The order's index **is** the driver's current race position, so each runner
scores the declared per-season points for it: the source's own start checkpoint plus this
race's points so far. The fastest-lap point is deliberately **not** applied, because it is
not knowable before the race ends and the salience projection's derived fastest lap is a
window artefact rather than a declared holder; the omission is stated rather than implied.

**Two limits are inherited and disclosed, not re-litigated here.** The declared tie rule
(equal points, then ``driver_number`` ascending) does not reproduce the source's own order
within a points tie; U3a measured 8 rows of disagreement and 2 under the alternative
candidate, so the recorded provisional position can differ from ``position_current`` inside
a tie group. And with every lap complete the provisional table equals the after table,
which proves our arithmetic and nothing about the source's real in-race values.

**A position inside a tie is a convention, so the block never presents it as settled.**
Eight of the 23 recorded drivers' derived provisional positions disagree with the source's
``position_current``, and every one sits inside a points tie - ``{3, 23}`` at 12,
``{10, 20}`` at 8, ``{31, 43}`` at 5 and ``{2, 24, 77}`` at 0 - because the declared tie
rule orders equal points by ``driver_number`` and the source does not. The final recorded
event is one of them: its own driver, 31, is derived P18 while the source's
``position_current`` says P19, and only the order inside the tie differs. The arithmetic is
right and the order is arbitrary, so :func:`render_championship` states a tied position as
tied (``P18 on 5 points, tied with 1 other driver``) and leaves a lone holder's bare position
byte for byte. **The team line is treated the same way, because teams can share a total**:
the recorded pre-race rows alone tie Haas F1 Team and RB on 34, and this module's team order
is itself a declared convention (points descending, then the source's own ``position_start``,
then ``team_name``). The tie counts are rendered, never used: no points total, gap, leader,
team total or derived position moves.

The team derivation, and the U3a impossibility it spends
---------------------------------------------------------

**A season team table cannot be derived from the driver rows, and this module records the
two measured reasons rather than re-attempting it.** ``standings.py`` measured both on the
recorded session: (1) the recorded ``drivers`` family is the session's **entry list**, so
it is **session-scoped** - a driver who did not start this race is unmapped however many
season points they hold, which is exactly the 19 points of drivers 3, 50 and 2; and (2) the
driver table carries **one team per driver per session**, so a season scored across two
teams cannot be expressed at all. The per-team disagreement measured there (Ferrari 6, Haas
1, RB 12) is a property of the source, not of a join.

So the **season team total comes from the source's own ``championship_teams`` row**, and
only **this race's delta** is derived: each running position's declared race points are
attributed to that driver's **entry-list team**, and only drivers the session actually
**classifies** (a ``session_result`` row with a non-null position) contribute. The
classification is the source's own statement of who scored this race; a driver with no
result row therefore contributes nothing to any team's delta, which is the same identity
``standings.py`` measured for the three row-less drivers. Measured on the recorded session
at its final moment, this closes exactly: for **all ten** teams the source's own
``points_start`` plus the derived delta equals the source's own ``points_current``, and the
derived position equals ``position_current``. The team order is points descending, then the
source's own ``position_start`` ascending, then ``team_name`` - the source's own pre-race
order is the declared tie-break, so a zero delta before the race reproduces the source.

**The delta is measured against the running order, so the picture is provisional.** Before
any in-race position has been observed the running order is empty, no race points have been
awarded, and the module reports the source's own **pre-race** row rather than inventing a
derivation from the grid. This is the moment the design's own caution applies to.

The four cases the moment can present, handled explicitly
---------------------------------------------------------

* **A driver with no ``championship_drivers`` row.** Their position and points are
  ``None``; the leader is still reported when the rows can carry one. If such a driver is
  inside the running order, the whole derived table is withheld, because one unknown runner
  makes every later position wrong - a partial table would be a silent lie.
* **A driver with no ``session_result`` row.** ``driver_classified`` is ``False`` and their
  race points are not attributed to their team's delta; their own provisional line is still
  reported, because the running order placed them.
* **An unresolvable team.** A driver absent from the entry list, or a team absent from the
  ``championship_teams`` rows, leaves the team fields ``None``: the module reports what it
  cannot resolve instead of a half-join.
* **A moment before any completed lap.** The running order is empty and the reported
  picture is the source's own pre-race one.

Every one of those dispositions is carried in :attr:`ChampionshipContext.unavailable`, a
declared and sorted set, so a caller and its tests read the same explicit statement the
prose block renders.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from f1show.collector import DetectedEvent
from f1show.events import EventType
from f1show.standings import (
    StartStanding,
    points_for_position,
    provisional_table,
)

__all__ = [
    "RECORDED_SEASON",
    "ChampionshipContext",
    "ChampionshipDriverRow",
    "ChampionshipSource",
    "ChampionshipUnavailable",
    "RaceClassification",
    "TeamStanding",
    "build_championship_source",
    "championship_context",
    "render_championship",
]

#: The recorded corpus's season. The three championship families carry no year field - only
#: ``meeting_key`` 1247 and ``session_key`` 9617 - the scope guard refuses ``sessions.json``,
#: and the declared points dataset is per-season, so the season is a **declared** input
#: rather than a derived one. The recorded session is the 2024 United States Grand Prix
#: (``fixtures/openf1/PROVENANCE.md``), so that is the declared value the run path passes.
RECORDED_SEASON = 2024


class ChampionshipUnavailable(str, Enum):
    """A declared reason a bounded championship field could not be stated.

    ``NO_RUNNING_ORDER`` is the pre-race picture: no in-race position has been observed
    yet, so the values shown are the source's own start rows and no race delta exists.
    ``NO_CHAMPIONSHIP_ROW`` is a driver the ``championship_drivers`` rows do not carry.
    ``UNRESOLVABLE_TEAM`` is a driver whose entry-list team, or whose team's
    ``championship_teams`` row, cannot be found.
    """

    NO_RUNNING_ORDER = "no_running_order"
    NO_CHAMPIONSHIP_ROW = "no_championship_row"
    UNRESOLVABLE_TEAM = "unresolvable_team"


@dataclass(frozen=True)
class ChampionshipDriverRow:
    """One ``championship_drivers`` start checkpoint, the source's own before-the-session row."""

    driver_number: int
    position_start: int
    points_start: float


@dataclass(frozen=True)
class TeamStanding:
    """One ``championship_teams`` start checkpoint, the source's own before-the-session row."""

    team_name: str
    position_start: int
    points_start: float


@dataclass(frozen=True)
class RaceClassification:
    """One ``session_result`` row: a driver's finished position, or ``None`` if unclassified."""

    driver_number: int
    position: int | None

    @property
    def is_classified(self) -> bool:
        """Whether the session classified this driver, which is what scores this race."""
        return self.position is not None


@dataclass(frozen=True)
class ChampionshipSource:
    """The three recorded championship families of one session, plus the declared season.

    Yielded by :func:`build_championship_source` from a corpus payload mapping, so the run
    path derives it once and the booth holds it beside the driver directory it already
    joins. An empty source is a corpus with no championship rows, which the adapter states
    as unavailable rather than treating as a zero-point field.
    """

    season: int
    drivers: tuple[ChampionshipDriverRow, ...]
    teams: tuple[TeamStanding, ...]
    classifications: tuple[RaceClassification, ...]

    @property
    def is_empty(self) -> bool:
        """Whether the corpus supplied none of the three families at all."""
        return not (self.drivers or self.teams or self.classifications)


@dataclass(frozen=True)
class ChampionshipContext:
    """One moment's bounded championship picture, every field explicitly optional.

    The driver fields describe the current event's driver; ``leader_*`` and
    ``gap_to_leader`` the season leader and the gap to them; ``team_*`` the driver's team.
    ``driver_tied_with`` and ``team_tied_with`` are the declared tie counts: how many
    **other** drivers, and how many **other** teams, share the same points total as the one
    the position was ordered inside (``0`` when the total is unique). They are reported so
    the prose can state a convention as a convention; they never enter the arithmetic.
    ``available`` fields are ``None`` only for a reason named in ``unavailable``, never
    because a value was guessed. No table is carried: the prompt block is context, not a
    source, and a full 23-row list would be neither bounded nor citable.
    """

    driver_number: int | None
    driver_position: int | None
    driver_points: float | None
    driver_classified: bool
    leader_driver_number: int | None
    leader_points: float | None
    gap_to_leader: float | None
    team_name: str | None
    team_position: int | None
    team_points: float | None
    driver_tied_with: int
    team_tied_with: int
    unavailable: tuple[ChampionshipUnavailable, ...]


def _as_int(value: object) -> int | None:
    """Return ``value`` when it is a real integer, otherwise an explicit unknown."""
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _as_number(value: object) -> float | None:
    """Return ``value`` as a finite number, refusing ``bool`` and every non-number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return (
        number
        if number == number and number not in (float("inf"), float("-inf"))
        else None
    )


def _as_text(value: object) -> str | None:
    """Return a non-blank string, otherwise an explicit unknown."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def build_championship_source(
    payloads: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    season: int = RECORDED_SEASON,
) -> ChampionshipSource:
    """Read the three championship families out of a corpus payload mapping.

    Pure: it only reshapes records it is handed. A record missing a field the derivation
    needs is **skipped** rather than half-read, exactly as the run path's driver-directory
    join skips a half-joined record; an absent family yields an empty tuple. The season is
    supplied because the recorded families carry no year field, and it must be a season the
    declared dataset states - that refusal belongs to :func:`f1show.standings.season_rules`
    and is not duplicated here.
    """
    drivers: list[ChampionshipDriverRow] = []
    for record in payloads.get("championship_drivers", ()):
        number = _as_int(record.get("driver_number"))
        position = _as_int(record.get("position_start"))
        points = _as_number(record.get("points_start"))
        if number is None or position is None or points is None:
            continue
        drivers.append(
            ChampionshipDriverRow(
                driver_number=number, position_start=position, points_start=points
            )
        )
    teams: list[TeamStanding] = []
    for record in payloads.get("championship_teams", ()):
        name = _as_text(record.get("team_name"))
        position = _as_int(record.get("position_start"))
        points = _as_number(record.get("points_start"))
        if name is None or position is None or points is None:
            continue
        teams.append(
            TeamStanding(team_name=name, position_start=position, points_start=points)
        )
    classifications: list[RaceClassification] = []
    for record in payloads.get("session_result", ()):
        number = _as_int(record.get("driver_number"))
        if number is None:
            continue
        classifications.append(
            RaceClassification(
                driver_number=number, position=_as_int(record.get("position"))
            )
        )
    return ChampionshipSource(
        season=season,
        drivers=tuple(drivers),
        teams=tuple(teams),
        classifications=tuple(classifications),
    )


def championship_context(
    events: Sequence[DetectedEvent],
    *,
    driver_number: int | None,
    source: ChampionshipSource,
    team_of_driver: Mapping[int, str],
) -> ChampionshipContext:
    """Derive the bounded championship context of the moment the prefix ends at.

    ``events`` is the booth's own prefix, the current event last, exactly as
    :func:`f1show.salience.salience_summary` and :func:`f1show.mode.turn_mode` receive it,
    so the three projections share one window boundary. ``driver_number`` is the current
    event's driver; ``team_of_driver`` is the session entry list, which the booth already
    holds as its driver directory. Pure and deterministic: the inputs are read, never
    mutated, and equal inputs always yield an equal context.
    """
    order = _running_order(events)
    checkpoints = {row.driver_number: row for row in source.drivers}
    classified = {
        row.driver_number for row in source.classifications if row.is_classified
    }
    unavailable: list[ChampionshipUnavailable] = []
    if not order:
        unavailable.append(ChampionshipUnavailable.NO_RUNNING_ORDER)
        return _pre_race_context(
            driver_number,
            source=source,
            team_of_driver=team_of_driver,
            classified=classified,
            checkpoints=checkpoints,
            unavailable=unavailable,
        )
    if any(number not in checkpoints for number in order):
        # One runner the start checkpoints never saw makes the whole table wrong for
        # every driver behind them, so it is withheld rather than partially guessed.
        unavailable.append(ChampionshipUnavailable.NO_CHAMPIONSHIP_ROW)
        team_name, team_position, team_points, team_tied, team_unknown = _team_view(
            driver_number,
            source=source,
            team_of_driver=team_of_driver,
            race_points=_race_delta(order, classified, team_of_driver, source.season),
        )
        if team_unknown:
            unavailable.append(ChampionshipUnavailable.UNRESOLVABLE_TEAM)
        return ChampionshipContext(
            driver_number=driver_number,
            driver_position=None,
            driver_points=None,
            driver_classified=driver_number in classified,
            leader_driver_number=None,
            leader_points=None,
            gap_to_leader=None,
            team_name=team_name,
            team_position=team_position,
            team_points=team_points,
            driver_tied_with=0,
            team_tied_with=team_tied,
            unavailable=_declared(unavailable),
        )
    table = provisional_table(
        [StartStanding(row.driver_number, row.points_start) for row in source.drivers],
        order,
        source.season,
    )
    row = next(
        (standing for standing in table if standing.driver_number == driver_number),
        None,
    )
    if row is None:
        unavailable.append(ChampionshipUnavailable.NO_CHAMPIONSHIP_ROW)
    driver_tied_with = (
        0
        if row is None
        else sum(1 for standing in table if standing.points == row.points) - 1
    )
    leader = table[0]
    race_points = _race_delta(order, classified, team_of_driver, source.season)
    team_name, team_position, team_points, team_tied, team_unknown = _team_view(
        driver_number,
        source=source,
        team_of_driver=team_of_driver,
        race_points=race_points,
    )
    if team_unknown:
        unavailable.append(ChampionshipUnavailable.UNRESOLVABLE_TEAM)
    return ChampionshipContext(
        driver_number=driver_number,
        driver_position=None if row is None else row.position,
        driver_points=None if row is None else row.points,
        driver_classified=driver_number in classified,
        leader_driver_number=leader.driver_number,
        leader_points=leader.points,
        gap_to_leader=None if row is None else leader.points - row.points,
        team_name=team_name,
        team_position=team_position,
        team_points=team_points,
        driver_tied_with=driver_tied_with,
        team_tied_with=team_tied,
        unavailable=_declared(unavailable),
    )


def _pre_race_context(
    driver_number: int | None,
    *,
    source: ChampionshipSource,
    team_of_driver: Mapping[int, str],
    classified: set[int],
    checkpoints: Mapping[int, ChampionshipDriverRow],
    unavailable: list[ChampionshipUnavailable],
) -> ChampionshipContext:
    """The picture before any in-race position: the source's own pre-race rows.

    No running order has been observed, so nothing has been scored this race and no
    provisional derivation is claimed. The driver and leader come straight from the
    source's ``position_start``/``points_start`` rows, the team from its own
    ``championship_teams`` row with a zero race delta, and the moment is marked
    ``NO_RUNNING_ORDER``.
    """
    driver = None if driver_number is None else checkpoints.get(driver_number)
    if driver is None:
        unavailable.append(ChampionshipUnavailable.NO_CHAMPIONSHIP_ROW)
    leader = next((row for row in source.drivers if row.position_start == 1), None)
    team_name, team_position, team_points, team_tied, team_unknown = _team_view(
        driver_number,
        source=source,
        team_of_driver=team_of_driver,
        race_points={},
    )
    if team_unknown:
        unavailable.append(ChampionshipUnavailable.UNRESOLVABLE_TEAM)
    return ChampionshipContext(
        driver_number=driver_number,
        driver_position=None if driver is None else driver.position_start,
        driver_points=None if driver is None else driver.points_start,
        driver_classified=driver_number in classified,
        leader_driver_number=None if leader is None else leader.driver_number,
        leader_points=None if leader is None else leader.points_start,
        gap_to_leader=(
            None
            if driver is None or leader is None
            else leader.points_start - driver.points_start
        ),
        team_name=team_name,
        team_position=team_position,
        team_points=team_points,
        # The pre-race driver position is the **source's own** ``position_start``, reported
        # verbatim rather than derived, so the module's tie convention does not apply to it.
        driver_tied_with=0,
        team_tied_with=team_tied,
        unavailable=_declared(unavailable),
    )


def _team_view(
    driver_number: int | None,
    *,
    source: ChampionshipSource,
    team_of_driver: Mapping[int, str],
    race_points: Mapping[str, float],
) -> tuple[str | None, int | None, float | None, int, bool]:
    """The driver's team, ranked by the source's own start total plus the derived delta.

    Returns ``(name, position, points, tied_with, unknown)``. ``unknown`` is ``True`` when
    the entry list names no team for the driver or the team has no ``championship_teams``
    row, and then the name, position and points are ``None`` rather than a half-join.
    ``tied_with`` is how many **other** teams share this team's total - the team order is a
    declared convention (points descending, then the source's own ``position_start``, then
    ``team_name``), so a shared total is reported rather than presented as settled. The
    season total is the source's ``points_start`` - never a sum of driver rows, which U3a
    measured impossible.
    """
    name = None if driver_number is None else team_of_driver.get(driver_number)
    if name is None or not any(row.team_name == name for row in source.teams):
        return None, None, None, 0, True
    totals = {
        row.team_name: row.points_start + race_points.get(row.team_name, 0.0)
        for row in source.teams
    }
    ordered = sorted(
        source.teams,
        key=lambda row: (-totals[row.team_name], row.position_start, row.team_name),
    )
    position = next(
        index for index, row in enumerate(ordered, start=1) if row.team_name == name
    )
    tied_with = (
        sum(1 for row in source.teams if totals[row.team_name] == totals[name]) - 1
    )
    return name, position, totals[name], tied_with, False


def _race_delta(
    order: Sequence[int],
    classified: set[int],
    team_of_driver: Mapping[int, str],
    season: int,
) -> dict[str, float]:
    """This race's points so far, per entry-list team.

    Each running position scores the declared per-season points for its index, but only a
    driver the session **classifies** contributes, and only when their entry-list team is
    known: a driver with no ``session_result`` row scores nothing this race, exactly as the
    three row-less drivers do in the recorded bytes. A driver with no resolvable team
    contributes to no team, which the team fields report rather than silently misattribute.
    """
    delta: dict[str, float] = {}
    for index, number in enumerate(order, start=1):
        if number not in classified:
            continue
        team = team_of_driver.get(number)
        if team is None:
            continue
        delta[team] = delta.get(team, 0.0) + points_for_position(season, index)
    return delta


def _running_order(events: Sequence[DetectedEvent]) -> tuple[int, ...]:
    """The current running order: each driver's latest in-window position, first to last.

    The window begins at the first ``LAP_COMPLETED`` event, exactly as U1's and U2's do, so
    the pre-race grid snapshot is not an in-race position. ``position.json`` carries no
    ``lap_number``, so "latest" is the last recorded read inside the window. The order is
    stable: a shared position would be broken by ``driver_number`` ascending.
    """
    start = _window_start(events)
    latest: dict[int, int] = {}
    for event in events[start:]:
        if event.event_type is not EventType.POSITION_CHANGE:
            continue
        number = _as_int(event.driver_number)
        position = _as_int(event.evidence.get("position"))
        if number is None or position is None:
            continue
        latest[number] = position
    return tuple(sorted(latest, key=lambda number: (latest[number], number)))


def _window_start(events: Sequence[DetectedEvent]) -> int:
    """The index of the window's first event: the first completed lap, or the end."""
    for index, event in enumerate(events):
        if event.event_type is EventType.LAP_COMPLETED:
            return index
    return len(events)


def _declared(
    unavailable: Sequence[ChampionshipUnavailable],
) -> tuple[ChampionshipUnavailable, ...]:
    """The declared reasons, deduplicated and in the enum's own order, so the set is stable."""
    return tuple(reason for reason in ChampionshipUnavailable if reason in unavailable)


#: Every bracket character, refused in the rendered block, exactly as the CONTEXT block does.
_BRACKETS = frozenset("[](){}")


def render_championship(
    context: ChampionshipContext,
    driver_directory: Mapping[int, tuple[str, str]],
) -> str:
    """Render one context as the prompt's ``CHAMPIONSHIP`` block: plain prose, no token.

    Driver names are joined from the session directory, and every recorded string is
    stripped of every bracket character, so the block can never carry a
    ``family[index].field``-shaped token and cannot add a citable reference. An unresolved
    driver renders ``driver <number>`` rather than a half-join, and each ``unavailable``
    reason is stated in prose instead of being left for the model to infer from a blank.
    A position decided by a declared tie convention is stated as tied - the tie count is
    rendered, never hidden - while a lone holder keeps its bare position exactly as it was.
    """
    lines = ["CHAMPIONSHIP:"]
    if ChampionshipUnavailable.NO_RUNNING_ORDER in context.unavailable:
        lines.append(
            "- the race has not produced an in-race running order yet, so this is the "
            "pre-race championship picture"
        )
    if context.driver_number is None:
        lines.append(
            "- the current event names no driver, so no driver championship position is "
            "shown"
        )
    elif context.driver_position is None or context.driver_points is None:
        lines.append(
            f"- {_driver_name(context.driver_number, driver_directory)} has no "
            "championship checkpoint in the supplied rows, so their position and points "
            "are unknown"
        )
    else:
        if context.driver_tied_with > 0:
            # The derived position is a convention inside a shared points total, so it is
            # state as tied rather than presented as a settled place. The points, the gap
            # and the position number itself are unchanged.
            lines.append(
                f"- the current driver is "
                f"{_driver_name(context.driver_number, driver_directory)}, "
                f"P{context.driver_position} on {_number(context.driver_points)} points"
                f"{_tie_phrase(context.driver_tied_with, 'driver')}"
            )
        else:
            lines.append(
                f"- the current driver is "
                f"{_driver_name(context.driver_number, driver_directory)}, "
                f"P{context.driver_position} on {_number(context.driver_points)} points in "
                "the season championship"
            )
    if context.leader_driver_number is None or context.leader_points is None:
        lines.append(
            "- the season leader cannot be established from the supplied championship rows"
        )
    else:
        gap = (
            "an unknown gap"
            if context.gap_to_leader is None
            else f"a gap of {_number(context.gap_to_leader)} points"
        )
        lines.append(
            f"- the season leader is "
            f"{_driver_name(context.leader_driver_number, driver_directory)}, "
            f"{_number(context.leader_points)} points, {gap}"
        )
    if (
        context.team_name is None
        or context.team_position is None
        or context.team_points is None
    ):
        lines.append(
            "- their team is not resolvable from the session entry list and the "
            "championship rows, so its position and points are unknown"
        )
    else:
        lines.append(
            f"- their team {_clean(context.team_name)} is P{context.team_position} on "
            f"{_number(context.team_points)} points"
            f"{_tie_phrase(context.team_tied_with, 'team')}"
        )
    if context.driver_number is not None and not context.driver_classified:
        lines.append(
            "- this driver has no classified race result, so this race's points are not "
            "counted in the team's race delta"
        )
    return "\n".join(lines)


def _tie_phrase(count: int, noun: str) -> str:
    """The declared tie qualifier for a position ordered inside a shared points total.

    A position inside a points tie is decided by this module's declared convention, not
    observed in the source, so the prose states the sharing rather than a settled position:
    ``P18 on 5 points, tied with 1 other driver``. ``count`` is the number of **other**
    holders - ``0`` yields an empty qualifier, so a lone holder keeps its bare position
    byte for byte and the wording never moves for a driver or team whose total is unique.
    The qualifier is prose with no bracket and no reference-shaped token, like the rest of
    the block.
    """
    if count <= 0:
        return ""
    plural = "" if count == 1 else "s"
    return f", tied with {count} other {noun}{plural}"


def _driver_name(number: int, directory: Mapping[int, tuple[str, str]]) -> str:
    """The driver's joined name, or the one declared fallback for an unknown number."""
    identity = directory.get(number)
    if identity is None:
        return f"driver {number}"
    cleaned = _clean(identity[0])
    return cleaned or f"driver {number}"


def _clean(text: str) -> str:
    """Strip every bracket character and collapse whitespace, so no token can survive."""
    without_brackets = "".join(
        " " if character in _BRACKETS else character for character in text
    )
    return " ".join(without_brackets.split())


def _number(value: float) -> str:
    """A declared rendering of a points total: at most three decimals, trailing zeros cut."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"
