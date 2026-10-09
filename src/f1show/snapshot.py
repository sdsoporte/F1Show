"""Immutable per-session Parquet snapshots, exported with DuckDB.

**One file per session.** A session is one immutable fixture, so it is one
artifact with one hash rather than a directory of per-family files.

**DuckDB here is a Parquet engine, not the live store.** DuckDB supports one
read-write process *or* many read-only processes and every Compose service is a
separate process, so it can never be the store several agents read while the
single sync writer writes; SQLite in WAL mode is (see ``store.py``).

**Contents are declared, not discovered.** The ``Store`` port has no operation
to list families, deliberately, so the caller names the families to export and
the result is reproducible from the call alone.

**Immutability is enforced, not assumed.** Writing to a path that already exists
raises ``FileExistsError`` unless the caller passes ``overwrite=True``; a
fixture that can be silently overwritten is not a fixture.

**The layout carries the store's own fields** so a round trip is lossless:
``family``, ``session_key``, ``record_id``, ``observed_at`` and the payload,
written ordered by ``(family, observed_at, record_id)``.

**Observation time travels with each row.** The ``Store`` port returns each
record paired with the instant it was observed, so a snapshot keeps every row's
own time and the declared ``(family, observed_at, record_id)`` file order carries
real chronology. When the port reported only payloads, a session collapsed onto
the single instant its caller declared, which made a mid-session seed take the
whole session or none of it.

**The replay source reads any number of instants**, so the corrected port needs
no reader change.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
from collections.abc import Sequence
from dataclasses import dataclass

import duckdb

from f1show.ports import Store

#: The declared physical layout of a snapshot, in order, public to readers.
SNAPSHOT_COLUMNS = ("family", "session_key", "record_id", "observed_at", "payload")


@dataclass(frozen=True)
class SnapshotResult:
    """What one export produced, including the hash a fixture is verified by."""

    session_key: int
    path: pathlib.Path
    row_count: int
    families: tuple[str, ...]
    sha256: str


def _utc_instant(value: dt.datetime, field: str) -> dt.datetime:
    """Normalise an aware instant to naive UTC; refine a naive one.

    The plain TIMESTAMP column stores a wall clock, and an offset-free "3pm" is
    ambiguous, so every row is stamped on the UTC clock.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field} must be timezone-aware; naive datetimes are ambiguous and are rejected"
        )
    return value.astimezone(dt.timezone.utc).replace(tzinfo=None)


def _identity(family: str, payload: dict[str, object]) -> str:
    """Return the record's explicit identity, or refuse to export an invented one."""
    value = payload.get("record_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"a stored record for family {family!r} has no non-empty string 'record_id'; "
            "the store contract guarantees one, so the snapshot refuses to invent an identity"
        )
    return value


async def write_session_snapshot(
    store: Store,
    session_key: int,
    families: Sequence[str],
    path: str | pathlib.Path,
    *,
    overwrite: bool = False,
) -> SnapshotResult:
    """Export one immutable Parquet snapshot of ``session_key``.

    Each declared family is read once through ``store.read_source_records``, each
    row keeping its own observation time, and the file is written through a fresh
    DuckDB connection from the ordered select; the hash is of the file as written.
    """
    target = pathlib.Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"refusing to overwrite the existing snapshot {target}: a snapshot is an immutable "
            "fixture, so pass overwrite=True only if replacing it is genuinely intended"
        )
    declared = tuple(families)
    if len(set(declared)) != len(declared):
        raise ValueError(
            "declared families must be unique, or one identity would be exported twice; "
            f"got {declared!r}"
        )
    rows: list[tuple[str, int, str, dt.datetime, str]] = []
    for family in declared:
        for observed_at, record in await store.read_source_records(family, session_key):
            payload = dict(record)
            # Sorted keys so the file does not depend on the store's dict order;
            # the parsed mapping is still equal to what the store returned.
            rows.append(
                (
                    family,
                    session_key,
                    _identity(family, payload),
                    _utc_instant(observed_at, "observed_at"),
                    json.dumps(payload, sort_keys=True),
                )
            )
    # The declared file order: family, then observation time, then identity.
    rows.sort(key=lambda row: (row[0], row[3], row[2]))

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
        # The ordered select is what makes two exports of one content byte-identical.
        connection.execute(
            "COPY (SELECT * FROM snapshot ORDER BY family, observed_at, record_id) "
            "TO ? (FORMAT PARQUET)",
            [str(target)],
        )
    finally:
        connection.close()

    return SnapshotResult(
        session_key=session_key,
        path=target,
        row_count=len(rows),
        families=declared,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    )
