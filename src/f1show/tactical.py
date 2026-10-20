"""Deterministic tactical analysis over recorded OpenF1 payloads (F06a, F06c).

``analyze_tactics`` is the single entry point: it takes the raw recorded
payloads of one session and returns a total-ordered tuple of alerts, each
traceable to the exact source record that produced it. It is pure: no network,
no clock, no randomness, and identical payloads always produce an identical
tuple.

**Scope of this unit (F06a, and F06c for the qualifying cutoff motor).**
Recorded-corpus-only analysis of gaps, freshness, pace and stint age, plus
qualifying cutoffs from :func:`analyze_qualifying_cutoffs`: the second pure
entry point this module carries, which reads the declared per-season rules in
:mod:`f1show.standings` and no constant of any venue. Telemetry
(car/location/weather), FastF1, Redis delivery, wiring either motor into the
booth or the run path, and audio are out of scope; the booth and the run path
are deliberately untouched.

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
from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from functools import cache
from statistics import median
from typing import cast

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from f1show.collector import GapKind, classify_gap
from f1show.standings import QualifyingRules, QualifyingSessionKind, qualifying_rules

#: The families the tactical motor reads. ``intervals`` is optional by
#: construction: the recorded corpus holds it for session 9617 only, so its
#: absence is declared analysis input, never an error.
_INTERVALS = "intervals"
_LAPS = "laps"
_STINTS = "stints"

#: The families the qualifying cutoff motor reads. ``intervals`` is absent from
#: the qualifying capture by construction, and that absence is declared.
_RACE_CONTROL = "race_control"
_POSITION = "position"


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

    #: The rendered TACTICAL context block shows at most this many alerts
    #: and states honestly how many are not shown.
    tactical_context_max_alerts: int = Field(default=8, ge=1)


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


@cache
def _cached_instant(value: str) -> dt.datetime | None:
    """Parse one recorded timestamp string once; the corpus repeats it per turn.

    The per-moment context re-reads the same recorded rows for every aired
    turn, so parsing them again each time is the difference between seconds
    and minutes on the recorded session. The parse is pure and the datetime
    immutable, so the cache is safe.
    """
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _as_instant(value: object) -> dt.datetime | None:
    """Parse a recorded timestamp, or report the unknown rather than guessing."""
    if not isinstance(value, str):
        return None
    return _cached_instant(value)


def _sort_key(alert: TacticalAlert) -> tuple[str, str, int, int]:
    """The declared total order: time, kind, driver, first source record."""
    return (
        alert.timestamp.isoformat() if alert.timestamp is not None else "",
        alert.kind.value,
        alert.driver_number,
        alert.sources[0].record_index,
    )


def _latest_readings(
    records: Sequence[Mapping[str, object]],
    session_key: int,
    as_of: dt.datetime | None = None,
) -> dict[int, tuple[int, Mapping[str, object], dt.datetime]]:
    """Each driver's newest attributed interval row, with its position in time.

    A row whose ``session_key`` differs is not attributed. A row without a
    parseable aware timestamp cannot be placed in time and cannot take part in
    freshness ordering, so it is not a reading; the row is not silently turned
    into a zero-age one. Ties break by record index, the family's own order.
    With ``as_of``, rows after that instant are simply not yet known: the
    per-moment state reads only the past of the instant.
    """
    readings: dict[int, tuple[int, Mapping[str, object], dt.datetime]] = {}
    for index, record in enumerate(records):
        if record.get("session_key") != session_key:
            continue
        when = _as_instant(record.get("date"))
        driver = record.get("driver_number")
        if when is None or not isinstance(driver, int):
            continue
        if as_of is not None and when > as_of:
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
    records: Sequence[Mapping[str, object]],
    session_key: int,
    settings: TacticalSettings,
    as_of: dt.datetime | None = None,
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
    windows: dict[
        int, tuple[float, tuple[tuple[int, float, int, dt.datetime | None], ...]]
    ] = {}
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
            when = _as_instant(record.get("date_start"))
            if as_of is not None and (when is None or when > as_of):
                # With a cutoff, a lap without a known instant cannot be
                # placed in the past and is not yet comparable.
                continue
            clean.append((lap, seconds, index, when))
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
    records: Sequence[Mapping[str, object]],
    session_key: int,
    settings: TacticalSettings,
    as_of: dt.datetime | None = None,
) -> Iterable[TacticalAlert]:
    """Pace alerts: a driver's clean-lap median vs the session best median.

    The session best is the minimum of the drivers' medians, all computed
    identically. Only a strictly-greater-than-threshold deficit alerts; the
    best driver (and any driver tied with it) never alerts. No record,
    best-ever or circuit comparison exists: the comparison corpus is exactly
    this session's own clean laps.
    """
    windows = _recent_pace_windows(records, session_key, settings, as_of)
    if not windows:
        return
    best = min(value for value, _ in windows.values())
    for driver, (value, window) in sorted(windows.items()):
        delta = value - best
        if delta <= settings.pace_delta_threshold_seconds:
            continue
        # The window's last KNOWN instant: a window ending on a lap with no
        # recorded date_start cannot place the alert at that lap, and a bare
        # None would misorder it; the alert carries the latest instant it can
        # prove, or None only when its whole window lacks one.
        timestamp = next(
            (item[3] for item in reversed(window) if item[3] is not None),
            None,
        )
        yield TacticalAlert(
            kind=TacticalKind.PACE_DELTA,
            driver_number=driver,
            timestamp=timestamp,
            facts={
                "median_seconds": value,
                "best_median_seconds": best,
                "delta_seconds": delta,
                "window_laps": settings.pace_window_laps,
            },
            sources=tuple(
                SourceRef(
                    family=_LAPS,
                    record_index=index,
                    driver_number=driver,
                    timestamp=when,
                )
                for _, _, index, when in window
            ),
        )


def _last_completed_laps(
    records: Sequence[Mapping[str, object]],
    session_key: int,
    as_of: dt.datetime | None = None,
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
        when = _as_instant(record.get("date_start"))
        if as_of is not None and (when is None or when > as_of):
            continue
        current = last.get(driver)
        if current is None or lap > current[0]:
            last[driver] = (lap, index, when)
    return last


def _tyre_alerts(
    lap_records: Sequence[Mapping[str, object]],
    stint_records: Sequence[Mapping[str, object]],
    session_key: int,
    settings: TacticalSettings,
    as_of: dt.datetime | None = None,
) -> Iterable[TacticalAlert]:
    """Tyre-age alerts for each driver's latest stint.

    The computed age is a declared estimate: ``tyre_age_at_start`` plus the
    laps run on the stint up to the driver's last completed clean lap, never
    clamped by the stint's recorded ``lap_end`` (the latest stint is the
    current one) and never read as a fact. A stint with no recorded age at
    start stays unknown. Only the highest stint number per driver is the
    current stint; an ended earlier stint makes no end-state claim. The
    alert fires at or over the threshold. With ``as_of``, a stint counts as
    current only once it has started: its ``lap_start`` must not exceed the
    driver's last completed lap at that instant, and a driver with no
    completed lap yet makes no tyre claim.
    """
    last_laps = _last_completed_laps(lap_records, session_key, as_of)
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
        if as_of is not None:
            completed = last_laps.get(driver)
            lap_start = record.get("lap_start")
            if completed is None:
                continue
            if isinstance(lap_start, bool) or not isinstance(lap_start, int):
                continue
            if lap_start > completed[0]:
                # The stint has not started yet at this instant.
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
        stint_laps = (
            max(0, completed[0] - lap_start + 1) if completed is not None else 0
        )
        age = float(age_at_start) + stint_laps
        if age < settings.tyre_age_threshold_laps:
            continue
        sources = [
            SourceRef(
                family=_STINTS,
                record_index=stint_index,
                driver_number=driver,
                timestamp=None,
            )
        ]
        timestamp: dt.datetime | None = None
        if completed is not None:
            lap_number, lap_index, when = completed
            timestamp = when
            sources.append(
                SourceRef(
                    family=_LAPS,
                    record_index=lap_index,
                    driver_number=driver,
                    timestamp=when,
                )
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
    as_of: dt.datetime | None = None,
) -> tuple[TacticalAlert, ...]:
    """Analyze one recorded session and return its tactical alerts.

    ``payloads`` maps a family name to its recorded records, exactly like
    :func:`f1show.collector.collect_session_events`. Only families this motor
    reads are consulted; a missing family is declared absence. The result is
    sorted by the declared total order of :func:`_sort_key`, so identical
    payloads always produce an identical tuple. With ``as_of``, the analysis
    reads only the past of that instant -- each family's rows at or before
    it -- so the same call yields the per-moment state a turn's prompt can
    carry; the end state is exactly ``as_of=None``.
    """
    settings = settings or TacticalSettings()
    alerts: list[TacticalAlert] = []
    interval_records = payloads.get(_INTERVALS, [])
    if interval_records:
        alerts.extend(
            _gap_alerts(
                _latest_readings(interval_records, session_key, as_of), settings
            )
        )
    lap_records = payloads.get(_LAPS, [])
    if lap_records:
        alerts.extend(_pace_alerts(lap_records, session_key, settings, as_of))
    stint_records = payloads.get(_STINTS, [])
    if stint_records:
        alerts.extend(
            _tyre_alerts(lap_records, stint_records, session_key, settings, as_of)
        )
    return tuple(sorted(alerts, key=_sort_key))


# --- F06c: the qualifying cutoff motor -----------------------------------------------
#
# The second pure entry point of this module. It consumes the declared per-season rules
# that ``f1show.standings`` states and the recorded payloads of one qualifying session,
# and it returns a total-ordered reading of the elimination line at one instant. Every
# number it reports is either declared (and traceable to the rule table) or measured
# (and traceable to the ``SourceRef`` of the record that produced it); what neither
# source states is an absence, never a zero.

#: The declared absences, verbatim in the result. Each names what is missing and what
#: the motor therefore refuses to claim, so a reader never has to infer either.
_ABSENT_INTERVALS = (
    "the intervals family is absent from these payloads: lapped and null intervals "
    "are declared unknown, never zero"
)
_ABSENT_RACE_CONTROL = (
    "the race_control family is absent from these payloads: no phase window is known "
    "and every boundary is declared absent"
)
_ABSENT_POSITION = (
    "the position family is absent from these payloads: no driver's place is read"
)
_ABSENT_LAPS = "the laps family is absent from these payloads: no hot lap is counted"


class QualifyingBoundarySource(str, Enum):
    """Where one phase boundary came from.

    ``SOURCE`` is a recorded ``race_control`` row, ``DECLARED`` is the declared phase
    length applied to a recorded start, and ``ABSENT`` is neither: the instant is
    unknown, and an unknown boundary is reported as unknown rather than guessed.
    """

    SOURCE = "source"
    DECLARED = "declared"
    ABSENT = "absent"


class QualifyingPhaseRule(str, Enum):
    """What the declared rules say one phase does to the drivers in it.

    ``ELIMINATES`` is every phase but the last: its participants who are not inside
    the line leave the session. ``CLASSIFIES`` is the last phase, which classifies its
    participants and eliminates nobody -- stated, never left to be inferred from a
    zero.
    """

    ELIMINATES = "eliminates"
    CLASSIFIES = "classifies"


class QualifyingStanding(str, Enum):
    """Where one driver stands against the elimination line of the active phase.

    ``ADVANCING`` and ``ELIMINATED`` are the two sides of the line, ``CLASSIFIED`` is
    the last phase's verdict for every driver it places, and ``UNRANKED`` is declared
    absence rather than a verdict: the driver has no comparable lap inside the window,
    so this motor makes no claim about whether that driver advances.
    """

    ADVANCING = "advancing"
    ELIMINATED = "eliminated"
    CLASSIFIED = "classified"
    UNRANKED = "unranked"


class QualifyingPhaseWindow(_Deterministic):
    """One declared phase, with the boundaries the source states and the rules it obeys.

    ``participants`` and ``advancing`` are declared: the phase's entrant count, and how
    many of them move on (the next phase's entrant count, or ``0`` in the phase that
    classifies). ``declared_duration_minutes`` is always reported, and so is the
    measured end when the source carries one, so a disagreement between the rule and
    the recording is visible instead of resolved silently: ``end`` is the instant the
    reading uses and ``end_source`` says which of the two produced it.

    ``hot_laps``, ``pit_out_laps_excluded`` and ``unreadable_laps_excluded`` are the
    declared counts of the lap corpus inside this window. All three are ``None`` while
    the window itself is unknown: an unknown window has no lap count, and reporting
    ``0`` would be a claim the capture does not support.
    """

    phase: int
    rule: QualifyingPhaseRule
    participants: int = Field(ge=1)
    advancing: int = Field(ge=0)
    declared_duration_minutes: int = Field(ge=1)
    start_source: QualifyingBoundarySource
    start: AwareDatetime | None = None
    measured_end: AwareDatetime | None = None
    declared_end: AwareDatetime | None = None
    end_source: QualifyingBoundarySource = QualifyingBoundarySource.ABSENT
    end: AwareDatetime | None = None
    hot_laps: int | None = Field(default=None, ge=0)
    pit_out_laps_excluded: int | None = Field(default=None, ge=0)
    unreadable_laps_excluded: int | None = Field(default=None, ge=0)
    sources: tuple[SourceRef, ...] = ()


class QualifyingStandingRow(_Deterministic):
    """One driver's place in the active phase: the classification and the live order.

    ``lap_position`` is the classification this motor derives -- rank by best eligible
    hot lap inside the window, ties broken by the earlier recorded lap start and then
    by driver number -- and it is what the verdict rests on, because that is what
    qualifying advances on. ``position`` is the source's own live running order as of
    the reading's instant, reported because it is a source fact and not a substitute
    for the classification; ``position_agrees`` says whether the two coincide, so a
    live order that lags the classification is visible instead of silent, and
    ``reading_age_seconds`` measures how old that reading was at the instant.

    Every part is ``None`` when its own source says nothing: no lap inside the window
    means no lap time, no lap rank and no lap source, and no ``position`` row inside
    the window means no place, no place source and no age.
    """

    driver_number: int
    standing: QualifyingStanding
    lap_position: int | None = Field(default=None, ge=1)
    best_lap_seconds: float | None = None
    lap_source: SourceRef | None = None
    position: int | None = Field(default=None, ge=1)
    position_source: SourceRef | None = None
    reading_age_seconds: float | None = None
    position_agrees: bool | None = None


class QualifyingCutoffReading(_Deterministic):
    """The cutoff of one qualifying session at one instant.

    ``phases`` states the declared phase structure with the boundaries known at
    ``as_of``; ``active_phase`` is the last phase whose window has started by then and
    ``line`` is that phase's declared advancement count, or ``None`` when the active
    phase is the one that classifies and nobody is eliminated. ``standings`` places
    every driver the source mentions in the active window against that line.

    ``absences`` names every family the payloads do not carry, in the order this motor
    reads them; ``laps_without_instant`` counts the recorded laps no window can ever
    hold, and ``laps_outside_every_window`` counts the placed laps that at ``as_of``
    fall in no known window -- a break lap is not a hot lap either.
    """

    season: int
    session_kind: QualifyingSessionKind
    as_of: AwareDatetime
    phases: tuple[QualifyingPhaseWindow, ...]
    active_phase: int | None = None
    line: int | None = None
    standings: tuple[QualifyingStandingRow, ...] = ()
    absences: tuple[str, ...] = ()
    laps_without_instant: int = Field(default=0, ge=0)
    laps_outside_every_window: int = Field(default=0, ge=0)


def _declared_phase_structure(
    rules: QualifyingRules,
) -> tuple[tuple[int, int, int, int, QualifyingPhaseRule], ...]:
    """The declared phases as ``(phase, minutes, participants, advancing, rule)``.

    The advancement count is never read from a payload: it is the *next* declared
    phase's participant count, because that is what the next phase can hold, and the
    last declared phase advances nobody because it classifies.
    """
    structure = []
    for index, phase in enumerate(rules.phases):
        following = rules.phases[index + 1] if index + 1 < len(rules.phases) else None
        structure.append(
            (
                phase.phase,
                phase.duration_minutes,
                phase.participants,
                following.participants if following is not None else 0,
                QualifyingPhaseRule.ELIMINATES
                if following is not None
                else QualifyingPhaseRule.CLASSIFIES,
            )
        )
    return tuple(structure)


def _phase_markers(
    records: Sequence[Mapping[str, object]],
    session_key: int,
    as_of: dt.datetime,
) -> dict[int, tuple[tuple[int, dt.datetime] | None, tuple[int, dt.datetime] | None]]:
    """Each phase's recorded start and end rows, as ``(index, instant)`` or ``None``.

    Only ``SESSION STARTED`` and ``SESSION FINISHED`` rows carrying a
    ``qualifying_phase`` state a boundary: a row without one is not a phase fact, and a
    row after ``as_of`` is not yet known. Where a family repeats a marker, the earliest
    recorded one is the boundary and the later ones are not re-read as it.
    """
    markers: dict[
        int, tuple[tuple[int, dt.datetime] | None, tuple[int, dt.datetime] | None]
    ] = {}
    for index, record in enumerate(records):
        if record.get("session_key") != session_key:
            continue
        phase = record.get("qualifying_phase")
        if isinstance(phase, bool) or not isinstance(phase, int):
            continue
        message = record.get("message")
        when = _as_instant(record.get("date"))
        if when is None or when > as_of:
            continue
        if message not in ("SESSION STARTED", "SESSION FINISHED"):
            continue
        start, end = markers.get(phase, (None, None))
        if message == "SESSION STARTED":
            if start is None or (when, index) < start:
                start = (index, when)
        elif end is None or (when, index) < end:
            end = (index, when)
        markers[phase] = (start, end)
    return markers


def _active_phase(
    phases: Sequence[QualifyingPhaseWindow],
) -> QualifyingPhaseWindow | None:
    """The last declared phase whose window has started, in declared order.

    Before the first phase starts there is no active phase and therefore no line; a
    moment in a break between two phases belongs to the phase that has just run, so the
    reading keeps stating its line rather than pretending no phase ever began.
    """
    active: QualifyingPhaseWindow | None = None
    for phase in phases:
        if phase.start is not None:
            active = phase
    return active


def _phase_of(
    phases: Sequence[QualifyingPhaseWindow], instant: dt.datetime
) -> QualifyingPhaseWindow | None:
    """The known window holding ``instant``; both boundaries are inside it.

    A lap starting exactly at a phase's start or exactly at its end is a lap of that
    phase. Windows are declared in order and a lap belongs to the last one holding it,
    so the assignment is total and deterministic even if two windows ever overlapped.
    """
    holding = [
        phase
        for phase in phases
        if phase.start is not None
        and phase.end is not None
        and phase.start <= instant <= phase.end
    ]
    return holding[-1] if holding else None


def _standings(
    active: QualifyingPhaseWindow | None,
    best_laps: Mapping[tuple[int, int], tuple[float, dt.datetime | None, int]],
    position_records: Sequence[Mapping[str, object]],
    session_key: int,
    as_of: dt.datetime,
) -> tuple[QualifyingStandingRow, ...]:
    """Every driver the source mentions in the active window, against its line.

    The verdict rests on the lap classification: a driver with no comparable lap is
    ``UNRANKED`` and this motor claims nothing about the line for that driver, even
    when a live position reading exists. ``position`` is that reading -- the newest
    ``position`` row inside the window at or before ``as_of``, where the family carries
    no lap number and no phase and the ``date`` filter is the only phase filter there
    is. Equal best lap times break by the earlier recorded start, then by driver
    number, so the order is total without a field the source does not carry.
    """
    if active is None or active.start is None or active.end is None:
        return ()
    ranked = {
        driver: entry
        for (phase, driver), entry in best_laps.items()
        if phase == active.phase
    }
    order = sorted(ranked.items(), key=lambda item: (item[1][0], item[1][1], item[0]))
    lap_position = {driver: place for place, (driver, _) in enumerate(order, start=1)}
    newest: dict[int, tuple[int, Mapping[str, object], dt.datetime]] = {}
    for index, record in enumerate(position_records):
        if record.get("session_key") != session_key:
            continue
        when = _as_instant(record.get("date"))
        driver = record.get("driver_number")
        place = record.get("position")
        if when is None or not isinstance(driver, int) or isinstance(place, bool):
            continue
        if not isinstance(place, int) or place < 1:
            continue
        if when > as_of or not active.start <= when <= active.end:
            continue
        current = newest.get(driver)
        if current is None or (when, -index) > (current[2], -current[0]):
            newest[driver] = (index, record, when)
    rows = []
    for driver in sorted(set(ranked) | set(newest)):
        placed = newest.get(driver)
        rank = lap_position.get(driver)
        if rank is None:
            standing = QualifyingStanding.UNRANKED
        elif active.rule is QualifyingPhaseRule.CLASSIFIES:
            standing = QualifyingStanding.CLASSIFIED
        elif rank <= active.advancing:
            standing = QualifyingStanding.ADVANCING
        else:
            standing = QualifyingStanding.ELIMINATED
        lap = ranked.get(driver)
        position = cast(int, placed[1]["position"]) if placed is not None else None
        rows.append(
            QualifyingStandingRow(
                driver_number=driver,
                standing=standing,
                lap_position=rank,
                best_lap_seconds=lap[0] if lap is not None else None,
                lap_source=(
                    SourceRef(
                        family=_LAPS,
                        record_index=lap[2],
                        driver_number=driver,
                        timestamp=lap[1],
                    )
                    if lap is not None
                    else None
                ),
                position=position,
                position_source=(
                    SourceRef(
                        family=_POSITION,
                        record_index=placed[0],
                        driver_number=driver,
                        timestamp=placed[2],
                    )
                    if placed is not None
                    else None
                ),
                reading_age_seconds=(
                    (as_of - placed[2]).total_seconds() if placed is not None else None
                ),
                position_agrees=(
                    position == rank
                    if position is not None and rank is not None
                    else None
                ),
            )
        )
    rows.sort(
        key=lambda row: (
            row.lap_position is None,
            row.lap_position or 0,
            row.driver_number,
        )
    )
    return tuple(rows)


def analyze_qualifying_cutoffs(
    session_key: int,
    season: int,
    session_kind: QualifyingSessionKind | str,
    payloads: Mapping[str, Sequence[Mapping[str, object]]],
    as_of: dt.datetime,
) -> QualifyingCutoffReading:
    """Read the qualifying cutoff of one recorded session at one instant.

    The rules come from :func:`f1show.standings.qualifying_rules`, which refuses a
    season or a session kind nobody declared before a single payload is read; the
    windows come from the ``race_control`` rows that carry a ``qualifying_phase`` and a
    ``SESSION STARTED``/``SESSION FINISHED`` pair, falling back to the declared phase
    length when the source states no end, and ``end_source`` says which of the two it
    used. A hot lap is a lap of this session starting inside the window with a finite
    positive duration that is not an out-lap: pit-out laps and unreadable durations are
    excluded and counted, in the window they were excluded from.

    ``position`` rows carry no lap number and no phase, so the only phase filter they
    admit is their ``date``; they are reported as the source's live order, while the
    classification and the verdict come from the lap times, which is what advances a
    driver. Deletion notices are not applied: ``race_control`` states them as free text
    with no phase and no lap key this motor can bind to a lap, so a deleted time can
    still be the fastest one reported here, and that limitation is pinned by a test
    instead of being left for a reader to assume away. A family the payloads do not
    carry is named in ``absences``. Nothing here reads a clock, a file, the network or
    a random source, so identical payloads and an identical instant produce an
    identical reading.
    """
    rules = qualifying_rules(season, session_kind)
    race_control = payloads.get(_RACE_CONTROL, ())
    lap_records = payloads.get(_LAPS, ())
    position_records = payloads.get(_POSITION, ())
    markers = _phase_markers(race_control, session_key, as_of)

    windows: list[QualifyingPhaseWindow] = []
    for phase, minutes, participants, advancing, rule in _declared_phase_structure(
        rules
    ):
        start_marker, end_marker = markers.get(phase, (None, None))
        start = start_marker[1] if start_marker is not None else None
        measured_end = end_marker[1] if end_marker is not None else None
        declared_end = (
            start + dt.timedelta(minutes=minutes) if start is not None else None
        )
        if measured_end is not None:
            end, end_source = measured_end, QualifyingBoundarySource.SOURCE
        elif declared_end is not None:
            end, end_source = declared_end, QualifyingBoundarySource.DECLARED
        else:
            end, end_source = None, QualifyingBoundarySource.ABSENT
        windows.append(
            QualifyingPhaseWindow(
                phase=phase,
                rule=rule,
                participants=participants,
                advancing=advancing,
                declared_duration_minutes=minutes,
                start=start,
                start_source=(
                    QualifyingBoundarySource.SOURCE
                    if start is not None
                    else QualifyingBoundarySource.ABSENT
                ),
                measured_end=measured_end,
                declared_end=declared_end,
                end=end,
                end_source=end_source,
                sources=tuple(
                    SourceRef(
                        family=_RACE_CONTROL,
                        record_index=marker[0],
                        timestamp=marker[1],
                    )
                    for marker in (start_marker, end_marker)
                    if marker is not None
                ),
            )
        )

    hot = dict.fromkeys((window.phase for window in windows), 0)
    pit_out = dict(hot)
    unreadable = dict(hot)
    best_laps: dict[tuple[int, int], tuple[float, dt.datetime | None, int]] = {}
    laps_without_instant = 0
    laps_outside_every_window = 0
    for index, record in enumerate(lap_records):
        if record.get("session_key") != session_key:
            continue
        when = _as_instant(record.get("date_start"))
        if when is None:
            # No instant means no window can ever hold this lap.
            laps_without_instant += 1
            continue
        if when > as_of:
            continue
        phase = _phase_of(windows, when)
        if phase is None:
            laps_outside_every_window += 1
            continue
        if record.get("is_pit_out_lap"):
            # An out-lap measures the pit lane, never a qualifying lap.
            pit_out[phase.phase] += 1
            continue
        seconds = record.get("lap_duration")
        if isinstance(seconds, bool) or not isinstance(seconds, int | float):
            unreadable[phase.phase] += 1
            continue
        seconds = float(seconds)
        if not math.isfinite(seconds) or seconds <= 0.0:
            unreadable[phase.phase] += 1
            continue
        hot[phase.phase] += 1
        driver = record.get("driver_number")
        if not isinstance(driver, int):
            continue
        key = (phase.phase, driver)
        current = best_laps.get(key)
        candidate = (seconds, when, index)
        if current is None or (candidate[0], candidate[1], candidate[2]) < (
            current[0],
            current[1],
            current[2],
        ):
            best_laps[key] = candidate

    known: list[QualifyingPhaseWindow] = []
    for window in windows:
        if window.start is None or window.end is None:
            # An unknown window has no lap count; zero would be a fabricated claim.
            known.append(window)
            continue
        known.append(
            window.model_copy(
                update={
                    "hot_laps": hot[window.phase],
                    "pit_out_laps_excluded": pit_out[window.phase],
                    "unreadable_laps_excluded": unreadable[window.phase],
                }
            )
        )

    active = _active_phase(known)
    absences = []
    if not payloads.get(_INTERVALS):
        absences.append(_ABSENT_INTERVALS)
    if not race_control:
        absences.append(_ABSENT_RACE_CONTROL)
    if not position_records:
        absences.append(_ABSENT_POSITION)
    if not lap_records:
        absences.append(_ABSENT_LAPS)
    return QualifyingCutoffReading(
        season=rules.season,
        session_kind=rules.session_kind,
        as_of=as_of,
        phases=tuple(known),
        active_phase=active.phase if active is not None else None,
        line=(
            active.advancing
            if active is not None and active.rule is QualifyingPhaseRule.ELIMINATES
            else None
        ),
        standings=_standings(active, best_laps, position_records, session_key, as_of),
        absences=tuple(absences),
        laps_without_instant=laps_without_instant,
        laps_outside_every_window=laps_outside_every_window,
    )


class TacticalSource:
    """The booth's per-moment tactical context, built once from recorded payloads.
    The source is the F06a motor viewed at a moving cutoff: ``context``
    returns the alerts as of one instant, each derived from the readings that
    existed at or before it. The end state and every earlier moment come from
    the same classification, so a turn's prompt can never see the future.

    The interval rows are parsed and ordered per driver **once**, at build
    time, and each ``context`` call bisects for the cutoff instead of
    re-scanning the family: a recorded run asks for a context per aired
    turn, and re-reading 21,041 rows per turn is the difference between
    seconds and minutes. The classification itself is not duplicated -- the
    per-driver selections feed the motor's own ``_gap_alerts``, and pace and
    stint age still run through the motor's helpers over the laps and stints.
    """

    def __init__(
        self,
        session_key: int,
        payloads: Mapping[str, Sequence[Mapping[str, object]]],
        settings: TacticalSettings,
    ) -> None:
        self.session_key = session_key
        self.settings = settings
        per_driver: dict[int, list[tuple[dt.datetime, int, Mapping[str, object]]]] = {}
        for index, record in enumerate(payloads.get(_INTERVALS, ())):
            if record.get("session_key") != session_key:
                continue
            when = _as_instant(record.get("date"))
            driver = record.get("driver_number")
            if when is None or not isinstance(driver, int):
                continue
            per_driver.setdefault(driver, []).append((when, index, record))
        self._readings: dict[
            int,
            tuple[
                list[dt.datetime], list[tuple[int, Mapping[str, object], dt.datetime]]
            ],
        ] = {}
        for driver, rows in per_driver.items():
            rows.sort(key=lambda row: (row[0], row[1]))
            self._readings[driver] = (
                [row[0] for row in rows],
                [(row[1], row[2], row[0]) for row in rows],
            )
        self._lap_records = tuple(payloads.get(_LAPS, ()))
        self._stint_records = tuple(payloads.get(_STINTS, ()))

    def context(self, at: dt.datetime) -> tuple[TacticalAlert, ...]:
        """The alerts as of ``at``, from the same deterministic classification.

        Each driver's newest reading at or before ``at`` is selected by
        bisection over the build-time ordering -- the same
        newest-then-lowest-index choice the motor's end state makes -- and
        feeds the same ``_gap_alerts`` branch. Pace and stint age read the
        laps and stints as of ``at`` through the motor's helpers.
        """
        alerts: list[TacticalAlert] = []
        readings: dict[int, tuple[int, Mapping[str, object], dt.datetime]] = {}
        for driver, (whens, rows) in self._readings.items():
            pos = bisect_left(whens, at)
            if pos < len(whens) and whens[pos] == at:
                picked = pos
            elif pos > 0:
                # The newest reading strictly before ``at``: among the rows
                # sharing that instant, the lowest record index, exactly the
                # end state's tie-break.
                picked = bisect_left(whens, whens[pos - 1])
            else:
                continue
            index, record, when = rows[picked]
            readings[driver] = (index, record, when)
        if readings:
            alerts.extend(_gap_alerts(readings, self.settings))
        if self._lap_records:
            alerts.extend(
                _pace_alerts(self._lap_records, self.session_key, self.settings, at)
            )
        if self._stint_records:
            alerts.extend(
                _tyre_alerts(
                    self._lap_records,
                    self._stint_records,
                    self.session_key,
                    self.settings,
                    at,
                )
            )
        return tuple(sorted(alerts, key=_sort_key))


def build_tactical_source(
    session_key: int,
    payloads: Mapping[str, Sequence[Mapping[str, object]]],
    settings: TacticalSettings | None = None,
) -> TacticalSource:
    """Build the per-moment tactical source from the recorded payloads.

    Only the families the motor reads are consulted; a missing family is
    declared absence -- the recorded corpus holds intervals for session 9617
    only, and session 9655 deliberately has none.
    """
    return TacticalSource(
        session_key=session_key,
        payloads=payloads,
        settings=settings or TacticalSettings(),
    )


def _tactical_line(alert: TacticalAlert) -> str:
    """One plain-prose line for the block: no bracket, no reference-shaped token."""
    d = alert.driver_number
    facts = alert.facts
    if alert.kind is TacticalKind.GAP_BATTLE:
        seconds = cast(float, facts["interval_seconds"])
        return f"driver {d} is {seconds:.1f} s behind the car ahead."
    if alert.kind is TacticalKind.GAP_LAPPED:
        laps = cast(int, facts["laps"])
        noun = "lap" if laps == 1 else "laps"
        return f"driver {d} is {laps} {noun} behind the leader."
    if alert.kind is TacticalKind.GAP_UNKNOWN:
        return f"driver {d}'s gap could not be read."
    if alert.kind is TacticalKind.STALE_READING:
        age = cast(float, facts["age_seconds"])
        return f"driver {d} has not reported for {age:.0f} s."
    if alert.kind is TacticalKind.PACE_DELTA:
        delta = cast(float, facts["delta_seconds"])
        return f"driver {d}'s recent pace is {delta:.1f} s off the session's best."
    age = cast(float, facts["tyre_age_laps"])
    return f"driver {d} is on an estimated {age:.0f}-lap tyre age."


def render_tactical(
    alerts: Sequence[TacticalAlert], max_alerts: int = 8
) -> tuple[str, ...]:
    """Render the bounded TACTICAL context block.

    At most ``max_alerts`` lines after the header, in the motor's declared
    total order, each plain prose with no bracket and no reference-shaped
    token, so the block stays context and never a source. A truncated block
    states honestly how many alerts are not shown. An empty context renders
    no block at all -- an empty tuple, a declared absence rather than an
    empty header.
    """
    if not alerts:
        return ()
    lines = ["TACTICAL:"]
    shown = list(alerts[:max_alerts])
    lines.extend(_tactical_line(alert) for alert in shown)
    hidden = len(alerts) - len(shown)
    if hidden > 0:
        noun = "alert" if hidden == 1 else "alerts"
        lines.append(f"and {hidden} more {noun} not shown.")
    return tuple(lines)


__all__ = [
    "QualifyingBoundarySource",
    "QualifyingCutoffReading",
    "QualifyingPhaseRule",
    "QualifyingPhaseWindow",
    "QualifyingStanding",
    "QualifyingStandingRow",
    "SourceRef",
    "TacticalAlert",
    "TacticalKind",
    "TacticalSettings",
    "TacticalSource",
    "analyze_qualifying_cutoffs",
    "analyze_tactics",
    "build_tactical_source",
    "render_tactical",
]
