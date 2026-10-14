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
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from f1show.collector import GapKind, classify_gap

#: The families the tactical motor reads. ``intervals`` is optional by
#: construction: the recorded corpus holds it for session 9617 only, so its
#: absence is declared analysis input, never an error.
_INTERVALS = "intervals"


class _Deterministic(BaseModel):
    """Our own contract: frozen, and an unexpected field is a bug in our code."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TacticalKind(str, Enum):
    """The alert kinds this motor emits."""

    GAP_BATTLE = "gap_battle"
    GAP_LAPPED = "gap_lapped"
    GAP_UNKNOWN = "gap_unknown"
    STALE_READING = "stale_reading"


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
    return tuple(sorted(alerts, key=_sort_key))


__all__ = [
    "SourceRef",
    "TacticalAlert",
    "TacticalKind",
    "TacticalSettings",
    "analyze_tactics",
]

