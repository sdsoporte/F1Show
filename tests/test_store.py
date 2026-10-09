"""Offline acceptance tests for the SQLite store behind the ``Store`` port.

Every test runs against a real temporary database under ``tmp_path``: nothing
here touches the network, DuckDB, the wall clock or a shared fixture. The
substitutability test is the point of the module: one body drives both
``SQLiteStore`` and the shipped in-memory double, and both must agree.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from f1show.fakes import InMemoryStore
from f1show.ports import Store
from f1show.store import SQLiteStore

#: Fixed instants and a fixed local DB path: these tests never read the wall clock.
UTC = dt.timezone.utc
MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=UTC)
LATER = MOMENT + dt.timedelta(seconds=10)


def record(record_id: str, **extra: object) -> dict[str, object]:
    """Build a source record carrying its explicit, caller-supplied identity."""
    return {"record_id": record_id, **extra}


def open_store(tmp_path: pathlib.Path) -> SQLiteStore:
    """Open a store on a fresh path inside the test's temporary directory."""
    return SQLiteStore(tmp_path / "f1show.sqlite3")


def ids(records: Sequence[Mapping[str, object]]) -> list[object]:
    """Return the record identities of a read result, in returned order."""
    return [item["record_id"] for item in records]


async def _observable(store: Store) -> dict[str, Any]:
    """Drive every port method and return only its observable results."""
    await store.write_source_batch(
        "sessions", 9462, [record("9462", year=2024, tags=["race"])], observed_at=MOMENT
    )
    await store.write_source_batch(
        "drivers",
        9462,
        [record("9462-1", driver_number=1, nested={"stint": 2})],
        observed_at=MOMENT,
    )
    result: dict[str, Any] = {
        "sessions": list(await store.read_source_records("sessions", 9462)),
        "isolated": list(await store.read_source_records("drivers", 9463)),
        "window": list(
            await store.read_source_records("drivers", 9462, since=MOMENT, until=MOMENT)
        ),
        "unset_watermark": await store.get_watermark("/v1/laps", 9462),
        "set_result": await store.set_watermark("/v1/laps", 9462, observed_at=MOMENT),
        "watermark": await store.get_watermark("/v1/laps", 9462),
    }
    await store.close()
    return result


EXPECTED_OBSERVABLE: dict[str, Any] = {
    "sessions": [{"record_id": "9462", "year": 2024, "tags": ["race"]}],
    "isolated": [],
    "window": [{"record_id": "9462-1", "driver_number": 1, "nested": {"stint": 2}}],
    "unset_watermark": None,
    "set_result": 1,
    "watermark": MOMENT,
}


@pytest.mark.anyio
async def test_sqlite_store_is_substitutable_for_the_in_memory_double(
    tmp_path: pathlib.Path,
) -> None:
    from_memory = await _observable(InMemoryStore())
    from_sqlite = await _observable(open_store(tmp_path))
    assert from_memory == EXPECTED_OBSERVABLE
    assert from_sqlite == EXPECTED_OBSERVABLE


@pytest.mark.anyio
async def test_sqlite_store_satisfies_the_store_protocol(tmp_path: pathlib.Path) -> None:
    store = open_store(tmp_path)
    assert isinstance(store, Store)
    await store.close()


@pytest.mark.anyio
async def test_schema_is_created_on_first_open_and_reopening_is_harmless(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "f1show.sqlite3"
    first = SQLiteStore(path)
    assert path.is_file()
    await first.write_source_batch(
        "laps", 9462, [record("9462-1", lap_number=1)], observed_at=MOMENT
    )
    await first.close()

    # WAL is a property of the database file, not of one connection.
    with sqlite3.connect(path) as probe:
        assert probe.execute("PRAGMA journal_mode").fetchone() == ("wal",)

    # Re-opening re-runs CREATE TABLE IF NOT EXISTS: it must neither fail nor
    # discard what the first open wrote.
    second = SQLiteStore(path)
    assert list(await second.read_source_records("laps", 9462)) == [
        {"record_id": "9462-1", "lap_number": 1}
    ]
    await second.close()


@pytest.mark.anyio
async def test_repeated_write_updates_the_row_and_returns_what_was_written(
    tmp_path: pathlib.Path,
) -> None:
    store = open_store(tmp_path)
    assert (
        await store.write_source_batch(
            "drivers", 9462, [record("9462-1", driver_number=1)], observed_at=MOMENT
        )
        == 1
    )
    # A two-record batch reports two writes even though one row already exists.
    assert (
        await store.write_source_batch(
            "drivers",
            9462,
            [record("9462-1", driver_number=2), record("9462-2", driver_number=3)],
            observed_at=LATER,
        )
        == 2
    )
    assert list(await store.read_source_records("drivers", 9462)) == [
        {"record_id": "9462-1", "driver_number": 2},
        {"record_id": "9462-2", "driver_number": 3},
    ]
    # The upsert replaced the observation time too, so the earlier window no
    # longer matches the updated row.
    assert list(await store.read_source_records("drivers", 9462, until=MOMENT)) == []
    assert ids(await store.read_source_records("drivers", 9462, since=LATER)) == [
        "9462-1",
        "9462-2",
    ]


@pytest.mark.anyio
async def test_records_isolate_by_family_and_by_session(tmp_path: pathlib.Path) -> None:
    store = open_store(tmp_path)
    await store.write_source_batch(
        "drivers", 9462, [record("9462-1", driver_number=1)], observed_at=MOMENT
    )
    await store.write_source_batch(
        "drivers", 9463, [record("9463-1", driver_number=4)], observed_at=MOMENT
    )
    await store.write_source_batch(
        "laps", 9462, [record("9462-1", lap_number=1)], observed_at=MOMENT
    )
    assert list(await store.read_source_records("drivers", 9462)) == [
        {"record_id": "9462-1", "driver_number": 1}
    ]
    assert list(await store.read_source_records("drivers", 9463)) == [
        {"record_id": "9463-1", "driver_number": 4}
    ]
    # The same identity text in another family is another row.
    assert list(await store.read_source_records("laps", 9462)) == [
        {"record_id": "9462-1", "lap_number": 1}
    ]
    assert await store.read_source_records("laps", 9463) == ()


@pytest.mark.anyio
async def test_since_and_until_are_inclusive_and_filter_by_instant(
    tmp_path: pathlib.Path,
) -> None:
    store = open_store(tmp_path)
    offset = dt.timezone(dt.timedelta(hours=5, minutes=30))
    await store.write_source_batch(
        "laps", 9462, [record("early", lap_number=1)], observed_at=MOMENT
    )
    # The same instant, written with a +05:30 offset. A text comparison of
    # ISO-8601 strings with mixed offsets would compare wall clocks and drop
    # this row from a UTC-bounded window.
    await store.write_source_batch(
        "laps", 9462, [record("middle", lap_number=2)], observed_at=MOMENT.astimezone(offset)
    )
    await store.write_source_batch(
        "laps", 9462, [record("late", lap_number=3)], observed_at=LATER
    )

    assert ids(await store.read_source_records("laps", 9462)) == ["early", "middle", "late"]
    assert ids(
        await store.read_source_records("laps", 9462, since=MOMENT)
    ) == ["early", "middle", "late"]
    assert ids(
        await store.read_source_records("laps", 9462, since=MOMENT, until=MOMENT)
    ) == ["early", "middle"]
    assert ids(await store.read_source_records("laps", 9462, until=MOMENT)) == ["early", "middle"]
    assert ids(await store.read_source_records("laps", 9462, since=LATER)) == ["late"]
    assert ids(await store.read_source_records("laps", 9462, until=LATER)) == [
        "early",
        "middle",
        "late",
    ]


@pytest.mark.anyio
async def test_a_record_without_a_record_id_is_rejected(tmp_path: pathlib.Path) -> None:
    store = open_store(tmp_path)
    good = record("9462-1", driver_number=1)
    for bad in ({}, {"record_id": ""}, {"record_id": "   "}, {"record_id": 1}):
        with pytest.raises(ValueError) as excinfo:
            await store.write_source_batch("drivers", 9462, [good, bad], observed_at=MOMENT)
        message = str(excinfo.value)
        assert "drivers" in message
        assert "record_id" in message
    # The batch is rejected as a whole: the valid record in it was not written.
    assert await store.read_source_records("drivers", 9462) == ()


@pytest.mark.anyio
async def test_round_trip_preserves_identity_and_nested_values(tmp_path: pathlib.Path) -> None:
    payload: dict[str, object] = {
        "record_id": "9462-1",
        "driver_number": 1,
        "name_acronym": "VER",
        "nested": {"stints": [1, 2], "tyre": None},
        "measured": 1.5,
        "final_lap": False,
    }
    store = open_store(tmp_path)
    await store.write_source_batch("drivers", 9462, [payload], observed_at=MOMENT)
    read_back = await store.read_source_records("drivers", 9462)
    assert list(read_back) == [payload]
    assert read_back[0]["record_id"] == "9462-1"


@pytest.mark.anyio
async def test_watermarks_are_per_endpoint_and_session(tmp_path: pathlib.Path) -> None:
    store = open_store(tmp_path)
    assert await store.get_watermark("/v1/laps", 9462) is None
    assert await store.set_watermark("/v1/laps", 9462, observed_at=MOMENT) == 1
    stored = await store.get_watermark("/v1/laps", 9462)
    assert stored is not None
    assert stored == MOMENT
    assert stored.utcoffset() is not None
    assert await store.get_watermark("/v1/position", 9462) is None
    assert await store.get_watermark("/v1/laps", 9463) is None
    await store.set_watermark("/v1/laps", 9462, observed_at=LATER)
    assert await store.get_watermark("/v1/laps", 9462) == LATER


@pytest.mark.anyio
async def test_naive_observation_times_are_rejected(tmp_path: pathlib.Path) -> None:
    store = open_store(tmp_path)
    naive = dt.datetime(2024, 3, 2, 15, 0, 0)
    with pytest.raises(ValueError) as excinfo:
        await store.write_source_batch("laps", 9462, [record("9462-1")], observed_at=naive)
    assert "timezone-aware" in str(excinfo.value)
    with pytest.raises(ValueError) as watermark:
        await store.set_watermark("/v1/laps", 9462, observed_at=naive)
    assert "timezone-aware" in str(watermark.value)
    with pytest.raises(ValueError):
        await store.read_source_records("laps", 9462, since=naive)


@pytest.mark.anyio
async def test_every_method_refuses_after_close(tmp_path: pathlib.Path) -> None:
    store = open_store(tmp_path)
    await store.close()
    await store.close()  # close is idempotent
    with pytest.raises(RuntimeError):
        await store.write_source_batch("laps", 9462, [record("9462-1")], observed_at=MOMENT)
    with pytest.raises(RuntimeError):
        await store.read_source_records("laps", 9462)
    with pytest.raises(RuntimeError):
        await store.set_watermark("/v1/laps", 9462, observed_at=MOMENT)
    with pytest.raises(RuntimeError):
        await store.get_watermark("/v1/laps", 9462)
