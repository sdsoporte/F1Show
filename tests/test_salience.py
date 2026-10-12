"""Offline acceptance tests for the F09g window salience projection.

Everything here is pure: the projection reads no file, opens no store, reads no clock and
draws no random number, so a summary is a function of the events alone and two calls on the
same events are equal. The only file this suite touches is the recorded fixture corpus, and
only in the one design-anchored test that reproduces the design's measured
start-to-lap-5 table.

**What is measured, not assumed.** The design's own table is the acceptance criterion:
biggest gain ZHOU Guanyu 19 to 14, the tied biggest losses ALONSO 5 to 10 and OCON 13 to
18, the busiest ALBON with 13 position changes and a 34.983 s stop on lap 3, a DOUBLE
YELLOW in sector 3, and the derived fastest lap SAINZ 99.923 on lap 2. A test that adjusted
those numbers to fit the projection would hide the only evidence the projection has, so the
table is asserted as written and a disagreement fails.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from f1show import salience
from f1show.collector import collect_session_events
from f1show.events import EventType
from f1show.salience import (
    FAST_OUTLIER_FACTOR,
    SLOW_OUTLIER_FACTOR,
    FlagReading,
    LapReading,
    PitReading,
    PositionMove,
    render_salience,
    salience_summary,
)

UTC = dt.timezone.utc
SESSION_KEY = 9617
T0 = dt.datetime(2024, 3, 2, 15, 0, 5, tzinfo=UTC)

#: The recorded fixture corpus, read the same way ``tests/test_run.py`` reads it.
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "openf1"
EVENT_FAMILIES = ("position", "laps", "pit", "stints", "race_control")

#: A reference-shaped token: ``family[record].field``. The CONTEXT block must never carry
#: one, or a new citable token would enter the prompt.
REFERENCE_TOKEN = re.compile(r"[a-z_]+\[\d+\]\.[a-z0-9_]+")

#: Every bracket character. The CONTEXT block is declared to carry none of them.
BRACKETS = "[](){}"


def detected(
    *,
    index: int,
    event_type: EventType = EventType.POSITION_CHANGE,
    family: str = "position",
    evidence: dict[str, object] | None = None,
    driver_number: int | None = 1,
    timestamp: dt.datetime | None = T0,
    session_key: int = SESSION_KEY,
):
    """Build one detected event with the recorded evidence shape the collector emits."""
    from f1show.collector import DetectedEvent

    return DetectedEvent(
        event_type=event_type,
        family=family,
        session_key=session_key,
        record_index=index,
        driver_number=driver_number,
        timestamp_field="date" if timestamp is not None else None,
        timestamp_value=timestamp,
        timestamp_unknown_reason=(
            None if timestamp is not None else "family_carries_no_timestamp_field"
        ),
        evidence={} if evidence is None else evidence,
    )


def lap(index: int, lap_number: int, duration: object, *, driver_number: int = 1):
    """One ``LAP_COMPLETED`` event; the duration may be null, as the corpus allows."""
    return detected(
        index=index,
        event_type=EventType.LAP_COMPLETED,
        family="laps",
        evidence={"lap_number": lap_number, "lap_duration": duration},
        driver_number=driver_number,
    )


def pos(index: int, driver_number: int, position: int):
    """One ``POSITION_CHANGE`` event."""
    return detected(
        index=index, evidence={"position": position}, driver_number=driver_number
    )


def pit(
    index: int,
    driver_number: int,
    lap_number: int,
    *,
    pit_duration: object = None,
    lane_duration: object = None,
    stop_duration: object = None,
):
    """One ``PIT_STOP`` event carrying the three recorded durations."""
    return detected(
        index=index,
        event_type=EventType.PIT_STOP,
        family="pit",
        evidence={
            "lap_number": lap_number,
            "pit_duration": pit_duration,
            "lane_duration": lane_duration,
            "stop_duration": stop_duration,
        },
        driver_number=driver_number,
    )


def flag(
    index: int,
    flag_value: object,
    *,
    sector: object = None,
    message: object = None,
    lap_number: object = None,
    category: object = "Flag",
):
    """One ``RACE_CONTROL`` event with the recorded race-control shapes."""
    return detected(
        index=index,
        event_type=EventType.RACE_CONTROL,
        family="race_control",
        evidence={
            "category": category,
            "flag": flag_value,
            "sector": sector,
            "message": message,
            "lap_number": lap_number,
        },
        driver_number=None,
    )


# --- The empty and the story-less window ---------------------------------------


def test_an_empty_input_returns_an_explicitly_empty_summary() -> None:
    summary = salience_summary(())

    assert summary.is_empty
    assert summary.event_count == 0
    assert summary.latest_lap is None
    assert summary.biggest_gains == ()
    assert summary.biggest_losses == ()
    assert summary.busiest_driver is None
    assert summary.busiest_changes == 0
    assert summary.pit_stops == ()
    assert summary.flags == ()
    assert summary.fastest_lap is None
    assert summary.lap_median is None
    assert summary.fast_outliers == ()
    assert summary.slow_outliers == ()


def test_a_prefix_with_no_completed_lap_has_no_window_and_no_story() -> None:
    """The window starts at the race start, so a pre-race prefix carries no story.

    The recorded corpus opens with a pre-race grid snapshot, and a gain measured from the
    grid disagrees with the design's measured table; the window therefore begins at the
    first completed lap, and a prefix that holds no completed lap is explicitly empty
    rather than invented from the grid.
    """
    events = (
        pos(0, 24, 19),
        pos(1, 24, 14),
        flag(2, "GREEN", message="GREEN LIGHT - PIT EXIT OPEN"),
    )

    summary = salience_summary(events)

    assert summary.is_empty
    assert summary.event_count == 0
    assert summary.biggest_gains == ()
    assert summary.flags == ()


def test_a_window_with_only_lap_one_and_null_durations_is_story_less() -> None:
    events = (lap(0, 1, 95.0, driver_number=4), lap(1, 2, None, driver_number=4))

    summary = salience_summary(events)

    assert summary.is_empty
    assert summary.fastest_lap is None
    assert summary.lap_median is None


# --- Positions: the gain, the loss and the busiest -----------------------------


def test_the_biggest_gain_and_loss_measure_first_to_last_position_in_the_window() -> (
    None
):
    events = (
        lap(0, 1, 109.752, driver_number=24),
        pos(1, 24, 19),
        pos(2, 24, 16),
        pos(3, 24, 14),
        pos(4, 14, 5),
        pos(5, 14, 10),
    )

    summary = salience_summary(events)

    assert summary.biggest_gains == (
        PositionMove(driver_number=24, first_position=19, last_position=14, change=-5),
    )
    assert summary.biggest_losses == (
        PositionMove(driver_number=14, first_position=5, last_position=10, change=5),
    )


def test_tied_extremes_are_all_reported_in_first_observation_order() -> None:
    """Two drivers losing five places are two biggest losses, not one arbitrary winner."""
    events = (
        lap(0, 1, 109.752),
        pos(1, 14, 5),
        pos(2, 31, 13),
        pos(3, 14, 10),
        pos(4, 31, 18),
    )

    summary = salience_summary(events)

    assert [move.driver_number for move in summary.biggest_losses] == [14, 31]
    assert [move.change for move in summary.biggest_losses] == [5, 5]
    assert summary.biggest_gains == ()


def test_a_driver_whose_position_does_not_change_is_in_neither_extreme() -> None:
    events = (
        lap(0, 1, 100.0),
        pos(1, 4, 2),
        pos(2, 24, 19),
        pos(3, 24, 14),
    )

    summary = salience_summary(events)

    assert [move.driver_number for move in summary.biggest_gains] == [24]
    assert summary.biggest_losses == ()


def test_the_busiest_driver_counts_recorded_position_changes() -> None:
    events = (
        lap(0, 1, 100.0),
        pos(1, 44, 16),
        pos(2, 31, 13),
        pos(3, 44, 17),
        pos(4, 31, 14),
        pos(5, 44, 18),
        pos(6, 31, 15),
    )

    summary = salience_summary(events)

    assert summary.busiest_changes == 3
    assert summary.busiest_driver == 44, (
        "a tied count is broken by the earliest first observation, then by driver number"
    )


def test_with_no_attributable_position_change_the_busiest_is_none() -> None:
    events = (
        lap(0, 1, 100.0),
        lap(1, 2, 99.0),
        flag(2, "GREEN", message="TRACK CLEAR"),
    )

    summary = salience_summary(events)

    assert summary.busiest_driver is None
    assert summary.busiest_changes == 0


# --- Pit stops -----------------------------------------------------------------


def test_pit_stops_carry_their_recorded_durations_and_explicit_nulls() -> None:
    events = (
        lap(0, 1, 100.0),
        pit(1, 23, 3, pit_duration=34.983, lane_duration=34.983, stop_duration=12.5),
        pit(2, 4, 4, lane_duration=30.0),
    )

    summary = salience_summary(events)

    assert summary.pit_stops == (
        PitReading(
            driver_number=23,
            lap_number=3,
            pit_duration=34.983,
            lane_duration=34.983,
            stop_duration=12.5,
        ),
        PitReading(
            driver_number=4,
            lap_number=4,
            pit_duration=None,
            lane_duration=30.0,
            stop_duration=None,
        ),
    )


# --- Race control --------------------------------------------------------------


def test_flags_carry_the_sector_when_present_and_omit_it_when_absent() -> None:
    events = (
        lap(0, 1, 100.0),
        flag(1, "GREEN", message="GREEN LIGHT - PIT EXIT OPEN"),
        flag(2, "DOUBLE YELLOW", sector=3, message="DOUBLE YELLOW IN TRACK SECTOR 3"),
    )

    summary = salience_summary(events)

    assert summary.flags == (
        FlagReading(
            flag="GREEN",
            sector=None,
            message="GREEN LIGHT - PIT EXIT OPEN",
            lap_number=None,
        ),
        FlagReading(
            flag="DOUBLE YELLOW",
            sector=3,
            message="DOUBLE YELLOW IN TRACK SECTOR 3",
            lap_number=None,
        ),
    )


@pytest.mark.parametrize(
    "flag_value",
    [None, "", "   ", 7],
    ids=["null", "empty", "blank", "not-text"],
)
def test_a_race_control_row_without_a_recorded_flag_is_not_a_flag(
    flag_value: object,
) -> None:
    """Race-control rows carry categories and messages too; only a flag is a flag."""
    events = (lap(0, 1, 100.0), flag(1, flag_value, message="SAFETY CAR DEPLOYED"))

    summary = salience_summary(events)

    assert summary.flags == ()


# --- The lap-time story --------------------------------------------------------


def test_the_fastest_lap_is_the_minimum_duration_with_lap_number_at_least_two() -> None:
    events = (
        lap(0, 1, 95.0, driver_number=4),
        lap(1, 2, 99.923, driver_number=55),
        lap(2, 2, 99.991, driver_number=1),
        lap(3, 3, 101.0, driver_number=16),
    )

    summary = salience_summary(events)

    assert summary.fastest_lap == LapReading(
        driver_number=55, lap_number=2, duration_seconds=99.923
    )


def test_null_and_non_numeric_durations_never_become_a_fastest_lap() -> None:
    events = (
        lap(0, 1, 100.0, driver_number=4),
        lap(1, 2, None, driver_number=4),
        lap(2, 3, "fast", driver_number=4),
        lap(3, 4, 104.0, driver_number=55),
    )

    summary = salience_summary(events)

    assert summary.fastest_lap == LapReading(
        driver_number=55, lap_number=4, duration_seconds=104.0
    )


def test_a_duration_too_large_to_represent_is_unknown_not_an_exception() -> None:
    """A corrupt payload with an unrepresentable magnitude stays unknown, never raises.

    A Python ``int`` of arbitrary width cannot be converted to a float; the projection must
    record the unknown rather than abort the whole summary, exactly as the collector's gap
    classifier does.
    """
    events = (
        lap(0, 1, 100.0),
        lap(1, 2, 10**400, driver_number=4),
        pit(2, 4, 3, pit_duration=10**400),
        lap(3, 4, 104.0, driver_number=55),
    )

    summary = salience_summary(events)

    assert summary.fastest_lap == LapReading(
        driver_number=55, lap_number=4, duration_seconds=104.0
    )
    assert summary.pit_stops[0].pit_duration is None


def test_the_outlier_rule_is_exact_at_both_fences() -> None:
    """A duration exactly on a declared fence is inside it; the rule is strict.

    With durations 150, 200, 200, 200 and 250 the median is 200, so the fences are exactly
    150 and 250. The two laps that sit on the fences are not outliers in either direction,
    and no other lap crosses one.
    """
    events = (
        lap(0, 1, 1.0),
        lap(1, 2, 200.0, driver_number=1),
        lap(2, 3, 200.0, driver_number=2),
        lap(3, 4, 200.0, driver_number=3),
        lap(4, 5, 150.0, driver_number=4),
        lap(5, 6, 250.0, driver_number=5),
    )

    summary = salience_summary(events)

    median = summary.lap_median
    assert median is not None
    assert median == 200.0
    assert FAST_OUTLIER_FACTOR * median == 150.0
    assert SLOW_OUTLIER_FACTOR * median == 250.0
    assert summary.fast_outliers == ()
    assert summary.slow_outliers == ()


def test_a_lap_beyond_a_fence_is_an_outlier_in_the_direction_it_crosses() -> None:
    events = (
        lap(0, 1, 1.0),
        lap(1, 2, 200.0, driver_number=1),
        lap(2, 3, 200.0, driver_number=2),
        lap(3, 4, 200.0, driver_number=3),
        lap(4, 5, 150.0, driver_number=4),
        lap(5, 6, 250.0, driver_number=5),
        lap(6, 7, 149.9, driver_number=6),
        lap(7, 8, 250.1, driver_number=7),
    )

    summary = salience_summary(events)

    assert summary.lap_median == 200.0
    assert summary.fast_outliers == (
        LapReading(driver_number=6, lap_number=7, duration_seconds=149.9),
    )
    assert summary.slow_outliers == (
        LapReading(driver_number=7, lap_number=8, duration_seconds=250.1),
    )


# --- Determinism and immutability ----------------------------------------------


def test_the_projection_is_deterministic() -> None:
    events = (
        lap(0, 1, 100.0),
        pos(1, 24, 19),
        pos(2, 24, 14),
        pit(3, 23, 3, pit_duration=34.983, lane_duration=34.983, stop_duration=12.5),
        flag(4, "DOUBLE YELLOW", sector=3, message="DOUBLE YELLOW IN TRACK SECTOR 3"),
        lap(5, 2, 99.923, driver_number=55),
    )

    assert salience_summary(events) == salience_summary(events)
    assert salience_summary(tuple(events)) == salience_summary(list(events))


def test_the_summary_is_frozen() -> None:
    summary = salience_summary((lap(0, 1, 100.0),))

    with pytest.raises(ValidationError):
        summary.event_count = 99  # type: ignore[misc]


# --- Rendering: plain prose, no new citable token -------------------------------


def test_the_rendered_block_carries_no_bracket_and_no_reference_shaped_token() -> None:
    """A hostile message must not be able to smuggle a bracket or a reference shape.

    The prompt's reference net is what guarantees nothing new becomes citable, so the
    CONTEXT block refuses the characters that net is built from rather than trusting that
    no recorded message happens to carry one.
    """
    events = (
        lap(0, 1, 100.0),
        flag(
            1,
            "DOUBLE (YELLOW)",
            sector=3,
            message="position[99].invented in the sector",
        ),
    )

    block = render_salience(salience_summary(events), {})

    assert not any(character in block for character in BRACKETS), block
    assert REFERENCE_TOKEN.search(block) is None, block
    assert "position" in block


def test_the_rendered_block_names_the_drivers_from_the_directory() -> None:
    events = (
        lap(0, 1, 109.752, driver_number=24),
        pos(1, 24, 19),
        pos(2, 24, 14),
        pos(3, 14, 5),
        pos(4, 14, 10),
    )
    directory = {
        24: ("ZHOU Guanyu", "Kick Sauber"),
        14: ("Fernando ALONSO", "Aston Martin"),
    }

    block = render_salience(salience_summary(events), directory)

    assert "ZHOU Guanyu, Kick Sauber, from P19 to P14, up 5 places" in block
    assert "Fernando ALONSO, Aston Martin, from P5 to P10, down 5 places" in block


def test_the_rendered_block_falls_back_when_the_directory_cannot_resolve_a_driver() -> (
    None
):
    events = (lap(0, 1, 100.0), pos(1, 91, 5), pos(2, 91, 2))

    block = render_salience(salience_summary(events), {})

    assert "driver 91" in block
    assert not any(character in block for character in BRACKETS), block


def test_the_rendered_block_for_an_empty_window_states_the_absence() -> None:
    block = render_salience(salience_summary(()), {})

    assert "no story" in block.lower()
    assert not any(character in block for character in BRACKETS), block


# --- The design-anchored acceptance: the measured start-to-lap-5 table ----------

#: Values measured on the recorded session's start-to-lap-5 window. A fence moved in either
#: direction, a different statistic or a different parsing rule shows up here as well as in
#: the synthetic boundary tests, so the recorded corpus is not a weaker pin than they are.
RECORDED_VALID_LAPS = 76
RECORDED_LAP_MEDIAN = 141.1955
RECORDED_FAST_FENCE = 105.896625
RECORDED_SLOW_FENCE = 176.494375
RECORDED_FAST_OUTLIERS = 19


def recorded_events():
    """Collect the recorded session exactly as the run path does."""
    payloads = {
        family: json.loads((FIXTURE_DIR / f"{family}.json").read_text(encoding="utf-8"))
        for family in EVENT_FAMILIES
    }
    return collect_session_events(SESSION_KEY, payloads)


def _completed_lap_index(events, lap_number: int) -> int:
    return min(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.LAP_COMPLETED
        and event.evidence.get("lap_number") == lap_number
    )


def _valid_lap_durations(events, end: int) -> list[float]:
    """The window's valid lap durations, counted independently of the projection.

    The projection exposes the median and the outlier sets but not its lap count, so the
    denominator is measured from the corpus here under the same declared rule - a
    ``LAP_COMPLETED`` event, ``lap_number >= 2`` and a finite numeric ``lap_duration`` -
    without reusing the module's private parsers.
    """
    durations: list[float] = []
    for event in events[:end]:
        if event.event_type is not EventType.LAP_COMPLETED:
            continue
        lap_number = event.evidence.get("lap_number")
        duration = event.evidence.get("lap_duration")
        if isinstance(lap_number, bool) or not isinstance(lap_number, int):
            continue
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            continue
        if lap_number >= 2:
            durations.append(float(duration))
    return durations


def test_the_projection_reproduces_the_designs_measured_start_to_lap_5_table() -> None:
    """The design's measured table and declared outlier rule, asserted as written.

    The window is the recorded session from the race start through the last event before
    the first lap-6 ``LAP_COMPLETED`` event, whose ``date_start`` is 19:14:32. That last
    event is ``TRACK CLEAR`` at 19:14:18, and every race-control row in the window is
    timestamped during lap 5, which runs from 19:11:43 to 19:14:32 - none of them during
    lap 6. That is the design's ``start → lap 5`` window. A number that disagrees with the
    design is reported as a finding rather than adjusted here.
    """
    events = recorded_events()
    summary = salience_summary(events[: _completed_lap_index(events, 6)])

    assert summary.biggest_gains == (
        PositionMove(driver_number=24, first_position=19, last_position=14, change=-5),
    ), "the design's biggest gain is ZHOU Guanyu 19 to 14"
    assert [move.driver_number for move in summary.biggest_losses] == [14, 31], (
        "the design's biggest losses are ALONSO 5 to 10 and OCON 13 to 18, in that order"
    )
    assert {
        (m.first_position, m.last_position, m.change) for m in summary.biggest_losses
    } == {
        (5, 10, 5),
        (13, 18, 5),
    }
    assert summary.busiest_driver == 23, "the design's busiest is Alexander ALBON"
    assert summary.busiest_changes == 13
    assert [
        (p.driver_number, p.lap_number, p.pit_duration) for p in summary.pit_stops
    ] == [(23, 3, 34.983)], "the design's long stop is ALBON's 34.983 s stop on lap 3"
    assert any(
        f.flag == "DOUBLE YELLOW"
        and f.sector == 3
        and f.message == "DOUBLE YELLOW IN TRACK SECTOR 3"
        for f in summary.flags
    ), "the design's start drama is a DOUBLE YELLOW in sector 3"
    assert summary.fastest_lap == LapReading(
        driver_number=55, lap_number=2, duration_seconds=99.923
    ), "the design's fastest lap is SAINZ 99.923 on lap 2"
    # The declared outlier rule on this window, so a fence moved in either direction fails
    # here and not only in the synthetic boundary tests.
    median = summary.lap_median
    assert median is not None, "a window with valid laps has a median"
    assert median == pytest.approx(RECORDED_LAP_MEDIAN)
    assert FAST_OUTLIER_FACTOR * median == pytest.approx(RECORDED_FAST_FENCE)
    assert SLOW_OUTLIER_FACTOR * median == pytest.approx(RECORDED_SLOW_FENCE)
    assert len(summary.fast_outliers) == RECORDED_FAST_OUTLIERS
    assert summary.slow_outliers == (), (
        "the declared rule classifies no slow outlier in this window; a fence that "
        "produced one would be a declared change, not this measurement"
    )
    assert (
        len(_valid_lap_durations(events, _completed_lap_index(events, 6)))
        == RECORDED_VALID_LAPS
    ), "the denominator the median is taken over, counted from the corpus"
    # The declared factors themselves, read live from the module rather than from this
    # test's imported names: a fence moved after import changes no classification here, so
    # only reading the module's own value catches it on the recorded corpus.
    assert (salience.FAST_OUTLIER_FACTOR, salience.SLOW_OUTLIER_FACTOR) == (0.75, 1.25)


def test_the_designs_window_rating_names_the_recorded_drivers() -> None:
    """The design's own names, joined from the session's entry list, reach the prose."""
    payloads = {
        family: json.loads((FIXTURE_DIR / f"{family}.json").read_text(encoding="utf-8"))
        for family in (*EVENT_FAMILIES, "drivers")
    }
    directory = {
        record["driver_number"]: (record["full_name"], record["team_name"])
        for record in payloads["drivers"]
        if record.get("session_key") == SESSION_KEY
    }
    events = collect_session_events(SESSION_KEY, payloads)
    summary = salience_summary(events[: _completed_lap_index(events, 6)])

    block = render_salience(summary, directory)

    assert "ZHOU Guanyu" in block
    assert "Fernando ALONSO" in block
    assert "Esteban OCON" in block
    assert "Alexander ALBON" in block
    assert "Carlos SAINZ" in block
    assert "from P19 to P14" in block
    assert "34.983" in block
    assert "99.923" in block
    assert not any(character in block for character in BRACKETS), block
