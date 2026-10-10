"""Offline acceptance tests for F04 deterministic event collection.

Every payload is the verbatim recorded fixture under ``fixtures/openf1``; no
network is touched and no assertion depends on the developer's shell. The
contract under test: one public entry point turns the raw recorded payloads of
one session into a deterministic, total-ordered tuple of evidence-carrying
events, and it makes no claim the fixtures cannot support.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

from f1show import (
    DetectedEvent,
    EventType,
    GapKind,
    classify_gap,
    collect_session_events,
)

UTC = dt.timezone.utc
SESSION_KEY = 9617
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "openf1"
EVENT_FAMILIES = ("position", "laps", "pit", "stints", "race_control")
SEGMENT_FIELDS = ("segments_sector_1", "segments_sector_2", "segments_sector_3")
#: Family counts measured on the recorded session: every in-scope record is one
#: event, because the fixture holds no repeated update to deduplicate.
RECORDED_FAMILY_COUNTS = {"position": 403, "laps": 1059, "pit": 23, "stints": 43, "race_control": 120}


def load(name: str) -> list[dict[str, Any]]:
    """Read one recorded payload verbatim."""
    text = (FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")
    return json.loads(text)


def payloads() -> dict[str, list[dict[str, Any]]]:
    """The raw recorded payloads for the five event-bearing families."""
    return {name: load(name) for name in EVENT_FAMILIES}


def events() -> tuple[DetectedEvent, ...]:
    """Collect the recorded session once, for the assertions that read it."""
    return collect_session_events(SESSION_KEY, payloads())


def as_json(stream: tuple[DetectedEvent, ...]) -> str:
    """A stable text form, for the byte-for-byte determinism check."""
    return json.dumps([event.model_dump(mode="json") for event in stream])


def segment_arrays(event: DetectedEvent) -> list[list[Any]]:
    """The lap's segment arrays that the record actually carries."""
    arrays: list[list[Any]] = []
    for field in SEGMENT_FIELDS:
        value = event.evidence[field]
        if isinstance(value, list):
            arrays.append(value)
    return arrays


def test_recorded_session_yields_a_stable_expected_sequence() -> None:
    collected = events()
    assert len(collected) == 1648
    assert Counter(event.family for event in collected) == RECORDED_FAMILY_COUNTS
    assert Counter(event.event_type for event in collected) == {
        EventType.POSITION_CHANGE: 403,
        EventType.LAP_COMPLETED: 1059,
        EventType.PIT_STOP: 23,
        EventType.STINT_START: 43,
        EventType.RACE_CONTROL: 120,
    }
    first = collected[0]
    assert (first.family, first.record_index, first.driver_number) == ("position", 0, 4)
    assert first.timestamp_field == "date"
    assert first.timestamp_value == dt.datetime(2024, 10, 20, 18, 6, 48, 657000, tzinfo=UTC)
    # The opening classification rows share one instant; record order breaks the tie.
    assert [event.record_index for event in collected[:6]] == [0, 1, 2, 3, 4, 5]
    assert {event.family for event in collected[:6]} == {"position"}
    last = collected[-1]
    assert (last.family, last.record_index, last.driver_number) == ("stints", 42, 31)
    assert last.timestamp_field is None
    assert last.timestamp_value is None


def test_known_timestamps_sort_first_and_unknowns_last() -> None:
    collected = events()
    known = [event for event in collected if event.timestamp_value is not None]
    unknown = [event for event in collected if event.timestamp_value is None]
    assert len(known) + len(unknown) == len(collected)
    assert unknown, "stints carry no timestamp; the recorded fixture exercises the tail"
    assert collected[len(known):] == tuple(unknown)
    instants = [event.timestamp_value for event in known if event.timestamp_value is not None]
    assert instants == sorted(instants)


def test_two_runs_over_the_same_bytes_are_byte_identical() -> None:
    first = collect_session_events(SESSION_KEY, payloads())
    second = collect_session_events(SESSION_KEY, payloads())
    assert first == second
    assert as_json(first) == as_json(second)


def test_every_event_traces_back_to_its_exact_source_record() -> None:
    raw = payloads()
    for event in collect_session_events(SESSION_KEY, raw):
        record = raw[event.family][event.record_index]
        assert record["session_key"] == event.session_key
        assert record.get("driver_number") == event.driver_number
        if event.timestamp_field is None:
            assert event.timestamp_value is None
            continue
        source = record.get(event.timestamp_field)
        expected = dt.datetime.fromisoformat(source) if source else None
        assert event.timestamp_value == expected


def test_plus_one_lap_gap_is_classified_without_a_numeric_cast() -> None:
    reading = classify_gap("+1 LAP")
    assert reading.kind == GapKind.LAPS
    assert reading.laps == 1
    assert reading.seconds is None
    assert classify_gap("+2 LAP").laps == 2
    seconds = classify_gap(1.234)
    assert (seconds.kind, seconds.seconds) == (GapKind.SECONDS, 1.234)
    assert classify_gap(None).kind == GapKind.ABSENT
    assert classify_gap("nonsense").kind == GapKind.UNKNOWN


def test_recorded_intervals_are_classified_without_coercion() -> None:
    kinds = Counter(classify_gap(record["gap_to_leader"]).kind for record in load("intervals"))
    assert kinds == {
        GapKind.SECONDS: 19604,
        GapKind.LAPS: 1331,
        GapKind.ABSENT: 106,
    }
    lap_strings = [
        record["gap_to_leader"] for record in load("intervals")
        if isinstance(record["gap_to_leader"], str)
    ]
    assert all(classify_gap(raw).laps == 1 for raw in lap_strings)


def test_null_lap_durations_survive_as_explicit_unknowns() -> None:
    unknown = [
        event for event in events()
        if event.family == "laps" and event.evidence["lap_duration"] is None
    ]
    assert len(unknown) == 2
    assert {event.driver_number for event in unknown} == {44, 63}
    assert all(event.event_type is EventType.LAP_COMPLETED for event in unknown)
    durations = [event.evidence["lap_duration"] for event in events() if event.family == "laps"]
    assert None in durations
    assert 0 not in durations


def test_null_date_start_survives_as_an_explicit_unknown() -> None:
    orphan = [
        event for event in events()
        if event.family == "laps"
        and event.timestamp_field == "date_start"
        and event.timestamp_value is None
    ]
    assert len(orphan) == 1
    assert (orphan[0].driver_number, orphan[0].evidence["lap_number"]) == (63, 1)
    assert orphan[0].timestamp_unknown_reason is not None


def test_stints_say_their_family_carries_no_timestamp() -> None:
    stints = [event for event in events() if event.family == "stints"]
    assert len(stints) == 43
    assert all(event.timestamp_field is None and event.timestamp_value is None for event in stints)
    assert all(event.timestamp_unknown_reason is not None for event in stints)
    assert {event.evidence["compound"] for event in stints} <= {"MEDIUM", "HARD", "SOFT"}


def test_partial_segment_arrays_survive_unchanged() -> None:
    collected = events()
    opening_lap = next(
        event for event in collected if event.family == "laps" and event.record_index == 0
    )
    assert opening_lap.evidence["segments_sector_1"] == [None, 2064, 2049, 2049, 2049, 2049]
    partial = sum(
        1
        for event in collected
        if event.family == "laps"
        for array in segment_arrays(event)
        if None in array
    )
    assert partial == 846


def test_three_pit_durations_stay_distinct() -> None:
    sample = next(event for event in events() if event.family == "pit" and event.record_index == 0)
    assert set(sample.evidence) == {"lap_number", "lane_duration", "pit_duration", "stop_duration"}
    assert sample.evidence["lane_duration"] == 34.983
    assert sample.evidence["pit_duration"] == 34.983
    assert sample.evidence["stop_duration"] == 12.5
    record = {
        "session_key": SESSION_KEY, "driver_number": 23, "lap_number": 3,
        "date": "2024-10-20T19:10:15.705000+00:00",
        "lane_duration": 34.983, "pit_duration": 40.5, "stop_duration": 12.5,
    }
    collected = collect_session_events(SESSION_KEY, {"pit": [record]})
    assert len(collected) == 1
    evidence = collected[0].evidence
    assert (evidence["lane_duration"], evidence["pit_duration"], evidence["stop_duration"]) == (
        34.983, 40.5, 12.5,
    )


def test_race_control_preserves_provider_fields_as_evidence() -> None:
    entries = [event for event in events() if event.family == "race_control"]
    assert len(entries) == 120
    first = next(event for event in entries if event.record_index == 0)
    assert first.evidence["category"] == "Other"
    assert first.evidence["message"] == "PINK HEAD PADDING MATERIAL MUST BE USED"
    assert first.evidence["lap_number"] == 1
    assert set(first.evidence) == {
        "category", "flag", "scope", "sector", "lap_number", "qualifying_phase", "message",
    }
    assert Counter(event.evidence["category"] for event in entries) == {
        "Other": 71, "Flag": 42, "Drs": 3, "SessionStatus": 2, "SafetyCar": 2,
    }
    assert Counter(event.evidence["flag"] for event in entries)["BLUE"] == 20


def test_no_overtake_event_exists_anywhere() -> None:
    types = {event.event_type for event in events()}
    assert EventType.OVERTAKE not in types
    assert types == {
        EventType.POSITION_CHANGE, EventType.LAP_COMPLETED, EventType.PIT_STOP,
        EventType.STINT_START, EventType.RACE_CONTROL,
    }


def test_position_change_claims_no_overtake() -> None:
    positions = [event for event in events() if event.family == "position"]
    assert len(positions) == 403
    assert all(event.event_type is EventType.POSITION_CHANGE for event in positions)
    assert all(set(event.evidence) == {"position"} for event in positions)
    assert not any("overtake" in json.dumps(event.evidence).lower() for event in positions)


def test_lap_one_completes_but_never_becomes_a_lap_time_record() -> None:
    collected = events()
    opening = [event for event in collected if event.family == "laps" and event.evidence["lap_number"] == 1]
    assert len(opening) == 20
    assert all(event.event_type is EventType.LAP_COMPLETED for event in opening)
    assert not {EventType.FASTEST_LAP, EventType.PERSONAL_BEST_LAP, EventType.SECTOR_BEST} & {
        event.event_type for event in collected
    }
    # A faster lap 1 than lap 2 still yields two completions and no record claim.
    synthetic = {"laps": [
        {"session_key": SESSION_KEY, "driver_number": 1, "lap_number": 1,
         "date_start": "2024-10-20T19:03:48.550000+00:00", "lap_duration": 10.0},
        {"session_key": SESSION_KEY, "driver_number": 1, "lap_number": 2,
         "date_start": "2024-10-20T19:05:48.550000+00:00", "lap_duration": 100.0},
    ]}
    compared = collect_session_events(SESSION_KEY, synthetic)
    assert [event.event_type for event in compared] == [EventType.LAP_COMPLETED] * 2
    assert EventType.FASTEST_LAP not in {event.event_type for event in compared}


def test_intervals_derive_no_events() -> None:
    without = collect_session_events(SESSION_KEY, payloads())
    with_intervals = collect_session_events(
        SESSION_KEY, {**payloads(), "intervals": load("intervals")}
    )
    assert with_intervals == without


def test_repeated_updates_deduplicate_by_identity_and_observation_time() -> None:
    record = {
        "session_key": SESSION_KEY, "driver_number": 1,
        "date": "2024-10-20T19:00:00+00:00", "position": 3,
    }
    repeated = collect_session_events(SESSION_KEY, {"position": [record, dict(record)]})
    assert len(repeated) == 1
    assert repeated[0].record_index == 0
    later = {**record, "date": "2024-10-20T19:00:01+00:00", "position": 4}
    both = collect_session_events(SESSION_KEY, {"position": [record, later]})
    assert [event.record_index for event in both] == [0, 1]
    assert [event.evidence["position"] for event in both] == [3, 4]


def test_records_of_another_session_are_not_attributed() -> None:
    other = {"session_key": 9625, "driver_number": 1, "date": "2024-10-27T19:00:00+00:00", "position": 1}
    assert collect_session_events(SESSION_KEY, {"position": [other]}) == ()


#: A numeric gap far beyond the range a float can represent. JSON parses such a
#: literal into a Python ``int`` of arbitrary width, so a corrupt payload really
#: reaches ``classify_gap`` with a value ``float()`` cannot convert.
OVERSIZED_DIGITS = 400
OVERSIZED_VALUE = 10**OVERSIZED_DIGITS
OVERSIZED_LITERAL = "9" * OVERSIZED_DIGITS

#: Hostile gap spellings the verifier already exercised, each with the outcome
#: the fixed classifier must keep: no input may raise, and none of these
#: spellings is a duration, so each stays unknown except the real `+N LAP` form
#: and the finite `-0.0`, whose existing readings must not change.
HOSTILE_GAP_INPUTS: tuple[tuple[object, GapKind], ...] = (
    ("+1 LAP", GapKind.LAPS),
    ("  +1 LAP", GapKind.UNKNOWN),
    ("+2 LAPS", GapKind.UNKNOWN),
    ("1:23.456", GapKind.UNKNOWN),
    ("abc", GapKind.UNKNOWN),
    ("", GapKind.UNKNOWN),
    (True, GapKind.UNKNOWN),
    (False, GapKind.UNKNOWN),
    ([], GapKind.UNKNOWN),
    ({}, GapKind.UNKNOWN),
    (-0.0, GapKind.SECONDS),
    (OVERSIZED_LITERAL, GapKind.UNKNOWN),
)


def test_oversized_integer_gap_is_unknown_and_does_not_raise() -> None:
    reading = classify_gap(OVERSIZED_VALUE)
    assert reading.kind == GapKind.UNKNOWN
    assert reading.seconds is None
    assert reading.laps is None


def test_oversized_integer_parsed_from_json_text_is_unknown_and_does_not_raise() -> None:
    record = json.loads('{"gap_to_leader": ' + OVERSIZED_LITERAL + "}")
    assert isinstance(record["gap_to_leader"], int)
    assert classify_gap(record["gap_to_leader"]).kind == GapKind.UNKNOWN


def test_normal_numeric_gap_still_reads_as_seconds() -> None:
    assert (classify_gap(3).kind, classify_gap(3).seconds) == (GapKind.SECONDS, 3.0)
    assert (classify_gap(1.234).kind, classify_gap(1.234).seconds) == (GapKind.SECONDS, 1.234)
    assert classify_gap(0).seconds == 0.0


def test_non_finite_numeric_gap_is_unknown() -> None:
    # Parent decision, not the verifier's finding: a non-finite number is not a
    # duration, and passing ``inf`` downstream as "seconds" would be a value
    # that means nothing and a later unit could misread.
    for raw in (float("inf"), float("-inf"), float("nan")):
        reading = classify_gap(raw)
        assert reading.kind == GapKind.UNKNOWN
        assert reading.seconds is None
        assert reading.laps is None


def test_hostile_gap_inputs_keep_their_classification_and_never_raise() -> None:
    for raw, expected_kind in HOSTILE_GAP_INPUTS:
        reading = classify_gap(raw)
        assert reading.kind is expected_kind, raw
        if reading.kind is GapKind.UNKNOWN:
            assert (reading.seconds, reading.laps) == (None, None), raw
        if reading.kind is GapKind.LAPS:
            assert reading.laps == 1, raw
