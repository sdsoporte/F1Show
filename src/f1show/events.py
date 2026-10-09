"""Internal event contracts shared by every F1Show role.

``EventType`` and ``EventEnvelope`` are **this project's** vocabulary, not the
provider's: OpenF1 serves endpoint records and the collector (F04) maps them.
Only ``SessionRecord`` and ``DriverRecord`` mirror an OpenF1 response, and only
because both shapes were observed at F01. Internal contracts forbid unknown
fields, because an unexpected field there is a bug in our own pipeline; ingested
source records tolerate them, because a provider may add a field at any time and
refusing it would break on a change we do not control.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """F1Show's internal event taxonomy, deliberately not OpenF1's vocabulary.

    The set is **extensible**: F04 adds members as it detects more families, and
    a consumer must tolerate a member it does not recognise. ``OVERTAKE``
    corresponds to OpenF1's documented ``overtakes`` endpoint and must never be
    inferred from a position change alone: pit cycles, penalties, retirements
    and lapped traffic all move positions without an overtake.
    """

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    POSITION_CHANGE = "position_change"
    LAP_COMPLETED = "lap_completed"
    PERSONAL_BEST_LAP = "personal_best_lap"
    FASTEST_LAP = "fastest_lap"
    SECTOR_BEST = "sector_best"
    FLAG = "flag"
    SAFETY_CAR = "safety_car"
    VIRTUAL_SAFETY_CAR = "virtual_safety_car"
    PIT_STOP = "pit_stop"
    STINT_START = "stint_start"
    INTERVAL_UPDATE = "interval_update"
    OVERTAKE = "overtake"
    RACE_CONTROL = "race_control"


class _Strict(BaseModel):
    """Internal contract: an unexpected field is a bug in our own pipeline."""

    model_config = ConfigDict(extra="forbid")


class Provenance(_Strict):
    """Where one observation came from, and when it was observed.

    Observation time is distinct from the event's own timestamp, so a record can
    be re-derived and audited without trusting the event time.
    """

    endpoint: Annotated[str, Field(min_length=1)]
    source_url: str | None = None
    observed_at: AwareDatetime


class EventEnvelope(_Strict):
    """One normalized event.

    ``payload`` is **explicitly provisional**: F01 observed only OpenF1's
    ``sessions`` and ``drivers`` shapes, so those are the only record models
    written today. The normalized per-family payloads are produced by the
    collector at F04; the extension point is a new ``EventType`` member plus its
    payload model, never a guessed shape for an endpoint nobody has seen.
    """

    schema_version: Annotated[int, Field(ge=1)]
    event_id: Annotated[str, Field(min_length=1)]
    event_type: EventType
    session_key: Annotated[int, Field(gt=0)]
    meeting_key: Annotated[int | None, Field(gt=0)] = None
    driver_number: Annotated[int | None, Field(gt=0)] = None
    event_time: AwareDatetime
    provenance: Provenance
    payload: dict[str, object]


class SessionRecord(BaseModel):
    """OpenF1's ``sessions`` shape, as observed at F01; unknown fields tolerated."""

    model_config = ConfigDict(extra="ignore")

    session_key: int
    session_name: str
    session_type: str
    date_start: datetime
    date_end: datetime
    meeting_key: int
    circuit_key: int
    circuit_short_name: str
    country_key: int
    country_code: str
    country_name: str
    location: str
    gmt_offset: str
    year: int
    is_cancelled: bool


class DriverRecord(BaseModel):
    """OpenF1's ``drivers`` shape, as observed at F01; unknown fields tolerated.

    There is deliberately **no** ``driverId`` field: OpenF1 exposes no driver
    identifier beyond the per-session ``driver_number`` and ``name_acronym``, so
    the stable identity mapping is this project's to own.
    """

    model_config = ConfigDict(extra="ignore")

    driver_number: int
    broadcast_name: str
    first_name: str
    last_name: str
    full_name: str
    name_acronym: str
    country_code: str
    headshot_url: str
    meeting_key: int
    session_key: int
    team_colour: str
    team_name: str
