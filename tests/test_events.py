"""Offline acceptance tests for the internal event contracts.

Only OpenF1's ``sessions`` and ``drivers`` shapes were observed at F01; the rest
of this module asserts F1Show's own taxonomy. No network is touched.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from f1show.events import (
    DriverRecord,
    EventEnvelope,
    EventType,
    Provenance,
    SessionRecord,
)

UTC = dt.timezone.utc
NOW = dt.datetime(2024, 3, 2, 15, 0, 1, tzinfo=UTC)

#: Field names are the F01 observation verbatim and ``session_key`` 9462 is the
#: session actually queried; the other identifiers are stand-ins with the
#: observed types, not a second observation.
SESSION: dict[str, Any] = {
    "session_key": 9462, "session_name": "Race", "session_type": "Race",
    "date_start": "2024-03-02T15:00:00+00:00", "date_end": "2024-03-02T17:00:00+00:00",
    "meeting_key": 1236, "circuit_key": 63, "circuit_short_name": "Sakhir",
    "country_key": 7, "country_code": "BHR", "country_name": "Bahrain",
    "location": "Sakhir", "gmt_offset": "03:00:00", "year": 2024, "is_cancelled": False,
}
DRIVER: dict[str, Any] = {
    "driver_number": 1, "broadcast_name": "M VERSTAPPEN", "first_name": "Max",
    "last_name": "VERSTAPPEN", "full_name": "Max VERSTAPPEN", "name_acronym": "VER",
    "country_code": "NED", "headshot_url": "https://example.invalid/1.png",
    "meeting_key": 1236, "session_key": 9462, "team_colour": "3671C6",
    "team_name": "Red Bull Racing",
}


def without(mapping: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Return a copy of ``mapping`` without ``keys``, for required-field tests."""
    return {key: value for key, value in mapping.items() if key not in keys}


def envelope(**overrides: Any) -> EventEnvelope:
    """Build a valid envelope, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "schema_version": 1, "event_id": "evt-0001",
        "event_type": EventType.POSITION_CHANGE, "session_key": 9462,
        "event_time": NOW, "payload": {"driver_number": 1},
        "provenance": {"endpoint": "/v1/position", "observed_at": NOW},
    }
    fields.update(overrides)
    return EventEnvelope(**fields)


def test_event_type_is_this_projects_taxonomy() -> None:
    assert [member.value for member in EventType] == [
        "session_start", "session_end", "position_change", "lap_completed",
        "personal_best_lap", "fastest_lap", "sector_best", "flag",
        "safety_car", "virtual_safety_car", "pit_stop", "stint_start",
        "interval_update", "overtake", "race_control",
    ]


def test_observed_records_parse_and_tolerate_provider_fields() -> None:
    session = SessionRecord(**{**SESSION, "some_field_added_by_the_provider": True})
    assert (session.session_key, session.session_name) == (9462, "Race")
    assert session.date_end == dt.datetime(2024, 3, 2, 17, 0, tzinfo=UTC)
    driver = DriverRecord(**{**DRIVER, "some_field_added_by_the_provider": True})
    assert (driver.driver_number, driver.name_acronym) == (1, "VER")
    assert driver.full_name == "Max VERSTAPPEN"


@pytest.mark.parametrize(
    ("model", "source", "missing"),
    [
        (SessionRecord, SESSION, "session_key"),
        (SessionRecord, SESSION, "circuit_key"),
        (DriverRecord, DRIVER, "name_acronym"),
    ],
)
def test_a_missing_required_record_field_is_rejected(
    model: Any, source: dict[str, Any], missing: str
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        model(**without(source, missing))
    assert missing in str(excinfo.value)


def test_event_envelope_rejects_an_unknown_field() -> None:
    with pytest.raises(ValidationError) as excinfo:
        envelope(not_a_field_of_ours=True)
    assert "not_a_field_of_ours" in str(excinfo.value)


@pytest.mark.parametrize("name", ["session_key", "driver_number", "meeting_key"])
@pytest.mark.parametrize("bad", [0, -9462])
def test_identifiers_must_be_positive(name: str, bad: int) -> None:
    with pytest.raises(ValidationError) as excinfo:
        envelope(**{name: bad})
    assert name in str(excinfo.value)


@pytest.mark.parametrize("bad", [0, -1])
def test_schema_version_below_one_is_rejected(bad: int) -> None:
    with pytest.raises(ValidationError) as excinfo:
        envelope(schema_version=bad)
    assert "schema_version" in str(excinfo.value)


@pytest.mark.parametrize("field", ["observed_at", "event_time"])
def test_naive_datetimes_are_rejected_and_aware_is_accepted(field: str) -> None:
    naive = dt.datetime(2024, 3, 2, 15, 0, 1)
    bad: dict[str, Any] = (
        {"provenance": {"endpoint": "/v1/position", "observed_at": naive}}
        if field == "observed_at"
        else {field: naive}
    )
    with pytest.raises(ValidationError) as excinfo:
        envelope(**bad)
    assert "timezone" in str(excinfo.value)
    assert Provenance(endpoint="/v1/position", observed_at=NOW).observed_at == NOW
    assert envelope().event_time == NOW


def test_provenance_is_mandatory_and_endpoint_is_not_empty() -> None:
    with pytest.raises(ValidationError) as excinfo:
        envelope(provenance=None)
    assert "provenance" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        envelope(provenance={"endpoint": "", "observed_at": NOW})
    assert "endpoint" in str(excinfo.value)


def test_provenance_source_url_is_absent_or_non_empty() -> None:
    # ``None`` is the one way to say "absent"; an empty string must not be a
    # second, silent spelling of the same thing.
    assert Provenance(endpoint="/v1/position", observed_at=NOW).source_url is None
    present = Provenance(
        endpoint="/v1/position", source_url="https://example.invalid/v1", observed_at=NOW
    )
    assert present.source_url == "https://example.invalid/v1"
    with pytest.raises(ValidationError) as excinfo:
        envelope(provenance={"endpoint": "/v1/position", "source_url": "", "observed_at": NOW})
    assert "source_url" in str(excinfo.value)


@pytest.mark.parametrize("field", ["date_start", "date_end"])
def test_session_record_timestamps_must_be_timezone_aware(field: str) -> None:
    # The observation carries UTC offsets and the rest of the package rejects
    # naive instants; an ingested session record must do the same.
    with pytest.raises(ValidationError) as excinfo:
        SessionRecord(**{**SESSION, field: "2024-03-02T15:00:00"})
    assert field in str(excinfo.value)
    assert "timezone" in str(excinfo.value)
