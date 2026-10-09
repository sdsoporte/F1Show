"""The SQLite implementation of the :class:`f1show.ports.Store` port.

**Why SQLite, and why WAL.** F01 chose a single ``sync`` writer plus a local
store over direct per-agent API access, and SQLite in WAL mode over DuckDB,
because DuckDB's own documentation supports one read-write process *or* many
read-only processes while every Compose service is a separate process. Several
agent processes read while one sync writer writes, and ``journal_mode = WAL`` is
exactly what makes that safe: readers never block the writer and the writer
never blocks readers. WAL is set on every open and persists in the database
file, so a reader that opens the same file sees it too.

**Durability trade-off.** ``synchronous = NORMAL`` is deliberate. In WAL mode it
never corrupts the database; it may lose the most recent committed transactions
after an operating-system crash or power loss, while an application crash loses
nothing. This store is a re-fetchable cache of OpenF1 data, not the system of
record: the sync writer may re-read any overlapping window, and the upsert below
makes a repeated read harmless. ``FULL`` would pay one fsync per write on a
cadence of roughly three seconds to buy back a loss the source can reproduce.

**Record identity is explicit.** Every record mapping must carry a non-empty
``record_id`` string, and a missing one is a ``ValueError`` instead of an
invented identity, because guessing would either duplicate a row or overwrite an
unrelated one. Deriving that identity belongs to the sync writer, which knows a
family's stable keys; for the two families observed at F01 the derivation is
``session_key`` for ``sessions`` and ``session_key`` + ``driver_number`` for
``drivers``. No derivation is invented here for any of OpenF1's other sixteen
endpoints, which have never been observed.

**Writes are upserts.** Rewriting ``(family, session_key, record_id)`` replaces
the payload and the observation time, so an overlapping read window is safe to
replay. Observation times are stored as fixed-width UTC ISO-8601 text: mixed
offsets would make the text comparison in a range filter compare wall clocks
instead of instants. The port is async while the ``sqlite3`` calls here are
short and synchronous, run on the calling thread, and never contend with
themselves because there is exactly one writer. The parent directory of the
database file must already exist; SQLite fails loudly at open if it does not.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3
from collections.abc import Mapping, Sequence

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_records (
    family      TEXT    NOT NULL,
    session_key INTEGER NOT NULL,
    record_id   TEXT    NOT NULL,
    observed_at TEXT    NOT NULL,
    payload     TEXT    NOT NULL,
    PRIMARY KEY (family, session_key, record_id)
);
CREATE INDEX IF NOT EXISTS idx_source_records_window
    ON source_records (family, session_key, observed_at);
CREATE TABLE IF NOT EXISTS watermarks (
    endpoint    TEXT    NOT NULL,
    session_key INTEGER NOT NULL,
    observed_at TEXT    NOT NULL,
    PRIMARY KEY (endpoint, session_key)
);
"""

_UPSERT_RECORD = """
INSERT INTO source_records (family, session_key, record_id, observed_at, payload)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (family, session_key, record_id) DO UPDATE SET
    observed_at = excluded.observed_at,
    payload     = excluded.payload
"""

_UPSERT_WATERMARK = """
INSERT INTO watermarks (endpoint, session_key, observed_at)
VALUES (?, ?, ?)
ON CONFLICT (endpoint, session_key) DO UPDATE SET observed_at = excluded.observed_at
"""


def _stamp(value: dt.datetime, field: str) -> str:
    """Serialise an aware instant as fixed-width UTC ISO-8601 text.

    Normalising to UTC unconditionally is what makes the inclusive range filter
    exact: two ISO-8601 strings carrying different offsets compare wall-clock
    time, so a ``+05:30`` observation would sort against a UTC bound
    incorrectly. A fixed ``timespec`` keeps lexicographic order identical to
    chronological order.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field} must be timezone-aware; naive datetimes are ambiguous and are rejected"
        )
    return value.astimezone(dt.timezone.utc).isoformat(timespec="microseconds")


def _record_id(family: str, record: Mapping[str, object]) -> str:
    """Return the record's explicit identity, or refuse to invent one."""
    value = record.get("record_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"source record for family {family!r} must carry a non-empty string 'record_id'; "
            "deriving an identity belongs to the sync writer, which knows the family's stable "
            "keys (for the families observed at F01: session_key for 'sessions' and "
            "session_key + driver_number for 'drivers'), and no derivation is invented for a "
            "family that has not been observed"
        )
    return value


class SQLiteStore:
    """A single-writer SQLite store; see the module docstring for the choices."""

    def __init__(self, path: str | pathlib.Path) -> None:
        """Open (creating if absent) the database at ``path`` with its schema.

        The persisted ``journal_mode`` is read back and **asserted**, because WAL
        is what makes the one-writer/many-readers assumption true: on a filesystem
        that cannot support it SQLite keeps a different mode silently, and the
        whole architecture would rest on a mode that is not in effect.

        ``synchronous`` is read back and recorded as well, but honestly: it is a
        per-connection pragma, not a property stored in the database file, so there
        is nothing a second connection could be checked against. It is reported on
        ``self.synchronous`` rather than asserted.
        """
        self._path = pathlib.Path(path)
        self._closed = False
        self._conn = sqlite3.connect(str(self._path))
        mode = self._conn.execute("PRAGMA journal_mode = WAL").fetchone()
        self.journal_mode = "unknown" if mode is None else str(mode[0]).lower()
        if self.journal_mode != "wal":
            self._conn.close()
            raise RuntimeError(
                f"SQLiteStore at {self._path} could not enable WAL: SQLite reports "
                f"journal_mode={self.journal_mode!r}. The single-writer/many-readers "
                "assumption rests on WAL, so this is refused rather than silently degraded"
            )
        self._conn.execute("PRAGMA synchronous = NORMAL")
        sync = self._conn.execute("PRAGMA synchronous").fetchone()
        self.synchronous: int | None = None if sync is None else int(sync[0])
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def _require_open(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("SQLiteStore is closed")
        return self._conn

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: dt.datetime,
    ) -> int:
        """Upsert ``records`` for one family and session, returning the count written.

        The whole batch is prepared, and therefore validated, before anything is
        executed: one record without a ``record_id`` rejects the batch without a
        partial write.
        """
        conn = self._require_open()
        stamp = _stamp(observed_at, "observed_at")
        rows = [
            (family, session_key, _record_id(family, record), stamp, json.dumps(dict(record)))
            for record in records
        ]
        with conn:
            conn.executemany(_UPSERT_RECORD, rows)
        return len(records)

    async def read_source_records(
        self,
        family: str,
        session_key: int,
        *,
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
    ) -> Sequence[Mapping[str, object]]:
        """Return the stored records whose batch observation time is in the
        inclusive ``[since, until]`` window, oldest first, as plain mappings that
        equal what was written, ``record_id`` included."""
        conn = self._require_open()
        since_stamp = None if since is None else _stamp(since, "since")
        until_stamp = None if until is None else _stamp(until, "until")
        cursor = conn.execute(
            # One static query for every window: a ``None`` bound short-circuits
            # its clause, so no SQL text is ever built from a caller value.
            """
            SELECT payload FROM source_records
            WHERE family = ? AND session_key = ?
              AND (? IS NULL OR observed_at >= ?)
              AND (? IS NULL OR observed_at <= ?)
            ORDER BY observed_at, rowid
            """,
            (family, session_key, since_stamp, since_stamp, until_stamp, until_stamp),
        )
        stored: list[Mapping[str, object]] = []
        for (payload,) in cursor:
            try:
                stored.append(json.loads(payload))
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"stored payload for family {family!r} session {session_key} is not "
                    "valid JSON; the local store is corrupt"
                ) from error
        return tuple(stored)

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: dt.datetime
    ) -> int:
        """Record ``observed_at`` as the per-``(endpoint, session_key)`` watermark
        and return the documented ``1``, matching the in-memory double."""
        conn = self._require_open()
        stamp = _stamp(observed_at, "observed_at")
        with conn:
            conn.execute(_UPSERT_WATERMARK, (endpoint, session_key, stamp))
        return 1

    async def get_watermark(self, endpoint: str, session_key: int) -> dt.datetime | None:
        """Return the watermark as an aware datetime, or ``None`` if unset."""
        conn = self._require_open()
        row = conn.execute(
            "SELECT observed_at FROM watermarks WHERE endpoint = ? AND session_key = ?",
            (endpoint, session_key),
        ).fetchone()
        return None if row is None else dt.datetime.fromisoformat(row[0])

    async def close(self) -> None:
        """Close the connection. Idempotent; every other method refuses after it."""
        if not self._closed:
            self._closed = True
            self._conn.close()
