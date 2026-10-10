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

**Publication is staged and atomic.** Every declared family is read and validated
first, the rows are written to a unique same-directory staging file, DuckDB is
closed, and only then is the finished file hashed and published: a non-overwrite
publication creates the final directory entry with ``os.link``, so a competing
publisher that appeared after the early existence check loses with
``FileExistsError`` instead of being overwritten, while ``overwrite=True`` uses
``os.replace`` only after a successful write and hash. A reader that observes the
final name therefore sees a complete file, never a partial one, and a failure
before publication leaves any previous file's bytes exactly as they were. Staging
names are removed on every handled failure, including cancellation delivered at an
await boundary, unless the filesystem refuses the removal itself: a refusal with no
other error surfaces to the caller, and a refusal while another error is unwinding
is recorded on that error and leaves the staging file visible on disk. A leftover
staging file is therefore a reported cleanup failure, never a partial published
target.

**Atomic visibility, not power-loss durability.** No ``fsync`` is issued, so this
is a guarantee about what another *process* can observe, not about what survives a
power cut. Cancellation is bounded for the same reason: the DuckDB ``COPY`` is
synchronous, so normal task cancellation cannot interrupt it - cancellation is only
delivered at the ``await`` where the store is read, which happens before any
staging file exists. An error raised inside the synchronous publication path is
still unwound through the ``finally`` cleanup. The one descriptor this module owns
is the ``mkstemp`` handle in ``_staging_path``; if closing it fails, the staging
name is removed before the close error surfaces, but the descriptor's post-failure
state cannot be proven here and is deliberately not guessed at.

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

import contextlib
import datetime as dt
import hashlib
import json
import os
import pathlib
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass

import duckdb

from f1show import _time  # shared aware-UTC validation; see the module docstring
from f1show.ports import Store

#: The declared physical layout of a snapshot, in order, public to readers.
SNAPSHOT_COLUMNS = ("family", "session_key", "record_id", "observed_at", "payload")

#: The suffix of a same-directory staging file awaiting publication.
STAGING_SUFFIX = ".staging"


@dataclass(frozen=True)
class SnapshotResult:
    """What one export produced, including the hash a fixture is verified by."""

    session_key: int
    path: pathlib.Path
    row_count: int
    families: tuple[str, ...]
    sha256: str


def _parquet_instant(value: dt.datetime, field: str) -> dt.datetime:
    """Validate an aware instant and convert it to the naive UTC the column stores.

    The Parquet ``TIMESTAMP`` column has no offset, so the aware instant is
    normalised by the shared validator and then deliberately made naive at this one
    physical boundary. The replay reader converts the same column back to aware UTC.
    """
    return _time.utc_instant(value, field).replace(tzinfo=None)


def _existing_snapshot_error(target: pathlib.Path) -> FileExistsError:
    """The one refusal message, shared by the early check and the atomic link."""
    return FileExistsError(
        f"refusing to overwrite the existing snapshot {target}: a snapshot is an immutable "
        "fixture, so pass overwrite=True only if replacing it is genuinely intended"
    )


def _staging_path(target: pathlib.Path) -> pathlib.Path:
    """Reserve a unique staging name in the target's own directory.

    Same-directory is what keeps publication a rename within one filesystem; a
    staging file in the system temp directory could cross a device boundary and turn
    the atomic rename into a copy. ``mkstemp`` picks and creates the name atomically
    and the handle is closed at once. Ownership of the name starts the moment
    ``mkstemp`` returns, so a failed close still removes it before that close error
    surfaces.
    """
    handle, name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=STAGING_SUFFIX, dir=target.parent
    )
    staging = pathlib.Path(name)
    try:
        os.close(handle)
    except BaseException:
        # The descriptor's state after a failed close is not knowable here: some
        # systems report an error after the descriptor was in fact released, so a
        # retry could close an unrelated descriptor that has reused the number.
        # Remove the name only - a leftover stays visible on disk - and let the
        # close error surface.
        with contextlib.suppress(OSError):
            staging.unlink()
        raise
    return staging


def _publish(staging: pathlib.Path, target: pathlib.Path, *, overwrite: bool) -> None:
    """Install a finished staging file at the final name, once, atomically.

    With ``overwrite=True`` the replacement is ``os.replace``, reached only after the
    bytes were written and hashed. Without it, ``os.link`` creates the final directory
    entry and fails with ``FileExistsError`` if the name is already taken, which is a
    filesystem decision a competing publisher cannot win between; a check followed by a
    replace could. There is deliberately no fallback when hard links are unsupported:
    the export fails instead of silently becoming non-atomic.
    """
    if overwrite:
        os.replace(staging, target)
        return
    try:
        os.link(staging, target)
    except FileExistsError as error:
        raise _existing_snapshot_error(target) from error
    # The staging name is removed by the caller's ``finally`` cleanup immediately
    # after this returns, so the linked inode is what remains at the target.


def _discard_staging(staging: pathlib.Path | None, *, primary: BaseException | None) -> None:
    """Remove the staging file, reporting a failure without replacing a prior one.

    ``primary`` is the exception already unwinding through the caller's ``finally``,
    captured there on purpose: asking ``sys.exc_info()`` inside this function's own
    ``except OSError`` would observe the cleanup error itself and could never tell a
    cleanup-only failure apart from a secondary one. With no primary error the
    cleanup failure surfaces to the caller; with one, that error keeps its identity
    and the cleanup failure is recorded as a note on it, so neither is lost.
    """
    if staging is None:
        return
    try:
        staging.unlink()
    except FileNotFoundError:
        return  # already published, or never created
    except OSError as cleanup_error:
        if primary is None:
            raise
        primary.add_note(
            f"snapshot staging cleanup also failed ({type(cleanup_error).__name__}: "
            f"{cleanup_error}); a staging file may remain at {staging}"
        )


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

    Each declared family is read once through ``store.read_source_records``, each row
    keeping its own observation time. The rows are gathered and validated first, then
    written to a same-directory staging file whose finished bytes are hashed and only
    then published; see the module docstring for the atomicity and cancellation limits.
    """
    target = pathlib.Path(path)
    declared = tuple(families)
    if not declared:
        raise ValueError(
            "declared families must not be empty: a snapshot of no declared family is not a "
            "fixture of anything, and a silently empty file is refused rather than written"
        )
    if len(set(declared)) != len(declared):
        raise ValueError(
            "declared families must be unique, or one identity would be exported twice; "
            f"got {declared!r}"
        )
    if target.exists() and not overwrite:
        raise _existing_snapshot_error(target)
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
                    _parquet_instant(observed_at, "observed_at"),
                    json.dumps(payload, sort_keys=True),
                )
            )
    # The declared file order: family, then observation time, then identity.
    rows.sort(key=lambda row: (row[0], row[3], row[2]))

    staging: pathlib.Path | None = None
    primary: BaseException | None = None
    try:
        # Reserved only after the rows validated, so an argument error cannot leave a
        # staging file behind, and same-directory so publication stays a rename.
        staging = _staging_path(target)
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
            if rows:  # DuckDB refuses ``executemany`` with no parameter sets
                connection.executemany(
                    "INSERT INTO snapshot (family, session_key, record_id, observed_at, payload) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [*rows],
                )
            # The ordered select is what makes two exports of one content byte-identical.
            connection.execute(
                "COPY (SELECT * FROM snapshot ORDER BY family, observed_at, record_id) "
                "TO ? (FORMAT PARQUET)",
                [str(staging)],
            )
        finally:
            connection.close()
        # Hash the closed, complete staging bytes before anything can see the target.
        digest = hashlib.sha256(staging.read_bytes()).hexdigest()
        _publish(staging, target, overwrite=overwrite)
    except BaseException as error:
        # Remembered explicitly rather than read back from ``sys.exc_info()`` in the
        # ``finally``: that call also reports an exception our caller is already
        # handling, which would misclassify a cleanup-only failure as secondary.
        primary = error
        raise
    finally:
        _discard_staging(staging, primary=primary)

    return SnapshotResult(
        session_key=session_key,
        path=target,
        row_count=len(rows),
        families=declared,
        sha256=digest,
    )
