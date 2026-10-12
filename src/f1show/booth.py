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
citation-marked line that also names a reference - a later line that is citation-shaped
under a tolerant reading (an optional leading bullet, optional whitespace before the
colon, any case) **and** carries a reference-shaped token, refused with its
own ``BoothReason.MULTIPLE_CITATION_LINES`` rather than aired with just its first
citation validated - is **refused** with a typed outcome instead of becoming a turn with
a guessed or partially checked source. The guarantee is about *tokens*, not lines: the
refusal needs **both** conditions, because a marker-shaped later line whose remainder
carries no reference token is **prose, not a citation attempt** -- an ordinary sentence
such as ``EVIDENCE: the gap closed by four tenths.`` merely opens with the word the prompt
uses as a section header, and refusing it was the deviation this unit corrects -- while a
marker-shaped line that *does* carry a token is still a second citation attempt and is
still refused. **One over-refusal is accepted as the price of that rule, and it is named
here rather than left to be discovered**: a marker-shaped line whose remainder *names a
supplied reference in prose* (``Evidence: position[0].position shows P3.``) is refused too,
because it is byte-shaped exactly like a second citation and no structural test separates
"prose that happens to mention evidence" from "another citation attempt". Closing it would
mean trading away one of the four escape channels this rule closes, which is the wrong
direction, and a model can rephrase trivially, so the cost is a retry rather than a lost
claim. A reference-shaped token anywhere in the aired commentary that is not one
of the supplied references -- or a matched reference with a bracket glued directly onto it
(``position[0].position[99]``) -- is refused as
``BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT``, which is the one rule that reaches a bare or
mid-line mention. Every emitted ``Turn`` therefore carries a non-empty ``evidence`` tuple
drawn from that one event's own references.

**Two faithful-but-wrong citation shapes are normalised, both measured in a live round**
(206 calls, round 5 Austin 2024): 55 answers copied the reference *together with its
rendered value* (``EVIDENCE: laps[6].lap_duration = 105.091``), because the prompt's
EVIDENCE block printed that line, and 93 cited the event's **identity**
(``EVIDENCE: laps[3]``), a faithful name of a real event that is not itself a reference.
Both are now admitted by normalisation: an item whose text before an ``=`` is a supplied
reference cites that reference and drops the copied value, and an item naming the event's
own identity expands to every reference the event owns, in recorded order. Neither
normalisation moves the invariant: the emitted tuple still contains only supplied
references, an unsupplied token on either shape is still refused, and the EVIDENCE block is
rendered so a reference and its value can no longer be copied together in the first place.

**The boundary of that guarantee, stated plainly.** The rule holds over reference-shaped
tokens *as they appear after normalization* -- Unicode format characters removed and every
whitespace character made a plain space -- and not over arbitrary obfuscation: an
obfuscation this normalization does not undo is out of scope, and **a family is known to
leak**. Any character that **survives normalization** and is neither a word character nor
whitespace -- the combining marks ``Mn``, ``Mc`` and ``Me`` are the common cases -- placed
inside a structural joint defeats the scanner, so ``U+034F`` is the pinned
**representative** rather than the whole leak: ``U+0301``, ``U+0308`` and the spacing mark
``U+0903`` behave the same way, and no exact placement was recorded for any of them.
**Six shapes are deliberately left
airing**, recorded here as an explicit enumeration so the count and the items cannot
disagree, so the next reader does not have to discover them:

1. A dotted suffix after a clean reference is prose, not a fabricated citation, so
   ``position[0].position.The tyres are gone.`` airs.
2. The unbracketed ``position99.invented`` shape is not one the collector's grammar
   produces.
3. A hyphenated suffix such as ``position[0].position-evil`` leaves the supplied reference
   itself intact.
4. A bare non-empty bracket with no field (``position[0]``) is not a complete reference
   token either.
5. A bracketed fragment separated from a clean reference by anything that is **not a word
   character** is never seen at all: the attached-bracket rule requires the bracket
   *immediately* after the matched token, and ``finditer`` consumes the word a later
   fragment would need, so any such separator defeats both rules and airs. The measured
   separators are dot (``position[0].position.[99].evil``), whitespace
   (``position[0].position [99].evil``), hyphen (``position[0].position-[99].evil``),
   comma (``position[0].position,[99].evil``), colon (``position[0].position:[99].evil``),
   slash (``position[0].position/[99].evil``), parenthesis
   (``position[0].position([99].evil``) and apostrophe
   (``position[0].position'[99].evil``); the list is **examples, not the definition** --
   the family is open, because every non-word separator behaves the same way. That is
   measured *after normalization*, so a **format** character does not separate: it is removed
   first, which leaves the bracket attached and the fragment refused.
6. A bracket-led token with no family word (``[99].invented``) is invisible to the scanner:
   its grammar is derived from the supplied references, which always carry a family word, so
   the pattern requires ``\\w+`` before the bracket and a family-less token never matches. It
   airs when nothing word-shaped immediately precedes the bracket, as in
   ``P3, [99].invented for Verstappen.``.

Shapes 5 and 6 are deliberately left airing, not overlooked: closing them is a **product
trade** -- more false refusals against the leak -- that belongs to the user rather than to
this module, so this unit declares and pins them here instead of silently narrowing them.
The cost of the tolerance is stated as the trade it is rather than left implicit:
whitespace is tolerated at the token's structural joints so that a fabricated citation
separated by a plain space -- ``position [1].invented`` -- cannot air, and the price is
that ordinary prose containing ``word [digits] . word`` is read as a spaced reference and
refused, as is an empty bracket such as ``word [ ]``, which needs neither a digit nor a dot
to be refused. A *supplied* reference spaced at the joints still airs, and that direction
is pinned so the tolerance cannot be widened into refusing it.

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
import re
import unicodedata
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

    ``UNSUPPLIED_REFERENCE_IN_TEXT`` names the content rule: the aired commentary carried
    a reference-shaped token that was never supplied. It stands apart from
    ``INVENTED_REFERENCE``, which is about the citation line itself, and from
    ``MULTIPLE_CITATION_LINES``, which is about a further citation-shaped line.
    """

    OUTSIDE_CONTEXT_WINDOW = "outside_context_window"
    NO_CITABLE_EVIDENCE = "no_citable_evidence"
    UNCITED = "uncited"
    INVENTED_REFERENCE = "invented_reference"
    MULTIPLE_CITATION_LINES = "multiple_citation_lines"
    UNSUPPLIED_REFERENCE_IN_TEXT = "unsupplied_reference_in_text"
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

#: The marker's own word: the tolerant predicate below spells the marker through the
#: constant too, so the citation format is still defined in exactly one place.
_CITATION_MARKER_WORD = _CITATION_MARKER.removesuffix(":")

#: The citation-shaped reading used **only** by the violation check: an optional leading
#: bullet, optional whitespace before the colon and any case. It is deliberately wider
#: than what acceptance reads, so a later line spelled as a citation attempt under any
#: variant is recognised; it is never applied to the first line, because widening what is
#: refused must not widen what is accepted. Since the token correction this shape is only
#: one of the two conditions for a violation: the line must also carry a reference-shaped
#: token, so a marker-shaped line of plain prose is not a citation attempt.
_CITATION_SHAPED = re.compile(
    rf"^\s*[-*+\u2022]?\s*{re.escape(_CITATION_MARKER_WORD)}\s*:",
    re.IGNORECASE,
)


def _opens_with_citation_marker(line: str) -> bool:
    """Whether ``line`` opens the citation line, read exactly as the acceptance path reads it.

    The marker is matched at the start of the stripped line and case-insensitively, so a
    commentary line that merely mentions the marker mid-sentence is not a citation line.
    This exact reading is what *accepts* the first line; the tolerant
    ``_is_citation_shaped`` below is what *refuses* a later one.
    """
    return line.strip().upper().startswith(_CITATION_MARKER)


def _is_citation_shaped(line: str) -> bool:
    """Whether ``line`` is a citation attempt under the tolerant reading, for refusal only."""
    return _CITATION_SHAPED.match(line) is not None


#: The scanned index: any bracket content, including none, deliberately wider than the
#: record index of digits the collector writes. A fabricated ``position[x].invented`` or
#: ``position[].invented`` is a citation attempt a reader cannot tell from a real one, so
#: this keeps the already-declared fail-closed cost instead of adding a new one.
_ANY_INDEX = r"[^\]]*"

#: The bare empty-bracket form, with no field. The collector always writes an index and a
#: field, so ``position[]`` on its own is a fabricated reference and is scanned even though
#: a non-empty bare ``position[0]`` would be ordinary prose and is left alone. Its joints
#: tolerate whitespace like the full form's, so ``position [ ]`` is the same token.
_EMPTY_BRACKET = r"\w+\s*\[\s*\]"


def _scan_view(text: str) -> str:
    """The view the reference scanner matches on: format characters gone, whitespace plain.

    Every Unicode format character (category ``Cf``: zero-width space, ZWJ/ZWNJ, BOM) is
    dropped, so a fabricated ``position[0]`` + zero-width space + ``.invented`` cannot hide
    behind invisible bytes whose aired text reads exactly like ``position[0].invented``.
    Every whitespace character -- NBSP included -- becomes a plain space, so the scanner's
    ``\\s*`` joints can recognise a reference split by a newline or a NBSP. Whitespace is
    *not* removed globally: that would merge unrelated words into invented tokens. The aired
    text is never changed by this view; it is only what the content rule matches on.
    """
    return "".join(
        " " if character.isspace() else character
        for character in text
        if unicodedata.category(character) != "Cf"
    )


def _reference_scanner(references: Sequence[str]) -> re.Pattern[str] | None:
    """Compile the scanner for one reference token out of the supplied references.

    The collector writes every reference as ``<family>[<record_index>].<field>`` and
    ``_citable_evidence`` reproduces that form, so the shape is *read off* a supplied
    reference rather than pasted in as a second pattern that could drift from it: each
    reference is split on the two separators the form itself carries -- the bracketed
    index and the dot before the field -- and the family and the field are read as word
    runs. The index window is wider than the digits the collector writes and reaches zero
    (``_ANY_INDEX``), the bare empty-bracket form is scanned without a field
    (``_EMPTY_BRACKET``), and every structural joint tolerates whitespace so a reference
    split by a newline or a NBSP is still one token. A reference that does not carry that
    structure yields no scanner, and the content rule then has nothing to flag rather than
    falling back to an invented pattern.
    """
    for reference in references:
        family, _, remainder = reference.partition("[")
        index, _, remainder = remainder.partition("]")
        if not (family and index and remainder.startswith(".")):
            continue
        field = remainder[1:]
        if not field:
            continue
        return re.compile(
            rf"(?<!\w)(?:\w+\s*\[{_ANY_INDEX}\]\s*\.\s*\w+|{_EMPTY_BRACKET})(?!\w)"
        )
    return None


def _canonical_reference(token: str) -> str:
    """A matched token with its joint whitespace removed, comparable to a supplied reference."""
    return "".join(token.split())


def _has_attached_bracket(text: str, end: int) -> bool:
    """Whether a bracket is glued directly onto the matched token, making it a fragment.

    Only the bracket continuation is a fragment. A ``.`` after a clean reference is prose --
    ``position[0].position.The tyres are gone.`` is a sentence boundary, not a fabricated
    citation -- so a dotted suffix is deliberately left airing.
    """
    return text[end : end + 1] == "["


def _is_citation_attempt(line: str, scanner: re.Pattern[str] | None) -> bool:
    """Whether a later line is a citation attempt: citation-shaped **and** token-carrying.

    The violation is about tokens, not lines. A later line that is citation-shaped under
    the tolerant reading but whose remainder carries no reference-shaped token is prose
    that happens to open with the word the prompt uses as a section header -- an ordinary
    sentence such as ``EVIDENCE: the gap closed by four tenths.`` -- so it is commentary
    and airs; refusing it was the deviation. Only a marker-shaped line that actually names
    a reference-shaped token is a second citation attempt, refused as
    ``MULTIPLE_CITATION_LINES``. The token is matched on the same normalized view the
    content rule uses (``_scan_view``), so both rules read one shape.

    ``scanner`` is the shape derived from the supplied references (``_reference_scanner``).
    It is ``None`` only when those references carry no ``<family>[<index>].<field>``
    structure, which the collector's grammar never produces; in that unreachable case the
    shape cannot be built, so this stays **fail-closed** and refuses the citation-shaped
    line as before rather than letting a second citation through unvalidated.
    """
    if not _is_citation_shaped(line):
        return False
    if scanner is None:
        return True
    return scanner.search(_scan_view(line)) is not None


def _parse_answer(
    raw: str, allowed: tuple[str, ...], identity: str | None = None
) -> _AcceptedAnswer | _RefusedAnswer:
    """Parse the citation-first protocol, refusing anything not backed by ``allowed``.

    The first non-empty line must be the citation line, and it must be the only one: a
    further line that is citation-shaped under the tolerant reading -- an optional leading
    bullet, optional whitespace before the colon, any case -- **and** carries a
    reference-shaped token is a protocol violation, refused as
    ``MULTIPLE_CITATION_LINES`` because the answer's commentary boundary is undefined and
    the rest of it arrives unvalidated. The token requirement is the correction: a
    marker-shaped later line whose remainder carries no reference token is prose that
    merely opens with the header word, not a citation attempt, so it airs as commentary
    instead of being refused; refusing it was the deviation. The reference shape is derived
    from ``allowed``, and if it cannot be built the check stays fail-closed and still
    refuses a citation-shaped line. What *accepts* the first line stays
    the exact marker the prompt teaches. The shape is decided before the content, so a
    missing or empty citation is ``UNCITED`` only once no later line opens with the
    marker.

    Each cited item is then normalised against the event's own tokens, in this order: an
    item carrying ``=`` is read as the text before the first ``=`` -- a copy artefact of a
    rendered ``reference = value`` line, whose left side must itself be acceptable -- then
    an item equal to ``identity`` (the event's own ``family[index]``) expands to every
    reference in ``allowed``, in recorded order, and anything else must be one of
    ``allowed``. Any cited item that survives neither route is ``INVENTED_REFERENCE``; the
    normalisations can only ever emit supplied references, so the guarantee does not move.
    Commentary that is blank after the citation is ``BLANK_TEXT``. The content rule
    matches on a normalized view of the aired commentary -- Unicode format characters
    removed, every whitespace character made a plain space -- and refuses
    ``UNSUPPLIED_REFERENCE_IN_TEXT`` when any reference-shaped token is not one of
    ``allowed``, so a never-supplied reference cannot ride in on a bare or mid-line mention.
    A bracket glued directly onto a matched token -- ``position[0].position[99]`` or
    ``position[0].position[99].evil`` -- is an attached fragment and is refused for the same
    reason; a dotted suffix is prose and airs. Order is
    preserved, duplicates are collapsed, and an empty item between commas is dropped --
    tolerance, never an injection, because an empty item carries no reference -- so the
    evidence tuple is exactly what was cited, after normalisation.
    """
    lines = raw.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip()), None)
    if start is None:
        return _RefusedAnswer(BoothReason.UNCITED)
    header = lines[start].strip()
    if not _opens_with_citation_marker(header):
        return _RefusedAnswer(BoothReason.UNCITED)
    # The reference shape is derived once, here, because the violation check needs it too:
    # a marker-shaped later line is only a citation attempt when it also names a token.
    scanner = _reference_scanner(allowed)
    if any(_is_citation_attempt(line, scanner) for line in lines[start + 1:]):
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
    expanded: list[str] = []
    for item in cited:
        candidate = item.partition("=")[0].strip() if "=" in item else item
        if identity is not None and candidate == identity:
            # The event's own identity names the whole event: it expands to every
            # reference the event owns, never airs as the bare identity.
            expanded.extend(allowed)
        elif candidate in permitted:
            expanded.append(candidate)
        else:
            return _RefusedAnswer(BoothReason.INVENTED_REFERENCE)
    evidence = tuple(dict.fromkeys(expanded))
    if not evidence:
        return _RefusedAnswer(BoothReason.UNCITED)
    text = "\n".join(lines[start + 1:]).strip()
    if not text:
        return _RefusedAnswer(BoothReason.BLANK_TEXT)
    scanned = _scan_view(text)
    if scanner is not None:
        for match in scanner.finditer(scanned):
            supplied = _canonical_reference(match.group(0)) in permitted
            if supplied and not _has_attached_bracket(scanned, match.end()):
                continue
            return _RefusedAnswer(BoothReason.UNSUPPLIED_REFERENCE_IN_TEXT)
    return _AcceptedAnswer(text=text, evidence=evidence)


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
            parsed = _parse_answer(
                response.text, tuple(item[0] for item in citable), identity=reference
            )
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
            "- The values under VALUES are commentary material only: they never belong on "
            "the citation line.",
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
        # A reference and its value are rendered apart, deliberately: a prompt line that
        # prints ``reference = value`` teaches a copy of the whole line, and 55 of 206
        # measured live answers cited the value together with the reference and were
        # refused. Here the reference list is citable verbatim and the values live on
        # numbered lines that carry no reference, so what a model copies is one or the
        # other, never both.
        lines.extend(f"- {reference}" for reference, _ in citable)
        lines.append(
            "VALUES, in the same order as the references above; commentary material only, "
            "never part of the citation line:"
        )
        lines.extend(
            f"{position}. {_render(value)}" for position, (_, value) in enumerate(citable, start=1)
        )
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
