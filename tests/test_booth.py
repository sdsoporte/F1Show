"""Offline acceptance tests for the F09 two-person commentary booth.

Everything here runs offline and for free: no live model call, no credential and no
network. The gateway is the shipped ``ScriptedModelClient`` for the answering paths and a
local scripted double for the failure families, and every emitted turn is stamped by the
shipped ``FrozenClock``, so no wall clock is read.

**What an offline suite can and cannot prove.** The two F04 hard rules have a
structural half and a semantic half. The structural half *is* tested: the assembled
prompt carries the prohibition against describing an on-track pass from a position
change, and against anchoring a fast-lap or gap claim on lap 1, and every emitted turn's
evidence cites only references drawn from the supplied event and nothing else. The
semantic half -- that a model's generated prose never *in fact* invents a pass or anchors
a claim on lap 1 -- is a property of the provider's output and is **not provable
offline**. It needs the separately authorized live trial that F13 owns, and this suite
claims nothing about it.

Every ordering or gated wait is bounded with ``asyncio.wait_for`` plus ``pytest.fail``
naming the hazard, because a suite that hangs instead of failing is a defect this project
has already shipped once. The booth itself is deliberately sequential, so these bounds are
a harness guard rather than a race assertion.
"""

from __future__ import annotations

import ast
import asyncio
import datetime as dt
import inspect
import re
from collections.abc import Awaitable, Sequence
from pathlib import Path
from typing import Any

import pytest

import f1show
import f1show.booth
from f1show.booth import (
    COLOR_PERSONA,
    LEAD_PERSONA,
    PRIORITY_EVENT_TYPES,
    BoothOutcome,
    BoothReason,
    BoothResult,
    CommentaryBooth,
    OutcomeKind,
    Persona,
    event_reference,
    evidence_references,
)
from f1show.collector import DetectedEvent
from f1show.config import BoothSettings
from f1show.dialogue import Speaker, Turn
from f1show.events import EventType
from f1show.fakes import FrozenClock, ScriptedModelClient
from f1show.gemini import (
    ModelError,
    ModelRateLimitedError,
    ModelResponseError,
    ModelServerError,
    ModelTimeoutError,
    ModelTransportError,
)
from f1show.ports import ModelClient, ModelRequest, ModelResponse

UTC = dt.timezone.utc
SESSION_KEY = 9617
T0 = dt.datetime(2024, 3, 2, 15, 0, 5, tzinfo=UTC)
T1 = dt.datetime(2024, 3, 2, 15, 0, 20, tzinfo=UTC)

#: Fictional model identifiers of the same deliberately fake shape as the other suites.
#: The real value is injected from configuration and no real model ID appears here.
TEST_MODEL_ID = "test-model"
OTHER_MODEL_ID = "test-model-other"

#: A hard test-side bound on every await. Five seconds is enormous for a fully offline,
#: in-memory booth; it exists so a stall fails loudly instead of hanging the suite.
HAZARD_TIMEOUT_SECONDS = 5.0

#: The source of the module actually imported, not of a copied path: a copy-based read
#: that does not prove which module it loaded is the trap a previous unit shipped.
BOOTH_SOURCE = Path(inspect.getsourcefile(f1show.booth) or "").resolve()

#: A reference-shaped token: ``family[record].field``. Used to prove the prompt offers
#: exactly the supplied references and no other.
REFERENCE_TOKEN = re.compile(r"[a-z_]+\[\d+\]\.[a-z0-9_]+")


async def bounded[T](
    awaitable: Awaitable[T], *, hazard: str, timeout: float = HAZARD_TIMEOUT_SECONDS
) -> T:
    """Await under a hard bound so a stall fails instead of hanging the suite.

    ``asyncio.wait_for`` raises the builtin ``TimeoutError`` for *its own* deadline,
    which is a different type from the model boundary's ``ModelTimeoutError``.
    """
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except TimeoutError:
        pytest.fail(
            f"HANG HAZARD: {hazard} did not finish within {timeout:g}s; a wait that can "
            "hang is a defect, so this fails instead of blocking the suite"
        )


def detected(
    *,
    index: int,
    event_type: EventType = EventType.POSITION_CHANGE,
    family: str = "position",
    evidence: dict[str, object] | None = None,
    timestamp: dt.datetime | None = T0,
    driver_number: int | None = 1,
    session_key: int = SESSION_KEY,
) -> DetectedEvent:
    """Build the detected event under test, with the recorded evidence shape."""
    if evidence is None:
        evidence = {"position": 3}
    return DetectedEvent(
        event_type=event_type,
        family=family,
        session_key=session_key,
        record_index=index,
        driver_number=driver_number,
        timestamp_field="date" if timestamp is not None else None,
        timestamp_value=timestamp,
        timestamp_unknown_reason=(
            None if timestamp is not None else "family_carries_no_timestamp_field"
        ),
        evidence=evidence,
    )


def ref(event: DetectedEvent) -> str:
    """The first citable reference of ``event``, for scripting an answer."""
    return evidence_references(event)[0]


def spoken(reference: str, text: str) -> ModelResponse:
    """A valid model answer: a citation line followed by the commentary."""
    return ModelResponse(
        model_id=TEST_MODEL_ID, text=f"EVIDENCE: {reference}\n{text}", input_tokens=3, output_tokens=5
    )


def answered(events: Sequence[DetectedEvent], texts: Sequence[str]) -> list[ModelResponse]:
    """One valid answer per event, in order."""
    return [spoken(ref(event), text) for event, text in zip(events, texts, strict=True)]


class ScriptedFailingModelClient:
    """A local double that raises the scripted ``ModelError`` instead of answering.

    ``ScriptedModelClient`` cannot raise, so a failure family needs a double that can.
    It records every request and raises rather than inventing a response.
    """

    def __init__(self, outcomes: Sequence[ModelResponse | ModelError]) -> None:
        self._queue = list(outcomes)
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self._queue:
            raise RuntimeError(
                "ScriptedFailingModelClient queue is exhausted; a silent fallback is forbidden"
            )
        outcome = self._queue.pop(0)
        if isinstance(outcome, ModelError):
            raise outcome
        return outcome


def make_booth(
    events: Sequence[DetectedEvent],
    model: ModelClient,
    *,
    settings: BoothSettings | None = None,
    max_context_turns: int = 4,
    context_char_budget: int = 400,
    context_window_seconds: float = 3600.0,
    max_output_tokens: int = 64,
    timeout_seconds: float = 3.0,
) -> CommentaryBooth:
    """Build the booth with the shipped frozen clock and explicit bounds."""
    if settings is None:
        settings = BoothSettings(model_id=TEST_MODEL_ID, language="en")
    return CommentaryBooth(
        model=model,
        events=events,
        settings=settings,
        clock=FrozenClock(T0),
        max_context_turns=max_context_turns,
        context_char_budget=context_char_budget,
        context_window_seconds=context_window_seconds,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )


async def spoken_order(booth: CommentaryBooth, *, hazard: str) -> tuple[Speaker, ...]:
    """Run a booth and return the emitted speakers, under the harness bound."""
    result = await bounded(booth.run(), hazard=hazard)
    return tuple(turn.speaker for turn in result.transcript.turns)


# --- Personas -----------------------------------------------------------------


def test_the_two_personas_are_distinct_seats_with_distinct_registers() -> None:
    assert LEAD_PERSONA.seat is Speaker.lead
    assert COLOR_PERSONA.seat is Speaker.color
    assert LEAD_PERSONA.name != COLOR_PERSONA.name
    assert LEAD_PERSONA.register_instruction.strip()
    assert COLOR_PERSONA.register_instruction.strip()
    assert LEAD_PERSONA.register_instruction != COLOR_PERSONA.register_instruction
    assert isinstance(LEAD_PERSONA, Persona)


@pytest.mark.anyio
async def test_each_seat_prompt_carries_only_its_own_persona() -> None:
    events = [detected(index=0), detected(index=1)]
    model = ScriptedModelClient(answered(events, ["Lead line.", "Colour line."]))
    booth = make_booth(events, model)

    result = await bounded(booth.run(), hazard="the two-seat persona run")

    assert [turn.speaker for turn in result.transcript.turns] == [Speaker.lead, Speaker.color]
    assert LEAD_PERSONA.name in model.requests[0].prompt
    assert LEAD_PERSONA.register_instruction in model.requests[0].prompt
    assert COLOR_PERSONA.register_instruction not in model.requests[0].prompt
    assert COLOR_PERSONA.name in model.requests[1].prompt
    assert COLOR_PERSONA.register_instruction in model.requests[1].prompt
    assert LEAD_PERSONA.register_instruction not in model.requests[1].prompt


# --- Turn order and the priority band -----------------------------------------


def test_the_priority_band_is_exactly_flags_and_incidents() -> None:
    for member in (EventType.FLAG, EventType.SAFETY_CAR, EventType.VIRTUAL_SAFETY_CAR):
        assert member in PRIORITY_EVENT_TYPES
    assert len(PRIORITY_EVENT_TYPES) == 3


@pytest.mark.anyio
async def test_turn_order_is_lead_first_then_strict_alternation() -> None:
    events = [detected(index=index) for index in range(4)]
    model = ScriptedModelClient(answered(events, ["L0.", "L1.", "L2.", "L3."]))
    booth = make_booth(events, model)

    result = await bounded(booth.run(), hazard="the four-event alternation run")

    assert [turn.speaker for turn in result.transcript.turns] == [
        Speaker.lead,
        Speaker.color,
        Speaker.lead,
        Speaker.color,
    ]
    assert [outcome.kind for outcome in result.outcomes] == [OutcomeKind.TURN] * 4
    assert all(outcome.event_type is EventType.POSITION_CHANGE for outcome in result.outcomes)


@pytest.mark.parametrize(
    "priority_type",
    [EventType.FLAG, EventType.SAFETY_CAR, EventType.VIRTUAL_SAFETY_CAR],
)
@pytest.mark.anyio
async def test_a_priority_event_lets_the_lead_take_the_next_slot(
    priority_type: EventType,
) -> None:
    first = detected(index=0)
    incident = detected(
        index=1,
        event_type=priority_type,
        family="race_control",
        evidence={"flag": "YELLOW"},
    )
    third = detected(index=2)
    events = [first, incident, third]
    model = ScriptedModelClient(answered(events, ["L0.", "L1.", "L2."]))
    booth = make_booth(events, model)

    order = await spoken_order(booth, hazard=f"the priority-band run for {priority_type.value}")

    # Plain alternation would give lead/colour/lead here; the incident pulls the lead in.
    assert order == (Speaker.lead, Speaker.lead, Speaker.color)


# --- Bounded context -----------------------------------------------------------


@pytest.mark.anyio
async def test_the_bounded_window_keeps_the_previous_turn_and_drops_older_ones_whole() -> None:
    events = [detected(index=index) for index in range(4)]
    texts = ["turn zero text", "turn one text", "turn two text", "turn three text"]
    model = ScriptedModelClient(answered(events, texts))
    booth = make_booth(events, model, max_context_turns=2)

    await bounded(booth.run(), hazard="the bounded-window run")

    prompt = model.requests[3].prompt
    assert texts[2] in prompt  # the immediately previous turn is always included
    assert texts[1] in prompt  # one older turn fits inside a window of two
    assert texts[0] not in prompt  # the third-oldest is dropped whole, not truncated


@pytest.mark.anyio
async def test_a_window_of_one_still_keeps_the_immediately_previous_turn() -> None:
    events = [detected(index=index) for index in range(3)]
    texts = ["turn zero text", "turn one text", "turn two text"]
    model = ScriptedModelClient(answered(events, texts))
    booth = make_booth(events, model, max_context_turns=1)

    await bounded(booth.run(), hazard="the single-slot context run")

    prompt = model.requests[2].prompt
    assert texts[1] in prompt
    assert texts[0] not in prompt


@pytest.mark.anyio
async def test_the_character_budget_drops_older_turns_whole_and_keeps_the_previous() -> None:
    events = [detected(index=index) for index in range(3)]
    long_turn = "L" * 200
    brief_turn = "B" * 10
    model = ScriptedModelClient(
        answered(events, [long_turn, brief_turn, "third turn text"])
    )
    booth = make_booth(events, model, max_context_turns=10, context_char_budget=50)

    await bounded(booth.run(), hazard="the character-budget run")

    prompt = model.requests[2].prompt
    assert brief_turn in prompt  # the previous turn always fits
    assert long_turn not in prompt  # over budget is dropped whole, never truncated


@pytest.mark.anyio
async def test_the_previous_turn_is_included_even_when_it_exceeds_the_budget() -> None:
    events = [detected(index=index) for index in range(2)]
    long_turn = "L" * 200
    model = ScriptedModelClient(answered(events, [long_turn, "second turn text"]))
    booth = make_booth(events, model, context_char_budget=5)

    await bounded(booth.run(), hazard="the over-budget previous-turn run")

    assert long_turn in model.requests[1].prompt


# --- Evidence-only sourcing ----------------------------------------------------


@pytest.mark.anyio
async def test_evidence_propagates_only_the_cited_references_of_the_supplied_event() -> None:
    event = detected(index=2, evidence={"position": 3, "status": "TRACK"})
    model = ScriptedModelClient(
        [spoken("position[2].status, position[2].position", "Verstappen is P3 on track.")]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the evidence-propagation run")

    (turn,) = result.transcript.turns
    assert turn.evidence == ("position[2].status", "position[2].position")
    assert turn.event_ref == event_reference(event) == "position[2]"
    assert all(reference.startswith(event_reference(event)) for reference in turn.evidence)
    assert turn.model_id == TEST_MODEL_ID
    assert turn.text == "Verstappen is P3 on track."


@pytest.mark.anyio
async def test_the_prompt_offers_exactly_the_supplied_references() -> None:
    event = detected(index=7, evidence={"position": 3})
    model = ScriptedModelClient([spoken(ref(event), "Verstappen is P3.")])
    booth = make_booth([event], model)

    await bounded(booth.run(), hazard="the prompt-reference run")

    prompt = model.requests[0].prompt
    assert "position[7].position = 3" in prompt
    assert set(REFERENCE_TOKEN.findall(prompt)) == {"position[7].position"}


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Verstappen is P3.", BoothReason.UNCITED),
        ("EVIDENCE:\nVerstappen is P3.", BoothReason.UNCITED),
        ("EVIDENCE: position[99].position\nVerstappen is P3.", BoothReason.INVENTED_REFERENCE),
        ("EVIDENCE: position[0].position\n   ", BoothReason.BLANK_TEXT),
    ],
)
@pytest.mark.anyio
async def test_an_answer_without_a_supplied_citation_is_refused(
    text: str, reason: BoothReason
) -> None:
    event = detected(index=0)
    model = ScriptedModelClient(
        [ModelResponse(model_id=TEST_MODEL_ID, text=text, input_tokens=1, output_tokens=1)]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the refused-answer run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is reason
    assert outcome.speaker is Speaker.lead


def test_the_protocol_violation_reason_is_typed_and_distinguishable() -> None:
    """The new reason names the violation, not the symptom, and stands apart from its peers."""
    assert BoothReason.MULTIPLE_CITATION_LINES.value == "multiple_citation_lines"
    assert BoothReason.MULTIPLE_CITATION_LINES not in {
        BoothReason.UNCITED,
        BoothReason.INVENTED_REFERENCE,
        BoothReason.BLANK_TEXT,
        BoothReason.NO_CITABLE_EVIDENCE,
        BoothReason.OUTSIDE_CONTEXT_WINDOW,
        BoothReason.REPEATS_PREVIOUS_TURN,
    }


@pytest.mark.anyio
async def test_a_second_citation_line_refuses_the_exact_defect_input() -> None:
    """The registered C1 input: a never-supplied reference on a second citation line.

    Before the correction these bytes aired a turn whose ``evidence`` was only the first
    citation and whose ``text`` carried ``position[99].invented`` verbatim. The turn must
    not exist at all, so its partially validated evidence tuple is never produced either.
    """
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=(
                    "EVIDENCE: position[0].position\n"
                    "EVIDENCE: position[99].invented\n"
                    "Verstappen is P3 on track."
                ),
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the second-citation-line defect run")

    # Never aired, so the partial evidence tuple of the refused answer is not produced.
    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.MULTIPLE_CITATION_LINES
    # Distinguishable from its neighbours: this is neither an uncited nor an invented citation.
    assert outcome.reason is not BoothReason.UNCITED
    assert outcome.reason is not BoothReason.INVENTED_REFERENCE
    assert outcome.speaker is Speaker.lead


@pytest.mark.parametrize(
    "second_line",
    [
        "EVIDENCE: position[0].position",
        "evidence: position[0].position",
        "   EVIDENCE: position[0].position",
    ],
)
@pytest.mark.anyio
async def test_any_later_line_that_opens_with_the_citation_marker_is_a_violation(
    second_line: str,
) -> None:
    """The violation check reads the marker exactly where the acceptance path reads it.

    The acceptance path matches the marker at the start of the stripped line and
    case-insensitively, so the violation check must match it the same way: a second line
    in lower case, or behind leading whitespace, is still a citation line. Refusing all
    three is what keeps the two checks from drifting apart.
    """
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=f"EVIDENCE: position[0].position\n{second_line}\nVerstappen is P3.",
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard=f"the marker-drift run for {second_line!r}")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.MULTIPLE_CITATION_LINES


@pytest.mark.parametrize(
    "text",
    [
        # An empty first citation does not soften the violation into UNCITED.
        "EVIDENCE:\nEVIDENCE: position[0].position\nVerstappen is P3 on track.",
        # Nothing but the two citation lines: the violation is not a BLANK_TEXT refusal
        # either, and the trailing whitespace never counts as commentary.
        "EVIDENCE: position[0].position\nEVIDENCE: position[0].position\n   ",
    ],
)
@pytest.mark.anyio
async def test_the_protocol_violation_is_decided_before_the_citation_content(text: str) -> None:
    """Shape before content: two citation-marked lines are a violation whatever they cite."""
    event = detected(index=0)
    model = ScriptedModelClient(
        [ModelResponse(model_id=TEST_MODEL_ID, text=text, input_tokens=1, output_tokens=1)]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the shape-before-content run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.MULTIPLE_CITATION_LINES
    assert outcome.reason is not BoothReason.UNCITED
    assert outcome.reason is not BoothReason.BLANK_TEXT


@pytest.mark.anyio
async def test_a_second_citation_line_is_refused_even_when_its_reference_was_supplied() -> None:
    """A supplied reference on a second citation line is refused, never merged in.

    Merging was the rejected alternative: the extra line is a protocol violation whether
    or not the reference it names was supplied, so the answer is not accepted as two
    citations even though both references exist in the event.
    """
    event = detected(index=0, evidence={"position": 3, "status": "TRACK"})
    assert evidence_references(event) == ("position[0].position", "position[0].status")
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=(
                    "EVIDENCE: position[0].position\n"
                    "EVIDENCE: position[0].status\n"
                    "Verstappen is P3 on track."
                ),
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the supplied-second-citation refusal run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.MULTIPLE_CITATION_LINES


@pytest.mark.anyio
async def test_commentary_that_merely_mentions_the_marker_mid_sentence_still_airs() -> None:
    """The over-refusal boundary: only a line *opening* with the marker is a violation."""
    event = detected(index=0)
    text = "Verstappen is P3 on track; the EVIDENCE: board confirms it."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the mid-sentence-marker run")

    (turn,) = result.transcript.turns
    assert turn.text == text
    assert turn.evidence == ("position[0].position",)
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    assert outcome.reason is None


@pytest.mark.anyio
async def test_the_prompt_teaches_the_same_marker_the_parser_accepts() -> None:
    """The prompt and the parser read one marker, so the taught format cannot drift.

    The marker is taken from the module rather than pasted into this file, so a future
    change to the constant changes both what the prompt says and what the parser accepts;
    this test fails if the prompt ever goes back to carrying its own literal. The same run
    proves the acceptance direction, because the answer is built from that same marker.

    The prompt has two independent sites that name the marker -- the rule line and the
    reference-section header -- so the check counts occurrences rather than testing
    membership: a membership check stays green while one site drifts back to a literal,
    which is the partial drift that left the prompt teaching two markers silently.
    """
    marker = f1show.booth._CITATION_MARKER
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=f"{marker} {ref(event)}\nVerstappen is P3 on track.",
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the prompt-marker agreement run")

    prompt = model.requests[0].prompt
    # Both sites -- the rule line and the reference-section header -- must interpolate the
    # parser's marker, so a literal reintroduced at either one alone is caught.
    assert prompt.count(marker) == 2, (
        "the assembled prompt must interpolate the parser's marker at both sites (the rule "
        "line and the reference-section header); a literal at either site leaves the model "
        f"two different markers. Counted {prompt.count(marker)} occurrences of {marker!r} "
        f"in:\n{prompt}"
    )
    assert f"- Start your answer with the citation line, exactly: {marker} " in prompt, (
        "the rule line must interpolate the parser's marker rather than carry its own literal"
    )
    assert f"\n{marker}\n" in prompt, (
        "the reference-section header must interpolate the parser's marker rather than "
        "carry its own literal"
    )
    (turn,) = result.transcript.turns
    assert turn.evidence == (ref(event),)


@pytest.mark.anyio
async def test_an_answer_built_with_a_different_marker_is_refused() -> None:
    """The opposite direction: the parser accepts only the marker the prompt teaches.

    The drifted marker is asserted to differ from the module's own, so the refusal below
    is genuinely about a different marker and not about some other parse failure.
    """
    marker = f1show.booth._CITATION_MARKER
    drifted_marker = "SOURCE:"
    assert drifted_marker != marker
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=f"{drifted_marker} {ref(event)}\nVerstappen is P3 on track.",
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the drifted-marker refusal run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNCITED


def test_the_documented_protocol_names_the_marker_the_parser_uses() -> None:
    """The module docstring states the same marker the code pins, so a bare rename shows.

    A constant change that leaves the documented answer protocol behind is exactly the
    drift C2 closed; reading the marker from the module and checking it against the
    module's own docstring makes "keep the docstring honest" a suite-enforced check.
    """
    marker = f1show.booth._CITATION_MARKER
    docstring = f1show.booth.__doc__ or ""
    assert marker in docstring


@pytest.mark.anyio
async def test_a_single_citation_line_still_airs_normally() -> None:
    """The happy path the correction must not break."""
    event = detected(index=0)
    model = ScriptedModelClient([spoken(ref(event), "Verstappen is P3 on track.")])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the single-citation happy-path run")

    (turn,) = result.transcript.turns
    assert turn.text == "Verstappen is P3 on track."
    assert turn.evidence == ("position[0].position",)
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    assert outcome.reason is None


@pytest.mark.anyio
async def test_a_supplied_reference_that_is_not_cited_is_never_attributed() -> None:
    event = detected(index=0, evidence={"position": 3, "status": "TRACK"})
    model = ScriptedModelClient([spoken("position[0].position", "Verstappen is P3.")])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the partial-citation run")

    (turn,) = result.transcript.turns
    assert turn.evidence == ("position[0].position",)


# --- The residual citation channels (F09b) --------------------------------------

#: A never-supplied reference in the collector's own ``<family>[<index>].<field>`` form.
#: It is the exact token every channel below tries to smuggle into the aired text.
NEVER_SUPPLIED = "position[99].invented"

#: Unicode format characters (category Cf) a fabricated reference can hide behind. The
#: scanner's normalized view drops them, so the token is read as if it were not obfuscated.
ZERO_WIDTH_SPACE = "\u200b"

#: A whitespace character that is not the ASCII space. The scanner's view makes it a space.
NON_BREAKING_SPACE = "\u00a0"


@pytest.mark.anyio
async def test_a_bullet_prefixed_citation_line_carrying_a_never_supplied_reference_is_a_violation() -> None:
    """Channel 1: a bullet-prefixed marker line is a citation attempt, not commentary.

    Before F09b these bytes aired a turn whose commentary carried the never-supplied
    ``position[99].invented`` verbatim, because the violation check matched the marker only
    at the very start of the stripped line.
    """
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=(
                    "EVIDENCE: position[0].position\n"
                    f"- EVIDENCE: {NEVER_SUPPLIED}\n"
                    "Verstappen is P3 on track."
                ),
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the bullet-prefixed citation-line run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.MULTIPLE_CITATION_LINES


@pytest.mark.anyio
async def test_a_citation_line_with_a_space_before_the_colon_and_a_never_supplied_reference_is_a_violation() -> None:
    """Channel 2: ``EVIDENCE :`` with a space before the colon is still a citation attempt.

    Before F09b the space made the line invisible to both checks, so it aired as
    commentary and carried the never-supplied reference through.
    """
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=(
                    "EVIDENCE: position[0].position\n"
                    f"EVIDENCE : {NEVER_SUPPLIED}\n"
                    "Verstappen is P3 on track."
                ),
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the spaced-colon citation-line run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.MULTIPLE_CITATION_LINES


@pytest.mark.anyio
async def test_a_never_supplied_reference_inside_the_commentary_refuses_the_turn() -> None:
    """Channel 3: a reference-shaped token mid-line, with no citation line of its own.

    Before F09b this aired: the token was neither a second citation line nor a
    citation-line entry, so no check ever saw it.
    """
    event = detected(index=0)
    text = f"Verstappen is P3 on track, per {NEVER_SUPPLIED}."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the mid-line reference escape run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_a_bare_never_supplied_reference_with_no_marker_refuses_the_turn() -> None:
    """Channel 4: a bare reference token with no marker at all, as the whole commentary.

    Before F09b this aired with the never-supplied reference as the entire turn text.
    """
    event = detected(index=0)
    model = ScriptedModelClient([spoken(ref(event), NEVER_SUPPLIED)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the bare-reference escape run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_a_supplied_reference_named_in_the_commentary_is_never_flagged() -> None:
    """The other side of the content rule: a token that *was* supplied still airs."""
    event = detected(index=0, evidence={"position": 3, "status": "TRACK"})
    text = "Verstappen is P3 on track; position[0].status reads TRACK."
    model = ScriptedModelClient([spoken("position[0].position", text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the supplied-reference-in-commentary run")

    (turn,) = result.transcript.turns
    assert turn.text == text
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    assert outcome.reason is None


@pytest.mark.anyio
async def test_the_scanned_reference_shape_is_derived_from_the_supplied_references() -> None:
    """The scanner is structural, not keyed to one family or to the supplied fields.

    The event supplies only ``laps[4].lap_number``, so a rule built from the supplied
    names would miss ``pit[9].duration``; the derived shape catches it.
    """
    event = detected(
        index=4,
        event_type=EventType.LAP_COMPLETED,
        family="laps",
        evidence={"lap_number": 12},
    )
    assert evidence_references(event) == ("laps[4].lap_number",)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=(
                    "EVIDENCE: laps[4].lap_number\n"
                    "Lap 12 done; pit[9].duration was 2.4s."
                ),
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the derived-reference-shape run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.parametrize("continuation", ["[99].evil", "[99]", "[99"])
@pytest.mark.anyio
async def test_a_fragment_glued_to_a_supplied_reference_refuses_the_turn(
    continuation: str,
) -> None:
    """Adjacency: a bracket glued directly onto a matched reference is a fragment.

    A ``.`` no longer counts here: a dotted suffix is prose, not a fabricated citation, so
    only the bracket continuation refuses. These are the bytes where ``finditer`` consumed
    ``position[0].position`` and left ``[99]...`` unable to start a new match, so the
    fragment rode into the transcript glued to a supplied reference.
    """
    event = detected(index=0)
    text = f"Verstappen is P3, per {ref(event)}{continuation}."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard=f"the adjacency-fragment run for {continuation!r}")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_a_fabricated_non_numeric_index_refuses_the_turn() -> None:
    """The index window: any non-empty bracket content is read as the index.

    Before this follow-up the scanner required digits between the brackets, so
    ``position[x].invented`` -- a citation attempt a reader cannot tell from a real one --
    aired inside the turn text.
    """
    event = detected(index=0)
    text = "Verstappen is P3, per position[x].invented"
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the non-numeric-index run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_the_unbracketed_residual_still_airs_as_a_declared_boundary() -> None:
    """The kept boundary: ``position99.invented`` is not refused, and that is deliberate.

    The scanner derives its shape from the supplied references, which always carry a
    bracketed index, so an unbracketed ``word<digits>.word`` is not read as a citation.
    Matching it would widen refusal with unmeasured false positives in ordinary prose. If
    the collector's reference grammar ever changes to that shape, this pin fails and the
    boundary has to be revisited -- which is the trigger, not an accident.
    """
    event = detected(index=0)
    text = "Verstappen is P3, per position99.invented."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the declared-boundary run")

    (turn,) = result.transcript.turns
    assert turn.text == text
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    assert outcome.reason is None


@pytest.mark.anyio
async def test_a_sentence_final_period_after_a_supplied_reference_still_airs() -> None:
    """Narrowing the dot continuation: a sentence-final period is ordinary prose.

    A ``.`` immediately after a matched reference counts as a malformed fragment only when
    it begins more dotted text. Under the earlier literal rule this exact case -- a correct
    answer, since sentences end with periods -- was refused, which is most answers.
    """
    event = detected(index=0)
    text = f"Verstappen is P3, per {ref(event)}."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the sentence-final-period run")

    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    assert outcome.reason is None
    (turn,) = result.transcript.turns
    assert turn.text == text


@pytest.mark.parametrize("token", ["position[]", "position[].invented"])
@pytest.mark.anyio
async def test_an_empty_bracket_index_refuses_the_turn(token: str) -> None:
    """The empty-bracket shape is reference-shaped prose and is refused.

    The collector always writes an index and a field, so ``position[]`` on its own and
    ``position[].invented`` are fabricated forms. The index window is zero-width so both
    are scanned; this is the same declared fail-closed cost, not a new kind of cost.
    """
    event = detected(index=0)
    text = f"Verstappen is P3, per {token}."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard=f"the empty-bracket run for {token!r}")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_the_hyphenated_suffix_still_airs_as_a_declared_boundary() -> None:
    """The second recorded boundary: a hyphenated suffix leaves the supplied reference intact.

    ``position[0].position-evil`` is not refused: the supplied reference is whole and the
    suffix is neither an attached bracket nor a fabricated token. Recorded here and in the
    module docstring so the next reader does not have to rediscover the boundary.
    """
    event = detected(index=0)
    text = f"Verstappen is P3, per {ref(event)}-evil."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the hyphenated-suffix boundary run")

    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    (turn,) = result.transcript.turns
    assert turn.text == text


@pytest.mark.parametrize(
    "commentary",
    [
        "The gap was table [4] . The value stands.",
        "See item [12] . Next sentence follows.",
        "The array a [ i ] . length is three.",
    ],
)
@pytest.mark.anyio
async def test_spaced_bracket_prose_is_refused_as_the_declared_cost_of_joint_tolerance(
    commentary: str,
) -> None:
    """The declared cost of the joint-whitespace tolerance: spaced-bracket prose refuses.

    Whitespace is tolerated at the token's structural joints so that a fabricated citation
    separated by a plain space -- ``position [1].invented`` -- cannot air. The price, stated
    plainly as the trade it is: ordinary prose which happens to contain
    ``word [digits] . word`` is read as a spaced reference and refused. Refusing a spaced
    fabricated citation a model can plausibly emit is worth more than accepting this prose,
    which this project does not expect in commentary; the cost is pinned here rather than
    left as a sentence, and the good direction is pinned by
    ``test_a_supplied_reference_spaced_at_the_joints_still_airs``. The other declared
    boundaries -- a dotted suffix is prose, the unbracketed ``position99.invented`` shape is
    not produced by the collector's grammar, and a hyphenated suffix leaves the reference
    intact -- stay declared in the module docstring and their own pins.
    """
    event = detected(index=0)
    model = ScriptedModelClient([spoken(ref(event), commentary)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard=f"the declared-joint-cost run for {commentary!r}")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_a_supplied_reference_spaced_at_the_joints_still_airs() -> None:
    """The good direction of the tolerance: a real reference spaced at the joints airs.

    ``position [0] . position`` canonicalizes to the supplied ``position[0].position`` and
    the turn airs, so nobody can widen the scanner into refusing a legitimately spaced
    supplied reference without failing this pin.
    """
    event = detected(index=0)
    text = "Verstappen is P3, per position [0] . position."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the spaced-supplied-reference run")

    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    (turn,) = result.transcript.turns
    assert turn.text == text


@pytest.mark.parametrize("suffix", [".evil", ".The tyres are gone."])
@pytest.mark.anyio
async def test_a_dotted_suffix_after_a_supplied_reference_is_prose_and_airs(
    suffix: str,
) -> None:
    """A ``.`` after a clean reference is a sentence boundary, not a fabricated citation.

    Protecting against a dotted suffix is not worth refusing ``position[0].position.The``,
    which is exactly what a model writes under token pressure when it omits the space after
    a full stop. The supplied reference is intact, so the turn airs.
    """
    event = detected(index=0)
    text = f"Verstappen is P3, per {ref(event)}{suffix}"
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard=f"the dotted-suffix run for {suffix!r}")

    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.TURN
    (turn,) = result.transcript.turns
    assert turn.text == text


@pytest.mark.anyio
async def test_a_fabricated_reference_split_by_a_zero_width_space_refuses_the_turn() -> None:
    """A zero-width space must not hide a fabricated reference behind invisible bytes.

    ``position[0]`` + ZWSP + ``.invented`` airs with text visually identical to
    ``position[0].invented``; the scanner's normalized view drops the format character, so
    the fabricated token is seen and refused.
    """
    event = detected(index=0)
    text = f"Verstappen is P3, per position[0]{ZERO_WIDTH_SPACE}.invented."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the zero-width-space run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_a_fabricated_reference_split_by_a_non_breaking_space_refuses_the_turn() -> None:
    """A NBSP between the family and the bracket must not hide a fabricated reference.

    The scanner's view makes every whitespace character a plain space, and the token's
    structural joints tolerate it, so the split reference is recognised and refused.
    """
    event = detected(index=0)
    text = f"Verstappen is P3, per position{NON_BREAKING_SPACE}[1].invented."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the non-breaking-space run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.anyio
async def test_a_fabricated_reference_split_by_a_newline_refuses_the_turn() -> None:
    """A newline between the family and the bracket must not hide a fabricated reference."""
    event = detected(index=0)
    text = "Verstappen is P3, per position\n[1].invented."
    model = ScriptedModelClient([spoken(ref(event), text)])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the newline-split run")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT


@pytest.mark.parametrize(
    "first_line",
    [
        "EVIDENCE : position[0].position",
        "- EVIDENCE: position[0].position",
        "* evidence: position[0].position",
    ],
)
@pytest.mark.anyio
async def test_the_tolerant_violation_predicate_never_widens_acceptance(first_line: str) -> None:
    """Widening what is *refused* must not widen what is *accepted* as the citation line.

    The first line is accepted only in the exact shape the prompt teaches, so a tolerant
    spelling that is not that exact marker leaves the answer uncited, exactly as before.
    """
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=f"{first_line}\nVerstappen is P3.",
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard=f"the acceptance-not-widened run for {first_line!r}")

    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.REFUSED
    assert outcome.reason is BoothReason.UNCITED


@pytest.mark.anyio
async def test_duplicate_citations_are_collapsed_and_their_order_is_preserved() -> None:
    """A pin on the collapse ``dict.fromkeys`` already performs: order kept, repeats dropped."""
    event = detected(index=0, evidence={"position": 3, "status": "TRACK", "driver": "VER"})
    assert evidence_references(event) == (
        "position[0].position",
        "position[0].status",
        "position[0].driver",
    )
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text=(
                    "EVIDENCE: position[0].driver, position[0].position, "
                    "position[0].status, position[0].position\n"
                    "Verstappen is P3 on track."
                ),
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the duplicate-citation collapse run")

    (turn,) = result.transcript.turns
    assert turn.evidence == (
        "position[0].driver",
        "position[0].position",
        "position[0].status",
    )


@pytest.mark.anyio
async def test_an_empty_citation_item_is_dropped_and_the_turn_still_airs() -> None:
    """An empty item between commas is dropped, and the turn still airs.

    Dropping an empty string is tolerance, never an injection: an empty item carries no
    reference, so nothing unsupplied can ride in through it. The documented behaviour is
    that the comma-heavy line is still the one citation line the protocol asks for and the
    evidence tuple is exactly the non-empty references.
    """
    event = detected(index=0)
    model = ScriptedModelClient(
        [
            ModelResponse(
                model_id=TEST_MODEL_ID,
                text="EVIDENCE: position[0].position,,\nVerstappen is P3 on track.",
                input_tokens=1,
                output_tokens=1,
            )
        ]
    )
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the empty-citation-item run")

    (turn,) = result.transcript.turns
    assert turn.text == "Verstappen is P3 on track."
    assert turn.evidence == ("position[0].position",)


def test_the_unsupplied_reference_reason_is_typed_and_distinguishable() -> None:
    """The content rule's reason stands apart from the citation-line reasons."""
    assert BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT.value == "unsupplied_reference_in_text"
    assert BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT not in {
        BoothReason.UNCITED,
        BoothReason.INVENTED_REFERENCE,
        BoothReason.MULTIPLE_CITATION_LINES,
        BoothReason.BLANK_TEXT,
        BoothReason.NO_CITABLE_EVIDENCE,
        BoothReason.OUTSIDE_CONTEXT_WINDOW,
        BoothReason.REPEATS_PREVIOUS_TURN,
    }


# --- Repetition suppression and stale-context exclusion ------------------------


@pytest.mark.parametrize(
    "repeat",
    ["The same sentence.", "  the   SAME sentence.  "],
)
@pytest.mark.anyio
async def test_a_candidate_that_repeats_the_previous_turn_is_suppressed(repeat: str) -> None:
    events = [detected(index=0), detected(index=1)]
    model = ScriptedModelClient(
        answered(events, ["The same sentence.", repeat])
    )
    booth = make_booth(events, model)

    result = await bounded(booth.run(), hazard="the repetition-suppression run")

    assert [turn.text for turn in result.transcript.turns] == ["The same sentence."]
    assert [outcome.kind for outcome in result.outcomes] == [
        OutcomeKind.TURN,
        OutcomeKind.SUPPRESSED,
    ]
    assert result.outcomes[1].reason is BoothReason.REPEATS_PREVIOUS_TURN


@pytest.mark.anyio
async def test_a_refused_turn_does_not_shift_the_alternation() -> None:
    events = [detected(index=index) for index in range(3)]
    model = ScriptedModelClient(
        [
            spoken(ref(events[0]), "Lead opens."),
            ModelResponse(
                model_id=TEST_MODEL_ID, text="uncited.", input_tokens=1, output_tokens=1
            ),
            spoken(ref(events[2]), "Colour answers."),
        ]
    )
    booth = make_booth(events, model)

    result = await bounded(booth.run(), hazard="the drop-does-not-shift run")

    # The colour slot was refused, so the third event still belongs to the colour seat.
    assert [turn.speaker for turn in result.transcript.turns] == [Speaker.lead, Speaker.color]
    assert [outcome.kind for outcome in result.outcomes] == [
        OutcomeKind.TURN,
        OutcomeKind.REFUSED,
        OutcomeKind.TURN,
    ]


@pytest.mark.anyio
async def test_a_suppressed_turn_does_not_shift_the_alternation() -> None:
    events = [detected(index=index) for index in range(3)]
    model = ScriptedModelClient(
        answered(events, ["Same line.", "Same line.", "New colour line."])
    )
    booth = make_booth(events, model)

    result = await bounded(booth.run(), hazard="the suppression-shift run")

    assert [turn.speaker for turn in result.transcript.turns] == [Speaker.lead, Speaker.color]
    assert [outcome.kind for outcome in result.outcomes] == [
        OutcomeKind.TURN,
        OutcomeKind.SUPPRESSED,
        OutcomeKind.TURN,
    ]


@pytest.mark.anyio
async def test_a_complex_evidence_value_is_rendered_and_remains_citable() -> None:
    event = detected(
        index=4,
        event_type=EventType.LAP_COMPLETED,
        family="laps",
        evidence={"lap_number": 12, "segments_sector_1": [20480, 20481, 0]},
    )
    model = ScriptedModelClient([spoken("laps[4].segments_sector_1", "Sector one is clean.")])
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the complex-evidence run")

    assert "- laps[4].segments_sector_1 = [20480, 20481, 0]" in model.requests[0].prompt
    assert result.transcript.turns[0].evidence == ("laps[4].segments_sector_1",)


@pytest.mark.anyio
async def test_an_event_older_than_the_bounded_window_never_reaches_the_model() -> None:
    stale = detected(index=0, timestamp=T0)
    fresh = detected(index=1, timestamp=T1)
    model = ScriptedModelClient([spoken(ref(fresh), "Fresh move.")])
    booth = make_booth([stale, fresh], model, context_window_seconds=10.0)

    result = await bounded(booth.run(), hazard="the stale-context run")

    assert len(model.requests) == 1  # the stale event is never sent
    assert "position[0].position" not in model.requests[0].prompt
    assert result.outcomes[0].kind is OutcomeKind.EXCLUDED
    assert result.outcomes[0].reason is BoothReason.OUTSIDE_CONTEXT_WINDOW
    assert [turn.speaker for turn in result.transcript.turns] == [Speaker.lead]


@pytest.mark.parametrize(
    ("age", "reaches_the_model"),
    [
        (dt.timedelta(seconds=10), True),  # exactly on the boundary is inside it
        (dt.timedelta(seconds=10, microseconds=1), False),  # a hair older is stale
    ],
)
@pytest.mark.anyio
async def test_the_stale_boundary_is_fresh_and_anything_older_is_stale(
    age: dt.timedelta, reaches_the_model: bool
) -> None:
    edge = detected(index=0, timestamp=T1 - age)
    fresh = detected(index=1, timestamp=T1)
    model = ScriptedModelClient(answered([edge, fresh], ["Edge.", "Fresh."]))
    booth = make_booth([edge, fresh], model, context_window_seconds=10.0)

    await bounded(booth.run(), hazard="the stale-boundary run")

    assert len(model.requests) == (2 if reaches_the_model else 1)


@pytest.mark.anyio
async def test_an_event_with_no_known_instant_is_not_treated_as_stale() -> None:
    unknown = detected(
        index=0,
        event_type=EventType.STINT_START,
        family="stints",
        evidence={"stint_number": 1},
        timestamp=None,
    )
    fresh = detected(index=1, timestamp=T1)
    model = ScriptedModelClient(answered([unknown, fresh], ["Stint begins.", "Fresh move."]))
    booth = make_booth([unknown, fresh], model, context_window_seconds=10.0)

    result = await bounded(booth.run(), hazard="the unknown-instant run")

    assert len(model.requests) == 2
    assert [outcome.kind for outcome in result.outcomes] == [OutcomeKind.TURN, OutcomeKind.TURN]


@pytest.mark.anyio
async def test_an_event_with_no_citable_evidence_never_reaches_the_model() -> None:
    event = detected(index=0, evidence={"position": None})
    model = ScriptedModelClient()
    booth = make_booth([event], model)

    result = await bounded(booth.run(), hazard="the no-citable-evidence run")

    assert model.requests == []
    assert result.transcript.turns == ()
    (outcome,) = result.outcomes
    assert outcome.kind is OutcomeKind.EXCLUDED
    assert outcome.reason is BoothReason.NO_CITABLE_EVIDENCE


# --- Determinism and the F04 hard rules ---------------------------------------


@pytest.mark.anyio
async def test_the_same_input_produces_the_same_order_and_prompts_twice() -> None:
    events = [detected(index=index) for index in range(4)]
    texts = ["L0.", "L1.", "L2.", "L3."]

    first_model = ScriptedModelClient(answered(events, texts))
    second_model = ScriptedModelClient(answered(events, texts))
    first = await bounded(make_booth(events, first_model).run(), hazard="the first determinism run")
    second = await bounded(
        make_booth(events, second_model).run(), hazard="the second determinism run"
    )

    assert [turn.speaker for turn in first.transcript.turns] == [
        turn.speaker for turn in second.transcript.turns
    ]
    assert [turn.text for turn in first.transcript.turns] == [
        turn.text for turn in second.transcript.turns
    ]
    assert [request.prompt for request in first_model.requests] == [
        request.prompt for request in second_model.requests
    ]
    assert [outcome.kind for outcome in first.outcomes] == [
        outcome.kind for outcome in second.outcomes
    ]


@pytest.mark.anyio
async def test_the_prompt_carries_the_no_overtake_and_lap_one_prohibitions() -> None:
    event = detected(index=0)
    model = ScriptedModelClient([spoken(ref(event), "Verstappen is P3.")])
    booth = make_booth([event], model)

    await bounded(booth.run(), hazard="the F04-prohibition run")

    prompt = model.requests[0].prompt
    assert "no overtake event" in prompt.lower()
    assert "position change is never an on-track pass" in prompt.lower()
    assert "lap 1 is excluded from every time comparison" in prompt.lower()


# --- Neutral degradation -------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "failure_type"),
    [
        (ModelTimeoutError("the call timed out"), "ModelTimeoutError"),
        (ModelRateLimitedError("rate limited"), "ModelRateLimitedError"),
        (ModelServerError("provider failed", status_code=503), "ModelServerError"),
        (ModelTransportError("connection reset"), "ModelTransportError"),
        (ModelResponseError("no usable text"), "ModelResponseError"),
    ],
)
@pytest.mark.anyio
async def test_each_model_error_family_degrades_neutrally(
    error: ModelError, failure_type: str
) -> None:
    failed = detected(index=0)
    recovered = detected(index=1)
    model = ScriptedFailingModelClient([error, spoken(ref(recovered), "Back on air.")])
    booth = make_booth([failed, recovered], model)

    result = await bounded(booth.run(), hazard=f"the {failure_type} degradation run")

    assert [turn.text for turn in result.transcript.turns] == ["Back on air."]
    assert [outcome.kind for outcome in result.outcomes] == [
        OutcomeKind.DEGRADED,
        OutcomeKind.TURN,
    ]
    assert result.outcomes[0].failure_type == failure_type
    assert result.outcomes[0].reason is None
    # A degradation is a silent gap, never a filler turn or an invented source.
    assert all(turn.evidence for turn in result.transcript.turns)


# --- The request, and the result shape ----------------------------------------


@pytest.mark.anyio
async def test_the_model_request_is_built_from_settings_and_bounds() -> None:
    event = detected(index=0)
    model = ScriptedModelClient([spoken(ref(event), "Verstappen is P3.")])
    settings = BoothSettings(model_id=OTHER_MODEL_ID, language="es")
    booth = make_booth(
        [event], model, settings=settings, max_output_tokens=77, timeout_seconds=1.5
    )

    await bounded(booth.run(), hazard="the request-shape run")

    (request,) = model.requests
    assert isinstance(request, ModelRequest)
    assert request.model_id == OTHER_MODEL_ID
    assert request.model_id != TEST_MODEL_ID
    assert request.max_output_tokens == 77
    assert request.timeout_seconds == 1.5
    assert "Commentate the one event below in es." in request.prompt


@pytest.mark.anyio
async def test_the_result_is_an_ordered_transcript_for_the_configured_session() -> None:
    events = [detected(index=0), detected(index=1)]
    model = ScriptedModelClient(answered(events, ["L0.", "L1."]))
    booth = make_booth(events, model)

    result = await bounded(booth.run(), hazard="the result-shape run")

    assert isinstance(result, BoothResult)
    assert result.transcript.session_key == SESSION_KEY
    assert result.transcript.language == "en"
    assert all(isinstance(turn, Turn) for turn in result.transcript.turns)
    assert len(result.outcomes) == len(events)
    assert all(isinstance(outcome, BoothOutcome) for outcome in result.outcomes)


def test_the_booth_module_names_no_real_model_id_literal() -> None:
    assert BOOTH_SOURCE.name == "booth.py" and BOOTH_SOURCE.exists()
    source = BOOTH_SOURCE.read_text(encoding="utf-8").lower()
    for marker in ("gemini-", "gpt-", "claude", "llama"):
        assert marker not in source, f"booth.py must not name a real model ID like {marker!r}"


def test_booth_source_names_the_marker_only_through_the_constant() -> None:
    """The marker may appear in code only as the constant's own value.

    The runtime prompt pin counts two interpolated sites, but a marker spelled as a fresh
    string literal *inside* a code path is invisible to every runtime check that reads the
    constant. This scans the module's string literals, excluding the constant's own value
    and docstrings -- documentation, which the docstring test separately pins to name the
    marker -- so reintroducing a literal in the prompt or the parser fails here.
    """
    marker = f1show.booth._CITATION_MARKER
    stem = marker.removesuffix(":")
    literal = re.compile(rf"{re.escape(stem)}\s*:", re.IGNORECASE)
    tree = ast.parse(BOOTH_SOURCE.read_text(encoding="utf-8"))

    docstrings: set[int] = set()
    constant_values: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_CITATION_MARKER":
                    constant_values.add(id(node.value))

    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and id(node) not in constant_values
        and literal.search(node.value)
    ]
    assert offenders == [], (
        "booth.py may name the citation marker only through _CITATION_MARKER; these "
        f"literals reintroduce it: {offenders!r}"
    )


#: The names this unit contributes to the package root. The list is deliberately narrow:
#: a sweep over every ``f1show.__all__`` entry would fail today on ``SnapshotResult``,
#: which is another unit's surface and its own tracked defect, not F09's.
F09_EXPORTED_NAMES = (
    "CommentaryBooth",
    "Persona",
    "LEAD_PERSONA",
    "COLOR_PERSONA",
    "BoothOutcome",
    "BoothResult",
    "OutcomeKind",
    "BoothReason",
)


def test_every_f09_name_is_exported_and_resolvable_from_the_package_root() -> None:
    """Each F09 name is both in ``f1show.__all__`` and importable from the package root.

    A root export that is listed but never imported stays invisible until someone runs
    ``from f1show import <name>`` and hits an ``ImportError`` in production, which is a
    defect this project has already shipped once with ``SnapshotResult``. The scope here
    is exactly this unit's eight names on purpose: a sweep over all of ``f1show.__all__``
    would fail today on ``SnapshotResult``, which belongs to another unit and is that
    unit's own tracked defect, not F09's surface to fix.

    The expected set is *derived* rather than trusted: every name ``f1show.booth``
    declares public under its own ``__all__`` and the package root also exports is exactly
    this unit's surface. A loop over ``F09_EXPORTED_NAMES`` alone stays green when a name
    is deleted from the list, so the equality against that derived set is what makes the
    pin fail on a shrink.
    """
    if not F09_EXPORTED_NAMES:
        pytest.fail(
            "F09_EXPORTED_NAMES must carry names for this sweep to check; an empty list "
            "makes this test pass with zero assertions"
        )
    if len(set(F09_EXPORTED_NAMES)) != len(F09_EXPORTED_NAMES):
        pytest.fail(f"F09_EXPORTED_NAMES carries duplicates: {F09_EXPORTED_NAMES}")
    derived = set(f1show.booth.__all__) & set(f1show.__all__)
    assert set(F09_EXPORTED_NAMES) == derived, (
        "F09_EXPORTED_NAMES must be exactly every booth public name the package root "
        f"exports; missing {sorted(derived - set(F09_EXPORTED_NAMES))}, extra "
        f"{sorted(set(F09_EXPORTED_NAMES) - derived)}"
    )
    for name in F09_EXPORTED_NAMES:
        assert name in f1show.__all__, f"{name} is missing from f1show.__all__"
        assert getattr(f1show, name) is not None, f"{name} is not resolvable from f1show"


# --- Construction guardrails ---------------------------------------------------


def test_an_empty_event_sequence_is_refused() -> None:
    with pytest.raises(ValueError):
        make_booth([], ScriptedModelClient())


def test_events_from_more_than_one_session_are_refused() -> None:
    mixed = [detected(index=0), detected(index=1, session_key=SESSION_KEY + 1)]
    with pytest.raises(ValueError):
        make_booth(mixed, ScriptedModelClient())


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("max_context_turns", 0),
        ("max_context_turns", -1),
        ("context_char_budget", -1),
        ("context_window_seconds", 0.0),
        ("context_window_seconds", -5.0),
        ("max_output_tokens", 0),
        ("timeout_seconds", 0.0),
        ("timeout_seconds", -1.0),
    ],
)
def test_every_bound_must_be_in_range(keyword: str, value: float) -> None:
    event = detected(index=0)
    arguments: dict[str, Any] = {
        "model": ScriptedModelClient(),
        "events": [event],
        "settings": BoothSettings(model_id=TEST_MODEL_ID, language="en"),
        "clock": FrozenClock(T0),
        "max_context_turns": 4,
        "context_char_budget": 400,
        "context_window_seconds": 3600.0,
        "max_output_tokens": 64,
        "timeout_seconds": 3.0,
    }
    arguments[keyword] = value
    with pytest.raises((ValueError, TypeError)):
        CommentaryBooth(**arguments)
