"""Offline acceptance tests for F06a deterministic tactical analysis.

Every payload is either the verbatim recorded fixture under ``fixtures/openf1``
or a minimal synthetic payload written inline; no network is touched. The
contract under test: one pure entry point turns the raw recorded payloads of
one session into a deterministic, total-ordered tuple of tactical alerts, each
traceable to the exact source record that produced it, making no claim the
fixtures cannot support.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from f1show import (
    GapKind,
    TacticalKind,
    TacticalSettings,
    analyze_tactics,
    build_tactical_source,
    render_tactical,
)
from f1show import tactical as tactical_module
from f1show.standings import QualifyingRulesError, QualifyingSessionKind
from f1show.tactical import (
    QualifyingBoundarySource,
    QualifyingCutoffReading,
    QualifyingPhaseRule,
    QualifyingPhaseWindow,
    QualifyingStanding,
    analyze_qualifying_cutoffs,
)

SESSION_KEY = 9617
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "openf1"


def load(name: str) -> list[dict[str, Any]]:
    """Read one recorded payload verbatim."""
    text = (FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")
    return json.loads(text)


def full_payloads() -> dict[str, list[dict[str, Any]]]:
    """The recorded payloads of every family the tactical motor reads."""
    return {name: load(name) for name in ("intervals", "laps", "stints")}


def alerts_of_kind(alerts: tuple[Any, ...], kind: TacticalKind) -> list[Any]:
    return [alert for alert in alerts if alert.kind is kind]


def test_battle_alert_names_follower_within_threshold() -> None:
    """A seconds interval at or under the threshold is one battle alert."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:10:00.000000+00:00",
                "driver_number": 4,
                "gap_to_leader": 5.2,
                "interval": 0.8,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:10:01.000000+00:00",
                "driver_number": 14,
                "gap_to_leader": 6.0,
                "interval": 2.5,
            },
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads)
    battles = alerts_of_kind(alerts, TacticalKind.GAP_BATTLE)
    assert [alert.driver_number for alert in battles] == [4]
    assert battles[0].facts["interval_seconds"] == 0.8
    assert battles[0].timestamp is not None
    assert battles[0].sources[0].family == "intervals"
    assert battles[0].sources[0].record_index == 0


def test_battle_threshold_is_configurable_and_inclusive() -> None:
    """A reading exactly at the threshold alerts; above it does not."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:10:00.000000+00:00",
                "driver_number": 4,
                "gap_to_leader": 5.0,
                "interval": 1.0,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:10:01.000000+00:00",
                "driver_number": 14,
                "gap_to_leader": 9.9,
                "interval": 1.01,
            },
        ]
    }
    alerts = analyze_tactics(
        SESSION_KEY, payloads, settings=TacticalSettings(battle_threshold_seconds=1.0)
    )
    assert [
        alert.driver_number for alert in alerts_of_kind(alerts, TacticalKind.GAP_BATTLE)
    ] == [4]


def test_leader_row_never_battles_itself() -> None:
    """A zero interval is the leader's own row, not a battle."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:10:00.000000+00:00",
                "driver_number": 1,
                "gap_to_leader": 0.0,
                "interval": 0.0,
            }
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads)
    assert alerts == ()


def test_lapped_reading_stays_a_lap_count() -> None:
    """``+1 LAP`` and ``+2 LAP`` alert with their lap counts, never seconds."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:31:00.000000+00:00",
                "driver_number": 22,
                "gap_to_leader": "+1 LAP",
                "interval": 43.5,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:31:04.000000+00:00",
                "driver_number": 27,
                "gap_to_leader": "+2 LAP",
                "interval": 65.0,
            },
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads)
    lapped = alerts_of_kind(alerts, TacticalKind.GAP_LAPPED)
    assert [alert.driver_number for alert in lapped] == [22, 27]
    assert [alert.facts["laps"] for alert in lapped] == [1, 2]
    assert all("seconds" not in alert.facts for alert in lapped)


def test_unknown_gap_is_declared_not_fabricated() -> None:
    """An unrecognised spelling yields an unknown alert carrying the raw value."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:10:00.000000+00:00",
                "driver_number": 31,
                "gap_to_leader": "PENALTY",
                "interval": 1.2,
            }
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads)
    unknowns = alerts_of_kind(alerts, TacticalKind.GAP_UNKNOWN)
    assert [alert.driver_number for alert in unknowns] == [31]
    assert unknowns[0].facts["raw"] == "PENALTY"


def test_absent_gap_produces_no_alert() -> None:
    """A null gap reading is declared absence: no alert, no error."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:10:00.000000+00:00",
                "driver_number": 44,
                "gap_to_leader": None,
                "interval": None,
            }
        ]
    }
    assert analyze_tactics(SESSION_KEY, payloads) == ()


def test_stale_driver_is_alerted_once_and_excluded() -> None:
    """A driver behind the freshness window gets one stale alert and no gap alert."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:00.000000+00:00",
                "driver_number": 10,
                "gap_to_leader": 3.0,
                "interval": 0.2,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:30.000000+00:00",
                "driver_number": 16,
                "gap_to_leader": 3.2,
                "interval": 0.3,
            },
        ]
    }
    alerts = analyze_tactics(
        SESSION_KEY, payloads, settings=TacticalSettings(staleness_seconds=15.0)
    )
    stale = alerts_of_kind(alerts, TacticalKind.STALE_READING)
    assert [alert.driver_number for alert in stale] == [10]
    assert stale[0].facts["age_seconds"] > 15.0
    assert stale[0].facts["staleness_seconds"] == 15.0
    # The stale driver's readings feed no gap alert; the fresh driver's 0.3 s
    # interval is a legitimate battle.
    battles = alerts_of_kind(alerts, TacticalKind.GAP_BATTLE)
    assert [alert.driver_number for alert in battles] == [16]
    fresh = [alert for alert in alerts if alert.kind is not TacticalKind.STALE_READING]
    assert fresh == battles


def test_only_the_newest_reading_alerts() -> None:
    """A driver's older readings do not multiply alerts."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:00.000000+00:00",
                "driver_number": 55,
                "gap_to_leader": 4.0,
                "interval": 0.1,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:04.000000+00:00",
                "driver_number": 55,
                "gap_to_leader": 4.0,
                "interval": 9.9,
            },
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads)
    assert alerts == ()


def test_missing_intervals_family_is_declared_absence() -> None:
    """No intervals payload means no gap or stale alerts, and no exception."""
    alerts = analyze_tactics(SESSION_KEY, {"laps": load("laps")})
    gap_kinds = {
        TacticalKind.GAP_BATTLE,
        TacticalKind.GAP_LAPPED,
        TacticalKind.GAP_UNKNOWN,
        TacticalKind.STALE_READING,
    }
    assert [alert for alert in alerts if alert.kind in gap_kinds] == []


def test_records_of_other_sessions_are_not_attributed() -> None:
    """A row carrying another session's key is ignored entirely."""
    payloads = {
        "intervals": [
            {
                "session_key": 9655,
                "date": "2024-10-20T18:10:00.000000+00:00",
                "driver_number": 4,
                "gap_to_leader": 1.0,
                "interval": 0.5,
            }
        ]
    }
    assert analyze_tactics(SESSION_KEY, payloads) == ()


def test_recorded_fixture_gap_alerts_are_pinned() -> None:
    """The recorded session's end-of-recording state, measured and pinned.

    With the declared defaults the newest reading overall is the recording's
    last row: 17 of the 20 drivers had stopped reporting by then (finished or
    retired), 3 backmarkers were still circulating a lap down, and no battle
    is live in that final state. A wider window exposes the mid-race fight:
    exactly one battle, driver 4, and seven lapped cars.
    """
    alerts = analyze_tactics(SESSION_KEY, full_payloads())
    battles = alerts_of_kind(alerts, TacticalKind.GAP_BATTLE)
    lapped = alerts_of_kind(alerts, TacticalKind.GAP_LAPPED)
    unknowns = alerts_of_kind(alerts, TacticalKind.GAP_UNKNOWN)
    stale = alerts_of_kind(alerts, TacticalKind.STALE_READING)
    assert [alert.driver_number for alert in battles] == []
    assert [(alert.driver_number, alert.facts["laps"]) for alert in lapped] == [
        (14, 1),
        (18, 1),
        (22, 1),
    ]
    assert len(stale) == 17
    assert len(unknowns) == 0
    assert len(battles) + len(lapped) + len(unknowns) + len(stale) == 20


def test_recorded_fixture_mid_race_battle_with_a_wider_window() -> None:
    """A wider freshness window shows the race's live fight on real data."""
    alerts = analyze_tactics(
        SESSION_KEY,
        full_payloads(),
        settings=TacticalSettings(staleness_seconds=600.0),
    )
    battles = alerts_of_kind(alerts, TacticalKind.GAP_BATTLE)
    assert [alert.driver_number for alert in battles] == [4]
    assert battles[0].facts["interval_seconds"] <= 1.0
    assert len(alerts_of_kind(alerts, TacticalKind.GAP_LAPPED)) == 7
    assert len(alerts_of_kind(alerts, TacticalKind.STALE_READING)) == 1
    gap_kinds = {
        TacticalKind.GAP_BATTLE,
        TacticalKind.GAP_LAPPED,
        TacticalKind.GAP_UNKNOWN,
        TacticalKind.STALE_READING,
    }
    assert len([alert for alert in alerts if alert.kind in gap_kinds]) == 9


def test_deterministic_total_order() -> None:
    """Identical payloads produce an identical ordered tuple."""
    first = analyze_tactics(SESSION_KEY, full_payloads())
    second = analyze_tactics(SESSION_KEY, full_payloads())
    assert json.dumps([alert.model_dump(mode="json") for alert in first]) == json.dumps(
        [alert.model_dump(mode="json") for alert in second]
    )
    keys = [
        (
            alert.timestamp.isoformat() if alert.timestamp is not None else "",
            alert.kind.value,
            alert.driver_number,
            alert.sources[0].record_index,
        )
        for alert in first
    ]
    assert keys == sorted(keys)


def test_classify_gap_is_the_consumed_surface() -> None:
    """The motor's gap classification is exercised through classify_gap kinds."""
    from f1show import classify_gap

    assert classify_gap("+1 LAP").kind is GapKind.LAPS
    assert classify_gap(None).kind is GapKind.ABSENT


def lap_row(
    driver: int, lap: int, duration: float | None, *, pit_out: bool = False
) -> dict[str, Any]:
    """One synthetic recorded lap row."""
    return {
        "session_key": SESSION_KEY,
        "driver_number": driver,
        "lap_number": lap,
        "lap_duration": duration,
        "is_pit_out_lap": pit_out,
        "date_start": f"2024-10-20T19:{10 + lap:02d}:00.000000+00:00",
    }


PACE_SETTINGS = TacticalSettings(pace_window_laps=3, pace_delta_threshold_seconds=0.5)


def test_pace_alert_fires_over_threshold_and_names_both_medians() -> None:
    """A median slower than the session best by more than the threshold alerts."""
    payloads = {
        "laps": [
            lap_row(4, 2, 100.0),
            lap_row(4, 3, 100.25),
            lap_row(4, 4, 100.5),
            lap_row(14, 2, 101.0),
            lap_row(14, 3, 101.25),
            lap_row(14, 4, 101.5),
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=PACE_SETTINGS)
    pace = alerts_of_kind(alerts, TacticalKind.PACE_DELTA)
    assert [alert.driver_number for alert in pace] == [14]
    assert pace[0].facts["median_seconds"] == 101.25
    assert pace[0].facts["best_median_seconds"] == 100.25
    assert pace[0].facts["delta_seconds"] == 1.0
    assert pace[0].facts["window_laps"] == 3
    assert [source.family for source in pace[0].sources] == ["laps", "laps", "laps"]
    assert pace[0].timestamp is not None


def test_pace_median_excludes_lap1_pit_out_and_nulls() -> None:
    """Lap 1, pit in/out laps and null durations never enter the median."""
    payloads = {
        "laps": [
            lap_row(4, 2, 100.0),
            lap_row(4, 3, 100.25),
            lap_row(4, 4, 100.5),
            lap_row(44, 1, 99.0),
            lap_row(44, 2, 50.0, pit_out=True),
            lap_row(44, 3, None),
            lap_row(44, 4, 102.0),
            lap_row(44, 5, 102.25),
            lap_row(44, 6, 102.5),
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=PACE_SETTINGS)
    pace = alerts_of_kind(alerts, TacticalKind.PACE_DELTA)
    assert [alert.driver_number for alert in pace] == [44]
    assert pace[0].facts["median_seconds"] == 102.25
    assert pace[0].facts["best_median_seconds"] == 100.25


def test_drivers_with_fewer_clean_laps_than_the_window_are_excluded() -> None:
    """A driver without a full clean window produces no pace claim at all."""
    payloads = {
        "laps": [
            lap_row(4, 2, 100.0),
            lap_row(4, 3, 100.25),
            lap_row(4, 4, 100.5),
            lap_row(90, 2, 130.0),
            lap_row(90, 3, 130.25),
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=PACE_SETTINGS)
    assert alerts_of_kind(alerts, TacticalKind.PACE_DELTA) == []


def test_delta_exactly_at_the_threshold_does_not_alert() -> None:
    """The pace alert is strictly greater than the threshold."""
    payloads = {
        "laps": [
            lap_row(4, 2, 100.0),
            lap_row(4, 3, 100.25),
            lap_row(4, 4, 100.5),
            lap_row(14, 2, 100.5),
            lap_row(14, 3, 100.75),
            lap_row(14, 4, 101.0),
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=PACE_SETTINGS)
    assert alerts_of_kind(alerts, TacticalKind.PACE_DELTA) == []


def test_tied_best_medians_alert_neither_tied_driver() -> None:
    """Two drivers sharing the best median both escape; the rest measure vs it."""
    payloads = {
        "laps": [
            lap_row(7, 2, 100.0),
            lap_row(7, 3, 100.25),
            lap_row(7, 4, 100.5),
            lap_row(9, 2, 100.0),
            lap_row(9, 3, 100.25),
            lap_row(9, 4, 100.5),
            lap_row(14, 2, 101.0),
            lap_row(14, 3, 101.25),
            lap_row(14, 4, 101.5),
        ]
    }
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=PACE_SETTINGS)
    pace = alerts_of_kind(alerts, TacticalKind.PACE_DELTA)
    assert [alert.driver_number for alert in pace] == [14]
    assert pace[0].facts["best_median_seconds"] == 100.25


def test_missing_laps_family_is_declared_absence() -> None:
    """No laps payload means no pace alerts, and no exception."""
    alerts = analyze_tactics(SESSION_KEY, {"intervals": load("intervals")})
    assert alerts_of_kind(alerts, TacticalKind.PACE_DELTA) == []


def test_recorded_fixture_pace_alerts_are_pinned() -> None:
    """The recorded session's pace picture, measured and pinned.

    With the declared defaults, twelve of the twenty drivers trail the
    session's best clean-lap median (97.889 s) by strictly more than the
    threshold; every alert carries the default five-lap window.
    """
    alerts = analyze_tactics(SESSION_KEY, full_payloads())
    pace = alerts_of_kind(alerts, TacticalKind.PACE_DELTA)
    assert len(pace) == 12
    assert len({alert.driver_number for alert in pace}) == 12
    assert all(alert.facts["window_laps"] == 5 for alert in pace)
    assert all(alert.facts["delta_seconds"] > 0.5 for alert in pace)
    assert {alert.facts["best_median_seconds"] for alert in pace} == {97.889}


def stint_row(
    driver: int,
    stint: int,
    lap_start: int,
    lap_end: int,
    *,
    compound: str = "MEDIUM",
    tyre_age_at_start: int | None = 0,
) -> dict[str, Any]:
    """One synthetic recorded stint row."""
    return {
        "session_key": SESSION_KEY,
        "driver_number": driver,
        "stint_number": stint,
        "lap_start": lap_start,
        "lap_end": lap_end,
        "compound": compound,
        "tyre_age_at_start": tyre_age_at_start,
    }


TYRE_SETTINGS = TacticalSettings(tyre_age_threshold_laps=25)


def test_tyre_age_alerts_at_and_over_the_threshold() -> None:
    """A computed age at or over the threshold alerts; below it does not."""
    payloads = {
        "laps": [
            lap_row(4, 10, 100.0),
            lap_row(4, 11, 100.25),
            lap_row(4, 12, 100.5),
        ],
        "stints": [
            stint_row(4, 2, 10, 12, tyre_age_at_start=15),
            stint_row(14, 1, 2, 40, tyre_age_at_start=0),
        ],
    }
    # Driver 4: laps on stint = 12 - 10 + 1 = 3, age = 15 + 3 = 18 < 25.
    # Driver 14: a long first stint; age = 0 + 11 = 11 < 25. Neither alerts.
    assert analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS) == ()
    payloads["stints"][0] = stint_row(4, 2, 10, 12, tyre_age_at_start=22)
    # Age = 22 + 3 = 25: exactly at the threshold alerts.
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS)
    ages = alerts_of_kind(alerts, TacticalKind.TYRE_AGE)
    assert [alert.driver_number for alert in ages] == [4]
    assert ages[0].facts["tyre_age_laps"] == 25
    assert ages[0].facts["tyre_age_at_start"] == 22
    assert ages[0].facts["stint_laps"] == 3
    assert ages[0].facts["stint_number"] == 2
    assert ages[0].facts["compound"] == "MEDIUM"
    assert [source.family for source in ages[0].sources] == ["stints", "laps"]


def test_tyre_age_counts_clean_laps_only() -> None:
    """Lap 1, pit in/out laps and null durations never extend the age."""
    payloads = {
        "laps": [
            lap_row(44, 9, 101.0),
            lap_row(44, 10, 50.0, pit_out=True),
            lap_row(44, 11, None),
        ],
        "stints": [stint_row(44, 3, 10, 30, tyre_age_at_start=20)],
    }
    # Last clean lap is 9, before the stint's lap_start 10: stint laps = 0,
    # age = 20 + 0 = 20 < 25. A pit-out lap 10 or the null lap 11 would have
    # pushed the count up.
    assert analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS) == ()
    payloads["laps"].insert(0, lap_row(44, 12, 101.25))
    # Now the last clean lap is 12: stint laps = 3, age = 23. Still below.
    assert analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS) == ()
    payloads["laps"].append(lap_row(44, 13, 101.5))
    # Last clean lap 13: stint laps = 4, age = 24. At the line but below.
    assert analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS) == ()
    payloads["laps"].append(lap_row(44, 14, 101.75))
    # Last clean lap 14: stint laps = 5, age = 25: at the threshold, alerts.
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS)
    ages = alerts_of_kind(alerts, TacticalKind.TYRE_AGE)
    assert [alert.driver_number for alert in ages] == [44]
    assert ages[0].facts["tyre_age_laps"] == 25


def test_only_the_latest_stint_is_evaluated() -> None:
    """An already-ended earlier stint makes no end-state age claim."""
    payloads = {
        "laps": [lap_row(31, 40, 100.0)],
        "stints": [
            stint_row(31, 1, 1, 25, tyre_age_at_start=0),
            stint_row(31, 2, 26, 50, tyre_age_at_start=0),
        ],
    }
    # Stint 1 would read 25 laps of use, but it ended laps ago; only stint 2
    # is current: laps on stint = 40 - 26 + 1 = 15, age 15 < 25.
    assert analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS) == ()
    payloads["stints"][1] = stint_row(31, 2, 26, 50, tyre_age_at_start=15)
    alerts = analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS)
    assert [
        alert.driver_number for alert in alerts_of_kind(alerts, TacticalKind.TYRE_AGE)
    ] == [31]
    assert alerts[0].facts["tyre_age_laps"] == 30


def test_unknown_tyre_age_produces_no_claim() -> None:
    """A stint with no tyre age at start stays unknown, never zero."""
    payloads = {
        "laps": [lap_row(77, 30, 100.0)],
        "stints": [stint_row(77, 2, 10, 50, tyre_age_at_start=None)],
    }
    assert analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS) == ()


def test_missing_stint_or_lap_families_are_declared_absence() -> None:
    """No stints means no tyre alerts; laps alone cannot compute an age."""
    assert (
        alerts_of_kind(
            analyze_tactics(
                SESSION_KEY, {"laps": load("laps")}, settings=TYRE_SETTINGS
            ),
            TacticalKind.TYRE_AGE,
        )
        == []
    )
    payloads = {"stints": [stint_row(4, 1, 1, 50, tyre_age_at_start=0)]}
    # Laps absent: no completed lap is known, stint laps = 0, age 0 < 25.
    assert analyze_tactics(SESSION_KEY, payloads, settings=TYRE_SETTINGS) == ()


def test_recorded_fixture_tyre_age_alerts_are_pinned() -> None:
    """The recorded session's end-of-race tyre picture, measured and pinned.

    Eleven drivers' latest stints carry a computed age at or over the
    declared 25-lap threshold, all on their second stint; the rest retired
    earlier or pitted into stints whose age stays below the line.
    """
    alerts = analyze_tactics(SESSION_KEY, full_payloads())
    ages = alerts_of_kind(alerts, TacticalKind.TYRE_AGE)
    measured = sorted(
        (alert.driver_number, alert.facts["tyre_age_laps"]) for alert in ages
    )
    assert measured == [
        (1, 31.0),
        (4, 25.0),
        (10, 38.0),
        (11, 30.0),
        (14, 30.0),
        (16, 30.0),
        (18, 28.0),
        (22, 37.0),
        (27, 29.0),
        (55, 35.0),
        (77, 40.0),
    ]
    assert all(alert.facts["stint_number"] == 2 for alert in ages)
    assert all(alert.facts["tyre_age_laps"] >= 25.0 for alert in ages)


# --- F06b: the tactical source layer -----------------------------------------


def test_source_context_at_the_newest_instant_reproduces_the_end_state() -> None:
    """As-of the newest reading overall, the context equals the end state."""
    source = build_tactical_source(SESSION_KEY, full_payloads())
    instants = [
        dt.datetime.fromisoformat(row["date"])
        for row in load("intervals")
        if row.get("session_key") == SESSION_KEY
    ] + [
        dt.datetime.fromisoformat(row["date_start"])
        for row in load("laps")
        if row.get("session_key") == SESSION_KEY
        and isinstance(row.get("date_start"), str)
    ]
    newest = max(instants)
    assert source.context(newest) == analyze_tactics(SESSION_KEY, full_payloads())


def test_context_only_reads_the_past_of_each_instant() -> None:
    """An instant before a driver's reading yields no alert for that driver."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:00.000000+00:00",
                "driver_number": 10,
                "gap_to_leader": 3.0,
                "interval": 0.2,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:05:00.000000+00:00",
                "driver_number": 16,
                "gap_to_leader": 3.2,
                "interval": 0.3,
            },
        ]
    }
    source = build_tactical_source(SESSION_KEY, payloads)
    early = dt.datetime.fromisoformat("2024-10-20T18:02:00+00:00")
    mid = dt.datetime.fromisoformat("2024-10-20T18:05:00+00:00")
    assert [alert.driver_number for alert in source.context(early)] == [10]
    mid_alerts = source.context(mid)
    # At mid, only the past counts: driver 10's lone old reading is stale and
    # driver 16's fresh 0.3 s interval is a legitimate battle.
    assert [
        alert.driver_number
        for alert in alerts_of_kind(mid_alerts, TacticalKind.STALE_READING)
    ] == [10]
    assert [
        alert.driver_number
        for alert in alerts_of_kind(mid_alerts, TacticalKind.GAP_BATTLE)
    ] == [16]


def test_context_freshness_is_measured_within_the_past() -> None:
    """The staleness window compares against the newest reading at or before the instant."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:00.000000+00:00",
                "driver_number": 10,
                "gap_to_leader": 3.0,
                "interval": 0.2,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:30.000000+00:00",
                "driver_number": 16,
                "gap_to_leader": 3.2,
                "interval": 0.3,
            },
        ]
    }
    source = build_tactical_source(
        SESSION_KEY, payloads, TacticalSettings(staleness_seconds=15.0)
    )
    at = dt.datetime.fromisoformat("2024-10-20T18:00:40+00:00")
    stale = alerts_of_kind(source.context(at), TacticalKind.STALE_READING)
    assert [alert.driver_number for alert in stale] == [10]
    assert stale[0].facts["age_seconds"] == 30.0


def test_context_before_any_reading_is_empty() -> None:
    """An instant before every reading makes no claim at all."""
    source = build_tactical_source(SESSION_KEY, full_payloads())
    early = dt.datetime.fromisoformat("2024-10-20T17:00:00+00:00")
    assert source.context(early) == ()


def test_source_without_intervals_declares_absence() -> None:
    """No intervals payload: the context yields no gap-family claim."""
    source = build_tactical_source(SESSION_KEY, {"laps": load("laps")})
    gap_kinds = {
        TacticalKind.GAP_BATTLE,
        TacticalKind.GAP_LAPPED,
        TacticalKind.GAP_UNKNOWN,
        TacticalKind.STALE_READING,
    }
    newest = max(
        dt.datetime.fromisoformat(row["date_start"])
        for row in load("laps")
        if row.get("session_key") == SESSION_KEY
        and isinstance(row.get("date_start"), str)
    )
    assert [alert for alert in source.context(newest) if alert.kind in gap_kinds] == []


def test_render_tactical_is_bounded_and_carries_no_reference_token() -> None:
    """Lines are plain prose under a TACTICAL header, capped and bracket-free."""
    payloads = {
        "intervals": [
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:00.000000+00:00",
                "driver_number": 10,
                "gap_to_leader": "+1 LAP",
                "interval": 0.2,
            },
            {
                "session_key": SESSION_KEY,
                "date": "2024-10-20T18:00:30.000000+00:00",
                "driver_number": 16,
                "gap_to_leader": 3.2,
                "interval": 0.3,
            },
        ]
    }
    source = build_tactical_source(
        SESSION_KEY, payloads, TacticalSettings(staleness_seconds=600.0)
    )
    lines = render_tactical(
        source.context(dt.datetime.fromisoformat("2024-10-20T18:01:00+00:00"))
    )
    assert lines[0] == "TACTICAL:"
    assert len(lines) - 1 <= 8
    assert all("[" not in line and "]" not in line for line in lines)
    assert any("driver 16" in line and "behind the car ahead" in line for line in lines)
    assert any("driver 10" in line and "1 lap" in line for line in lines)


def test_render_tactical_truncates_with_an_honest_count() -> None:
    """More alerts than the cap truncates and states how many are not shown."""
    intervals = []
    for number in range(1, 13):
        intervals.append(
            {
                "session_key": SESSION_KEY,
                "date": f"2024-10-20T18:00:{number:02d}.000000+00:00",
                "driver_number": number,
                "gap_to_leader": float(number),
                "interval": 0.5,
            }
        )
    source = build_tactical_source(SESSION_KEY, {"intervals": intervals})
    lines = render_tactical(
        source.context(dt.datetime.fromisoformat("2024-10-20T18:01:00+00:00"))
    )
    assert lines[0] == "TACTICAL:"
    assert lines[-1] == "and 4 more alerts not shown."
    assert len(lines) == 10


def test_source_defaults_pin_the_context_cap() -> None:
    """The declared cap lives in the settings with its default of 8."""
    assert TacticalSettings().tactical_context_max_alerts == 8


def test_pace_alert_timestamp_uses_the_windows_last_known_instant() -> None:
    """A window ending on a lap with no recorded instant still yields a placed alert.

    Regression for the F06b review's frozen finding: the window's instant slot
    is None for such a lap, and the alert must carry the latest instant the
    window can prove instead of an unplaced None.
    """
    laps = []
    for n in range(2, 8):
        laps.append(lap_row(14, n, 100.0 + n))
        laps.append(lap_row(4, n, 110.0 + n))
    unplaced = lap_row(4, 8, 117.0)
    unplaced["date_start"] = None
    laps.append(unplaced)

    alerts = analyze_tactics(
        SESSION_KEY, {"laps": laps}, TacticalSettings(pace_delta_threshold_seconds=0.01)
    )

    pace = alerts_of_kind(alerts, TacticalKind.PACE_DELTA)
    assert [alert.driver_number for alert in pace] == [4]
    assert pace[0].timestamp == dt.datetime.fromisoformat(
        "2024-10-20T19:17:00+00:00"
    ), (
        "the alert is placed at the window's last known instant (lap 7), never None "
        "while its window still holds placed laps"
    )


# --- F06c: the qualifying cutoff motor over the recorded session 9608 ---------
#
# The declared rules live in ``f1show.standings`` and are read here, never re-stated;
# what these tests pin is that the motor consumes them, that every value it reports is
# traceable to the record that produced it, and that what the capture cannot support is
# declared as an absence instead of being coerced into a zero or a guess.

QUALIFYING_SESSION_KEY = 9608
QUALIFYING_DIR = FIXTURE_DIR / "9608"
QUALIFYING_FAMILIES = ("laps", "position", "race_control")


def load_qualifying(name: str) -> list[dict[str, Any]]:
    """Read one recorded qualifying payload verbatim."""
    return json.loads((QUALIFYING_DIR / f"{name}.json").read_text(encoding="utf-8"))


def qualifying_payloads(*drop: str) -> dict[str, list[dict[str, Any]]]:
    """The recorded qualifying payloads; ``intervals`` is deliberately not one of them."""
    return {
        name: load_qualifying(name) for name in QUALIFYING_FAMILIES if name not in drop
    }


def at(value: str) -> dt.datetime:
    """One recorded instant, parsed the way the motor parses it."""
    return dt.datetime.fromisoformat(value)


def qualifying_cutoff(
    payloads: dict[str, list[dict[str, Any]]] | None = None,
    as_of: str = "2024-10-19T23:00:00.262000+00:00",
    season: int = 2024,
    session_kind: QualifyingSessionKind | str = QualifyingSessionKind.MAIN_QUALIFYING,
) -> QualifyingCutoffReading:
    """The cutoff reading of one instant over the recorded capture by default."""
    return analyze_qualifying_cutoffs(
        QUALIFYING_SESSION_KEY,
        season,
        session_kind,
        qualifying_payloads() if payloads is None else payloads,
        at(as_of),
    )


def window(reading: QualifyingCutoffReading, phase: int) -> QualifyingPhaseWindow:
    """The declared phase ``phase`` of a reading."""
    return next(candidate for candidate in reading.phases if candidate.phase == phase)


def advancing(reading: QualifyingCutoffReading) -> set[int]:
    """The drivers the reading places inside the line."""
    return {
        row.driver_number
        for row in reading.standings
        if row.standing is QualifyingStanding.ADVANCING
    }


def control(instant: str, message: str, phase: int | None) -> dict[str, Any]:
    """One minimal ``race_control`` row."""
    return {
        "session_key": QUALIFYING_SESSION_KEY,
        "date": instant,
        "message": message,
        "qualifying_phase": phase,
    }


def lap_at(
    instant: str | None,
    driver: int,
    seconds: float | None,
    *,
    pit_out: bool = False,
    lap_number: int = 3,
) -> dict[str, Any]:
    """One minimal ``laps`` row."""
    return {
        "session_key": QUALIFYING_SESSION_KEY,
        "date_start": instant,
        "driver_number": driver,
        "lap_number": lap_number,
        "lap_duration": seconds,
        "is_pit_out_lap": pit_out,
    }


def position_at(instant: str, driver: int, place: int) -> dict[str, Any]:
    """One minimal ``position`` row: no lap number, no phase, only the date."""
    return {
        "session_key": QUALIFYING_SESSION_KEY,
        "date": instant,
        "driver_number": driver,
        "position": place,
    }


def test_an_undeclared_season_is_refused_by_the_declared_rules() -> None:
    """The motor refuses through ``qualifying_rules`` before reading a payload."""
    with pytest.raises(QualifyingRulesError) as refusal:
        qualifying_cutoff(season=2025)
    assert str(refusal.value) == (
        "no declared qualifying rules for season 2025; declared qualifying seasons: [2024]"
    )


def test_an_undeclared_session_kind_is_refused_by_the_declared_rules() -> None:
    """A kind nobody measured is refused, never defaulted to the main format."""
    with pytest.raises(QualifyingRulesError) as refusal:
        qualifying_cutoff(session_kind="Sprint Qualifying")
    assert str(refusal.value) == (
        "no declared qualifying rules for season 2024 and session kind "
        "'Sprint Qualifying'; declared session kinds for 2024: ['Qualifying']"
    )


def test_the_phase_windows_are_measured_and_carry_both_boundary_sources() -> None:
    """The windows come from ``race_control``; the declared length stays visible."""
    reading = qualifying_cutoff()
    assert [phase.rule for phase in reading.phases] == [
        QualifyingPhaseRule.ELIMINATES,
        QualifyingPhaseRule.ELIMINATES,
        QualifyingPhaseRule.CLASSIFIES,
    ]
    assert [phase.participants for phase in reading.phases] == [20, 15, 10]
    assert [phase.advancing for phase in reading.phases] == [15, 10, 0]
    assert [phase.declared_duration_minutes for phase in reading.phases] == [18, 15, 12]
    first = window(reading, 1)
    assert first.start == at("2024-10-19T22:00:00.234000+00:00")
    assert first.measured_end == at("2024-10-19T22:18:00.241000+00:00")
    assert first.declared_end == at("2024-10-19T22:18:00.234000+00:00")
    assert first.end == first.measured_end
    assert first.start_source is QualifyingBoundarySource.SOURCE
    assert first.end_source is QualifyingBoundarySource.SOURCE, (
        "the recording states this boundary; the declared length is still reported"
    )
    assert first.measured_end != first.declared_end, (
        "the two sources really do disagree here, by 7 ms, which is why both are reported"
    )
    assert [(source.family, source.record_index) for source in first.sources] == [
        ("race_control", 1),
        ("race_control", 11),
    ]
    assert [phase.phase for phase in reading.phases] == [1, 2, 3]


def test_a_window_without_a_recorded_end_uses_the_declared_duration() -> None:
    """The rule fills the boundary the source does not state, and says so."""
    payloads = {
        "race_control": [
            control("2024-10-19T22:00:00+00:00", "SESSION STARTED", 1),
            control("2024-10-19T22:05:00+00:00", "CAR 10 (GAS) LAP DELETED", None),
        ]
    }
    reading = qualifying_cutoff(payloads, as_of="2024-10-19T22:30:00+00:00")
    first, second, third = reading.phases
    assert first.measured_end is None
    assert first.declared_end == at("2024-10-19T22:18:00+00:00")
    assert first.end == first.declared_end
    assert first.end_source is QualifyingBoundarySource.DECLARED
    assert second.start is None and second.end is None
    assert second.start_source is QualifyingBoundarySource.ABSENT
    assert second.end_source is QualifyingBoundarySource.ABSENT
    assert third.hot_laps is None, "an unknown window is never counted as zero hot laps"
    assert reading.active_phase == 1


def test_the_boundary_between_advancing_and_eliminated_is_the_declared_count() -> None:
    """Boundary values: the last advancing place and the first eliminated one."""
    reading = qualifying_cutoff(as_of="2024-10-19T22:18:00.241000+00:00")
    assert reading.active_phase == 1
    assert reading.line == 15
    rows = reading.standings
    assert len(rows) == 20
    inside = [row for row in rows if row.standing is QualifyingStanding.ADVANCING]
    outside = [row for row in rows if row.standing is QualifyingStanding.ELIMINATED]
    assert len(inside) == 15 and len(outside) == 5
    assert (inside[-1].lap_position, inside[-1].driver_number) == (15, 18)
    assert (outside[0].lap_position, outside[0].driver_number) == (16, 23)
    assert inside[-1].best_lap_seconds is not None
    assert outside[0].best_lap_seconds is not None
    assert inside[-1].best_lap_seconds < outside[0].best_lap_seconds


def test_the_declared_advancement_reproduces_the_measured_entrants() -> None:
    """The declared count is checked against who actually drove the next phase."""
    first = qualifying_cutoff(as_of="2024-10-19T22:18:00.241000+00:00")
    second = qualifying_cutoff(as_of="2024-10-19T22:40:00.257000+00:00")
    third = qualifying_cutoff(as_of="2024-10-19T23:00:00.262000+00:00")
    assert len(advanced := advancing(first)) == 15
    assert advanced == {row.driver_number for row in second.standings}
    assert len(advanced := advancing(second)) == 10
    assert advanced == {row.driver_number for row in third.standings}


def test_the_live_position_order_is_reported_and_marks_its_disagreement() -> None:
    """The live order and the lap-time order are both stated, and they disagree."""
    reading = qualifying_cutoff(as_of="2024-10-19T22:18:00.241000+00:00")
    rows = {row.driver_number: row for row in reading.standings}
    agreed = rows[18]
    assert (agreed.position, agreed.lap_position) == (15, 15)
    assert agreed.position_agrees is True
    assert agreed.position_source is not None
    assert agreed.position_source.family == "position"
    lagged = rows[23]
    assert (lagged.position, lagged.lap_position) == (13, 16)
    assert lagged.position_agrees is False
    assert lagged.standing is QualifyingStanding.ELIMINATED
    assert lagged.reading_age_seconds is not None


def test_a_pit_out_lap_is_not_a_hot_lap_and_is_counted_as_excluded() -> None:
    """Pit interference: an out-lap measures the pit lane, never a qualifying lap."""
    reading = qualifying_cutoff(as_of="2024-10-19T22:40:00.257000+00:00")
    second = window(reading, 2)
    assert second.hot_laps == 47
    assert second.pit_out_laps_excluded == 30
    assert second.unreadable_laps_excluded == 0
    driver_laps = [
        lap
        for lap in load_qualifying("laps")
        if lap["driver_number"] == 30
        and lap.get("date_start") is not None
        and at(lap["date_start"]) >= at("2024-10-19T22:25:00.239000+00:00")
        and at(lap["date_start"]) <= at("2024-10-19T22:40:00.257000+00:00")
    ]
    assert len(driver_laps) == 3
    assert all(lap["is_pit_out_lap"] is True for lap in driver_laps)
    row = {row.driver_number: row for row in reading.standings}[30]
    assert row.best_lap_seconds is None
    assert row.lap_source is None
    assert row.lap_position is None
    assert row.position == 15
    assert row.standing is QualifyingStanding.UNRANKED


def test_a_lap_with_no_duration_is_excluded_and_counted_not_dropped() -> None:
    """A null duration is not a time: it is excluded, and the exclusion is declared."""
    reading = qualifying_cutoff()
    third = window(reading, 3)
    assert third.hot_laps == 27
    assert third.pit_out_laps_excluded == 19
    assert third.unreadable_laps_excluded == 2
    nulls = [lap for lap in load_qualifying("laps") if lap.get("lap_duration") is None]
    assert len(nulls) == 22, "measured on the capture; 20 of them are also out-laps"
    assert reading.laps_without_instant == 1
    assert reading.laps_outside_every_window == 14


def test_the_absent_intervals_family_is_declared_absence_never_zero() -> None:
    """S2's lapped/null intervals: the family is absent, and that is what is said."""
    payloads = qualifying_payloads()
    assert "intervals" not in payloads, "the capture deliberately holds no intervals"
    reading = qualifying_cutoff(payloads)
    assert reading.absences == (
        "the intervals family is absent from these payloads: lapped and null intervals "
        "are declared unknown, never zero",
    )
    assert reading.line == 0 or reading.line is None


def test_each_missing_telemetry_family_is_declared_with_its_own_absence() -> None:
    """Missing telemetry is declared per family, never coerced into an empty claim."""
    reading = qualifying_cutoff(qualifying_payloads("position", "laps"))
    assert reading.absences == (
        "the intervals family is absent from these payloads: lapped and null intervals "
        "are declared unknown, never zero",
        "the position family is absent from these payloads: no driver's place is read",
        "the laps family is absent from these payloads: no hot lap is counted",
    )
    assert reading.standings == ()
    assert reading.active_phase == 3
    assert window(reading, 3).hot_laps == 0


def test_a_driver_with_no_reading_inside_the_window_is_unranked() -> None:
    """Stale data: a position row outside the window is no reading inside it."""
    payloads = {
        "race_control": [
            control("2024-10-19T10:00:00+00:00", "SESSION STARTED", 1),
            control("2024-10-19T10:18:00+00:00", "SESSION FINISHED", 1),
        ],
        "position": [
            position_at("2024-10-19T09:59:00+00:00", 4, 1),
            position_at("2024-10-19T10:05:00+00:00", 1, 2),
        ],
        "laps": [lap_at("2024-10-19T10:04:00+00:00", 4, 93.0)],
    }
    reading = qualifying_cutoff(payloads, as_of="2024-10-19T10:10:00+00:00")
    rows = {row.driver_number: row for row in reading.standings}
    assert rows[4].position is None
    assert rows[4].position_source is None
    assert rows[4].reading_age_seconds is None
    assert rows[4].lap_position == 1
    assert rows[1].position == 2 and rows[1].lap_position is None
    assert rows[1].standing is QualifyingStanding.UNRANKED


def test_a_lap_exactly_on_a_window_boundary_is_inside_it() -> None:
    """Boundary instants: both ends of a window are closed, and one tick past is out."""
    payloads = {
        "race_control": [
            control("2024-10-19T10:00:00+00:00", "SESSION STARTED", 1),
            control("2024-10-19T10:18:00+00:00", "SESSION FINISHED", 1),
        ],
        "laps": [
            lap_at("2024-10-19T10:00:00+00:00", 4, 90.0),
            lap_at("2024-10-19T10:18:00+00:00", 1, 89.0),
            lap_at("2024-10-19T10:18:00.000001+00:00", 16, 88.0),
            lap_at("2024-10-19T10:09:00+00:00", 4, None),
            lap_at("2024-10-19T10:10:00+00:00", 16, 95.0, pit_out=True),
        ],
        "position": [position_at("2024-10-19T10:17:00+00:00", 1, 1)],
    }
    reading = qualifying_cutoff(payloads, as_of="2024-10-19T10:20:00+00:00")
    first = window(reading, 1)
    assert first.hot_laps == 2
    assert first.pit_out_laps_excluded == 1
    assert first.unreadable_laps_excluded == 1
    assert reading.laps_outside_every_window == 1
    assert [row.driver_number for row in reading.standings] == [1, 4], (
        "driver 16's only laps are an out-lap and a lap past the window, so it holds "
        "no reading inside the window and gets no row at all"
    )


def test_the_instant_cuts_the_lap_corpus_and_the_position_readings() -> None:
    """The reading is the state at the instant, never the end state in disguise."""
    early = qualifying_cutoff(as_of="2024-10-19T22:09:00+00:00")
    late = qualifying_cutoff(as_of="2024-10-19T22:18:00.241000+00:00")
    assert window(early, 1).hot_laps == 40
    assert window(late, 1).hot_laps == 93
    assert [phase.hot_laps for phase in early.phases] == [40, None, None]
    assert [row.lap_position for row in early.standings] == list(range(1, 21))
    assert early.standings != late.standings
    early_pole = early.standings[0].best_lap_seconds
    late_pole = late.standings[0].best_lap_seconds
    assert early_pole is not None and late_pole is not None
    assert early_pole > late_pole


def test_before_the_first_window_starts_no_line_exists() -> None:
    """A declared phase that has not started has no window and no line."""
    reading = qualifying_cutoff(as_of="2024-10-19T21:59:59.999999+00:00")
    assert reading.active_phase is None
    assert reading.line is None
    assert reading.standings == ()
    assert [phase.end_source for phase in reading.phases] == [
        QualifyingBoundarySource.ABSENT,
        QualifyingBoundarySource.ABSENT,
        QualifyingBoundarySource.ABSENT,
    ]


def test_the_last_phase_classifies_ten_and_eliminates_nobody() -> None:
    """Ten classified, no eliminated driver, and no line to be outside of."""
    reading = qualifying_cutoff()
    assert reading.active_phase == 3
    assert reading.line is None
    third = window(reading, 3)
    assert third.rule is QualifyingPhaseRule.CLASSIFIES
    assert third.participants == 10 and third.advancing == 0
    assert len(reading.standings) == 10
    assert {row.standing for row in reading.standings} == {
        QualifyingStanding.CLASSIFIED
    }
    assert [row.lap_position for row in reading.standings] == list(range(1, 11))


def test_the_cutoff_reading_is_a_function_of_its_inputs_alone() -> None:
    """Purity: identical payloads and instants produce an identical reading."""
    assert qualifying_cutoff() == qualifying_cutoff()
    assert (
        qualifying_cutoff(as_of="2024-10-19T22:18:00.241000+00:00")
        != qualifying_cutoff()
    )


def test_the_module_carries_no_circuit_name_and_no_capture_constant() -> None:
    """S2's last clause: no hardcoded venue, and no per-capture constant."""
    source = (Path(tactical_module.__file__)).read_text(encoding="utf-8")
    for token in (
        "circuit_key",
        "circuit_short_name",
        "meeting_key",
        "Austin",
        "Monza",
        "Lusail",
        "Silverstone",
        "9608",
        "1247",
    ):
        assert token not in source, (
            f"the module names the capture-specific token {token!r}"
        )


def test_a_deleted_lap_is_not_applied_and_that_limitation_is_pinned() -> None:
    """Declared limitation: a deletion notice is free text, so no lap is disqualified.

    ``race_control`` states nine deletions, each in a message that carries no
    ``qualifying_phase`` and no lap key the motor can bind to a lap, so this motor reads
    durations and not the judgements passed on them. Measured on the capture: exactly
    one deletion matches a driver's best lap inside a window -- driver 11, 93.26 s,
    deleted for track limits at turn 9 in phase 3 -- and the phase-3 verdict does not
    move, because that phase classifies every driver in it. Pinned so the limitation is
    a stated fact rather than an assumption a later reader makes.
    """
    reading = qualifying_cutoff()
    row = {candidate.driver_number: candidate for candidate in reading.standings}[11]
    assert row.best_lap_seconds is not None
    assert abs(row.best_lap_seconds - 93.26) < 0.001
    assert row.standing is QualifyingStanding.CLASSIFIED
