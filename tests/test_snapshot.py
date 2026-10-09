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
import errno
import hashlib
import os
import pathlib
import types
from collections.abc import Callable, Mapping, Sequence

import anyio
import duckdb
import pytest

import f1show.snapshot as snapshot_module
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


def staging_leftovers(directory: pathlib.Path) -> list[pathlib.Path]:
    """Every staging file a failed publication left behind, if any.

    Staging names are same-directory and end in the declared suffix, so a leftover
    is observable from the target's own directory rather than inferred.
    """
    return sorted(entry for entry in directory.iterdir() if entry.suffix == ".staging")


def deny_staging_unlink(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make removing a staging file fail, as a filesystem denying unlink would.

    Only ``.staging`` names are affected, so pytest's own temporary-directory
    teardown and every other unlink in the test keep working normally.
    """
    real_unlink = pathlib.Path.unlink

    def failing_unlink(self: pathlib.Path, missing_ok: bool = False) -> None:
        if self.suffix == ".staging":
            raise OSError(errno.EACCES, "simulated unlink denial")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(pathlib.Path, "unlink", failing_unlink)


class _FailingCopyConnection:
    """A DuckDB connection proxy whose COPY writes real partial bytes and fails.

    The bytes are written on purpose: a failure injected before anything reached
    disk could not tell cleanup apart from a no-op. ``error`` lets a test raise one
    specific exception object, so primary-preservation can be asserted by identity.
    """

    def __init__(self, real: duckdb.DuckDBPyConnection, error: duckdb.Error | None = None) -> None:
        self._real = real
        self._error = error if error is not None else duckdb.Error("simulated COPY failure")

    def execute(self, sql: str, parameters: list[object] | None = None) -> object:
        if str(sql).lstrip().upper().startswith("COPY"):
            assert parameters is not None
            pathlib.Path(str(parameters[0])).write_bytes(b"partial-parquet")
            raise self._error
        if parameters is None:
            return self._real.execute(sql)
        return self._real.execute(sql, parameters)

    def executemany(self, sql: str, parameters: list[object]) -> object:
        return self._real.executemany(sql, parameters)

    def close(self) -> None:
        self._real.close()


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
    assert staging_leftovers(tmp_path) == []


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


@pytest.mark.anyio
async def test_an_empty_family_declaration_is_refused_before_any_mutation(
    tmp_path: pathlib.Path,
) -> None:
    """Zero declared families is a declaration error, even with a missing parent.

    The parent directory deliberately does not exist: an argument error must be
    reported as one, and nothing may be created to reach that conclusion. A
    nonempty declaration whose families have no rows is different and stays
    legitimate (next test).
    """
    store = InMemoryStore()
    target = tmp_path / "never-created" / "snap.parquet"
    with pytest.raises(ValueError) as excinfo:
        await write_session_snapshot(store, SESSION, (), target)
    assert "families" in str(excinfo.value)
    assert not target.parent.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_declared_families_with_no_rows_export_a_readable_empty_snapshot(
    tmp_path: pathlib.Path,
) -> None:
    """A nonempty declaration with no rows is a legitimate empty snapshot."""
    store = InMemoryStore()
    result = await write_session_snapshot(
        store, SESSION, ("sessions",), tmp_path / "empty.parquet"
    )
    assert result.row_count == 0
    assert result.families == ("sessions",)
    assert SnapshotReplaySource(result.path, session_key=SESSION).records() == ()


@pytest.mark.anyio
async def test_duplicate_declared_families_are_still_refused(
    tmp_path: pathlib.Path,
) -> None:
    store = InMemoryStore()
    with pytest.raises(ValueError) as excinfo:
        await write_session_snapshot(
            store, SESSION, ("sessions", "sessions"), tmp_path / "snap.parquet"
        )
    assert "unique" in str(excinfo.value)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_a_failed_copy_leaves_no_partial_target_and_no_staging_files(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A COPY that dies mid-write must not publish the bytes it left behind."""
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    real_connect = duckdb.connect
    monkeypatch.setattr(
        snapshot_module.duckdb,
        "connect",
        lambda *args, **kwargs: _FailingCopyConnection(real_connect(*args, **kwargs)),
    )
    with pytest.raises(duckdb.Error):
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert not target.exists()
    assert staging_leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_a_failed_overwrite_preserves_the_previous_snapshot_bytes(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit overwrite is only ever installed after a successful write."""
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    first = await write_session_snapshot(store, SESSION, FAMILIES, target)
    original = target.read_bytes()
    real_connect = duckdb.connect
    monkeypatch.setattr(
        snapshot_module.duckdb,
        "connect",
        lambda *args, **kwargs: _FailingCopyConnection(real_connect(*args, **kwargs)),
    )
    with pytest.raises(duckdb.Error):
        await write_session_snapshot(store, SESSION, FAMILIES, target, overwrite=True)
    assert target.read_bytes() == original
    assert first.sha256 == hashlib.sha256(original).hexdigest()
    assert [entry.name for entry in tmp_path.iterdir()] == [target.name]


@pytest.mark.anyio
async def test_a_hash_failure_publishes_nothing_and_leaves_no_staging(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hash is taken from the finished staging file before publication."""
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"

    def exploding_sha256(*args: object, **kwargs: object) -> object:
        raise RuntimeError("simulated hash failure")

    monkeypatch.setattr(
        snapshot_module, "hashlib", types.SimpleNamespace(sha256=exploding_sha256)
    )
    with pytest.raises(RuntimeError):
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert not target.exists()
    assert staging_leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_a_publication_failure_preserves_the_previous_snapshot_bytes(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit overwrite replaces the target only when publication succeeds."""
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    await write_session_snapshot(store, SESSION, FAMILIES, target)
    original = target.read_bytes()

    def failing_replace(source: object, destination: object) -> None:
        raise OSError(errno.EIO, "simulated publication failure")

    monkeypatch.setattr(snapshot_module.os, "replace", failing_replace)
    with pytest.raises(OSError):
        await write_session_snapshot(store, SESSION, FAMILIES, target, overwrite=True)
    assert target.read_bytes() == original
    assert staging_leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_a_competitor_created_after_the_exists_check_is_not_overwritten(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal must be the filesystem's atomic decision, not an earlier check.

    The competing publisher appears when publication is attempted, i.e. strictly
    after the early existence check has already passed. The export must refuse,
    leave the competitor's bytes untouched, and clean its own staging file.
    """
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    competitor_bytes = b"a competing publisher won the race"
    real_link = os.link

    def competing_link(source: object, destination: object, *args: object, **kwargs: object) -> None:
        pathlib.Path(str(destination)).write_bytes(competitor_bytes)
        real_link(source, destination, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(snapshot_module.os, "link", competing_link)
    with pytest.raises(FileExistsError) as excinfo:
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert str(target) in str(excinfo.value)
    assert "overwrite" in str(excinfo.value)
    assert target.read_bytes() == competitor_bytes
    assert staging_leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_unsupported_hard_links_fail_without_a_check_then_replace_fallback(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filesystem without hard links must fail, not silently lose atomicity."""
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"

    def unsupported_link(source: object, destination: object, *args: object, **kwargs: object) -> None:
        raise OSError(errno.ENOTSUP, "hard links are not supported here")

    monkeypatch.setattr(snapshot_module.os, "link", unsupported_link)
    with pytest.raises(OSError) as excinfo:
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert excinfo.value.errno == errno.ENOTSUP
    assert not target.exists()
    assert staging_leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_a_base_exception_during_publication_still_cleans_staging(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cleanup runs for an interrupt as well as for an ordinary error."""
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"

    def interrupted_link(source: object, destination: object, *args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt("simulated interrupt during publication")

    monkeypatch.setattr(snapshot_module.os, "link", interrupted_link)
    with pytest.raises(KeyboardInterrupt):
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert not target.exists()
    assert staging_leftovers(tmp_path) == []


@pytest.mark.anyio
async def test_cancellation_at_the_store_await_leaves_no_snapshot_and_no_staging(
    tmp_path: pathlib.Path,
) -> None:
    """Cancellation is delivered at the store await, before any staging exists.

    The synchronous COPY cannot be interrupted by normal task cancellation, so the
    only real cancellation point is this await; the export must unwind without
    leaving a target or a staging file.
    """
    started = anyio.Event()
    target = tmp_path / "snap.parquet"

    class BlockingStore(InMemoryStore):
        async def read_source_records(
            self,
            family: str,
            session_key: int,
            *,
            since: dt.datetime | None = None,
            until: dt.datetime | None = None,
        ) -> Sequence[tuple[dt.datetime, Mapping[str, object]]]:
            started.set()
            await anyio.sleep_forever()
            return ()

    with anyio.move_on_after(0.2):
        await write_session_snapshot(BlockingStore(), SESSION, FAMILIES, target)
    assert started.is_set()
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_a_cleanup_only_failure_surfaces_and_keeps_the_published_target(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cleanup failure with no prior error must reach the caller, not vanish.

    The snapshot is already published by then, so the failure is about the leftover
    staging name alone. The target must stay a complete, readable snapshot: rolling
    it back to hide the cleanup error would destroy a valid export.
    """
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    deny_staging_unlink(monkeypatch)
    with pytest.raises(OSError) as excinfo:
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert excinfo.value.errno == errno.EACCES
    source = SnapshotReplaySource(target, session_key=SESSION)
    assert len(source.records()) == 3
    # The unremovable staging file is the reported cleanup failure, not a hidden one.
    assert len(staging_leftovers(tmp_path)) == 1


@pytest.mark.anyio
async def test_a_primary_export_failure_survives_a_secondary_cleanup_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The export's own error keeps its identity when cleanup also fails."""
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    primary = duckdb.Error("simulated COPY failure with a later unlink denial")
    real_connect = duckdb.connect
    monkeypatch.setattr(
        snapshot_module.duckdb,
        "connect",
        lambda *args, **kwargs: _FailingCopyConnection(real_connect(*args, **kwargs), primary),
    )
    deny_staging_unlink(monkeypatch)
    with pytest.raises(duckdb.Error) as excinfo:
        await write_session_snapshot(store, SESSION, FAMILIES, target)
    assert excinfo.value is primary
    assert any("cleanup also failed" in note for note in primary.__notes__)
    assert not target.exists()
    assert len(staging_leftovers(tmp_path)) == 1


@pytest.mark.anyio
async def test_a_close_failure_after_staging_creation_removes_the_orphan_path(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed close must not leave the staging file it already created.

    Ownership of the name starts when ``mkstemp`` returns, so the path is removed
    even though the descriptor close failed. The injected failure happens before the
    real close, so the test releases the captured descriptor with the original close
    in its teardown and leaks nothing itself.
    """
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    real_close = os.close
    leaked: list[int] = []

    def failing_close(descriptor: int) -> None:
        leaked.append(descriptor)
        raise OSError(errno.EIO, "simulated close failure")

    monkeypatch.setattr(snapshot_module.os, "close", failing_close)
    try:
        with pytest.raises(OSError) as excinfo:
            await write_session_snapshot(store, SESSION, FAMILIES, target)
        assert excinfo.value.errno == errno.EIO
        assert len(leaked) == 1
        assert not target.exists()
        assert staging_leftovers(tmp_path) == []
    finally:
        for descriptor in leaked:
            real_close(descriptor)


def test_discard_staging_raises_alone_and_yields_to_a_primary_error(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The helper's two outcomes, pinned without the async path in the way."""
    deny_staging_unlink(monkeypatch)
    leftover = tmp_path / f".snap.parquet.leftover{snapshot_module.STAGING_SUFFIX}"
    leftover.write_bytes(b"staged")
    with pytest.raises(OSError) as excinfo:
        snapshot_module._discard_staging(leftover, primary=None)
    assert excinfo.value.errno == errno.EACCES
    primary_error = RuntimeError("the export already failed")
    snapshot_module._discard_staging(leftover, primary=primary_error)
    assert any("cleanup also failed" in note for note in primary_error.__notes__)
    assert leftover.exists()  # the unremovable staging file stays visible


@pytest.mark.anyio
async def test_a_cleanup_only_failure_surfaces_while_the_caller_handles_an_error(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller's own active exception is not this export's primary error.

    Reading the primary from ``sys.exc_info()`` in the ``finally`` would see the
    ``RuntimeError`` being handled here and wrongly swallow the cleanup failure; the
    explicit local capture does not.
    """
    store = await seeded(InMemoryStore())
    target = tmp_path / "snap.parquet"
    deny_staging_unlink(monkeypatch)
    try:
        raise RuntimeError("an unrelated exception the caller is already handling")
    except RuntimeError:
        with pytest.raises(OSError) as excinfo:
            await write_session_snapshot(store, SESSION, FAMILIES, target)
        assert excinfo.value.errno == errno.EACCES
    assert len(staging_leftovers(tmp_path)) == 1
