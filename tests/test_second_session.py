"""Measured facts of the **second** recorded window, session 9655 (F09j).

This module is a pin, not a re-derivation: every number below was measured from the
bytes written by the throwaway recorder (``var/capture_9655.py``) for the Qatar
Grand Prix, ``session_key=9655``, ``meeting_key=1251``,
``date_start=2024-12-01T16:00:00+00:00``. Nothing here is inherited from session
9617's suite: that session's order, indices, null timestamps, seat consequences and
counts are its own, so importing them would pin a coincidence instead of a fact.

The corpus is read through the project's own surface only -
``load_recorded_session(9655, fixtures_dir=Path("fixtures/openf1/9655"))`` and
``collect_session_events`` - so a loader or collector regression on the second
window fails here. The end-to-end case reuses ``run_session`` with a **local** echo
double; ``tests/test_run.py`` is deliberately not imported, because the second
window must stand on its own measurements.

Why these numbers and no others: a test that asserted anything beyond the recorded
bytes would either be checking the fixture's identity (already covered) or guessing
at live OpenF1 behaviour this snapshot cannot establish.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from collections import Counter
from collections.abc import Awaitable
from pathlib import Path

import pytest

from f1show.booth import OutcomeKind
from f1show.collector import FAMILY_ORDER, DetectedEvent, collect_session_events
from f1show.config import BoothSettings
from f1show.dialogue import Speaker
from f1show.fakes import FrozenClock
from f1show.ports import ModelRequest, ModelResponse
from f1show.run import load_recorded_session, run_session
from f1show.start import group_start_events

SESSION_KEY = 9655
#: The exact relative path the parent task named; it resolves from the repository root,
#: which is where pytest runs this suite.
FIXTURES_DIR = Path("fixtures/openf1/9655")

#: A fictional model identifier, the same deliberately fake shape the other suites use.
TEST_MODEL_ID = "second-window-test-model"

#: A hard test-side bound so a stalled run fails loudly instead of hanging the suite.
HAZARD_TIMEOUT_SECONDS = 60.0

#: One recorded record count per family, read from the written files.
RECORD_COUNTS = {
    "sessions": 1,
    "drivers": 20,
    "position": 510,
    "laps": 944,
    "pit": 60,
    "stints": 82,
    "race_control": 112,
    "championship_drivers": 23,
    "championship_teams": 10,
    "session_result": 20,
}

#: One event count per event-bearing family, measured with the collector.
EVENT_COUNTS = {
    "position": 510,
    "laps": 944,
    "pit": 60,
    "stints": 82,
    "race_control": 112,
}

#: Total events the collector derives from the five event-bearing families.
TOTAL_EVENTS = 1708

#: Events whose own evidence carries a ``lap_number`` in 1..5: the "five-lap window".
FIRST_FIVE_LAPS_TOTAL = 114
FIRST_FIVE_LAPS_BY_FAMILY = {"laps": 92, "race_control": 20, "pit": 2}

#: The start group: twenty lap-1 rows air as one turn at the lowest member index, and
#: the other nineteen members' own turns are absorbed.
START_MEMBERS = 20
START_POSITION = 29
START_COVERED = 19

#: The end-to-end run: one turn per event except the covered start members.
RUN_TURNS = 1689
RUN_EXCLUDED = 19

#: The booth's own two reference shapes, both offered in the prompt: a field reference
#: (``- family[record].field``) and a bare identity (``- family[record]``, for the group
#: turn). The double cites the **first** reference the prompt offers and never invents one.
_PROMPT_REFERENCE = re.compile(r"^-\s+([a-z_]+\[\d+\]\.[a-z0-9_]+)\s*$", re.MULTILINE)
_PROMPT_IDENTITY = re.compile(r"^-\s+([a-z_]+\[\d+\])\s*$", re.MULTILINE)


async def bounded[T](awaitable: Awaitable[T], *, hazard: str) -> T:
    """Await under a hard bound so a stall fails instead of blocking the suite."""
    try:
        return await asyncio.wait_for(awaitable, timeout=HAZARD_TIMEOUT_SECONDS)
    except TimeoutError:
        pytest.fail(
            f"HANG HAZARD: {hazard} did not finish within {HAZARD_TIMEOUT_SECONDS:g}s"
        )


def recorded_payloads() -> dict[str, list[dict[str, object]]]:
    """The second window through the project's own loader."""
    return load_recorded_session(SESSION_KEY, fixtures_dir=FIXTURES_DIR)


def recorded_events() -> tuple[DetectedEvent, ...]:
    """Collect the second window once, for the assertions that read it."""
    return collect_session_events(SESSION_KEY, recorded_payloads())


def _in_first_five_laps(event: DetectedEvent) -> bool:
    """Whether the event's own evidence places it in laps 1..5.

    The lap number is read as a real integer: ``True == 1`` would otherwise let a
    boolean stand in for a recorded lap.
    """
    lap_number = event.evidence.get("lap_number")
    return (
        isinstance(lap_number, int)
        and not isinstance(lap_number, bool)
        and 1 <= lap_number <= 5
    )


def test_second_window_family_record_counts() -> None:
    """Every family wrote the record count the capture reported, verbatim.

    The ten counts are read straight from the written files. Nine of them are then
    re-read through ``load_recorded_session``, which confirms the session filter keeps
    every record (all ten files belong to 9655 alone, unlike 9617's ``sessions`` file
    which held the whole season).
    """
    raw_counts = {
        family: len(json.loads((FIXTURES_DIR / f"{family}.json").read_text("utf-8")))
        for family in RECORD_COUNTS
    }
    assert raw_counts == RECORD_COUNTS

    # ``sessions`` is written but deliberately not loaded by the project's loader, so
    # the round-trip covers the nine families the loader does read.
    loaded = recorded_payloads()
    assert set(loaded) == set(FAMILY_ORDER) | {
        "drivers",
        "championship_drivers",
        "championship_teams",
        "session_result",
    }
    assert {family: len(loaded[family]) for family in loaded} == {
        family: RECORD_COUNTS[family] for family in loaded
    }


def test_second_window_event_count_and_families() -> None:
    """The collector derives one event per record here, and no other event at all."""
    events = recorded_events()
    assert len(events) == TOTAL_EVENTS
    assert Counter(event.family for event in events) == EVENT_COUNTS
    # Every event belongs to this session, and none came from a non-event family.
    assert {event.session_key for event in events} == {SESSION_KEY}
    assert {event.family for event in events} == set(FAMILY_ORDER)


def test_second_window_first_five_laps() -> None:
    """The "five-lap window" of this session holds 114 events, measured.

    The unit is the user's framing, not a collector constant: an event is in the
    window when its own evidence carries a ``lap_number`` from 1 to 5. The breakdown
    states what the window actually contains here, because laps, race-control rows
    and pit stops all carry a lap number.
    """
    events = recorded_events()
    window = [event for event in events if _in_first_five_laps(event)]
    assert len(window) == FIRST_FIVE_LAPS_TOTAL
    assert Counter(event.family for event in window) == FIRST_FIVE_LAPS_BY_FAMILY
    assert Counter(event.evidence["lap_number"] for event in window) == {
        1: 34,
        2: 18,
        3: 20,
        4: 21,
        5: 21,
    }


def test_second_window_start_group() -> None:
    """The start group of this session is 20 members airing at index 29.

    These are session-specific measurements: the indices come from this window's
    record order, so 9617's start indices say nothing about them.
    """
    events = recorded_events()
    group = group_start_events(events)
    assert group is not None
    assert len(group.members) == START_MEMBERS
    assert group.position == START_POSITION
    assert len(group.covered) == START_COVERED
    assert group.positions == tuple(
        range(START_POSITION, START_POSITION + START_MEMBERS)
    )
    assert all(
        member.event_type.value == "lap_completed"
        and member.evidence.get("lap_number") == 1
        for member in group.members
    )
    # ``position`` is the first member's index and ``covered`` excludes it, so the two
    # account for every member exactly once.
    assert {group.position} | set(group.covered) == set(group.positions)


class FirstReferenceEchoModel:
    """A local offline provider that cites the first reference the prompt offers.

    The recorded window has far too many events to script by hand, so this double
    reads the reference list the booth supplied and cites its first entry; it can
    therefore never answer with an invented source. It is deliberately local: the
    second window is not allowed to lean on ``tests/test_run.py``'s double.
    """

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        match = _PROMPT_REFERENCE.search(request.prompt) or _PROMPT_IDENTITY.search(
            request.prompt
        )
        if match is None:
            raise AssertionError(
                "the booth supplied no reference to cite; the double refuses to invent one"
            )
        reference = match.group(1)
        return ModelResponse(
            model_id=request.model_id,
            text=f"EVIDENCE: {reference}\nCommentary on {reference}.",
            input_tokens=1,
            output_tokens=1,
        )


@pytest.mark.anyio
async def test_second_window_run_session_end_to_end() -> None:
    """One offline run of the second window: one turn per event but the covered start rows.

    The assertion pins the shape of the transcript the recorder's bytes produce: 1708
    typed outcomes for 1708 events, of which the 19 covered start members are excluded
    and the remaining 1689 air a turn, led by the lead speaker and stamped with the
    configured fictional model id.
    """
    events = recorded_events()
    model = FirstReferenceEchoModel()

    result = await bounded(
        run_session(
            payloads=recorded_payloads(),
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(dt.datetime(2024, 12, 1, 16, 0, 0, tzinfo=dt.UTC)),
            settings=BoothSettings(model_id=TEST_MODEL_ID, language="en"),
        ),
        hazard="the second recorded window's end-to-end run",
    )

    turns = result.transcript.turns
    assert result.transcript.session_key == SESSION_KEY
    assert len(result.outcomes) == len(events) == TOTAL_EVENTS
    assert Counter(outcome.kind for outcome in result.outcomes) == {
        OutcomeKind.TURN: RUN_TURNS,
        OutcomeKind.EXCLUDED: RUN_EXCLUDED,
    }
    assert len(turns) == RUN_TURNS == len(model.requests)
    assert turns[0].speaker is Speaker.lead
    assert {turn.speaker for turn in turns} == {Speaker.lead, Speaker.color}
    # The booth strips the citation and keeps it as evidence, so the double's answer
    # round-trips: the cited reference is either the event's own identity (the group
    # turn cites one bare identity) or one of the fields the event offered.
    for turn in turns:
        assert turn.text.startswith("Commentary on ") and turn.evidence
        cited = turn.text[len("Commentary on ") : -1]
        assert cited == turn.event_ref or cited in turn.evidence
    assert {turn.model_id for turn in turns} == {TEST_MODEL_ID}
