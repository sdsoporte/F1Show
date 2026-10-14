"""Deterministic tactical analysis over recorded OpenF1 payloads (F06a).

``analyze_tactics`` is the single entry point: it takes the raw recorded
payloads of one session and returns a total-ordered tuple of alerts, each
traceable to the exact source record that produced it. It is pure: no network,
no clock, no randomness, and identical payloads always produce an identical
tuple.

**Scope of this unit (F06a).** Race-only, recorded-corpus-only analysis of
gaps, freshness, pace and stint age. Qualifying cutoffs, telemetry
(car/location/weather), FastF1, Redis delivery, booth integration and audio
are out of scope; the booth and the run path are deliberately untouched.

**The motor consumes** :func:`f1show.collector.classify_gap` -- the F04
handoff. Gap values are classified, never cast: ``+1 LAP`` stays a lap count,
``None`` is absence, and an unrecognised spelling is unknown. Branching is by
:class:`GapKind`; readings of different kinds are never compared.

**Unknowns stay unknown.** An unreadable timestamp, a null gap or a missing
family is declared, never coerced. No strategy claim is made: tyre life and
pit loss are estimates by construction, and no record, best-ever or circuit
comparison exists.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from statistics import median

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from f1show.collector import GapKind, classify_gap

#: The families the tactical motor reads. ``intervals`` is optional by
#: construction: the recorded corpus holds it for session 9617 only, so its
#: absence is declared analysis input, never an error.
_INTERVALS = "intervals"
_LAPS = "laps"
_STINTS = "stints"


class _Deterministic(BaseModel):
    """Our own contract: frozen, and an unexpected field is a bug in our code."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TacticalKind(str, Enum):
    """The alert kinds this motor emits."""

    GAP_BATTLE = "gap_battle"
    GAP_LAPPED = "gap_lapped"
    GAP_UNKNOWN = "gap_unknown"
    STALE_READING = "stale_reading"
    PACE_DELTA = "pace_delta"
    TYRE_AGE = "tyre_age"


class TacticalSettings(_Deterministic):
    """The configurable thresholds of the tactical motor.

    Defaults are declared here and pinned by tests; every threshold is a
    session-level judgement, not a circuit-specific fact.
    """

    #: An interval at or under this many seconds is a battle. The leader's own
    #: zero interval is never a battle.
    battle_threshold_seconds: float = Field(default=1.0, gt=0.0)

    #: A driver whose newest reading is more than this many seconds behind the
    #: newest reading overall is stale and feeds no gap alert.
    staleness_seconds: float = Field(default=15.0, gt=0.0)

    #: The number of recent clean laps each driver's pace median is taken
    #: over. Drivers with fewer clean laps than this produce no pace claim.
    pace_window_laps: int = Field(default=5, ge=1)

    #: A driver whose clean-lap median exceeds the session best median by
    #: strictly more than this many seconds gets a pace alert.
    pace_delta_threshold_seconds: float = Field(default=0.5, gt=0.0)

    #: A computed tyre age at or over this many laps alerts. The age is a
    #: declared estimate, never a fact.
    tyre_age_threshold_laps: int = Field(default=25, ge=1)


class SourceRef(_Deterministic):
    """One traceable reference to the source record an alert came from."""

    family: str
    record_index: int = Field(ge=0)
    driver_number: int | None = None
    timestamp: AwareDatetime | None = None


class TacticalAlert(_Deterministic):
    """One tactical alert with its measured facts and source references."""

    kind: TacticalKind
    driver_number: int
    timestamp: AwareDatetime | None = None
    facts: Mapping[str, object]
    sources: tuple[SourceRef, ...] = Field(min_length=1)


def _as_instant(value: object) -> dt.datetime | None:
    """Parse a recorded timestamp, or report the unknown rather than guessing."""
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _sort_key(alert: TacticalAlert) -> tuple[str, str, int, int]:
    """The declared total order: time, kind, driver, first source record."""
    return (
        alert.timestamp.isoformat() if alert.timestamp is not None else "",
        alert.kind.value,
        alert.driver_number,
        alert.sources[0].record_index,
    )


def _latest_readings(
    records: Sequence[Mapping[str, object]], session_key: int
) -> dict[int, tuple[int, Mapping[str, object], dt.datetime]]:
    """Each driver's newest attributed interval row, with its position in time.

    A row whose ``session_key`` differs is not attributed. A row without a
    parseable aware timestamp cannot be placed in time and cannot take part in
    freshness ordering, so it is not a reading; the row is not silently turned
    into a zero-age one. Ties break by record index, the family's own order.
    """
    readings: dict[int, tuple[int, Mapping[str, object], dt.datetime]] = {}
    for index, record in enumerate(records):
        if record.get("session_key") != session_key:
            continue
        when = _as_instant(record.get("date"))
        driver = record.get("driver_number")
        if when is None or not isinstance(driver, int):
            continue
        current = readings.get(driver)
        if current is None or (when, -index) > (current[2], -current[0]):
            readings[driver] = (index, record, when)
    return readings


def _gap_alerts(
    readings: Mapping[int, tuple[int, Mapping[str, object], dt.datetime]],
    settings: TacticalSettings,
) -> Iterable[TacticalAlert]:
    """One gap-family alert per driver's newest fresh reading, via classify_gap.

    Priority is declared: a lapped reading wins (a lapped car's interval is
    not a meaningful battle), then the battle threshold applied to the
    ``interval`` field -- the gap to the car ahead, not to the leader -- and
    only then an unrecognised ``gap_to_leader`` spelling. ``ABSENT`` on both
    fields is declared absence: no alert, no claim.
    """
    if not readings:
        return
    newest_overall = max(when for _, _, when in readings.values())
    for driver, (index, record, when) in sorted(readings.items()):
        age = (newest_overall - when).total_seconds()
        if age > settings.staleness_seconds:
            yield TacticalAlert(
                kind=TacticalKind.STALE_READING,
                driver_number=driver,
                timestamp=when,
                facts={
                    "age_seconds": age,
                    "newest_overall": newest_overall.isoformat(),
                    "staleness_seconds": settings.staleness_seconds,
                },
                sources=(
                    SourceRef(
                        family=_INTERVALS,
                        record_index=index,
                        driver_number=driver,
                        timestamp=when,
                    ),
                ),
            )
            continue
        leader = classify_gap(record.get("gap_to_leader"))
        gap = classify_gap(record.get("interval"))
        source = SourceRef(
            family=_INTERVALS, record_index=index, driver_number=driver, timestamp=when
        )
        if leader.kind is GapKind.LAPS and leader.laps is not None:
            yield TacticalAlert(
                kind=TacticalKind.GAP_LAPPED,
                driver_number=driver,
                timestamp=when,
                facts={"laps": leader.laps},
                sources=(source,),
            )
        elif (
            gap.kind is GapKind.SECONDS
            and gap.seconds is not None
            and 0.0 < gap.seconds <= settings.battle_threshold_seconds
        ):
            yield TacticalAlert(
                kind=TacticalKind.GAP_BATTLE,
                driver_number=driver,
                timestamp=when,
                facts={"interval_seconds": gap.seconds},
                sources=(source,),
            )
        elif leader.kind is GapKind.UNKNOWN:
            yield TacticalAlert(
                kind=TacticalKind.GAP_UNKNOWN,
                driver_number=driver,
                timestamp=when,
                facts={"raw": record.get("gap_to_leader")},
                sources=(source,),
            )
        # ``ABSENT`` on both fields is declared absence: no alert, no claim.


def _recent_pace_windows(
    records: Sequence[Mapping[str, object]], session_key: int, settings: TacticalSettings
) -> dict[int, tuple[float, tuple[tuple[int, float, int, dt.datetime | None], ...]]]:
    """Each driver's clean-lap median over its most recent window.

    A clean lap is a lap-2-or-later record with a positive finite duration
    that is not a pit in/out lap: lap 1 is a standing start and is never
    compared as a lap time, pit laps measure the pit lane, and a null or
    corrupt duration is not a time. A driver with fewer clean laps than the
    window produces no pace claim at all. The window is the driver's most
    recent clean laps by lap number; ties break by record index.
    """
    per_driver: dict[int, list[tuple[int, Mapping[str, object]]]] = {}
    for index, record in enumerate(records):
        if record.get("session_key") != session_key:
            continue
        driver = record.get("driver_number")
        if not isinstance(driver, int):
            continue
        per_driver.setdefault(driver, []).append((index, record))
    windows: dict[int, tuple[float, tuple[tuple[int, float, int, dt.datetime | None], ...]]] = {}
    for driver, rows in per_driver.items():
        clean: list[tuple[int, float, int, dt.datetime | None]] = []
        for index, record in rows:
            lap = record.get("lap_number")
            duration = record.get("lap_duration")
            if isinstance(lap, bool) or not isinstance(lap, int) or lap < 2:
                continue
            if record.get("is_pit_out_lap"):
                continue
            if isinstance(duration, bool) or not isinstance(duration, int | float):
                continue
            seconds = float(duration)
            if not math.isfinite(seconds) or seconds <= 0.0:
                continue
            clean.append((lap, seconds, index, _as_instant(record.get("date_start"))))
        if len(clean) < settings.pace_window_laps:
            continue
        clean.sort(key=lambda item: (item[0], item[2]))
        window = tuple(
            (lap, seconds, index, when)
            for lap, seconds, index, when in clean[-settings.pace_window_laps :]
        )
        windows[driver] = (median(item[1] for item in window), window)
    return windows


def _pace_alerts(
    records: Sequence[Mapping[str, object]], session_key: int, settings: TacticalSettings
) -> Iterable[TacticalAlert]:
    """Pace alerts: a driver's clean-lap median vs the session best median.

    The session best is the minimum of the drivers' medians, all computed
    identically. Only a strictly-greater-than-threshold deficit alerts; the
    best driver (and any driver tied with it) never alerts. No record,
    best-ever or circuit comparison exists: the comparison corpus is exactly
    this session's own clean laps.
    """
    windows = _recent_pace_windows(records, session_key, settings)
    if not windows:
        return
    best = min(value for value, _ in windows.values())
    for driver, (value, window) in sorted(windows.items()):
        delta = value - best
        if delta <= settings.pace_delta_threshold_seconds:
            continue
        yield TacticalAlert(
            kind=TacticalKind.PACE_DELTA,
            driver_number=driver,
            timestamp=window[-1][2],
            facts={
                "median_seconds": value,
                "best_median_seconds": best,
                "delta_seconds": delta,
                "window_laps": settings.pace_window_laps,
            },
            sources=tuple(
                SourceRef(family=_LAPS, record_index=index, driver_number=driver, timestamp=when)
                for _, _, index, when in window
            ),
        )


def _last_completed_laps(
    records: Sequence[Mapping[str, object]], session_key: int
) -> dict[int, tuple[int, int, dt.datetime | None]]:
    """Each driver's last completed clean lap: number, record index, instant.

    A completed lap is a real lap: a non-null finite positive duration on a
    non-pit in/out record. Pit in/out laps and null or corrupt durations are
    not completed laps of racing; lap 1 is a completed lap and counts for
    wear, though never as a comparable lap time.
    """
    last: dict[int, tuple[int, int, dt.datetime | None]] = {}
    for index, record in enumerate(records):
        if record.get("session_key") != session_key:
            continue
        driver = record.get("driver_number")
        lap = record.get("lap_number")
        duration = record.get("lap_duration")
        if not isinstance(driver, int):
            continue
        if isinstance(lap, bool) or not isinstance(lap, int):
            continue
        if record.get("is_pit_out_lap"):
            continue
        if isinstance(duration, bool) or not isinstance(duration, int | float):
            continue
        seconds = float(duration)
        if not math.isfinite(seconds) or seconds <= 0.0:
            continue
        current = last.get(driver)
        if current is None or lap > current[0]:
            last[driver] = (lap, index, _as_instant(record.get("date_start")))
    return last


def _tyre_alerts(
    lap_records: Sequence[Mapping[str, object]],
    stint_records: Sequence[Mapping[str, object]],
    session_key: int,
    settings: TacticalSettings,
) -> Iterable[TacticalAlert]:
    """Tyre-age alerts for each driver's latest stint.

    The computed age is a declared estimate: ``tyre_age_at_start`` plus the
    laps run on the stint up to the driver's last completed clean lap, never
    clamped by the stint's recorded ``lap_end`` (the latest stint is the
    current one) and never read as a fact. A stint with no recorded age at
    start stays unknown. Only the highest stint number per driver is the
    current stint; an ended earlier stint makes no end-state claim. The
    alert fires at or over the threshold.
    """
    last_laps = _last_completed_laps(lap_records, session_key)
    latest_stint: dict[int, tuple[int, int, Mapping[str, object]]] = {}
    for index, record in enumerate(stint_records):
        if record.get("session_key") != session_key:
            continue
        driver = record.get("driver_number")
        stint = record.get("stint_number")
        if not isinstance(driver, int):
            continue
        if isinstance(stint, bool) or not isinstance(stint, int):
            continue
        current = latest_stint.get(driver)
        if current is None or stint > current[0]:
            latest_stint[driver] = (stint, index, record)
    for driver, (stint_number, stint_index, record) in sorted(latest_stint.items()):
        age_at_start = record.get("tyre_age_at_start")
        lap_start = record.get("lap_start")
        if isinstance(age_at_start, bool) or not isinstance(age_at_start, int | float):
            continue
        if isinstance(lap_start, bool) or not isinstance(lap_start, int):
            continue
        completed = last_laps.get(driver)
        stint_laps = max(0, completed[0] - lap_start + 1) if completed is not None else 0
        age = float(age_at_start) + stint_laps
        if age < settings.tyre_age_threshold_laps:
            continue
        sources = [
            SourceRef(family=_STINTS, record_index=stint_index, driver_number=driver, timestamp=None)
        ]
        timestamp: dt.datetime | None = None
        if completed is not None:
            lap_number, lap_index, when = completed
            timestamp = when
            sources.append(
                SourceRef(family=_LAPS, record_index=lap_index, driver_number=driver, timestamp=when)
            )
        yield TacticalAlert(
            kind=TacticalKind.TYRE_AGE,
            driver_number=driver,
            timestamp=timestamp,
            facts={
                "tyre_age_laps": age,
                "tyre_age_at_start": float(age_at_start),
                "stint_laps": stint_laps,
                "stint_number": stint_number,
                "compound": record.get("compound"),
            },
            sources=tuple(sources),
        )


def analyze_tactics(
    session_key: int,
    payloads: Mapping[str, Sequence[Mapping[str, object]]],
    settings: TacticalSettings | None = None,
) -> tuple[TacticalAlert, ...]:
    """Analyze one recorded session and return its tactical alerts.

    ``payloads`` maps a family name to its recorded records, exactly like
    :func:`f1show.collector.collect_session_events`. Only families this motor
    reads are consulted; a missing family is declared absence. The result is
    sorted by the declared total order of :func:`_sort_key`, so identical
    payloads always produce an identical tuple.
    """
    settings = settings or TacticalSettings()
    alerts: list[TacticalAlert] = []
    interval_records = payloads.get(_INTERVALS, [])
    if interval_records:
        alerts.extend(_gap_alerts(_latest_readings(interval_records, session_key), settings))
    lap_records = payloads.get(_LAPS, [])
    if lap_records:
        alerts.extend(_pace_alerts(lap_records, session_key, settings))
    stint_records = payloads.get(_STINTS, [])
    if stint_records:
        alerts.extend(_tyre_alerts(lap_records, stint_records, session_key, settings))
    return tuple(sorted(alerts, key=_sort_key))


__all__ = [
    "SourceRef",
    "TacticalAlert",
    "TacticalKind",
    "TacticalSettings",
    "analyze_tactics",
]

