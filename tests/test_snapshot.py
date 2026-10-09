"""Offline acceptance tests for immutable per-session Parquet snapshots.

Every test runs under ``tmp_path`` against a real temporary SQLite database or
the shipped in-memory double, with a fresh DuckDB connection: no network, no
wall clock, no shared fixture. The digest-identity test is the acceptance
criterion, so it is asserted directly and first among the determinism checks.
The parametrized test runs one body against **both** store implementations, so
a divergence between them cannot hide (the F03a parity rule).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import pathlib
from collections.abc import Callable

import duckdb
import pytest

from f1show.fakes import InMemoryStore
from f1show.ports import Store
from f1show.replay import SnapshotReplaySource
from f1show.snapshot import SNAPSHOT_COLUMNS, write_session_snapshot
from f1show.store import SQLiteStore

UTC = dt.timezone.utc
MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=UTC)
MID = MOMENT + dt.timedelta(seconds=10)
LATER = MOMENT + dt.timedelta(seconds=20)
SESSION = 9462
FAMILIES = ("sessions", "drivers")

#: One factory per store implementation, mirroring ``tests/test_store.py``.
STORE_FACTORIES = [
    pytest.param(lambda path: SQLiteStore(path / "snapshot.sqlite3"), id="sqlite"),
    pytest.param(lambda path: InMemoryStore(), id="in-memory"),
]


def record(record_id: str, **extra: object) -> dict[str, object]:
    """Build a source record carrying its explicit, caller-supplied identity."""
    return {"record_id": record_id, **extra}


async def seeded(store: Store) -> Store:
    """Fill both declared families with several distinct instants in one session."""
    await store.write_source_batch(
        "sessions",
        SESSION,
        [record(str(SESSION), year=2024, gmt_offset="01:00:00")],
        observed_at=MOMENT,
    )
    await store.write_source_batch(
        "drivers", SESSION, [record("9462-2", driver_number=2)], observed_at=MOMENT
    )
    # MID is strictly inside the session. A correct writer keeps this row after a
    # seed at MOMENT, which is what makes the mid-session split observable.
    await store.write_source_batch(
        "drivers",
        SESSION,
        [record("9462-1", driver_number=1, nested={"stint": 2, "tyre": None})],
        observed_at=MID,
    )
    await store.write_source_batch(
        "drivers", 9463, [record("9463-1", driver_number=4)], observed_at=LATER
    )
    return store


async def stored_rows(store: Store) -> dict[str, dict[str, object]]:
    """Every record the store holds for the session, keyed by identity."""
    rows: dict[str, dict[str, object]] = {}
    for family in FAMILIES:
        for _, item in await store.read_source_records(family, SESSION):
            rows[str(item["record_id"])] = dict(item)
    return rows


def read_file(path: pathlib.Path) -> tuple[tuple[str, ...], list[tuple[object, ...]]]:
    """Read a snapshot with a fresh DuckDB connection, in the file's own row order."""
    connection = duckdb.connect()
    try:
        layout = connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]
        ).fetchall()
        rows = connection.execute(
            "SELECT family, observed_at, record_id FROM read_parquet(?)", [str(path)]
        ).fetchall()
    finally:
        connection.close()
    return tuple(str(row[0]) for row in layout), list(rows)


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_a_snapshot_round_trips_every_row_the_store_held(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    """One body, both stores: the port parity rule applied to the snapshot writer."""
    store = await seeded(build_store(tmp_path))
    result = await write_session_snapshot(store, SESSION, FAMILIES, tmp_path / "snap.parquet")
    stored = await stored_rows(store)
    source = SnapshotReplaySource(result.path, session_key=SESSION)
    assert result.row_count == len(stored)
    assert result.families == FAMILIES
    # Equal mappings, ``record_id`` included, and nothing from the other session.
    assert {str(item["record_id"]): dict(item) for item in source.records()} == stored
    await store.close()


@pytest.mark.anyio
@pytest.mark.parametrize("build_store", STORE_FACTORIES)
async def test_a_real_exported_session_seeds_exactly_at_an_interior_instant(
    build_store: Callable[[pathlib.Path], Store], tmp_path: pathlib.Path
) -> None:
    """The point of carrying per-row times: a mid-session seed splits a session.

    Before the port reported observation time, every row in a snapshot carried the
    one instant its caller declared, so seeding at an instant inside the session
    took the whole session or none of it. The split below was impossible to assert,
    and it is asserted against both store implementations through the real writer.
    """
    store = await seeded(build_store(tmp_path))
    result = await write_session_snapshot(store, SESSION, FAMILIES, tmp_path / "snap.parquet")
    source = SnapshotReplaySource(result.path, session_key=SESSION)

    seeded_ids = [str(item["record_id"]) for item in source.seed(MOMENT)]
    later_ids = [str(item["record_id"]) for item in source.replay(after=MOMENT)]
    every = [str(item["record_id"]) for item in source.records()]
    assert seeded_ids == ["9462-2", str(SESSION)]
    assert later_ids == ["9462-1"]
    assert seeded_ids + later_ids == every
    await store.close()


@pytest.mark.anyio
async def test_the_same_store_content_exported_twice_has_the_same_sha256(
    tmp_path: pathlib.Path,
) -> None:
    """The acceptance criterion: identical content must export byte-identically."""
    store = await seeded(SQLiteStore(tmp_path / "f1show.sqlite3"))
    first = await write_session_snapshot(store, SESSION, FAMILIES, tmp_path / "first.parquet")
    second = await write_session_snapshot(store, SESSION, FAMILIES, tmp_path / "second.parquet")
    assert first.sha256 == second.sha256
    assert first.sha256 == hashlib.sha256((tmp_path / "first.parquet").read_bytes()).hexdigest()
    assert len(first.sha256) == 64


@pytest.mark.anyio
async def test_both_store_implementations_export_the_same_bytes_and_records(
    tmp_path: pathlib.Path,
) -> None:
    """A snapshot from the double must be indistinguishable from the SQLite one."""
    from_sqlite = await write_session_snapshot(
        await seeded(SQLiteStore(tmp_path / "sqlite.sqlite3")),
        SESSION,
        FAMILIES,
        tmp_path / "sqlite.parquet",
    )
    from_memory = await write_session_snapshot(
        await seeded(InMemoryStore()),
        SESSION,
        FAMILIES,
        tmp_path / "memory.parquet",
    )
    assert from_sqlite.sha256 == from_memory.sha256
    assert SnapshotReplaySource(
        from_sqlite.path, session_key=SESSION
    ).records() == SnapshotReplaySource(from_memory.path, session_key=SESSION).records()


@pytest.mark.anyio
async def test_the_file_row_order_is_family_observed_at_record_id(
    tmp_path: pathlib.Path,
) -> None:
    store = await seeded(SQLiteStore(tmp_path / "f1show.sqlite3"))
    result = await write_session_snapshot(store, SESSION, FAMILIES, tmp_path / "snap.parquet")
    layout, rows = read_file(result.path)
    assert layout == SNAPSHOT_COLUMNS
    # Each row keeps its own instant, so the declared (family, observed_at,
    # record_id) order is observable rather than degenerate: within "drivers",
    # identity 9462-1 sorts after 9462-2 only because its instant is later.
    assert rows == sorted(rows, key=lambda row: (row[0], row[1], row[2]))
    assert rows == [
        ("drivers", MOMENT.replace(tzinfo=None), "9462-2"),
        ("drivers", MID.replace(tzinfo=None), "9462-1"),
        ("sessions", MOMENT.replace(tzinfo=None), str(SESSION)),
    ]
    assert {row[1] for row in rows} == {
        MOMENT.replace(tzinfo=None),
        MID.replace(tzinfo=None),
    }


@pytest.mark.anyio
async def test_an_existing_snapshot_is_refused_unless_overwrite_is_passed(
    tmp_path: pathlib.Path,
) -> None:
    target = tmp_path / "snap.parquet"
    store = await seeded(SQLiteStore(tmp_path / "f1show.sqlite3"))
    first = await write_session_snapshot(store, SESSION, FAMILIES, target)
    with pytest.raises(FileExistsError) as excinfo:
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert str(target) in str(excinfo.value)
    assert "overwrite" in str(excinfo.value)
    # The override succeeds and produces exactly the same immutable artifact.
    again = await write_session_snapshot(store, SESSION, FAMILIES, target, overwrite=True)
    assert again.sha256 == first.sha256


@pytest.mark.anyio
async def test_the_snapshot_is_readable_with_duckdb_alone(tmp_path: pathlib.Path) -> None:
    store = await seeded(SQLiteStore(tmp_path / "f1show.sqlite3"))
    result = await write_session_snapshot(store, SESSION, FAMILIES, tmp_path / "snap.parquet")
    await store.close()
    connection = duckdb.connect()  # the store is closed; nothing here consults it
    try:
        rows = connection.execute(
            "SELECT family, session_key, record_id FROM read_parquet(?)", [str(result.path)]
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == result.row_count
    assert {row[0] for row in rows} == set(FAMILIES)
    assert {row[1] for row in rows} == {SESSION}
