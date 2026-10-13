"""The wall-clock playback policy: how long to wait before releasing the next event.

**What this module owns.** One decision: given the events of a recorded run and a declared
time scale, how long the pipeline must wait before it releases each event, so that a run
consumes the session **at the rate it happened**. It owns no effect and no clock of its
own: every wait is delegated to the injected :class:`~f1show.ports.MonotonicClock`, and the
module never reads wall time, opens a store, builds a prompt or calls a model.

**The rule.** An event's target offset is ``timestamp_value - origin`` divided by the
declared ``scale``, where the origin is the run's **own earliest known instant** rather
than the session's ``date_start``. A run that begins mid-session therefore paces from its
first known event, and two runs over the same events wait the same way. The wait is that
target minus the monotonic time already elapsed, **clamped at zero**: an event the
pipeline has fallen behind on is released immediately rather than asking the clock to
rewind.

**One wait per event, in order.** Every event is waited on exactly once, including the
ones whose wait is zero. That keeps the accounting parallel to the events — ``waits[i]``
belongs to ``events[i]`` — so the sum of the waits is the run's scaled span and a
measurement can be checked without reconstructing which event was skipped.

**Unknown timestamps are declared, not invented.** An event whose own timestamp is unknown
is released with no wait, because the recorded corpus contains such members — the
null-timestamp lap-1 orphan, and a family whose records carry no timestamp field at all —
and treating "now" as their instant would assert a fact the data does not have.

**Why this is not the request cadence.** :mod:`f1show.request_policy` paces the outbound
requests *to the provider*, on its own monotonic clock; this module paces the pipeline's
**consumption** of records it already holds. They measure different durations, and a run
can exercise either without the other.

**What it must not change.** Pacing changes *when* a turn airs and never *what* it says:
at any scale the transcript is byte-identical to the unpaced run. That is an invariant
this module keeps by construction — it neither reads nor alters an event.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from f1show.collector import DetectedEvent
from f1show.ports import MonotonicClock

__all__ = [
    "PacingSpec",
    "pacing_origin",
    "release_at_offsets",
]


@dataclass(frozen=True)
class PacingSpec:
    """The declared playback cadence of one run.

    ``scale`` multiplies the session's own duration: ``1.0`` is real time, ``10.0`` runs
    ten times faster. It is a declared parameter rather than a module constant because a
    ninety-minute race at ``1.0`` takes ninety minutes, so the tests that must run fast
    exercise the same code path at a high scale instead of skipping it.

    A boolean is refused although Python counts it as an integer: ``True`` is not a scale,
    the same discipline the start aggregation applies to a recorded lap number.
    """

    scale: float = 1.0

    def __post_init__(self) -> None:
        if isinstance(self.scale, bool) or not isinstance(self.scale, int | float):
            raise ValueError(f"the pacing scale must be a number; got {self.scale!r}")
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError(
                f"the pacing scale must be a positive finite number; got {self.scale!r}"
            )


def pacing_origin(events: Sequence[DetectedEvent]) -> dt.datetime | None:
    """The run's own earliest known instant, or ``None`` when no event carries one.

    The minimum rather than the first record's instant, because the recorded order is not
    the timestamp order: the corpus interleaves families, and a member with an unknown
    timestamp is ordered last while still belonging to the same moment.
    """
    known = [
        event.timestamp_value for event in events if event.timestamp_value is not None
    ]
    return min(known) if known else None


async def release_at_offsets(
    events: Sequence[DetectedEvent], *, clock: MonotonicClock, spec: PacingSpec
) -> AsyncIterator[DetectedEvent]:
    """Yield each event once its own recorded offset has arrived on the injected clock.

    An async generator rather than a function returning a sequence, because the waiting
    **is** the product: a caller that collected every event and then waited would pace
    nothing. The elapsed time is read from the same monotonic clock that spends it, so the
    rule holds whatever the clock's origin is, and a late event clamps to a zero wait
    instead of moving time backwards.
    """
    origin = pacing_origin(events)
    started = clock.monotonic()
    for event in events:
        wait = 0.0
        if origin is not None and event.timestamp_value is not None:
            target = (event.timestamp_value - origin).total_seconds() / spec.scale
            wait = max(0.0, target - (clock.monotonic() - started))
        await clock.sleep(wait)
        yield event
