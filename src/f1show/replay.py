"""Deterministic replay from an immutable Parquet session snapshot.

A replay source is built from a snapshot file, never from the store, so it works
with the database file absent: that is what makes a snapshot a fixture.

**Explicit session selection.** A source is constructed for one ``session_key``
and refuses a snapshot that holds a different session rather than replaying the
wrong one.

**Deterministic iteration.** Records come back in the total order
``(observed_at, family, record_id)``. Observation time leads because a replay is
a chronology; ties break by family and then by identity, and the order has to be
*total* rather than merely stable because a stable sort leaves the sequence of
equal keys dependent on the reader's row order, which is the drift that makes a
run irreproducible. ``record_id`` is unique per ``(family, session)``, so no two
records can tie on all three keys.

**No family-specific state reconstruction.** The F03 plan promised "correct
positions, stints and lap history" from a mid-session seed, and that is not
achievable honestly here: only OpenF1's ``sessions`` and ``drivers`` shapes have
ever been observed, so a ``positions`` or ``stints`` reconstruction would invent
semantics for families nobody has seen, and event and state derivation belongs
to F04's collector. Seeding is therefore generic - the records observed at or
before an instant - and nothing family-specific is claimed or promised.

**The instant rule is shared with the writer.** ``start`` and ``after`` are
validated by the same internal helper the snapshot writer uses, so the two cannot
drift: an aware instant is normalised to UTC and compared as an instant, two
offsets for one moment partition identically, and a naive or non-datetime value is
refused. The stored column is naive UTC because the Parquet ``TIMESTAMP`` type has
no offset; this reader converts it back to aware UTC on load.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
from collections.abc import Iterator, Mapping

import duckdb

from f1show import _time  # shared aware-UTC validation; see the module docstring


class SessionMismatchError(RuntimeError):
    """Raised when a snapshot holds a different session than the one requested."""


class SnapshotReplaySource:
    """Replays one session from one snapshot file; see the module docstring.

    The file is read once through a fresh DuckDB connection and held in memory,
    so two passes cannot differ.
    """

    def __init__(self, path: str | pathlib.Path, *, session_key: int) -> None:
        self._path = pathlib.Path(path)
        self._session_key = session_key
        self._entries = self._load()

    def _load(self) -> tuple[tuple[dt.datetime, str, str, dict[str, object]], ...]:
        """Read the snapshot and refuse a file that holds another session."""
        connection = duckdb.connect()
        try:
            rows = connection.execute(
                "SELECT family, session_key, record_id, observed_at, payload "
                "FROM read_parquet(?)",
                [str(self._path)],
            ).fetchall()
        except duckdb.Error as error:
            raise RuntimeError(f"{self._path} is not a readable snapshot: {error}") from error
        finally:
            connection.close()

        others = sorted({int(row[1]) for row in rows} - {self._session_key})
        if others:
            raise SessionMismatchError(
                f"snapshot {self._path} holds session(s) {others} but this replay source was "
                f"constructed for session {self._session_key}; replaying another session is refused"
            )

        entries: list[tuple[dt.datetime, str, str, dict[str, object]]] = []
        for family, _holder, record_id, observed_at, payload in rows:
            moment = observed_at
            if moment.tzinfo is None:  # the writer stamps naive UTC
                moment = moment.replace(tzinfo=dt.timezone.utc)
            try:
                record = json.loads(payload)
            except (TypeError, json.JSONDecodeError) as error:
                raise RuntimeError(
                    f"snapshot {self._path} holds a malformed payload for "
                    f"{family!r}/{record_id!r}: {error}"
                ) from error
            entries.append((moment, str(family), str(record_id), record))
        # A total order, not a stable one: equal keys cannot come back in a
        # different sequence on another read.
        entries.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
        return tuple(entries)

    @property
    def session_key(self) -> int:
        """The one session this source will replay."""
        return self._session_key

    def records(self) -> tuple[Mapping[str, object], ...]:
        """Every record, in the declared total order, as fresh copies."""
        return tuple(copy.deepcopy(entry[3]) for entry in self._entries)

    def seed(self, start: dt.datetime) -> tuple[Mapping[str, object], ...]:
        """Records observed at or before ``start``, for a mid-session start."""
        moment = _time.utc_instant(start, "start")
        return tuple(copy.deepcopy(e[3]) for e in self._entries if e[0] <= moment)

    def replay(self, *, after: dt.datetime | None = None) -> Iterator[Mapping[str, object]]:
        """Iterate the records strictly after ``after``, or all of them."""
        moment = None if after is None else _time.utc_instant(after, "after")
        selected = tuple(
            copy.deepcopy(e[3]) for e in self._entries if moment is None or e[0] > moment
        )
        return iter(selected)

    def __iter__(self) -> Iterator[Mapping[str, object]]:
        return self.replay()
