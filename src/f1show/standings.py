"""The provisional championship table, derived from the running order (F09g U3a).

**What the design asks for.** The championship picture of a race weekend reaches this
project as **two checkpoints per entity**: ``points_start``/``position_start`` before the
session and ``points_current``/``position_current`` after it, both carried in one call by
the source. An **in-race** table cannot come from the source at all - there is no such
endpoint - so the design requires it to be **derived** from the running order plus a small
**declared per-season** points dataset. This module is that derivation.

It carries one more **declared per-season** dataset besides the points: the **qualifying
rules** of F06c T2, shaped exactly like the first so there is one way to read a declared
rule. That dataset is described at the end of this docstring; nothing about it is derived
from a payload either.

**Pure by construction.** It reads no file, opens no store, reads no clock and draws no
random number, so a table is a function of its inputs and equal inputs always give an
equal table. Inputs are read, never mutated: every function builds a fresh points map and
the ``StartStanding``/``RaceResult`` rows are frozen dataclasses. Nothing here is wired
into the prompt (that is U3b): no value computed here is citable, no reference enters
``event.evidence``, and this module adds no name to the package root.

The declared per-season dataset
-------------------------------

One frozen :class:`SeasonRules` per season, exposed through :data:`SEASON_RULES` (a
read-only mapping) and the accessors :func:`season_rules`, :func:`race_points_scale`,
:func:`fastest_lap_point` and :func:`points_for_position`. An undeclared season is an
error, never a guess.

* **The race points scale, positions 1 to 10:** ``25, 18, 15, 12, 10, 8, 6, 4, 2, 1``.
  Position 11 and beyond scores nothing. Position ``None`` (an unclassified DNF) scores
  nothing, and a position below 1 is refused because it is not a real finishing position.
* **The fastest-lap point is the one declared per-season difference:** **1** in 2024 and
  **0** in 2025. In 2024 the point is **not unconditional**: the declared dataset carries
  the regulation's **top-10 condition** as ``fastest_lap_max_position = 10``, and the
  derivation applies it rather than leaving it to the caller. A holder whose position
  cannot be established is **refused**, not guessed.

**What this dataset deliberately does not model**, declared so the limit is visible
rather than implied: **sprint points** (a sprint has its own scale, and the recorded
fixtures need none - the single recorded session is a race with no sprint row);
**half points** for a shortened race; **penalties and disqualification**
(the recorded ``dsq``/``dnf``/``dns`` flags are not consulted; an unclassified driver
simply scores nothing); **countback tie-breaks** (see below); and **any team or entry-list
aggregation**, which the recorded data does not support (see the validation section).

The fastest-lap eligibility condition, modelled and measured
------------------------------------------------------------

The 2024 regulation does not award the fastest-lap point to whoever sets the lap alone:
the holder must be **classified inside the top 10**. The declared dataset therefore states
the condition (``fastest_lap_max_position = 10`` for 2024, ``None`` for 2025), and both
:func:`after_table` and :func:`provisional_table` apply it with the position each already
computes. Measured on the recorded session: its fastest valid lap is **driver 31, lap 53,
97.33 s**, and driver 31 is classified **P18**, so the point is **0** - the driver's points
stay 5.0, not 6.0 - and **no other recorded value moves**. This matters beyond the
recorded bytes: a caller that derives a fastest lap without an eligibility condition (the
salience projection does) can pass it here, and the module refuses to over-credit it.

**The declared error behaviour when a position is unknown:** a season that grants the
point but supplies no position for the holder is **refused** with
:class:`StandingsInputError`. Awarding the point would credit something the regulation may
not allow, and dropping it would silently hide a missing position, so refusing is the only
honest third option; it also keeps the obligation inside the module rather than on the
caller. A season that grants no point is different: there the declaration is **inert**
whatever the position, including an unknown one, because there is no point to award.

The declared tie rule
---------------------

Points decide the order; **equal points are ordered by ``driver_number`` ascending**, and
positions are then assigned ``1..n`` with no shared positions. The rule is declared rather
than implicit, and it is deliberately *not* an attempt to reproduce the source's own tie
order, because the recorded fields cannot: measured on the 23 recorded rows, our rule
disagrees with ``position_current`` on **8** rows, and ordering each tie group by
``position_start`` (the other defensible candidate) still disagrees on **2** (drivers 43
and 31, tied at 5 points, swap). A rule that happened to match one recorded session would
not be a rule.

Validation against the source's own checkpoints, measured
----------------------------------------------------------

The recorded session 9617 carries ``championship_drivers`` (23 rows), ``championship_teams``
(10 rows) and ``session_result`` (20 rows), so it can be asked three questions. Each answer
below is a measurement on those bytes, and the one that disagrees is reported as a finding
rather than fitted:

1. **``points_current == points_start + session_result.points`` holds for every driver.**
   For the 20 drivers the result names, the identity is exact row by row; for the three the
   result does not name (drivers 2, 3 and 50) ``points_current`` equals ``points_start``
   exactly, which is the same identity read with no points awarded. Derived by
   :func:`after_table`, all **23** values match ``points_current``.
2. **The ordering holds as a grouping, not as a tie order.** ``position_current`` is
   non-increasing in ``points_current`` for all 23 recorded rows, so points alone reproduce
   the groups; the order *within* a tie is not recoverable from the recorded fields.
3. **A team's ``points_current`` is not the sum of its recorded drivers' points.** The
   global total agrees exactly (**2078** on both sides), but Ferrari differs by **6**, Haas
   F1 Team by **1** and RB by **12**. Those three differences sum to **19**, exactly the
   points of the three ``championship_drivers`` rows that carry no team in the recorded
   entry list (driver 3: 12, driver 50: 7, driver 2: 0). Driver 3's 12 accounts for RB's
   remainder and driver 2's 0 for Williams' 0, but Ferrari's 6 and Haas' 1 together equal a
   single unmapped row of 7 - a split the recorded driver table cannot express. The
   disagreement is a property of the source and of season-long team accounting, not of this
   derivation, and it is left uncorrected.

What the final-moment property proves
-------------------------------------

At the final moment - every lap complete - the running order **is** the classification, so
:func:`provisional_table` and :func:`after_table` must agree. That equality is implemented
and tested against the recorded session and, separately, with a fastest-lap point declared.

**It proves our arithmetic and nothing else.** There is no recorded in-race table anywhere
in the corpus, so no fixture can confirm that the source's real in-race points looked like
these; what holds is that two of our own derivations from the same inputs coincide at the
boundary, and that a running order which differs from the classification produces a
different table (so the property is not vacuous). It is arithmetic self-consistency, not
source validation of live values.

The declared per-season qualifying rules (F06c T2)
--------------------------------------------------

The second declared dataset this module states, shaped like the first: one frozen
:class:`QualifyingRules` per ``(season, session kind)``, exposed through
:data:`QUALIFYING_RULES` (a read-only mapping) and the refusing accessor
:func:`qualifying_rules`. The refusal order is declared and testable - an undeclared
**season** first, naming the declared seasons exactly as :func:`season_rules` does, then an
undeclared **session kind** for a declared season, naming the kinds that season declares -
and both refusals are :class:`QualifyingRulesError`, a :class:`StandingsInputError`, so one
``except`` still covers every declared-dataset refusal in this module.

**What 2024 main qualifying declares:** **three phases**, of **18, 15 and 12 minutes**, with
**20, 15 and 10 participants** - so five drivers are eliminated after each of the first two
phases and the last phase classifies ten. Those are the values F06c measured on the capture
of session ``9608`` and then *declared*, which is the direction that matters: this module
reads no payload, so no phase length, elimination count or boundary can be read, computed or
inferred from the fixture corpus at runtime. The capture supplies lap times and positions;
every rule comes from the table below.

**What is deliberately not declared**, each for a measured reason rather than an oversight:

* **Sprint Qualifying.** Only session ``9608`` - a ``Qualifying`` session - was captured, so
  an unmeasured session kind has no declaration and is **refused**, never invented and never
  defaulted to the main-session format. Naming it in :class:`QualifyingSessionKind` would be a
  declaration nobody measured.
* **The inter-phase breaks.** Measured at **7** and **8** minutes, i.e. not uniform, so no
  inter-phase gap is a rule; :class:`QualifyingPhase` carries no gap field, and a caller that
  needs a break has to read it from the source.
* **Absolute phase windows.** The windows of ``9608`` are **data** - ``race_control``'s
  ``qualifying_phase`` rows carry a start/finish pair per phase - and 14 recorded laps start
  outside every window. The declared rules therefore carry **lengths**, and a window is only
  stated once a start instant arrives from the source.
* **Any circuit-specific constant.** Nothing here names a track: the same declared row
  describes the same session format anywhere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

__all__ = [
    "QUALIFYING_RULES",
    "SEASON_RULES",
    "QualifyingPhase",
    "QualifyingRules",
    "QualifyingRulesError",
    "QualifyingSessionKind",
    "RaceResult",
    "SeasonRules",
    "Standing",
    "StandingsInputError",
    "StartStanding",
    "after_table",
    "fastest_lap_point",
    "order_standings",
    "points_for_position",
    "provisional_table",
    "qualifying_rules",
    "race_points_scale",
    "season_rules",
]

#: The declared race points scale for positions 1 to 10, identical in 2024 and 2025.
_RACE_POINTS_POSITIONS_1_TO_10: tuple[int, ...] = (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)


class StandingsInputError(ValueError):
    """A caller gave the derivation input it cannot honestly consume.

    Raised for an undeclared season, a finishing position below 1, a result or running
    order that names a driver missing from the start checkpoints, and a duplicated driver.
    :class:`QualifyingRulesError` is a subclass, so this one name also covers the declared
    qualifying dataset's refusals: an undeclared qualifying season and an undeclared
    session kind.
    """


@dataclass(frozen=True)
class SeasonRules:
    """The declared points rules for one season.

    ``race_points`` is the scale for positions ``1..len(race_points)`` in order.
    ``fastest_lap_point`` is the point's value and is ``0`` when the season grants none.
    ``fastest_lap_max_position`` is the **condition** attached to that point: it is earned
    only by a holder classified at or inside this position, and is ``None`` when the season
    grants no fastest-lap point at all. The two move together - a declared season with
    ``fastest_lap_point == 0`` states ``fastest_lap_max_position is None``, and vice versa.
    """

    season: int
    race_points: tuple[int, ...]
    fastest_lap_point: int
    fastest_lap_max_position: int | None


@dataclass(frozen=True)
class StartStanding:
    """One driver's championship checkpoint before the race."""

    driver_number: int
    points: float


@dataclass(frozen=True)
class RaceResult:
    """One driver's race result row.

    ``position`` is the recorded finishing position, or ``None`` for an unclassified
    driver (a DNF carried by the source with a null position). ``fastest_lap`` is true for
    the driver the race declares as setting the fastest lap; it only matters in a season
    whose :class:`SeasonRules` grants the point.
    """

    driver_number: int
    position: int | None
    fastest_lap: bool = False


@dataclass(frozen=True)
class Standing:
    """One row of a derived championship table."""

    position: int
    driver_number: int
    points: float


#: The declared per-season dataset. Read-only: a caller cannot edit a season in place.
SEASON_RULES: Mapping[int, SeasonRules] = MappingProxyType(
    {
        2024: SeasonRules(
            season=2024,
            race_points=_RACE_POINTS_POSITIONS_1_TO_10,
            fastest_lap_point=1,
            # The 2024 regulation grants the point only to a holder classified in the
            # top 10; position 11 and beyond earns nothing (see _fastest_lap_points).
            fastest_lap_max_position=10,
        ),
        2025: SeasonRules(
            season=2025,
            race_points=_RACE_POINTS_POSITIONS_1_TO_10,
            fastest_lap_point=0,
            # No fastest-lap point exists in 2025, so there is no position condition.
            fastest_lap_max_position=None,
        ),
    }
)


def season_rules(season: int) -> SeasonRules:
    """The declared rules for ``season``, or an error naming the declared seasons."""
    try:
        return SEASON_RULES[season]
    except KeyError:
        raise StandingsInputError(
            f"no declared points rules for season {season!r}; "
            f"declared seasons: {sorted(SEASON_RULES)}"
        ) from None


def race_points_scale(season: int) -> tuple[int, ...]:
    """The race points scale, positions 1 to 10, for ``season``."""
    return season_rules(season).race_points


def fastest_lap_point(season: int) -> int:
    """The fastest-lap point for ``season``: ``1`` in 2024 and ``0`` in 2025."""
    return season_rules(season).fastest_lap_point


def points_for_position(season: int, position: int | None) -> int:
    """The race points for one finishing position, or ``0`` when it scores nothing.

    ``None`` is an unclassified driver and scores nothing. A position beyond the scale
    scores nothing; a position below ``1`` is not a real position and is refused.
    """
    return _points_for(season_rules(season), position)


# --- the declared per-season qualifying rules (F06c T2) -------------------------------


class QualifyingSessionKind(str, Enum):
    """A session kind the declared qualifying dataset can state rules for.

    The value is the source's own ``session_type`` literal, so a recorded payload reaches
    the declaration with no mapping in between. ``Qualifying`` is the only member because
    only session 9608 was captured: **Sprint Qualifying is deliberately absent**, so no
    caller can name it and :func:`qualifying_rules` refuses it by naming what *is*
    declared rather than inventing a format nobody measured.
    """

    MAIN_QUALIFYING = "Qualifying"


class QualifyingRulesError(StandingsInputError):
    """The declared qualifying dataset does not state the rules a caller asked for.

    Raised for an undeclared season and for an undeclared session kind, and each refusal
    names what *is* declared. A :class:`StandingsInputError`, so a caller that already
    catches this module's declared-dataset refusals needs no second handler.
    """


@dataclass(frozen=True)
class QualifyingPhase:
    """One declared phase of a qualifying session.

    ``phase`` is the phase number the source itself uses (``1``, ``2``, ``3`` in
    ``race_control.qualifying_phase``). ``duration_minutes`` is how long the phase lasts,
    and ``participants`` is how many drivers take part in it, so the next phase's count is
    also the number that advance. There is deliberately **no** gap field: the recorded
    breaks are 7 and 8 minutes, not uniform, so no inter-phase gap is a rule.
    """

    phase: int
    duration_minutes: int
    participants: int


@dataclass(frozen=True)
class QualifyingRules:
    """The declared qualifying rules for one season and one session kind.

    ``phases`` is the phase structure in order, each phase carrying its own length and
    participant count. The rules carry phase **lengths**, not absolute windows: a window is
    data, so a caller holding a start instant can state one, and nothing here pretends to
    know when a session began.
    """

    season: int
    session_kind: QualifyingSessionKind
    phases: tuple[QualifyingPhase, ...]


#: The declared qualifying dataset. Read-only: a caller cannot edit a season in place.
QUALIFYING_RULES: Mapping[tuple[int, QualifyingSessionKind], QualifyingRules] = (
    MappingProxyType(
        {
            (2024, QualifyingSessionKind.MAIN_QUALIFYING): QualifyingRules(
                season=2024,
                session_kind=QualifyingSessionKind.MAIN_QUALIFYING,
                # Measured on the capture of session 9608 (F06c L9) and declared here:
                # 18/15/12 minutes and 20 -> 15 -> 10 participants. Declared once, never
                # derived from the payload the motor is checked against.
                phases=(
                    QualifyingPhase(phase=1, duration_minutes=18, participants=20),
                    QualifyingPhase(phase=2, duration_minutes=15, participants=15),
                    QualifyingPhase(phase=3, duration_minutes=12, participants=10),
                ),
            ),
        }
    )
)


def qualifying_rules(
    season: int, session_kind: QualifyingSessionKind | str
) -> QualifyingRules:
    """The declared qualifying rules for ``season`` and ``session_kind``.

    ``session_kind`` is the enum member or the source's own literal (``"Qualifying"``),
    because the member's value *is* that literal. An undeclared **season** is refused first,
    naming the declared seasons exactly as :func:`season_rules` does; an undeclared
    **session kind** for a declared season is refused next, naming the kinds that season
    declares. Neither refusal falls back to another season, to a default kind, or to the
    main-session format.
    """
    declared_seasons = sorted({declared for declared, _ in QUALIFYING_RULES})
    if season not in declared_seasons:
        raise QualifyingRulesError(
            f"no declared qualifying rules for season {season!r}; "
            f"declared qualifying seasons: {declared_seasons}"
        )
    kind = _declared_session_kind(session_kind)
    rules = QUALIFYING_RULES.get((season, kind)) if kind is not None else None
    if rules is not None:
        return rules
    declared_kinds = sorted(
        declared.value
        for declared_season, declared in QUALIFYING_RULES
        if declared_season == season
    )
    raise QualifyingRulesError(
        f"no declared qualifying rules for season {season!r} and session kind "
        f"{session_kind!r}; declared session kinds for {season}: {declared_kinds}"
    )


def order_standings(points_by_driver: Mapping[int, float]) -> tuple[Standing, ...]:
    """Order a points map into a table, applying the declared tie rule.

    Points descending, then ``driver_number`` ascending for equal points. Deterministic and
    independent of the mapping's iteration order. The returned rows are new objects and the
    mapping is not modified.
    """
    ordered = sorted(points_by_driver.items(), key=lambda item: (-item[1], item[0]))
    return tuple(
        Standing(position=index, driver_number=number, points=points)
        for index, (number, points) in enumerate(ordered, start=1)
    )


def after_table(
    start: Sequence[StartStanding],
    result: Sequence[RaceResult],
    season: int,
) -> tuple[Standing, ...]:
    """The **after** table: the start checkpoints plus one race result.

    Every start checkpoint keeps its points. Every result row adds the points for its
    finishing position and, when the row declares the fastest lap and the holder's
    finishing position satisfies the season's declared condition, the fastest-lap point. A
    driver the result does not name keeps the start points unchanged, which is how the
    recorded data reads for a driver who did not take part. The inputs are read, never
    mutated.
    """
    rules = season_rules(season)
    points = _start_points(start)
    seen: set[int] = set()
    for row in result:
        if row.driver_number in seen:
            raise StandingsInputError(
                f"duplicate result row for driver {row.driver_number}"
            )
        seen.add(row.driver_number)
        if row.driver_number not in points:
            raise StandingsInputError(
                f"result names driver {row.driver_number}, "
                "which is absent from the start checkpoints"
            )
        gained = _points_for(rules, row.position)
        if row.fastest_lap:
            gained += _fastest_lap_points(rules, row.position, row.driver_number)
        points[row.driver_number] += gained
    return order_standings(points)


def provisional_table(
    start: Sequence[StartStanding],
    running_order: Sequence[int],
    season: int,
    *,
    fastest_lap_driver_number: int | None = None,
) -> tuple[Standing, ...]:
    """The **provisional in-race** table from the start checkpoints plus the running order.

    ``running_order`` is the drivers in current race order - first to last - so the index
    of a driver in that sequence **is** their current position, and each scores the points
    for it. A driver absent from the order (retired, or not yet classified) keeps the start
    points unchanged. The fastest-lap point is not knowable before the race ends, so it is
    awarded only when the caller declares ``fastest_lap_driver_number``; leaving it out
    means the season's point is not applied. When it is declared, the point is granted only
    if the holder's current position (its index in ``running_order``) satisfies the
    season's declared eligibility, and a holder whose position is not in the order is
    refused in a season that grants the point. The inputs are read, never mutated.
    """
    rules = season_rules(season)
    points = _start_points(start)
    seen: set[int] = set()
    position_of: dict[int, int] = {}
    for position, driver_number in enumerate(running_order, start=1):
        if driver_number in seen:
            raise StandingsInputError(
                f"duplicate driver {driver_number} in the running order"
            )
        seen.add(driver_number)
        if driver_number not in points:
            raise StandingsInputError(
                f"running order names driver {driver_number}, "
                "which is absent from the start checkpoints"
            )
        position_of[driver_number] = position
        points[driver_number] += _points_for(rules, position)
    if fastest_lap_driver_number is not None:
        if fastest_lap_driver_number not in points:
            raise StandingsInputError(
                f"the fastest lap names driver {fastest_lap_driver_number}, "
                "which is absent from the start checkpoints"
            )
        points[fastest_lap_driver_number] += _fastest_lap_points(
            rules,
            position_of.get(fastest_lap_driver_number),
            fastest_lap_driver_number,
        )
    return order_standings(points)


def _fastest_lap_points(
    rules: SeasonRules, position: int | None, driver_number: int
) -> int:
    """The fastest-lap point for a holder, applying the season's declared condition.

    A season that grants no fastest-lap point returns ``0`` whatever the position, so the
    declaration is inert. A season that grants one returns the point only when the holder
    is classified at or inside ``fastest_lap_max_position``. When the season grants the
    point but the holder's position cannot be established, this **refuses** instead of
    guessing: neither awarding nor dropping it would be honest, because the outcome is
    decided by a position nobody supplied.
    """
    if rules.fastest_lap_point == 0 or rules.fastest_lap_max_position is None:
        return 0
    if position is None:
        raise StandingsInputError(
            f"driver {driver_number} is declared for the fastest lap, but no position "
            f"can be established, and season {rules.season} grants the point only to a "
            f"holder inside position {rules.fastest_lap_max_position}"
        )
    if position < 1:
        raise StandingsInputError(
            f"position {position!r} is not a real finishing position"
        )
    if position > rules.fastest_lap_max_position:
        return 0
    return rules.fastest_lap_point


def _points_for(rules: SeasonRules, position: int | None) -> int:
    """The points for one position under an already-resolved season's rules."""
    if position is None:
        return 0
    if position < 1:
        raise StandingsInputError(
            f"position {position!r} is not a real finishing position"
        )
    if position > len(rules.race_points):
        return 0
    return rules.race_points[position - 1]


def _start_points(start: Sequence[StartStanding]) -> dict[int, float]:
    """A fresh driver-to-points map from the start checkpoints, refusing duplicates."""
    points: dict[int, float] = {}
    for row in start:
        if row.driver_number in points:
            raise StandingsInputError(
                f"duplicate start checkpoint for driver {row.driver_number}"
            )
        points[row.driver_number] = float(row.points)
    return points


def _declared_session_kind(session_kind: object) -> QualifyingSessionKind | None:
    """The declared kind a caller's value names, or ``None`` when it names none.

    The table is keyed by the enum, and a ``str``-mixing enum member hashes by its *name*
    rather than by its value, so the source's literal would never match a key on its own.
    The value is normalised here instead of leaving each caller to guess which form works.
    """
    if isinstance(session_kind, QualifyingSessionKind):
        return session_kind
    if isinstance(session_kind, str):
        try:
            return QualifyingSessionKind(session_kind)
        except ValueError:
            return None
    return None
