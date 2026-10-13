"""Offline acceptance tests for the F09g U3b bounded championship adapter.

Everything here is pure: the adapter reads no file, opens no store, reads no clock and
draws no random number, so one moment's context is a function of its inputs alone and two
calls on the same inputs are equal. The only file this suite touches is the recorded
fixture corpus, and only in the validation that re-derives the source's own team
checkpoints through the public adapter.

**The four cases the unit promises to handle are exercised one by one**, because a
championship picture that silently omits them would tell a seat something the corpus does
not support:

* a driver with no ``championship_drivers`` row;
* a driver with no ``session_result`` row, whose race points are therefore not attributed
  to their team's race delta;
* a driver whose entry-list team cannot be resolved in the ``championship_teams`` rows;
* a moment before any completed lap, where the picture is the source's own pre-race one.

**The U3a impossibility is not re-derived here, it is spent.** ``standings.py`` measured
that a season team table cannot be rebuilt from the driver rows (the entry list is
session-scoped, and one driver row carries one team), so the adapter takes the season team
total from the source's own ``championship_teams`` row and derives only this race's delta.
The recorded validation below pins the consequence: for all ten teams, the source's own
``points_start`` plus the adapter's derived delta equals the source's own
``points_current`` exactly, and the team's provisional position equals ``position_current``.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any


import f1show.championship
from f1show.championship import (
    RECORDED_SEASON,
    ChampionshipSource,
    ChampionshipUnavailable,
    build_championship_source,
    championship_context,
    render_championship,
)
from f1show.collector import collect_session_events
from f1show.events import EventType

SESSION_KEY = 9617
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "openf1"
CHAMPIONSHIP_SOURCE = Path(inspect.getsourcefile(f1show.championship) or "").resolve()


def _load(name: str) -> list[dict[str, Any]]:
    """Read one recorded fixture family verbatim."""
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def detected(
    *,
    index: int,
    event_type: EventType = EventType.POSITION_CHANGE,
    family: str = "position",
    evidence: dict[str, object] | None = None,
    driver_number: int | None = 1,
) -> Any:
    """Build one detected event with the recorded evidence shape."""
    if evidence is None:
        evidence = {"position": 1}
    from f1show.collector import DetectedEvent

    return DetectedEvent(
        event_type=event_type,
        family=family,
        session_key=SESSION_KEY,
        record_index=index,
        driver_number=driver_number,
        timestamp_field="date",
        timestamp_value=None,
        timestamp_unknown_reason="family_carries_no_timestamp_field",
        evidence=evidence,
    )


def race_events() -> tuple[Any, ...]:
    """A three-driver race: one completed lap, then the order settling to 2, 1, 3."""
    return (
        detected(
            index=0,
            event_type=EventType.LAP_COMPLETED,
            family="laps",
            evidence={"lap_number": 1, "lap_duration": 100.0},
            driver_number=1,
        ),
        detected(index=1, evidence={"position": 1}, driver_number=2),
        detected(index=2, evidence={"position": 2}, driver_number=1),
        detected(index=3, evidence={"position": 3}, driver_number=3),
    )


def small_source(**overrides: Any) -> ChampionshipSource:
    """A three-driver, two-team recorded-shaped source, plus the driver-to-team join."""
    payloads: dict[str, list[dict[str, object]]] = {
        "championship_drivers": [
            {"driver_number": 1, "position_start": 1, "points_start": 100.0},
            {"driver_number": 2, "position_start": 2, "points_start": 90.0},
            {"driver_number": 3, "position_start": 3, "points_start": 80.0},
        ],
        "championship_teams": [
            {"team_name": "Alpha", "position_start": 1, "points_start": 200.0},
            {"team_name": "Beta", "position_start": 2, "points_start": 150.0},
        ],
        "session_result": [
            {"driver_number": 1, "position": 1, "points": 25.0},
            {"driver_number": 2, "position": 2, "points": 18.0},
        ],
    }
    payloads.update(overrides)
    return build_championship_source(payloads, season=RECORDED_SEASON)


#: The session's entry list for the small source: driver 1 and 3 race for Alpha.
SMALL_TEAMS = {1: "Alpha", 2: "Beta", 3: "Alpha"}


# --- the provisional driver derivation ----------------------------------------------


def test_the_current_driver_gets_a_provisional_position_points_and_gap() -> None:
    """The start checkpoints plus this race's running-order points, under the declared rules.

    The running order is 2, 1, 3, so driver 2 scores 25 (90 + 25 = 115), driver 1 scores 18
    (100 + 18 = 118) and driver 3 scores 15 (80 + 15 = 95). Driver 1 therefore leads on 118
    and driver 2 sits P2 on 115, a gap of 3.
    """
    context = championship_context(
        race_events(),
        driver_number=2,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )

    assert context.driver_position == 2
    assert context.driver_points == 115.0
    assert context.leader_driver_number == 1
    assert context.leader_points == 118.0
    assert context.gap_to_leader == 3.0
    assert context.driver_classified is True
    assert context.unavailable == ()


def test_the_driver_not_yet_observed_keeps_the_start_points() -> None:
    """A driver absent from the running order scores nothing this race so far."""
    events = tuple(event for event in race_events() if event.driver_number != 3)
    context = championship_context(
        events,
        driver_number=3,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )

    assert context.driver_position == 3  # 80 points, behind 1 (118) and 2 (115)
    assert context.driver_points == 80.0
    assert context.gap_to_leader == 38.0


# --- the four named cases -----------------------------------------------------------


def test_a_driver_with_no_championship_row_is_stated_not_guessed() -> None:
    """A driver the start checkpoints never saw has no derivable position."""
    context = championship_context(
        race_events(),
        driver_number=4,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )

    assert context.driver_position is None
    assert context.driver_points is None
    assert context.gap_to_leader is None
    # The leader is still derivable from the rows the source does carry.
    assert context.leader_driver_number == 1
    assert context.leader_points == 118.0
    assert ChampionshipUnavailable.NO_CHAMPIONSHIP_ROW in context.unavailable


def test_a_row_less_driver_inside_the_order_withholds_the_whole_table() -> None:
    """One unknown runner makes every later position wrong, so the table is withheld."""
    events = race_events() + (
        detected(index=4, evidence={"position": 4}, driver_number=4),
    )
    context = championship_context(
        events,
        driver_number=1,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )

    assert context.driver_position is None
    assert context.leader_driver_number is None
    assert context.leader_points is None
    assert context.gap_to_leader is None
    assert ChampionshipUnavailable.NO_CHAMPIONSHIP_ROW in context.unavailable


def test_a_driver_with_no_session_result_row_does_not_feed_the_team_delta() -> None:
    """The mode's own race points stay on the driver line but leave the team total alone.

    Driver 3 finishes this race so far in P3, worth 15 points, but has no
    ``session_result`` row, so the race awards them nothing and their team Alpha keeps only
    driver 1's classified 18 (200 + 18 = 218). Driver 2's Beta gets 150 + 25 = 175.
    """
    context = championship_context(
        race_events(),
        driver_number=3,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )

    assert context.driver_points == 95.0
    assert context.driver_classified is False
    assert context.team_name == "Alpha"
    assert context.team_position == 1
    assert context.team_points == 218.0

    classified = championship_context(
        race_events(),
        driver_number=1,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )
    assert classified.driver_classified is True


def test_an_unresolvable_team_leaves_the_team_fields_unknown() -> None:
    """A driver absent from the entry list, or a team absent from the team rows, is stated."""
    absent_driver = championship_context(
        race_events(),
        driver_number=1,
        source=small_source(),
        team_of_driver={2: "Beta", 3: "Alpha"},
    )
    assert absent_driver.team_name is None
    assert absent_driver.team_position is None
    assert absent_driver.team_points is None
    assert ChampionshipUnavailable.UNRESOLVABLE_TEAM in absent_driver.unavailable

    absent_team = championship_context(
        race_events(),
        driver_number=1,
        source=small_source(),
        team_of_driver={1: "Gamma", 2: "Beta", 3: "Alpha"},
    )
    assert absent_team.team_name is None
    assert ChampionshipUnavailable.UNRESOLVABLE_TEAM in absent_team.unavailable


def test_before_any_completed_lap_the_picture_is_the_sources_pre_race_one() -> None:
    """No window, no provisional derivation: the source's own start row is reported.

    The pre-race leader is the row whose ``position_start`` is 1 (driver 1 on 100 points),
    the driver's gap is the difference of the start points, and each team's provisional
    points are its source ``points_start`` with no race delta at all.
    """
    pre_race = (
        detected(index=0, evidence={"position": 1}, driver_number=1),
        detected(index=1, evidence={"position": 2}, driver_number=2),
    )
    context = championship_context(
        pre_race,
        driver_number=2,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )

    assert ChampionshipUnavailable.NO_RUNNING_ORDER in context.unavailable
    assert context.driver_position == 2
    assert context.driver_points == 90.0
    assert context.leader_driver_number == 1
    assert context.leader_points == 100.0
    assert context.gap_to_leader == 10.0
    assert context.team_name == "Beta"
    assert context.team_position == 2
    assert context.team_points == 150.0


def test_an_empty_prefix_is_before_any_completed_lap() -> None:
    """The declared empty-prefix case is the same pre-race handling, not a crash."""
    context = championship_context(
        (),
        driver_number=1,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )

    assert ChampionshipUnavailable.NO_RUNNING_ORDER in context.unavailable
    assert context.driver_points == 100.0
    assert context.team_points == 200.0


# --- purity, determinism and a bounded surface --------------------------------------


def test_two_calls_on_the_same_inputs_are_equal() -> None:
    events = race_events()
    source = small_source()
    first = championship_context(
        events, driver_number=2, source=source, team_of_driver=SMALL_TEAMS
    )
    second = championship_context(
        events, driver_number=2, source=source, team_of_driver=dict(SMALL_TEAMS)
    )
    assert first == second


def test_inputs_are_never_mutated() -> None:
    events = list(race_events())
    events_before = list(events)
    teams = dict(SMALL_TEAMS)
    teams_before = dict(teams)
    source = small_source()

    championship_context(events, driver_number=2, source=source, team_of_driver=teams)

    assert events == events_before
    assert teams == teams_before


def test_the_adapter_module_carries_no_io_clock_or_random_source() -> None:
    """The module is pure by inspection, not only by claim."""
    source = CHAMPIONSHIP_SOURCE.read_text(encoding="utf-8")
    assert CHAMPIONSHIP_SOURCE.name == "championship.py"
    for forbidden in (
        "open(",
        "datetime.now",
        "time.time",
        "import random",
        "random.",
        "httpx",
        "pathlib",
        "socket",
    ):
        assert forbidden not in source, (
            f"the championship adapter must stay pure, but its source names {forbidden!r}"
        )


def test_the_module_records_the_u3a_team_impossibility() -> None:
    """The two measured reasons a season team table cannot come from the driver rows."""
    docstring = f1show.championship.__doc__ or ""
    assert "session-scoped" in docstring
    assert "one team per driver per session" in docstring
    assert "championship_teams" in docstring


# --- the recorded validation, through the public adapter ----------------------------


def recorded_source() -> ChampionshipSource:
    """The recorded session's three championship families, as the loader hands them over."""
    return build_championship_source(
        {
            "championship_drivers": _load("championship_drivers"),
            "championship_teams": _load("championship_teams"),
            "session_result": _load("session_result"),
        },
        season=RECORDED_SEASON,
    )


def recorded_entry_list() -> dict[int, str]:
    return {
        int(row["driver_number"]): str(row["team_name"]) for row in _load("drivers")
    }


def recorded_driver_directory() -> dict[int, tuple[str, str]]:
    """The recorded session's joined driver directory, as the booth holds it."""
    return {
        int(row["driver_number"]): (str(row["full_name"]), str(row["team_name"]))
        for row in _load("drivers")
    }


def recorded_events() -> Sequence[Any]:
    payloads = {
        family: _load(family)
        for family in ("position", "laps", "pit", "stints", "race_control")
    }
    return collect_session_events(SESSION_KEY, payloads)


def test_the_recorded_source_rows_are_read_without_loss() -> None:
    source = recorded_source()

    assert len(source.drivers) == 23
    assert len(source.teams) == 10
    assert len(source.classifications) == 20
    assert source.season == RECORDED_SEASON


def test_the_recorded_final_moment_reproduces_every_team_checkpoint() -> None:
    """Every team's derived total and position equals the source's own after-checkpoint.

    The season base is the source's ``championship_teams`` row, so the U3a impossibility
    (a season table rebuilt from the driver rows) never arises; the identity pinned here
    is that the **derived race delta** closes the gap to ``points_current`` for all ten
    teams. A rule that silently dropped a classified driver would fail on the team it
    belongs to.
    """
    events = recorded_events()
    source = recorded_source()
    entry = recorded_entry_list()
    teams = _load("championship_teams")

    for row in teams:
        name = str(row["team_name"])
        driver = next(number for number, team in entry.items() if team == name)
        context = championship_context(
            events,
            driver_number=driver,
            source=source,
            team_of_driver=entry,
        )
        assert context.team_name == name, f"team {name} did not resolve"
        assert context.team_points == float(row["points_current"]), (
            f"team {name} derived {context.team_points} against the recorded "
            f"{row['points_current']}"
        )
        assert context.team_position == int(row["position_current"]), (
            f"team {name} derived position {context.team_position} against the recorded "
            f"{row['position_current']}"
        )


def test_the_recorded_final_moment_states_the_measured_current_driver() -> None:
    """The last recorded event's own block, quoted as measured.

    The final recorded event is a stint start for driver 31 (Esteban OCON, Alpine). The
    running order at that moment is the full twenty-car field, so driver 31 sits P18 on
    their recorded 5 start points (nothing on the declared scale at P18), the leader is
    driver 1 (Max VERSTAPPEN) on 354, a gap of 349, and Alpine is P9 on 13.
    """
    events = recorded_events()
    context = championship_context(
        events,
        driver_number=events[-1].driver_number,
        source=recorded_source(),
        team_of_driver=recorded_entry_list(),
    )

    assert context.driver_number == 31
    assert context.driver_position == 18
    assert context.driver_points == 5.0
    assert context.leader_driver_number == 1
    assert context.leader_points == 354.0
    assert context.gap_to_leader == 349.0
    assert context.team_name == "Alpine"
    assert context.team_position == 9
    assert context.team_points == 13.0


def test_the_recorded_final_moment_provisional_agrees_with_the_declared_tie_order() -> (
    None
):
    """The driver side is the reviewed ``provisional_table`` applied to the live order.

    The recorded derived position is checked against ``standings.provisional_table``
    computed independently in the test, so the adapter is pinned as a wiring of the
    reviewed derivation rather than a second implementation of it.
    """
    from f1show.standings import StartStanding, provisional_table

    events = recorded_events()
    source = recorded_source()
    order = _running_order(events)
    table = provisional_table(
        [StartStanding(row.driver_number, row.points_start) for row in source.drivers],
        order,
        RECORDED_SEASON,
    )
    expected = {standing.driver_number: standing for standing in table}

    for number in order:
        context = championship_context(
            events,
            driver_number=number,
            source=source,
            team_of_driver=recorded_entry_list(),
        )
        assert context.driver_position == expected[number].position
        assert context.driver_points == expected[number].points


def _running_order(events: Sequence[Any]) -> tuple[int, ...]:
    """The test-side running order: the same window rule, read from the recorded events."""
    start = next(
        (
            index
            for index, event in enumerate(events)
            if event.event_type is EventType.LAP_COMPLETED
        ),
        len(events),
    )
    latest: dict[int, int] = {}
    for event in events[start:]:
        if event.event_type is not EventType.POSITION_CHANGE:
            continue
        number = event.driver_number
        position = event.evidence.get("position")
        if (
            number is None
            or not isinstance(position, int)
            or isinstance(position, bool)
        ):
            continue
        latest[number] = position
    return tuple(sorted(latest, key=lambda number: (latest[number], number)))


# --- the rendered block -------------------------------------------------------------


def test_render_states_the_three_lines_in_plain_prose() -> None:
    context = championship_context(
        race_events(),
        driver_number=2,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )
    block = render_championship(
        context, {1: ("One Racer", "Alpha"), 2: ("Two Racer", "Beta")}
    )

    assert block.splitlines()[0] == "CHAMPIONSHIP:"
    assert "Two Racer" in block
    assert "P2 on 115 points" in block
    assert "One Racer" in block and "118 points" in block
    assert "gap of 3 points" in block
    assert "Beta" in block and "P2 on 175 points" in block
    assert not any(character in block for character in "[](){}"), block


def test_render_states_the_pre_race_and_unknown_cases_before_it_guesses() -> None:
    pre_race = championship_context(
        (),
        driver_number=2,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )
    block = render_championship(pre_race, {})
    assert "pre-race" in block
    assert not any(character in block for character in "[](){}"), block

    unknown = championship_context(
        race_events(),
        driver_number=99,
        source=small_source(),
        team_of_driver=SMALL_TEAMS,
    )
    unknown_block = render_championship(unknown, {})
    assert "no championship checkpoint" in unknown_block
    assert not any(character in block for character in "[](){}"), unknown_block


# --- U3b-R1: a tie is a convention, stated as one -----------------------------------


def test_the_recorded_final_event_states_the_tie_instead_of_a_settled_position() -> (
    None
):
    """The measured contradiction, stated as a convention rather than as a fact.

    The final recorded event's driver is 31. Their derived provisional position is **P18** on
    5 points, while the source's own ``position_current`` for that driver is **P19** - the
    source puts driver 43 at P18. The points agree (both drivers are on 5), so only the order
    inside the tie differs, because the declared rule orders equal points by ``driver_number``
    and the source does not. The block must therefore state the sharing and must not render
    the bare settled form for a tied driver; the arithmetic is untouched.
    """
    events = recorded_events()
    context = championship_context(
        events,
        driver_number=31,
        source=recorded_source(),
        team_of_driver=recorded_entry_list(),
    )

    assert context.driver_position == 18
    assert context.driver_points == 5.0
    assert context.driver_tied_with == 1
    source_row = next(
        row for row in _load("championship_drivers") if int(row["driver_number"]) == 31
    )
    assert int(source_row["position_current"]) == 19, (
        "the source contradicts the derived order inside the 5-point tie, which is the "
        "measured basis for this test"
    )
    other = next(
        row for row in _load("championship_drivers") if int(row["driver_number"]) == 43
    )
    assert (float(source_row["points_current"]), int(other["position_current"])) == (
        5.0,
        18,
    ), "driver 43 is the other driver on 5 points, and the source puts them at P18"

    block = render_championship(context, recorded_driver_directory())
    assert "P18 on 5 points, tied with 1 other driver" in block, block
    assert "P18 on 5 points in the season championship" not in block, (
        "a tied position must not be rendered in the bare settled form"
    )
    # The numbers are identical: only the tied position's wording changed.
    assert "Max VERSTAPPEN" in block and "354 points" in block, block
    assert "gap of 349 points" in block, block
    assert "Alpine is P9 on 13 points" in block, block
    assert not any(character in block for character in "[](){}"), block


def test_a_driver_alone_in_their_points_group_keeps_the_bare_position() -> None:
    """The lone holder's wording does not move: no tie qualifier appears at all."""
    context = championship_context(
        recorded_events(),
        driver_number=1,
        source=recorded_source(),
        team_of_driver=recorded_entry_list(),
    )

    assert context.driver_tied_with == 0
    assert context.team_tied_with == 0
    block = render_championship(context, recorded_driver_directory())
    assert "P1 on 354 points in the season championship" in block, block
    assert "tied with" not in block, block


def test_the_recorded_three_way_tie_at_zero_is_stated_with_its_count() -> None:
    """The 0-point group ``{2, 24, 77}`` renders each member as tied with two others."""
    events = recorded_events()
    source = recorded_source()
    entry = recorded_entry_list()
    contexts = {
        number: championship_context(
            events, driver_number=number, source=source, team_of_driver=entry
        )
        for number in (2, 24, 77)
    }

    assert {n: c.driver_points for n, c in contexts.items()} == {
        2: 0.0,
        24: 0.0,
        77: 0.0,
    }
    assert {n: c.driver_position for n, c in contexts.items()} == {
        2: 21,
        24: 22,
        77: 23,
    }
    assert {n: c.driver_tied_with for n, c in contexts.items()} == {2: 2, 24: 2, 77: 2}
    block = render_championship(contexts[2], recorded_driver_directory())
    assert "P21 on 0 points, tied with 2 other drivers" in block, block
    assert "P21 on 0 points in the season championship" not in block, block


def test_the_team_line_states_a_shared_total_because_teams_can_tie() -> None:
    """The team answer: two teams can share a total, so the same treatment applies.

    The recorded pre-race rows alone tie Haas F1 Team and RB on 34, so the team line is a
    declared convention too and is stated as tied. The team's position and points do not
    move; the tie count is rendered, never used.
    """
    context = championship_context(
        (),
        driver_number=20,
        source=recorded_source(),
        team_of_driver=recorded_entry_list(),
    )

    assert context.team_name == "Haas F1 Team"
    assert (context.team_position, context.team_points, context.team_tied_with) == (
        6,
        34.0,
        1,
    )
    teams = {
        str(row["team_name"]): float(row["points_start"])
        for row in _load("championship_teams")
    }
    assert teams["Haas F1 Team"] == teams["RB"] == 34.0, (
        "the tied team is RB, on the same source start total"
    )
    block = render_championship(context, recorded_driver_directory())
    assert "Haas F1 Team is P6 on 34 points, tied with 1 other team" in block, block


def test_the_tie_treatment_changes_only_the_wording_of_the_measured_turns() -> None:
    """The measured blast radius of the tie qualifier over the recorded session.

    Of the recorded session's **1,648** turns, **462** carry a driver inside a shared points
    total and **8** carry a team inside one, **470** in all (the sets overlap). Every one of
    those turns gets the tie qualifier; the other 1,178 keep their wording byte for byte. The
    numbers are a measurement, not a target: a rule change moves them and this pin fails.
    """
    events = recorded_events()
    source = recorded_source()
    entry = recorded_entry_list()
    driver_turns = 0
    team_turns = 0
    either = 0
    for index, event in enumerate(events):
        context = championship_context(
            events[: index + 1],
            driver_number=event.driver_number,
            source=source,
            team_of_driver=entry,
        )
        if context.driver_tied_with > 0:
            driver_turns += 1
        if context.team_tied_with > 0:
            team_turns += 1
        if context.driver_tied_with > 0 or context.team_tied_with > 0:
            either += 1

    assert len(events) == 1648
    assert (driver_turns, team_turns, either) == (462, 8, 470)
