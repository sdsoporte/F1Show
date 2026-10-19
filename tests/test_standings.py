"""Offline acceptance tests for the F09g provisional championship derivation.

Everything here is pure: the derivation reads no file, opens no store, reads no clock and
draws no random number, so a table is a function of its inputs alone and two calls on the
same inputs are equal. The only files this suite touches are the recorded fixture corpus
and only in the tests that validate the derivation against the source's own checkpoints.

**What is measured, not assumed.** The recorded session 9617 carries `championship_drivers`
(23 rows), `championship_teams` (10 rows) and `session_result` (20 rows), so the source
answers three questions about itself. Two of them hold and one does not, and each is stated
as it was measured:

* `points_current == points_start + session_result.points` holds for **every** one of the
  23 recorded drivers, with the three drivers that have no `session_result` row keeping
  their start points exactly.
* `position_current` is non-increasing in `points_current` for every row, but the recorded
  fields do **not** determine the order *within* a tie group: the declared rule
  (driver_number ascending) disagrees on **8** rows and start-position stability still
  disagrees on **2**.
* A team's `points_current` is **not** the sum of its recorded drivers' `points_current`:
  Ferrari differs by **6**, Haas F1 Team by **1** and RB by **12**, while the global total
  agrees exactly (2078).
* The 2024 fastest-lap point is **conditional**, and the condition bites on this very
  session: its fastest valid lap is **driver 31, lap 53 (97.33 s)**, classified **P18**, so
  the point is **0** and no recorded value moves. The check lives in the module, so a naive
  caller that passes a derived fastest lap through cannot over-credit it.

A test that adjusted those last two to fit the code would hide the only evidence the
derivation has against the source, so they are pinned as recorded findings and the code is
left alone.

The module also carries the **second declared per-season dataset** it states: the
qualifying rules of F06c T2 (three phases, 18/15/12 minutes, 20 → 15 → 10 participants for
2024 main qualifying). The tests for it are the last section of this file and they read
**no fixture at all**, deliberately: the declared table must not be derived from, or pinned
to, the captured session, because it is the input the cutoff motor is checked *against*.
The capture's role was to measure the values once; the values are declared here.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import Any, cast

import pytest

from f1show.championship import RECORDED_SEASON
from f1show.standings import (
    QUALIFYING_RULES,
    SEASON_RULES,
    QualifyingPhase,
    QualifyingRules,
    QualifyingRulesError,
    QualifyingSessionKind,
    RaceResult,
    Standing,
    StandingsInputError,
    StartStanding,
    after_table,
    fastest_lap_point,
    order_standings,
    points_for_position,
    provisional_table,
    qualifying_rules,
    race_points_scale,
    season_rules,
)

#: The recorded fixture corpus, read the same way ``tests/test_salience.py`` reads it.
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "openf1"


def _load(name: str) -> list[dict[str, Any]]:
    """Read one recorded fixture family verbatim."""
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _start_checkpoints() -> list[StartStanding]:
    """The recorded before-session checkpoints, one per championship_drivers row."""
    return [
        StartStanding(
            driver_number=int(row["driver_number"]), points=float(row["points_start"])
        )
        for row in _load("championship_drivers")
    ]


def _race_result() -> list[RaceResult]:
    """The recorded race result rows; a driver with no position is unclassified."""
    return [
        RaceResult(
            driver_number=int(row["driver_number"]),
            position=None if row["position"] is None else int(row["position"]),
        )
        for row in _load("session_result")
    ]


# --- the declared points dataset -----------------------------------------------------


def test_race_points_scale_boundaries() -> None:
    """Position 1 and position 10 score; position 11 and beyond score nothing."""
    for season in (2024, 2025):
        assert race_points_scale(season) == (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)
        assert points_for_position(season, 1) == 25
        assert points_for_position(season, 10) == 1
        assert points_for_position(season, 11) == 0
        assert points_for_position(season, 20) == 0
        assert points_for_position(season, None) == 0


def test_a_position_below_one_is_refused() -> None:
    """Zero is not a real finishing position, so it is an error, not a silent nothing."""
    with pytest.raises(StandingsInputError):
        points_for_position(2024, 0)


def test_fastest_lap_point_exists_in_2024_and_not_in_2025() -> None:
    """The one declared per-season difference: the fastest-lap point is 1 then 0."""
    assert fastest_lap_point(2024) == 1
    assert fastest_lap_point(2025) == 0


def test_fastest_lap_point_changes_the_after_table_only_in_2024() -> None:
    """The same result adds a point under 2024 and adds nothing under 2025."""
    start = [StartStanding(1, 100.0), StartStanding(2, 90.0), StartStanding(3, 80.0)]
    result = [
        RaceResult(1, 1),
        RaceResult(2, 2, fastest_lap=True),
        RaceResult(3, 3),
    ]
    got_2024 = {
        row.driver_number: row.points for row in after_table(start, result, 2024)
    }
    got_2025 = {
        row.driver_number: row.points for row in after_table(start, result, 2025)
    }
    assert got_2024 == {1: 125.0, 2: 109.0, 3: 95.0}
    assert got_2025 == {1: 125.0, 2: 108.0, 3: 95.0}


def test_the_declared_fastest_lap_point_and_condition_move_together() -> None:
    """A granting season declares a maximum position; a non-granting one declares none."""
    assert season_rules(2024).fastest_lap_point == 1
    assert season_rules(2024).fastest_lap_max_position == 10
    assert season_rules(2025).fastest_lap_point == 0
    assert season_rules(2025).fastest_lap_max_position is None
    for rules in SEASON_RULES.values():
        assert (rules.fastest_lap_point == 0) == (
            rules.fastest_lap_max_position is None
        )


def test_fastest_lap_point_requires_a_top_ten_finish() -> None:
    """The declared boundary: a holder classified P10 earns the 2024 point, P11 does not."""
    start = [StartStanding(31, 0.0)]
    inside = {
        row.driver_number: row.points
        for row in after_table(start, [RaceResult(31, 10, fastest_lap=True)], 2024)
    }
    outside = {
        row.driver_number: row.points
        for row in after_table(start, [RaceResult(31, 11, fastest_lap=True)], 2024)
    }
    assert inside[31] == 2.0  # 1 point for P10 plus the fastest-lap point
    assert (
        outside[31] == 0.0
    )  # P11 scores nothing, and the fastest-lap point is refused

    many = [StartStanding(number, 0.0) for number in range(1, 12)]
    order = list(range(1, 12))
    at_ten = {
        row.driver_number: row.points
        for row in provisional_table(many, order, 2024, fastest_lap_driver_number=10)
    }
    at_eleven = {
        row.driver_number: row.points
        for row in provisional_table(many, order, 2024, fastest_lap_driver_number=11)
    }
    assert at_ten[10] == 2.0
    assert at_eleven[11] == 0.0


def test_fastest_lap_point_is_inert_in_a_season_without_it() -> None:
    """In 2025 no fastest-lap point exists, so the declaration does nothing anywhere."""
    start = [StartStanding(1, 0.0), StartStanding(20, 0.0)]
    result = [RaceResult(1, 1, fastest_lap=True), RaceResult(20, 20, fastest_lap=True)]
    table = {row.driver_number: row.points for row in after_table(start, result, 2025)}
    assert table == {1: 25.0, 20: 0.0}
    # An unknown position is inert too, because there is no point to award.
    unknown = [
        RaceResult(1, 1, fastest_lap=True),
        RaceResult(20, None, fastest_lap=True),
    ]
    assert {
        row.driver_number: row.points for row in after_table(start, unknown, 2025)
    } == {1: 25.0, 20: 0.0}
    # Provisional: driver 20 is not in the order, so its position is unknown, still inert.
    provisional = {
        row.driver_number: row.points
        for row in provisional_table(start, [1], 2025, fastest_lap_driver_number=20)
    }
    assert provisional[20] == 0.0


def test_a_fastest_lap_holder_with_no_known_position_is_refused_in_2024() -> None:
    """The declared choice: a granting season refuses rather than guess a position."""
    start = [StartStanding(1, 0.0), StartStanding(20, 0.0)]
    with pytest.raises(StandingsInputError):
        after_table(
            start, [RaceResult(1, 1), RaceResult(20, None, fastest_lap=True)], 2024
        )
    with pytest.raises(StandingsInputError):
        provisional_table(start, [1], 2024, fastest_lap_driver_number=20)


def test_an_undeclared_season_is_refused() -> None:
    """The dataset declares 2024 and 2025; any other season is an explicit error."""
    with pytest.raises(StandingsInputError):
        season_rules(2023)
    with pytest.raises(StandingsInputError):
        after_table([StartStanding(1, 0.0)], [], 2019)
    with pytest.raises(StandingsInputError):
        provisional_table([StartStanding(1, 0.0)], [1], 2019)


def test_the_declared_dataset_is_read_only() -> None:
    """A declared season rule cannot be edited in place by any caller."""
    read_only: Any = SEASON_RULES
    with pytest.raises(TypeError):
        read_only[1999] = season_rules(2024)


# --- ordering and the tie rule -------------------------------------------------------


def test_equal_points_are_ordered_by_driver_number() -> None:
    """The declared tie rule: equal points, then driver_number ascending."""
    table = order_standings({7: 12.0, 3: 12.0, 5: 20.0})
    assert table == (
        Standing(position=1, driver_number=5, points=20.0),
        Standing(position=2, driver_number=3, points=12.0),
        Standing(position=3, driver_number=7, points=12.0),
    )


def test_tie_order_does_not_depend_on_input_order() -> None:
    """The tie rule is a property of the values, not of the mapping's iteration order."""
    forward = order_standings({1: 1.0, 2: 1.0, 3: 1.0})
    backward = order_standings({3: 1.0, 2: 1.0, 1: 1.0})
    assert forward == backward
    assert [row.driver_number for row in forward] == [1, 2, 3]


# --- empty and partial inputs --------------------------------------------------------


def test_empty_checkpoints_give_an_empty_table() -> None:
    """No start checkpoints and no result is an empty table, not an error."""
    assert after_table([], [], 2024) == ()
    assert provisional_table([], [], 2024) == ()


def test_empty_result_keeps_every_start_point() -> None:
    """A race with no recorded result rows changes nothing."""
    start = [StartStanding(1, 10.0), StartStanding(2, 5.0)]
    assert after_table(start, [], 2024) == (
        Standing(position=1, driver_number=1, points=10.0),
        Standing(position=2, driver_number=2, points=5.0),
    )


def test_partial_result_awards_only_the_rows_it_carries() -> None:
    """Drivers the result does not name keep their start points."""
    start = [StartStanding(1, 0.0), StartStanding(2, 0.0), StartStanding(3, 0.0)]
    assert after_table(start, [RaceResult(3, 1)], 2024) == (
        Standing(position=1, driver_number=3, points=25.0),
        Standing(position=2, driver_number=1, points=0.0),
        Standing(position=3, driver_number=2, points=0.0),
    )


def test_a_result_driver_absent_from_the_checkpoints_is_refused() -> None:
    """A driver the start table never saw cannot be given points honestly."""
    with pytest.raises(StandingsInputError):
        after_table([StartStanding(1, 0.0)], [RaceResult(9, 1)], 2024)
    with pytest.raises(StandingsInputError):
        provisional_table([StartStanding(1, 0.0)], [9], 2024)
    with pytest.raises(StandingsInputError):
        provisional_table(
            [StartStanding(1, 0.0)], [1], 2024, fastest_lap_driver_number=9
        )


def test_duplicate_driver_rows_are_refused() -> None:
    """Two rows for one driver would double-count and are an error."""
    with pytest.raises(StandingsInputError):
        after_table([StartStanding(1, 0.0), StartStanding(1, 5.0)], [], 2024)
    with pytest.raises(StandingsInputError):
        after_table([StartStanding(1, 0.0)], [RaceResult(1, 1), RaceResult(1, 2)], 2024)
    with pytest.raises(StandingsInputError):
        provisional_table([StartStanding(1, 0.0)], [1, 1], 2024)


# --- the provisional table and the final-moment property -----------------------------


def test_provisional_table_rewards_the_running_order() -> None:
    """The running order's index is the driver's current position."""
    start = [StartStanding(10, 0.0), StartStanding(20, 0.0), StartStanding(30, 0.0)]
    table = provisional_table(start, [30, 10, 20], 2024)
    assert table == (
        Standing(position=1, driver_number=30, points=25.0),
        Standing(position=2, driver_number=10, points=18.0),
        Standing(position=3, driver_number=20, points=15.0),
    )


def test_provisional_does_not_restate_the_after_table_before_the_end() -> None:
    """The equality at the final moment is not vacuous: a different order differs."""
    start = [StartStanding(1, 0.0), StartStanding(2, 0.0), StartStanding(3, 0.0)]
    result = [RaceResult(1, 1), RaceResult(2, 2), RaceResult(3, 3)]
    after = after_table(start, result, 2024)
    early = provisional_table(start, [3, 1, 2], 2024)
    assert early != after


def test_final_moment_provisional_equals_after_on_the_recorded_session() -> None:
    """Every lap complete: the provisional running order is the classification."""
    start = _start_checkpoints()
    result = _race_result()
    after = after_table(start, result, 2024)
    classified = sorted(
        (row for row in result if row.position is not None),
        key=lambda row: cast(int, row.position),
    )
    running_order = [row.driver_number for row in classified]
    assert provisional_table(start, running_order, 2024) == after
    assert len(after) == 23


def test_final_moment_property_holds_with_a_fastest_lap_declared() -> None:
    """The property survives the season's fastest-lap point when both sides carry it."""
    start = [StartStanding(1, 100.0), StartStanding(2, 90.0), StartStanding(3, 80.0)]
    result = [RaceResult(1, 1), RaceResult(2, 2, fastest_lap=True), RaceResult(3, 3)]
    after = after_table(start, result, 2024)
    provisional = provisional_table(start, [1, 2, 3], 2024, fastest_lap_driver_number=2)
    assert provisional == after


# --- purity and determinism ----------------------------------------------------------


def test_inputs_are_not_mutated() -> None:
    """The derivation reads its inputs and never rewrites them."""
    start = _start_checkpoints()
    result = _race_result()
    start_before = list(start)
    result_before = list(result)
    after_table(start, result, 2024)
    provisional_table(
        start,
        [row.driver_number for row in result if row.position is not None],
        2024,
        fastest_lap_driver_number=31,
    )
    assert start == start_before
    assert result == result_before


def test_the_derivation_is_deterministic_and_order_independent() -> None:
    """Two calls are equal, and the row order of the inputs does not matter."""
    start = _start_checkpoints()
    result = _race_result()
    first = after_table(start, result, 2024)
    assert after_table(start, result, 2024) == first
    assert after_table(list(reversed(start)), list(reversed(result)), 2024) == first
    order = [row.driver_number for row in result if row.position is not None]
    assert provisional_table(start, order, 2024) == provisional_table(
        start, order, 2024
    )


# --- validation against the source's own checkpoints ---------------------------------


def test_recorded_session_result_points_match_the_declared_scale() -> None:
    """The source's own session_result.points equals the declared scale, row by row."""
    rows = _load("session_result")
    assert len(rows) == 20
    for row in rows:
        position = None if row["position"] is None else int(row["position"])
        assert float(row["points"]) == points_for_position(2024, position)


def test_recorded_after_table_reproduces_every_recorded_current_points() -> None:
    """`points_current == points_start + result points` holds for all 23 drivers."""
    after = {
        row.driver_number: row.points
        for row in after_table(_start_checkpoints(), _race_result(), 2024)
    }
    recorded = {
        int(row["driver_number"]): float(row["points_current"])
        for row in _load("championship_drivers")
    }
    assert len(recorded) == 23
    assert after == recorded

    start = {row.driver_number: row.points for row in _start_checkpoints()}
    without_result = sorted(
        set(after) - {int(row["driver_number"]) for row in _load("session_result")}
    )
    assert without_result == [2, 3, 50]
    for number in without_result:
        assert after[number] == start[number]


def test_recorded_fastest_lap_holder_outside_the_top_ten_scores_nothing() -> None:
    """The recorded instance: driver 31 sets the fastest lap from P18, so 0 points.

    The recorded session's fastest valid lap is driver 31 on lap 53 (97.33 s), and driver
    31 is classified P18, so the 2024 top-10 condition refuses the point: the driver's
    points stay at the recorded 5.0 and the whole recorded table is unchanged. This is the
    probe a naive wiring would get wrong, so it is pinned against the recorded bytes.
    """
    valid = [row for row in _load("laps") if row.get("lap_duration") is not None]
    fastest = min(valid, key=lambda row: float(row["lap_duration"]))
    assert (int(fastest["driver_number"]), int(fastest["lap_number"])) == (31, 53)
    assert float(fastest["lap_duration"]) == 97.33

    start = _start_checkpoints()
    plain = _race_result()
    assert next(row for row in plain if row.driver_number == 31).position == 18
    flagged = [
        RaceResult(row.driver_number, row.position, fastest_lap=row.driver_number == 31)
        for row in plain
    ]
    recorded = {
        int(row["driver_number"]): float(row["points_current"])
        for row in _load("championship_drivers")
    }
    after = {row.driver_number: row.points for row in after_table(start, flagged, 2024)}
    assert after == recorded
    assert after[31] == 5.0

    classified = sorted(
        (row for row in plain if row.position is not None),
        key=lambda row: cast(int, row.position),
    )
    running_order = [row.driver_number for row in classified]
    provisional = provisional_table(
        start, running_order, 2024, fastest_lap_driver_number=31
    )
    assert provisional == after_table(start, plain, 2024)
    assert provisional == provisional_table(start, running_order, 2024)


def test_recorded_position_current_is_monotone_in_points_current() -> None:
    """Row by row, a later recorded position never carries more recorded points."""
    rows = sorted(
        _load("championship_drivers"), key=lambda row: int(row["position_current"])
    )
    assert [int(row["position_current"]) for row in rows] == list(range(1, 24))
    for ahead, behind in zip(rows, rows[1:], strict=False):
        assert float(ahead["points_current"]) >= float(behind["points_current"])


def test_recorded_tie_order_is_a_finding_not_an_identity() -> None:
    """The recorded fields do not determine the source's order within a tie group.

    Our declared rule (driver_number ascending) disagrees with `position_current` on the
    **8** rows of the four tie groups; start-position stability, the other defensible
    candidate, still disagrees on **2** (drivers 43 and 31, tied at 5, swap). Neither rule
    reproduces the source, so no test may claim it does; what is pinned here is the
    measured disagreement, not a code expectation.
    """
    rows = _load("championship_drivers")
    source_position = {
        int(row["driver_number"]): int(row["position_current"]) for row in rows
    }

    declared = {
        row.driver_number: row.position
        for row in after_table(_start_checkpoints(), _race_result(), 2024)
    }
    declared_disagreements = sorted(
        n for n in source_position if source_position[n] != declared[n]
    )
    assert declared_disagreements == [2, 3, 10, 20, 23, 24, 31, 43]
    assert len(declared_disagreements) == 8

    stable = [
        row["driver_number"]
        for row in sorted(
            rows,
            key=lambda row: (-float(row["points_current"]), int(row["position_start"])),
        )
    ]
    stable_disagreements = [
        n for index, n in enumerate(stable, start=1) if source_position[int(n)] != index
    ]
    assert stable_disagreements == [31, 43]

    tie_groups = {}
    for row in rows:
        tie_groups.setdefault(float(row["points_current"]), []).append(
            int(row["driver_number"])
        )
    assert {
        points: members for points, members in tie_groups.items() if len(members) > 1
    } == {
        12.0: [23, 3],
        8.0: [20, 10],
        5.0: [43, 31],
        0.0: [24, 2, 77],
    }


def test_recorded_team_totals_disagree_with_the_recorded_driver_rows() -> None:
    """A team's recorded points are not the sum of its recorded drivers' points.

    The global total agrees exactly (**2078** both ways), but the per-team sum does not:
    Ferrari differs by **6**, Haas F1 Team by **1** and RB by **12**, while the other seven
    teams match. The three differences sum to **19**, exactly the points of the three
    `championship_drivers` rows that carry no team in the recorded entry list: driver 3
    (12), driver 50 (7) and driver 2 (0). Driver 3's 12 accounts for RB's remainder and
    driver 2's 0 for Williams' 0, but Ferrari's 6 and Haas' 1 together equal a single
    unmapped row of 7, a split the recorded driver table cannot express. This is a
    property of the source, not of the derivation, and it is pinned rather than smoothed.
    """
    teams = {str(row["team_name"]): row for row in _load("championship_teams")}
    championship_drivers = _load("championship_drivers")
    entry_list = {int(row["driver_number"]): row for row in _load("drivers")}

    assert (
        sum(float(row["points_current"]) for row in championship_drivers)
        == sum(float(row["points_current"]) for row in teams.values())
        == 2078.0
    )

    divergence: dict[str, float] = {}
    for name, team in teams.items():
        members = [
            row
            for row in championship_drivers
            if entry_list.get(int(row["driver_number"]), {}).get("team_name") == name
        ]
        divergence[name] = float(team["points_current"]) - sum(
            float(row["points_current"]) for row in members
        )
    assert {name: gap for name, gap in divergence.items() if gap != 0.0} == {
        "Ferrari": 6.0,
        "Haas F1 Team": 1.0,
        "RB": 12.0,
    }

    unmapped = {
        int(row["driver_number"]): float(row["points_current"])
        for row in championship_drivers
        if int(row["driver_number"]) not in entry_list
    }
    assert unmapped == {2: 0.0, 3: 12.0, 50: 7.0}
    assert sum(divergence.values()) == sum(unmapped.values()) == 19.0


# --- the declared qualifying rules (F06c T2) -----------------------------------------
#
# Nothing in this section reads a fixture, on purpose. The declared table must not be
# derived from, or pinned to, the captured session: it is the input the cutoff motor will
# be checked *against*, so every value below is a pin on the declaration itself. The
# capture's only role was to measure these values once (F06c L9), and the numbers asserted
# here are that measurement written down as a rule - 3 phases, 18/15/12 minutes,
# 20 -> 15 -> 10 participants - not a value read at runtime.


def test_the_declared_qualifying_rules_resolve_for_the_recorded_season() -> None:
    """2024 main qualifying is declared, and it is the season the corpus declares."""
    rules = qualifying_rules(2024, QualifyingSessionKind.MAIN_QUALIFYING)
    assert isinstance(rules, QualifyingRules)
    assert rules.season == 2024
    assert rules.session_kind == QualifyingSessionKind.MAIN_QUALIFYING
    # The declared kind's value *is* the source's own `sessions.session_type` literal for
    # 9608, so the recorded payload reaches the declaration with no mapping in between.
    assert QualifyingSessionKind.MAIN_QUALIFYING == "Qualifying"
    assert qualifying_rules(2024, "Qualifying") is rules
    assert QUALIFYING_RULES[(2024, QualifyingSessionKind.MAIN_QUALIFYING)] is rules
    # S4's injected default: the declared qualifying season is the recorded season
    # `championship.py` declares, so a caller passing that default lands on this row.
    assert rules.season == RECORDED_SEASON


def test_the_declared_phase_structure_is_the_measured_one() -> None:
    """Three phases of 18, 15 and 12 minutes, with 20, 15 and 10 participants."""
    phases = qualifying_rules(2024, QualifyingSessionKind.MAIN_QUALIFYING).phases
    assert [
        (phase.phase, phase.duration_minutes, phase.participants) for phase in phases
    ] == [(1, 18, 20), (2, 15, 15), (3, 12, 10)]
    assert all(isinstance(phase, QualifyingPhase) for phase in phases)


def test_the_advancement_boundary_is_the_last_advancing_position() -> None:
    """The boundary the declared counts draw: P15 advances out of phase 1, P16 does not.

    The declared rules carry phase *lengths*, not absolute windows, so the boundary they
    state is the advancement one - twenty participants, fifteen of which continue - and the
    instant-level boundary (the last instant of a phase versus the first of the next) can
    only be drawn once a start instant arrives from the data, which is T3's business. Here
    the boundary is exact rather than approximate: 15 is inside the advancing set and 16 is
    the first position outside it, twice over, and the last phase classifies its ten.
    """
    first, second, third = qualifying_rules(
        2024, QualifyingSessionKind.MAIN_QUALIFYING
    ).phases

    advancing_after_phase_one = set(range(1, second.participants + 1))
    assert 15 in advancing_after_phase_one
    assert 16 not in advancing_after_phase_one
    assert set(range(1, first.participants + 1)) - advancing_after_phase_one == {
        16,
        17,
        18,
        19,
        20,
    }

    advancing_after_phase_two = set(range(1, third.participants + 1))
    assert 10 in advancing_after_phase_two
    assert 11 not in advancing_after_phase_two
    assert set(range(1, second.participants + 1)) - advancing_after_phase_two == {
        11,
        12,
        13,
        14,
        15,
    }

    assert third.participants == 10  # the classified field of the last declared phase


def test_the_declared_qualifying_shape_declares_no_inter_phase_gap() -> None:
    """The 7- and 8-minute breaks are measured, not uniform, and deliberately not a rule."""
    assert tuple(field.name for field in fields(QualifyingRules)) == (
        "season",
        "session_kind",
        "phases",
    )
    assert tuple(field.name for field in fields(QualifyingPhase)) == (
        "phase",
        "duration_minutes",
        "participants",
    )


def test_an_undeclared_qualifying_season_is_refused() -> None:
    """Only 2024 is declared; any other season is an error naming what is declared."""
    assert issubclass(QualifyingRulesError, StandingsInputError)
    for season in (2023, 2025, 9612):
        with pytest.raises(QualifyingRulesError) as raised:
            qualifying_rules(season, QualifyingSessionKind.MAIN_QUALIFYING)
        message = str(raised.value)
        assert repr(season) in message
        assert "declared qualifying seasons: [2024]" in message


def test_an_undeclared_session_kind_is_refused() -> None:
    """Sprint Qualifying was never captured, so it is refused, never defaulted."""
    for kind in ("Sprint Qualifying", "Sprint", "Practice", "Race", ""):
        with pytest.raises(QualifyingRulesError) as raised:
            qualifying_rules(2024, kind)
        message = str(raised.value)
        assert repr(kind) in message
        assert "declared session kinds for 2024: ['Qualifying']" in message


def test_the_declared_qualifying_dataset_is_read_only() -> None:
    """Neither the table nor a declared rule can be edited in place by any caller."""
    assert not isinstance(QUALIFYING_RULES, dict)
    read_only: Any = QUALIFYING_RULES
    with pytest.raises(TypeError):
        read_only[(2024, QualifyingSessionKind.MAIN_QUALIFYING)] = None

    rules = qualifying_rules(2024, QualifyingSessionKind.MAIN_QUALIFYING)
    with pytest.raises(FrozenInstanceError):
        rules.season = 2025  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        rules.phases = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        rules.phases[0].duration_minutes = 20  # type: ignore[misc]
