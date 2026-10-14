"""Offline acceptance tests for F06a deterministic tactical analysis.

Every payload is either the verbatim recorded fixture under ``fixtures/openf1``
or a minimal synthetic payload written inline; no network is touched. The
contract under test: one pure entry point turns the raw recorded payloads of
one session into a deterministic, total-ordered tuple of tactical alerts, each
traceable to the exact source record that produced it, making no claim the
fixtures cannot support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1show import (
    GapKind,
    TacticalKind,
    TacticalSettings,
    analyze_tactics,
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


def alerts_of_kind(
    alerts: tuple[Any, ...], kind: TacticalKind
) -> list[Any]:
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
    assert [alert.driver_number for alert in alerts_of_kind(alerts, TacticalKind.GAP_BATTLE)] == [4]


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
    assert [alert.driver_number for alert in alerts_of_kind(alerts, TacticalKind.TYRE_AGE)] == [31]
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
            analyze_tactics(SESSION_KEY, {"laps": load("laps")}, settings=TYRE_SETTINGS),
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
    measured = sorted((alert.driver_number, alert.facts["tyre_age_laps"]) for alert in ages)
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
