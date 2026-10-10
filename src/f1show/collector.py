"""Deterministic event detection over recorded OpenF1 payloads (F04).

``collect_session_events`` is the single collection entry point: it takes the
raw recorded payloads of one session and returns a total-ordered tuple of
events, each traceable to the exact source record that produced it.

**Only five families derive events in the MVP**: ``position`` → position
changes, ``laps`` → lap completions, ``pit`` → pit stops, ``stints`` → stint
starts and ``race_control`` → race-control records. No other family is read and
no other event type is emitted.

**Deliberate non-claims.** No ``overtake`` event is emitted: nothing in these
fixtures proves an on-track pass, and a position change can come from a pit
stop, a penalty, a retirement or a car being lapped. No fastest-lap, record or
best-sector claim is emitted: a record needs a comparison corpus that does not
exist, sector data is partial and lap 1 is a standing start, so lap 1 is never
compared as a lap time. ``intervals`` derives no events at all; its gap values
are normalized by :func:`classify_gap`, which preserves ``+1 LAP`` as a lap
count rather than casting it to a number.

**Unknowns stay unknown.** A record with no timestamp, a null timestamp or a
null duration is represented with an explicit ``None`` and, when applicable, the
reason it has none. Nothing is coerced to ``0`` or silently dropped.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from f1show.events import EventType

#: The families that derive events, in the family rank used to break timestamp
#: ties. This order is part of the documented total order and must not change
#: silently: changing it changes the event sequence.
FAMILY_ORDER: tuple[str, ...] = ("position", "laps", "pit", "stints", "race_control")

_FAMILY_RANK = {family: rank for rank, family in enumerate(FAMILY_ORDER)}

_EVENT_TYPE = {
    "position": EventType.POSITION_CHANGE,
    "laps": EventType.LAP_COMPLETED,
    "pit": EventType.PIT_STOP,
    "stints": EventType.STINT_START,
    "race_control": EventType.RACE_CONTROL,
}

#: The timestamp field each family actually carries; ``None`` means the family
#: has no timestamp field at all and no other family's clock may be borrowed.
_TIMESTAMP_FIELD: dict[str, str | None] = {
    "position": "date",
    "laps": "date_start",
    "pit": "date",
    "stints": None,
    "race_control": "date",
}

#: What identifies one source record within its family, so a repeated update is
#: deduplicated by source identity and observation time rather than by intent.
_IDENTITY_FIELDS = {
    "position": ("driver_number",),
    "laps": ("driver_number", "lap_number"),
    "pit": ("driver_number", "lap_number"),
    "stints": ("driver_number", "stint_number"),
    "race_control": (
        "driver_number", "lap_number", "category", "flag", "scope", "sector", "message",
    ),
}

#: The family's own fields kept as evidence, with their recorded values untouched.
_EVIDENCE_FIELDS = {
    "position": ("position",),
    "laps": (
        "lap_number", "lap_duration",
        "duration_sector_1", "duration_sector_2", "duration_sector_3",
        "segments_sector_1", "segments_sector_2", "segments_sector_3",
        "is_pit_out_lap", "i1_speed", "i2_speed", "st_speed",
    ),
    "pit": ("lap_number", "lane_duration", "pit_duration", "stop_duration"),
    "stints": ("stint_number", "lap_start", "lap_end", "compound", "tyre_age_at_start"),
    "race_control": (
        "category", "flag", "scope", "sector", "lap_number", "qualifying_phase", "message",
    ),
}

_NO_TIMESTAMP_FIELD = "family_carries_no_timestamp_field"
_MISSING_TIMESTAMP_VALUE = "record_field_missing_or_null"

_GAP_PATTERN = re.compile(r"^\+(\d+) LAP$")


class _Deterministic(BaseModel):
    """Our own contract: frozen, and an unexpected field is a bug in our code."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GapKind(str, Enum):
    """How a recorded gap value is expressed, before any interpretation."""

    SECONDS = "seconds"
    LAPS = "laps"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class GapReading(_Deterministic):
    """One normalized gap value.

    ``+1 LAP`` becomes ``LAPS`` with ``laps=1`` and ``seconds=None``: a lapped
    gap is not a duration and is never turned into one. ``None`` is ``ABSENT``,
    and an unrecognised spelling, an unrepresentable magnitude or a non-finite
    number is ``UNKNOWN`` rather than an exception.
    """

    kind: GapKind
    seconds: float | None = None
    laps: int | None = None

    @model_validator(mode="after")
    def _value_matches_kind(self) -> GapReading:
        if self.kind is GapKind.SECONDS and self.seconds is None:
            raise ValueError("a seconds reading must carry its value")
        if self.kind is GapKind.LAPS and self.laps is None:
            raise ValueError("a laps reading must carry its lap count")
        if self.kind in (GapKind.ABSENT, GapKind.UNKNOWN) and (
            self.seconds is not None or self.laps is not None
        ):
            raise ValueError("an absent or unknown reading carries no value")
        return self


class DetectedEvent(_Deterministic):
    """One event, rooted in exactly one source record.

    ``family`` and ``record_index`` locate the producing record inside the
    payload it came from; ``timestamp_field`` names the field actually used and
    ``timestamp_value`` carries it, or ``timestamp_unknown_reason`` says why the
    event has no instant. ``evidence`` holds the family's own recorded fields.
    """

    event_type: EventType
    family: str
    session_key: int
    record_index: int = Field(ge=0)
    driver_number: int | None = None
    timestamp_field: str | None = None
    timestamp_value: AwareDatetime | None = None
    timestamp_unknown_reason: str | None = None
    evidence: dict[str, object]

    @model_validator(mode="after")
    def _unknown_is_explicit(self) -> DetectedEvent:
        if self.timestamp_value is None and self.timestamp_unknown_reason is None:
            raise ValueError("an event without a timestamp value must state why it has none")
        if self.timestamp_value is not None and self.timestamp_unknown_reason is not None:
            raise ValueError("an event with a timestamp value must not also state its absence")
        return self


def _as_int(value: object) -> int | None:
    """Return ``value`` when it is a real integer, otherwise an explicit unknown."""
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


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


def classify_gap(raw: object) -> GapReading:
    """Classify one raw ``gap_to_leader`` or ``interval`` value.

    This is the normalization surface for ``intervals``: the family derives no
    events in the MVP, so its values are classified here and their tactical
    reading is left to the deferred unit.

    A numeric value that cannot be represented as a duration is ``UNKNOWN``
    rather than an exception or a meaningless number: a value too large for a
    float (a corrupt payload can carry a Python ``int`` of arbitrary width) and
    a non-finite ``inf``/``-inf``/``nan`` both stay unknown.
    """
    if raw is None:
        return GapReading(kind=GapKind.ABSENT)
    if isinstance(raw, bool):
        return GapReading(kind=GapKind.UNKNOWN)
    if isinstance(raw, int | float):
        try:
            seconds = float(raw)
        except (OverflowError, ValueError):
            return GapReading(kind=GapKind.UNKNOWN)
        # Parent decision, not the verifier's finding: a non-finite number is
        # not a duration, and handing ``inf`` downstream as "seconds" would be
        # a value that means nothing and that a later unit could misread.
        if not math.isfinite(seconds):
            return GapReading(kind=GapKind.UNKNOWN)
        return GapReading(kind=GapKind.SECONDS, seconds=seconds)
    if isinstance(raw, str):
        match = _GAP_PATTERN.match(raw)
        if match is not None:
            return GapReading(kind=GapKind.LAPS, laps=int(match.group(1)))
    return GapReading(kind=GapKind.UNKNOWN)


def collect_session_events(
    session_key: int,
    payloads: Mapping[str, Sequence[Mapping[str, object]]],
) -> tuple[DetectedEvent, ...]:
    """Detect the MVP events of one session from its raw recorded payloads.

    ``payloads`` maps a family name to its recorded records; only the five
    families in :data:`FAMILY_ORDER` are read and a record whose ``session_key``
    is not ``session_key`` is not attributed. Records of the same family that
    share both their source identity and their observation time are one repeated
    update and yield one event, the first occurrence.

    **Total order.** Events with a known timestamp come first, sorted by
    ``(timestamp_value, family_rank, record_index)``; events with no timestamp
    follow, sorted by ``(family_rank, record_index)``. ``family_rank`` is the
    position in :data:`FAMILY_ORDER` and ``record_index`` is the record's index
    in its payload. The key is total because ``(family, record_index)`` is
    unique, so identical payloads always produce an identical sequence.
    """
    events: list[DetectedEvent] = []
    for family in FAMILY_ORDER:
        seen: set[tuple[object, ...]] = set()
        for record_index, record in enumerate(payloads.get(family, ())):
            if _as_int(record.get("session_key")) != session_key:
                continue
            timestamp_field = _TIMESTAMP_FIELD[family]
            timestamp_value = (
                _as_instant(record.get(timestamp_field))
                if timestamp_field is not None
                else None
            )
            identity = tuple(record.get(field) for field in _IDENTITY_FIELDS[family])
            dedup_key = (family, identity, timestamp_field, timestamp_value)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            if timestamp_value is not None:
                reason = None
            elif timestamp_field is None:
                reason = _NO_TIMESTAMP_FIELD
            else:
                reason = _MISSING_TIMESTAMP_VALUE
            events.append(
                DetectedEvent(
                    event_type=_EVENT_TYPE[family],
                    family=family,
                    session_key=session_key,
                    record_index=record_index,
                    driver_number=_as_int(record.get("driver_number")),
                    timestamp_field=timestamp_field,
                    timestamp_value=timestamp_value,
                    timestamp_unknown_reason=reason,
                    evidence={field: record.get(field) for field in _EVIDENCE_FIELDS[family]},
                )
            )
    return _total_order(events)


def _total_order(events: Iterable[DetectedEvent]) -> tuple[DetectedEvent, ...]:
    """Apply the documented total order; unknown instants sort after known ones."""
    known = [event for event in events if event.timestamp_value is not None]
    unknown = [event for event in events if event.timestamp_value is None]
    known.sort(
        key=lambda event: (
            event.timestamp_value, _FAMILY_RANK[event.family], event.record_index,
        )
    )
    unknown.sort(key=lambda event: (_FAMILY_RANK[event.family], event.record_index))
    return tuple(known) + tuple(unknown)
