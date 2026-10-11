"""The two-person commentary booth: personas, explicit turns, evidence-only sourcing (F09).

This module **composes, it does not transport**. It is handed the collaborators it needs
at construction - a ``ModelClient``, the ordered ``DetectedEvent`` sequence the F04
collector produced, ``BoothSettings`` for the model ID and the language, a ``Clock`` for
the turn stamps and the bounds below - and it never constructs an HTTP client, reads a
credential or names a model ID. Wiring those collaborators together is F10's job. The one
import from the F08 gateway is the typed ``ModelError`` taxonomy this module must handle;
no gateway adapter or policy class is imported or built here.

**Deterministic order.** The lead opens, then the seats alternate strictly. A priority
band - ``FLAG``, ``SAFETY_CAR`` and ``VIRTUAL_SAFETY_CAR``, the flags and incidents -
lets the lead take the next slot instead of waiting its turn. The choice is a function of
the events alone: there is no random source and the clock never chooses a speaker, so the
same input always produces the same order. A non-priority event's seat follows the last
turn that actually aired, so a refused, degraded or suppressed turn never shifts the
alternation; a priority event is the single exception that lets the lead speak twice in a
row.

**Bounded context.** The prompt carries the current event plus at most ``max_context_turns``
prior turns under a ``context_char_budget`` over their text. The immediately previous turn
is always included; anything older is dropped *whole*, never truncated mid-turn. An event
whose instant is older than ``context_window_seconds`` behind the newest supplied instant
is stale and never reaches the model at all. An event with no known instant (the collector
emits ``stint_start`` with no timestamp field by design) is not invented into one and is
never treated as stale.

**Evidence-only sourcing, structurally enforced.** Each event exposes a stable identity and
one reference per recorded, non-null evidence field. The prompt lists exactly those
references; the answer protocol requires a first line of
``EVIDENCE: <reference>[, <reference>...]`` and requires it to be the **only** line that
opens with the citation marker. That marker is defined once, and the assembled prompt
interpolates it from the same definition the parser accepts, so the format the model is
taught and the format that is checked come from one source and cannot drift apart. An
answer that cites nothing, cites a reference that was
never supplied, leaves no commentary after the citation, or carries a further
citation-marked line - a protocol violation, refused with its own
``BoothReason.MULTIPLE_CITATION_LINES`` rather than aired with just its first citation
validated - is **refused** with a typed outcome instead of becoming a turn with a guessed
or partially checked source. Every emitted ``Turn`` therefore carries a non-empty
``evidence`` tuple drawn from that one event's own references.

**Neutral degradation.** Any ``ModelError`` - timeout, rate limit, server, transport, a
malformed or refused answer - emits no turn and records a typed degradation outcome. There
is no filler, no apology and no fabricated attribution: the transcript simply shows fewer
turns.

**Two F04 hard rules, and the honest limit of offline proof.** There is no overtake event,
so a position change must never become a description of an on-track pass; and lap 1 is
excluded from every time comparison, so no fastest-lap or gap claim may be anchored on it.
The *structural* half is enforced and tested here: the assembled prompt carries both
prohibitions and every emitted turn's evidence cites only the supplied event. The
*semantic* half - that the provider's generated prose never in fact invents a pass or
anchors a claim on lap 1 - is a property of the model's output and is **not provable
offline**; it belongs to the separately authorized live trial that F13 owns.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from f1show.collector import DetectedEvent
from f1show.config import BoothSettings
from f1show.dialogue import Speaker, Transcript, Turn
from f1show.events import EventType
from f1show.gemini import ModelError
from f1show.ports import Clock, ModelClient, ModelRequest

__all__ = [
    "COLOR_PERSONA",
    "LEAD_PERSONA",
    "PRIORITY_EVENT_TYPES",
    "BoothOutcome",
    "BoothReason",
    "BoothResult",
    "CommentaryBooth",
    "OutcomeKind",
    "Persona",
    "event_reference",
    "evidence_references",
]

#: The priority band: a flag or an incident is a break in the running order, so the lead
#: takes the next slot rather than waiting for its own. It is exactly these three event
#: types and no more.
PRIORITY_EVENT_TYPES: frozenset[EventType] = frozenset(
    {EventType.FLAG, EventType.SAFETY_CAR, EventType.VIRTUAL_SAFETY_CAR}
)


class _Record(BaseModel):
    """Internal contract: strict and frozen, like every other record in this project."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Persona(_Record):
    """One booth seat as data: its seat, its display name and its register.

    The register instruction is what differentiates the two seats - the lead reports what
    happened, the colour adds the reading of it - and it is carried into the prompt for
    the seat that is speaking. That it is actually *used*, and not merely claimed in a
    docstring, is asserted by test.
    """

    seat: Speaker
    name: str
    register_instruction: str

    @field_validator("name", "register_instruction")
    @classmethod
    def _strip_non_blank(cls, value: str, info: ValidationInfo) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{info.field_name} must not be blank")
        return stripped


#: The two shipped personas. Fictional names; no real commentator, model or credential is
#: named anywhere in this module.
LEAD_PERSONA = Persona(
    seat=Speaker.lead,
    name="Alex Moreau",
    register_instruction=(
        "You are the lead commentator. State plainly and factually what just happened: "
        "the driver, the position, the lap or the stop, taken from the evidence. Short "
        "broadcast sentences. No speculation about causes and no tactical reading."
    ),
)
COLOR_PERSONA = Persona(
    seat=Speaker.color,
    name="Sam Ellis",
    register_instruction=(
        "You are the colour commentator. Add the tactical or technical reading of what "
        "the lead just reported, using only the evidence given: tyre age, compound, the "
        "lap or the duration. Never restate the lead's sentence and never invent a cause "
        "the evidence does not carry."
    ),
)

_PERSONAS: dict[Speaker, Persona] = {
    Speaker.lead: LEAD_PERSONA,
    Speaker.color: COLOR_PERSONA,
}


class OutcomeKind(str, Enum):
    """What the booth did with one event."""

    TURN = "turn"
    REFUSED = "refused"
    DEGRADED = "degraded"
    SUPPRESSED = "suppressed"
    EXCLUDED = "excluded"


class BoothReason(str, Enum):
    """Why an event produced no turn, when it was not a model failure.

    ``MULTIPLE_CITATION_LINES`` names the protocol violation itself, not its symptom: the
    answer opened more than one line with the citation marker, so the whole answer is
    refused and is never aired with only its first citation validated.
    """

    OUTSIDE_CONTEXT_WINDOW = "outside_context_window"
    NO_CITABLE_EVIDENCE = "no_citable_evidence"
    UNCITED = "uncited"
    INVENTED_REFERENCE = "invented_reference"
    MULTIPLE_CITATION_LINES = "multiple_citation_lines"
    BLANK_TEXT = "blank_text"
    REPEATS_PREVIOUS_TURN = "repeats_previous_turn"


class BoothOutcome(_Record):
    """One typed, observable disposition of one event, in event order.

    A turn records ``kind=TURN``. A model failure records ``kind=DEGRADED`` with the
    failure's class name in ``failure_type``; every other non-turn disposition records its
    ``reason``. Nothing here carries a source that does not exist.
    """

    kind: OutcomeKind
    event_ref: str
    event_type: EventType
    speaker: Speaker | None = None
    failure_type: str | None = None
    reason: BoothReason | None = None


class BoothResult(_Record):
    """An ordered session transcript plus one outcome per supplied event.

    ``transcript`` holds only the turns that were actually emitted, so its length is the
    honest count of what went to air; ``outcomes`` stays one-per-event so every refusal,
    degradation, suppression and exclusion stays observable.
    """

    transcript: Transcript
    outcomes: tuple[BoothOutcome, ...]


def event_reference(event: DetectedEvent) -> str:
    """The stable identity of one event within its session: ``family[record_index]``.

    ``record_index`` is unique inside a family, so this cannot collide inside one booth
    run, and it is derived only from the event's own recorded location.
    """
    return f"{event.family}[{event.record_index}]"


def _citable_evidence(event: DetectedEvent) -> tuple[tuple[str, object], ...]:
    """The event's own recorded references, paired with their values.

    A field the record carries as an explicit ``None`` is *unknown*, not evidence, so it
    is not offered as a citable reference; the collector already states why it is absent.
    """
    reference = event_reference(event)
    return tuple(
        (f"{reference}.{field}", value)
        for field, value in event.evidence.items()
        if value is not None
    )


def evidence_references(event: DetectedEvent) -> tuple[str, ...]:
    """Every reference the event offers, in the recorded evidence order."""
    return tuple(reference for reference, _ in _citable_evidence(event))


@dataclass(frozen=True)
class _AcceptedAnswer:
    """A parsed answer that named only supplied references and left commentary."""

    text: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class _RefusedAnswer:
    """A parsed answer that cannot become a turn, with the reason it cannot."""

    reason: BoothReason


#: The answer protocol's one citation marker. The acceptance path, the
#: protocol-violation check and the assembled prompt all read it from here, so the
#: marker the model is taught and the marker the parser accepts cannot drift apart.
_CITATION_MARKER = "EVIDENCE:"


def _opens_with_citation_marker(line: str) -> bool:
    """Whether ``line`` opens the citation line, read exactly as the acceptance path reads it.

    The marker is matched at the start of the stripped line and case-insensitively, so a
    commentary line that merely mentions the marker mid-sentence is not a citation line.
    """
    return line.strip().upper().startswith(_CITATION_MARKER)


def _parse_answer(raw: str, allowed: tuple[str, ...]) -> _AcceptedAnswer | _RefusedAnswer:
    """Parse the citation-first protocol, refusing anything not backed by ``allowed``.

    The first non-empty line must be the citation line, and it must be the only one: a
    further line that opens with the citation marker is a protocol violation, refused as
    ``MULTIPLE_CITATION_LINES`` because the answer's commentary boundary is undefined and
    the rest of it arrives unvalidated. The shape is decided before the content, so a
    missing or empty citation is ``UNCITED`` only once no later line opens with the
    marker; any cited reference absent from ``allowed`` is ``INVENTED_REFERENCE``; and
    commentary that is blank after the citation is ``BLANK_TEXT``. Order is preserved and
    duplicates are collapsed, so the evidence tuple is exactly what was cited.
    """
    lines = raw.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip()), None)
    if start is None:
        return _RefusedAnswer(BoothReason.UNCITED)
    header = lines[start].strip()
    if not _opens_with_citation_marker(header):
        return _RefusedAnswer(BoothReason.UNCITED)
    if any(_opens_with_citation_marker(line) for line in lines[start + 1:]):
        return _RefusedAnswer(BoothReason.MULTIPLE_CITATION_LINES)
    cited = tuple(
        dict.fromkeys(
            item.strip()
            for item in header[len(_CITATION_MARKER):].split(",")
            if item.strip()
        )
    )
    if not cited:
        return _RefusedAnswer(BoothReason.UNCITED)
    permitted = set(allowed)
    if any(reference not in permitted for reference in cited):
        return _RefusedAnswer(BoothReason.INVENTED_REFERENCE)
    text = "\n".join(lines[start + 1:]).strip()
    if not text:
        return _RefusedAnswer(BoothReason.BLANK_TEXT)
    return _AcceptedAnswer(text=text, evidence=cited)


def _normalise(text: str) -> str:
    """A comparison form for repetition: casefolded with runs of whitespace collapsed."""
    return " ".join(text.split()).casefold()


def _render(value: object) -> str:
    """A deterministic text form of one evidence value for the prompt.

    ``sort_keys`` makes two equal mappings with different key order render identically, and
    a value JSON cannot encode falls back to ``repr`` instead of aborting the prompt.
    """
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=repr)
    except (TypeError, ValueError):
        return repr(value)


def _bounded_int(value: object, name: str, *, minimum: int) -> int:
    """Return ``value`` as an ``int`` of at least ``minimum``, refusing ``bool``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value!r}")
    return value


def _positive_seconds(value: object, name: str) -> float:
    """Return ``value`` as a positive, finite number of seconds, refusing ``bool``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{name} must be a positive finite number of seconds, got {value!r}")
    return seconds


class CommentaryBooth:
    """One two-person booth over one ordered sequence of collected events.

    Construction is the composition point: every collaborator and every bound is injected,
    and a bound is validated here so a nonsensical one fails loudly at the call site
    rather than silently changing what airs. ``run`` makes one model call per event that
    is not stale and carries citable evidence, in event order, and returns the transcript
    plus the outcome of every event.
    """

    def __init__(
        self,
        *,
        model: ModelClient,
        events: Sequence[DetectedEvent],
        settings: BoothSettings,
        clock: Clock,
        max_context_turns: int,
        context_char_budget: int,
        context_window_seconds: float,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> None:
        self._model = model
        self._events = tuple(events)
        if not self._events:
            raise ValueError(
                "the booth needs at least one detected event: the session key it "
                "commentates is derived from them, so an empty sequence names no session"
            )
        session_keys = sorted({event.session_key for event in self._events})
        if len(session_keys) != 1:
            raise ValueError(
                "the booth commentates exactly one session; the supplied events carry "
                f"session keys {session_keys}"
            )
        self._settings = settings
        self._clock = clock
        self._session_key = self._events[0].session_key
        self._max_context_turns = _bounded_int(max_context_turns, "max_context_turns", minimum=1)
        self._context_char_budget = _bounded_int(
            context_char_budget, "context_char_budget", minimum=0
        )
        self._context_window_seconds = _positive_seconds(
            context_window_seconds, "context_window_seconds"
        )
        self._max_output_tokens = _bounded_int(max_output_tokens, "max_output_tokens", minimum=1)
        self._timeout_seconds = _positive_seconds(timeout_seconds, "timeout_seconds")

    def __repr__(self) -> str:
        # The model client's own repr is deliberately not rendered.
        return (
            f"CommentaryBooth(model={type(self._model).__name__}, "
            f"events={len(self._events)}, session_key={self._session_key}, "
            f"model_id={self._settings.model_id!r})"
        )

    async def run(self) -> BoothResult:
        """Commentate every event in order, and return the transcript plus every outcome."""
        turns: list[Turn] = []
        outcomes: list[BoothOutcome] = []
        newest = max(
            (
                event.timestamp_value
                for event in self._events
                if event.timestamp_value is not None
            ),
            default=None,
        )
        for event in self._events:
            reference = event_reference(event)
            citable = _citable_evidence(event)
            if self._is_stale(event, newest):
                outcomes.append(
                    self._outcome(
                        OutcomeKind.EXCLUDED,
                        reference,
                        event,
                        reason=BoothReason.OUTSIDE_CONTEXT_WINDOW,
                    )
                )
                continue
            if not citable:
                outcomes.append(
                    self._outcome(
                        OutcomeKind.EXCLUDED,
                        reference,
                        event,
                        reason=BoothReason.NO_CITABLE_EVIDENCE,
                    )
                )
                continue
            speaker = self._speaker_for(event, turns)
            request = ModelRequest(
                model_id=self._settings.model_id,
                prompt=self._prompt(
                    event, _PERSONAS[speaker], citable, self._bounded_context(turns)
                ),
                max_output_tokens=self._max_output_tokens,
                timeout_seconds=self._timeout_seconds,
            )
            try:
                response = await self._model.generate(request)
            except ModelError as error:
                # Neutral: no turn, no filler. The failure's class name is the only
                # provider-derived fact recorded, never its message or payload.
                outcomes.append(
                    self._outcome(
                        OutcomeKind.DEGRADED,
                        reference,
                        event,
                        speaker=speaker,
                        failure_type=type(error).__name__,
                    )
                )
                continue
            parsed = _parse_answer(response.text, tuple(item[0] for item in citable))
            if isinstance(parsed, _RefusedAnswer):
                outcomes.append(
                    self._outcome(
                        OutcomeKind.REFUSED,
                        reference,
                        event,
                        speaker=speaker,
                        reason=parsed.reason,
                    )
                )
                continue
            if turns and _normalise(parsed.text) == _normalise(turns[-1].text):
                outcomes.append(
                    self._outcome(
                        OutcomeKind.SUPPRESSED,
                        reference,
                        event,
                        speaker=speaker,
                        reason=BoothReason.REPEATS_PREVIOUS_TURN,
                    )
                )
                continue
            turns.append(
                Turn(
                    speaker=speaker,
                    text=parsed.text,
                    evidence=parsed.evidence,
                    event_ref=reference,
                    model_id=self._settings.model_id,
                    created_at=self._clock.now(),
                )
            )
            outcomes.append(self._outcome(OutcomeKind.TURN, reference, event, speaker=speaker))
        return BoothResult(
            transcript=Transcript(
                session_key=self._session_key,
                language=self._settings.language,
                turns=tuple(turns),
            ),
            outcomes=tuple(outcomes),
        )

    def _speaker_for(self, event: DetectedEvent, turns: Sequence[Turn]) -> Speaker:
        """Choose the seat for one event: lead first, then the last turn's opposite.

        Alternation follows what actually aired rather than every processed event, so a
        turn that was refused, degraded or suppressed never shifts it. The priority band
        is the one exception: a flag or an incident hands the next slot to the lead even
        when the last turn already came from the lead.
        """
        if event.event_type in PRIORITY_EVENT_TYPES:
            return Speaker.lead
        if not turns or turns[-1].speaker is Speaker.color:
            return Speaker.lead
        return Speaker.color

    def _outcome(
        self,
        kind: OutcomeKind,
        reference: str,
        event: DetectedEvent,
        *,
        speaker: Speaker | None = None,
        failure_type: str | None = None,
        reason: BoothReason | None = None,
    ) -> BoothOutcome:
        return BoothOutcome(
            kind=kind,
            event_ref=reference,
            event_type=event.event_type,
            speaker=speaker,
            failure_type=failure_type,
            reason=reason,
        )

    def _is_stale(self, event: DetectedEvent, newest: dt.datetime | None) -> bool:
        """Whether the event sits further back than the bounded window from ``newest``.

        An event with no known instant is never called stale: the collector already states
        that it has none, and inventing one to exclude it would be the very guessing this
        module exists to prevent. The boundary itself is fresh (age equal to the window is
        inside it).
        """
        if newest is None or event.timestamp_value is None:
            return False
        return newest - event.timestamp_value > dt.timedelta(seconds=self._context_window_seconds)

    def _bounded_context(self, turns: Sequence[Turn]) -> tuple[Turn, ...]:
        """The most recent turns within the turn count and character budget, oldest first.

        The immediately previous turn is always included, even when it alone exceeds the
        budget, because a booth with no memory of its last line cannot avoid repeating it.
        Every older turn is either included whole or dropped whole; the walk stops at the
        first turn that does not fit, so a gap never closes over a dropped turn.
        """
        if not turns:
            return ()
        selected = [turns[-1]]
        used = len(turns[-1].text)
        for turn in reversed(turns[:-1]):
            if len(selected) >= self._max_context_turns:
                break
            if used + len(turn.text) > self._context_char_budget:
                break
            selected.append(turn)
            used += len(turn.text)
        return tuple(reversed(selected))

    def _prompt(
        self,
        event: DetectedEvent,
        persona: Persona,
        citable: tuple[tuple[str, object], ...],
        prior_turns: tuple[Turn, ...],
    ) -> str:
        """Assemble the whole prompt from the supplied references and the bounded history.

        No reference outside ``citable`` appears anywhere in it, so the prompt cannot hand
        the model a source the event does not own. Both F04 prohibitions are carried
        verbatim in the rules block.
        """
        lines = [
            f"You are {persona.name}, the {persona.seat.value} commentator in a two-person "
            "Formula 1 booth.",
            persona.register_instruction,
            f"Commentate the one event below in {self._settings.language}.",
            "",
            "RULES:",
            "- Cite only the references listed under EVIDENCE; never name a reference that "
            "is not listed there.",
            f"- Start your answer with the citation line, exactly: {_CITATION_MARKER} "
            "<reference>[, <reference>...]",
            "- After that line, write the commentary and nothing else.",
            "- There is no overtake event in this data: a position change is never an "
            "on-track pass. Report the position change itself and nothing more.",
            "- Lap 1 is excluded from every time comparison: never anchor a fastest-lap or "
            "gap claim on lap 1.",
            "- Do not repeat the previous turn.",
            "",
            _CITATION_MARKER,
        ]
        lines.extend(f"- {reference} = {_render(value)}" for reference, value in citable)
        lines.extend(["", "EVENT:", f"type: {event.event_type.value}", f"family: {event.family}"])
        if event.driver_number is not None:
            lines.append(f"driver_number: {event.driver_number}")
        if event.timestamp_value is not None:
            lines.append(f"timestamp: {event.timestamp_value.isoformat()}")
        else:
            lines.append(f"timestamp: unknown ({event.timestamp_unknown_reason})")
        lines.extend(["", "PREVIOUS TURNS:"])
        if prior_turns:
            lines.extend(f"- {turn.speaker.value}: {turn.text}" for turn in prior_turns)
        else:
            lines.append("- (none)")
        return "\n".join(lines)
