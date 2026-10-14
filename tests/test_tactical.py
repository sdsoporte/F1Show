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
    assert len(alerts) == 9


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
