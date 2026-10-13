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
    "Pacer",
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

    The **minimum** rather than the first record's instant, and the reason is robustness
    rather than the delivered corpus: the collector happens to sort known timestamps before
    returning them, so over both recorded sessions the first event is already the earliest
    -- an independent verifier measured exactly that, and an earlier version of this
    docstring justified the rule with "the recorded order is not the timestamp order", which
    is false for the corpus as shipped. The minimum stays because the rule must not
    *depend* on that sort: a different family order, a future collector, or any caller that
    hands over its own sequence could put a later instant first, and the run's origin would
    then be wrong in a way nothing would report.
    """
    known = [
        event.timestamp_value for event in events if event.timestamp_value is not None
    ]
    return min(known) if known else None


class Pacer:
    """The playback rule together with one run's own origin.

    Two callers need the same arithmetic: the paced release below, which streams a
    recorded session's events, and the booth, which walks its own event sequence
    internally and therefore cannot consume a paced stream. Keeping the rule in one object
    is what stops two nearly equal copies of it from drifting apart.
    """

    def __init__(self, events: Sequence[DetectedEvent], spec: PacingSpec) -> None:
        self.spec = spec
        self.origin = pacing_origin(events)

    def wait_seconds(self, event: DetectedEvent, *, elapsed_seconds: float) -> float:
        """How long to wait before releasing ``event``, given the run's elapsed time.

        Zero when the data cannot place the event -- either the event carries no instant or
        the whole run carries none -- and zero when the event is already behind schedule,
        because asking a clock to rewind is not something a clock can do.
        """
        if self.origin is None or event.timestamp_value is None:
            return 0.0
        offset = (event.timestamp_value - self.origin).total_seconds()
        target = offset / self.spec.scale
        if not math.isfinite(target):
            raise ValueError(
                "the declared playback scale cannot place this event in finite time: an "
                f"offset of {offset:.3f}s at scale {self.spec.scale!r} is not a duration a "
                "clock can wait, and a wait that can hang is a defect rather than a plan"
            )
        return max(0.0, target - elapsed_seconds)


async def release_at_offsets(
    events: Sequence[DetectedEvent], *, clock: MonotonicClock, spec: PacingSpec
) -> AsyncIterator[DetectedEvent]:
    """Yield each event once its own recorded offset has arrived on the injected clock.

    An async generator rather than a function returning a sequence, because the waiting
    **is** the product: a caller that collected every event and then waited would pace
    nothing. Every event is waited on exactly once -- including the ones whose wait is
    zero -- so the waits correspond to the events one for one and their sum is the run's
    scaled span.
    """
    pacer = Pacer(events, spec)
    started = clock.monotonic()
    for event in events:
        await clock.sleep(
            pacer.wait_seconds(event, elapsed_seconds=clock.monotonic() - started)
        )
        yield event
