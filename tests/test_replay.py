"""Offline acceptance tests for the deterministic snapshot replay source.

The replay source is a fixture reader: it must work with the SQLite database
file absent, iterate the same sequence every time, and split a session at one
instant for mid-session seeding. These tests never touch a store, the network
or the wall clock.
"""

from __future__ import annotations

import datetime as dt
import pathlib

import duckdb
import pytest

from f1show.replay import SessionMismatchError, SnapshotReplaySource

UTC = dt.timezone.utc
MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=UTC)
LATER = MOMENT + dt.timedelta(seconds=30)
SESSION = 9462
OTHER_SESSION = 9463


def snapshot_rows(session_key: int) -> list[tuple[object, ...]]:
    """Rows for one session with three instants' worth of ties and families.

    ``record_id`` is unique per ``(family, session)``, which is what makes the
    ``(observed_at, family, record_id)`` replay order total rather than merely
    stable. Two families deliberately share ``MOMENT``.
    """
    return [
        ("drivers", session_key, "d2", LATER.replace(tzinfo=None), '{"record_id": "d2"}'),
        ("sessions", session_key, "s1", MOMENT.replace(tzinfo=None), '{"record_id": "s1"}'),
        ("drivers", session_key, "d1", MOMENT.replace(tzinfo=None), '{"record_id": "d1"}'),
        ("laps", session_key, "l1", MOMENT.replace(tzinfo=None), '{"record_id": "l1"}'),
    ]


def write_snapshot(path: pathlib.Path, rows: list[tuple[object, ...]]) -> pathlib.Path:
    """Write a snapshot-shaped Parquet directly, mirroring the declared layout.

    The fixture is built here rather than through the writer so the reader is
    pinned to the declared file layout independently of the writer's internals.
    It deliberately holds several distinct instants, because the reader must be
    generic over any chronology; ``tests/test_snapshot.py`` exercises the same
    chronologies end to end through the real writer and the ``Store`` port.
    """
    connection = duckdb.connect()
    try:
        connection.execute(
            """
            CREATE TABLE snapshot (
                family      VARCHAR   NOT NULL,
                session_key BIGINT    NOT NULL,
                record_id   VARCHAR   NOT NULL,
                observed_at TIMESTAMP NOT NULL,
                payload     VARCHAR   NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO snapshot (family, session_key, record_id, observed_at, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            [*rows],
        )
        connection.execute(
            "COPY (SELECT * FROM snapshot ORDER BY family, observed_at, record_id) "
            "TO ? (FORMAT PARQUET)",
            [str(path)],
        )
    finally:
        connection.close()
    return path


def fixture(tmp_path: pathlib.Path, session_key: int = SESSION) -> pathlib.Path:
    return write_snapshot(tmp_path / f"snapshot-{session_key}.parquet", snapshot_rows(session_key))


def test_replay_refuses_a_snapshot_for_a_different_session(tmp_path: pathlib.Path) -> None:
    path = fixture(tmp_path)
    assert SnapshotReplaySource(path, session_key=SESSION).session_key == SESSION
    with pytest.raises(SessionMismatchError) as excinfo:
        SnapshotReplaySource(path, session_key=OTHER_SESSION)
    message = str(excinfo.value)
    assert str(OTHER_SESSION) in message
    assert str(SESSION) in message


def test_iteration_is_identical_across_passes_and_breaks_every_tie(
    tmp_path: pathlib.Path,
) -> None:
    source = SnapshotReplaySource(fixture(tmp_path), session_key=SESSION)
    expected = ["d1", "l1", "s1", "d2"]  # (observed_at, family, record_id)
    first = [str(item["record_id"]) for item in source]
    second = [str(item["record_id"]) for item in source]
    assert first == expected
    assert second == expected
    assert [str(item["record_id"]) for item in source.records()] == expected
    # The file groups by family; the reader re-orders chronologically. Both are
    # declared orders, and neither may drift between passes.
    assert first != ["d1", "d2", "l1", "s1"]


def test_mid_session_seeding_splits_at_the_instant_and_repeats(
    tmp_path: pathlib.Path,
) -> None:
    source = SnapshotReplaySource(fixture(tmp_path), session_key=SESSION)
    every = [str(item["record_id"]) for item in source.records()]

    seeded = source.seed(MOMENT)  # at or before: the boundary is inclusive
    after = [str(item["record_id"]) for item in source.replay(after=MOMENT)]
    assert [str(item["record_id"]) for item in seeded] == ["d1", "l1", "s1"]
    assert after == ["d2"]
    assert [str(item["record_id"]) for item in seeded] + after == every
    # The same instant yields the same seed, and the seed is family-agnostic.
    assert source.seed(MOMENT) == seeded

    assert source.seed(MOMENT - dt.timedelta(seconds=1)) == ()
    assert [str(item["record_id"]) for item in source.replay(after=MOMENT - dt.timedelta(seconds=1))] == every
    assert [str(item["record_id"]) for item in source.seed(LATER)] == every
    assert list(source.replay(after=LATER)) == []
    assert [str(item["record_id"]) for item in source.replay()] == every


def test_naive_instants_are_rejected(tmp_path: pathlib.Path) -> None:
    source = SnapshotReplaySource(fixture(tmp_path), session_key=SESSION)
    naive = dt.datetime(2024, 3, 2, 15, 0, 0)
    with pytest.raises(ValueError) as seed_error:
        source.seed(naive)
    assert "timezone-aware" in str(seed_error.value)
    with pytest.raises(ValueError) as replay_error:
        source.replay(after=naive)
    assert "timezone-aware" in str(replay_error.value)
