"""Shared aware-UTC validation for the snapshot boundary and the replay reader.

The two modules used to carry their own copy of the same rule, which is a
maintenance hazard: one of them could drift and still look plausible. The rule
lives here once.

**Aware UTC is the internal instant.** A validated value is normalised to
``astimezone(UTC)``, so two callers expressing one instant with different offsets
produce the same value and partition a session identically.

**Naive stays rejected.** A wall clock without an offset is ambiguous, so it is
refused rather than guessed, and a ``tzinfo`` that cannot resolve an offset for the
instant (``utcoffset() is None``) is refused as well. A non-``datetime`` is a
type error, reported as one.

**The physical Parquet boundary converts.** The snapshot's ``TIMESTAMP`` column has
no offset, so the writer converts a validated instant to naive UTC at that one
boundary (see ``snapshot._parquet_instant``); the reader converts the same column
back to aware UTC. This helper makes no decision about the storage format.
"""

from __future__ import annotations

import datetime as dt


def utc_instant(value: dt.datetime, field: str) -> dt.datetime:
    """Validate a timezone-aware instant and normalise it to aware UTC.

    ``field`` names the caller's own boundary so an error identifies the parameter
    that was wrong rather than a generic "timestamp".
    """
    if not isinstance(value, dt.datetime):
        raise TypeError(
            f"{field} must be a datetime, got {type(value).__name__}; an instant is "
            "required, not a value that merely looks like a timestamp"
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field} must be timezone-aware; naive datetimes are ambiguous and are rejected"
        )
    return value.astimezone(dt.timezone.utc)
