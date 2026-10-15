"""Offline acceptance tests for the F10 thin single-process orchestration.

Every test here runs offline and for free: no live model call, no credential is read and
no network is touched. The composition path - the recorded fixtures, the F04 collector
and the F09 booth - runs in one process against a local fake provider, and the one
gateway-facing claim (the per-dialect base URL) is proved by capturing the composed URL
from an ``httpx`` recording transport with a fabricated response.

What is deliberately **not** exercised: the gateway provider branch of ``main``. A real
generation needs its own separately granted call, so the native-client branch is never
built here. The offline branch is what proves the composition, and the missing-provider
refusal proves the live branch cannot be entered by omission.

Bounded waits use ``asyncio.wait_for`` plus ``pytest.fail`` naming the hazard, because a
suite that hangs instead of failing is a defect this project has already shipped once.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import inspect
import json
import re
from collections.abc import Awaitable, Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
from google.genai import Client as GenaiClient

import f1show
import f1show.booth
import f1show.run
from f1show.booth import (
    PRIORITY_EVENT_TYPES,
    BoothResult,
    OutcomeKind,
    event_reference,
    evidence_references,
)
from f1show.collector import FAMILY_ORDER, DetectedEvent, collect_session_events
from f1show.config import BoothSettings, Mode, ModelProvider, Settings
from f1show.dialogue import Speaker
from f1show.events import EventType
from f1show.fakes import FrozenClock
from f1show.gemini import GoogleGenAIClient, ModelServerError
from f1show.mode import announces_caution
from f1show.ports import ModelClient, ModelRequest, ModelResponse
from f1show.run import (
    DEFAULT_FIXTURE_DIR,
    RecordedSessionNotFoundError,
    RecordedSourceMissingError,
    load_recorded_session,
    main,
    native_base_url,
    run_session,
)
from f1show.start import group_start_events

UTC = dt.timezone.utc
SESSION_KEY = 9617
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "openf1"
EVENT_FAMILIES = ("position", "laps", "pit", "stints", "race_control")
T0 = dt.datetime(2024, 10, 20, 18, 6, 48, tzinfo=UTC)

#: Fictional model identifier of the same deliberately fake shape as the other suites.
#: The real value is injected from configuration; no real model ID appears anywhere.
TEST_MODEL_ID = "test-model"
#: An obviously fictional key handed straight to the SDK stub. Never a real credential,
#: never read from the environment.
PLACEHOLDER_API_KEY = "placeholder-api-key-not-a-real-credential"  # noqa: S105

#: The gateway declarations under test. These are the exact strings recorded in
#: ``docs/EXTERNAL-CONTRACTS.md``: one carrying ``/v1`` and one carrying no version.
DECLARED_WITH_VERSION = "http://127.0.0.1:8317/v1"
DECLARED_WITHOUT_VERSION = "http://127.0.0.1:8317"
#: The composed path the SDK builds when an api key is set and the base carries no
#: version segment. Captured from the wire in the parameterised test below.
COMPOSED_PATH = f"/v1beta/models/{TEST_MODEL_ID}:generateContent"

#: The fabricated native-dialect answer the recording transport returns, so no byte
#: crosses a network.
FABRICATED_NATIVE_RESPONSE = {
    "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
    "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 1},
    "modelVersion": "gateway-reported-model-version",
}

#: A reference line in the assembled prompt: ``- family[record].field``, alone on its line.
#: The citation-format correction prints a reference and its value on separate lines, so this
#: is end-anchored: a numbered value line, the old ``reference = value`` line and a bulleted
#: rule line are all left alone, and only a supplied reference is ever cited.
_PROMPT_REFERENCE = re.compile(r"^-\s+([a-z_]+\[\d+\]\.[a-z0-9_]+)\s*$", re.MULTILINE)

#: The start turn's declared surface is one **identity** per member -- ``- laps[10]``, with no
#: field -- because the group turn names whole events rather than single fields. It is a
#: narrower shape than the line above, and the double accepts it for the same reason it
#: accepts the other: the booth offered it in this very prompt.
_PROMPT_IDENTITY = re.compile(r"^-\s+([a-z_]+\[\d+\])\s*$", re.MULTILINE)

#: Any reference-shaped token anywhere in the prompt: ``family[record].field``. The set of
#: these must equal the current event's supplied references, so the MODE instruction text
#: can never make a new token citable.
REFERENCE_TOKEN = re.compile(r"[a-z_]+\[\d+\]\.[a-z0-9_]+")

#: Every bracket character. The MODE instruction block is declared to carry none of them.
BRACKETS = "[](){}"

#: A hard test-side bound on every await, so a stall fails loudly instead of hanging.
HAZARD_TIMEOUT_SECONDS = 30.0


async def bounded[T](awaitable: Awaitable[T], *, hazard: str) -> T:
    """Await under a hard bound so a stall fails instead of blocking the suite."""
    try:
        return await asyncio.wait_for(awaitable, timeout=HAZARD_TIMEOUT_SECONDS)
    except TimeoutError:
        pytest.fail(
            f"HANG HAZARD: {hazard} did not finish within {HAZARD_TIMEOUT_SECONDS:g}s"
        )


def load(name: str) -> list[dict[str, Any]]:
    """Read one recorded payload verbatim."""
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def recorded_payloads() -> dict[str, list[dict[str, Any]]]:
    """The recorded payloads for the five event-bearing families."""
    return {name: load(name) for name in EVENT_FAMILIES}


def recorded_events() -> tuple[DetectedEvent, ...]:
    """Collect the recorded session once, for the assertions that read it."""
    return collect_session_events(SESSION_KEY, recorded_payloads())


#: A minimal recorded-shaped payload, used where the full corpus would be noise.
SMALL_PAYLOADS: Mapping[str, Sequence[Mapping[str, object]]] = {
    "position": [
        {
            "session_key": SESSION_KEY,
            "driver_number": 1,
            "position": 3,
            "date": "2024-10-20T18:06:48.657000+00:00",
        },
        {
            "session_key": SESSION_KEY,
            "driver_number": 1,
            "position": 4,
            "date": "2024-10-20T18:06:55.000000+00:00",
        },
        {
            "session_key": SESSION_KEY,
            "driver_number": 1,
            "position": 2,
            "date": "2024-10-20T18:07:00.000000+00:00",
        },
    ]
}


def small_events() -> tuple[DetectedEvent, ...]:
    """Collect the controlled three-event payload."""
    return collect_session_events(SESSION_KEY, SMALL_PAYLOADS)


def booth_settings(
    model_id: str = TEST_MODEL_ID, language: str = "en"
) -> BoothSettings:
    """The booth settings every run here shares, with a fictional model id."""
    return BoothSettings(model_id=model_id, language=language)


class EvidenceEchoModelClient:
    """A local offline provider that answers from the prompt's own references.

    The full recorded session has far too many events to script by hand, so this double
    reads the reference list the booth actually supplied and cites its first entry. It
    therefore cannot answer with an invented source, and a valid turn is produced for
    every call - which is what makes the turn-order and evidence assertions meaningful.

    Two offered shapes exist and both are the booth's own: a field reference
    (``- family[record].field``) for a single-event turn, and a bare identity
    (``- family[record]``) for the start turn, whose declared surface is one identity per
    member. The field form is tried first, so every single-event prompt behaves exactly as
    it did before; when neither shape is offered the double still refuses.
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
                "the booth supplied no reference to cite; the fake refuses to invent one"
            )
        reference = match.group(1)
        return ModelResponse(
            model_id=request.model_id,
            text=f"EVIDENCE: {reference}\nCommentary on {reference}.",
            input_tokens=1,
            output_tokens=1,
        )


class FailingModelClient:
    """A local provider that always raises the typed server failure."""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise ModelServerError("the placeholder provider failed", status_code=503)


def transcript_digest(result: BoothResult) -> str:
    """A stable text form of the transcript, for the determinism check."""
    return json.dumps(result.transcript.model_dump(mode="json"), sort_keys=True)


# --- The per-dialect base URL: a pure derivation, proved from the wire -----------


def test_native_base_url_strips_only_a_trailing_version_segment() -> None:
    assert native_base_url(DECLARED_WITH_VERSION) == DECLARED_WITHOUT_VERSION
    assert native_base_url(DECLARED_WITHOUT_VERSION) == DECLARED_WITHOUT_VERSION
    # A version segment that is not last, or a plain path segment, is left alone: a
    # derivation that always dropped the last path segment would break the second case.
    assert (
        native_base_url("https://gateway.invalid/v1/extra")
        == "https://gateway.invalid/v1/extra"
    )
    assert (
        native_base_url("https://gateway.invalid/api") == "https://gateway.invalid/api"
    )
    assert (
        native_base_url("https://gateway.invalid/v1beta") == "https://gateway.invalid"
    )
    assert native_base_url("https://gateway.invalid/v2") == "https://gateway.invalid"


def test_native_base_url_refuses_a_blank_declaration() -> None:
    with pytest.raises(ValueError):
        native_base_url("   ")


async def capture_composed_url(declared: str) -> tuple[list[str], str]:
    """Compose one native request through a recording transport, with zero network I/O.

    The transport is the recorder: it appends the URL the SDK actually sent and returns a
    fabricated 200, so the composed string is observed rather than rebuilt with string
    arithmetic. It never reads a credential: the placeholder key is passed in directly.
    """
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, json=FABRICATED_NATIVE_RESPONSE)

    inner = GenaiClient(
        api_key=PLACEHOLDER_API_KEY,
        http_options={
            "base_url": native_base_url(declared),
            "async_client_args": {"transport": httpx.MockTransport(handler)},
        },
    )
    try:
        response = await bounded(
            GoogleGenAIClient(inner).generate(
                ModelRequest(
                    model_id=TEST_MODEL_ID,
                    prompt="placeholder prompt for the F10 base-URL probe",
                    max_output_tokens=16,
                    timeout_seconds=5.0,
                )
            ),
            hazard=f"the wire capture for {declared!r}",
        )
    finally:
        await inner.aio.aclose()
    return captured, response.text


@pytest.mark.parametrize("declared", [DECLARED_WITH_VERSION, DECLARED_WITHOUT_VERSION])
@pytest.mark.anyio
async def test_the_native_base_url_derivation_composes_one_version_segment_on_the_wire(
    declared: str,
) -> None:
    """Both declared forms compose the SAME URL, captured from the wire, never rebuilt.

    The SDK appends its own versioned path when an api key is set, so a base URL that
    already carries ``/v1`` composes a doubled version segment and the gateway answers
    404. The derivation strips exactly that trailing version segment, and both cases must
    produce one ``/v1beta/``: a normalisation written only for today's ``/v1`` shape would
    fail the version-less declaration silently.
    """
    captured, text = await capture_composed_url(declared)

    expected = f"{DECLARED_WITHOUT_VERSION}{COMPOSED_PATH}"
    assert captured == [expected], f"declared {declared!r} composed {captured!r}"
    assert "/v1/v1beta/" not in captured[0]
    assert captured[0].count("/v1beta/") == 1
    assert text == "ok"


# --- run_session: recorded fixtures through events and the booth ----------------


@pytest.mark.anyio
async def test_run_session_turns_the_recorded_fixtures_into_an_evidence_carrying_transcript() -> (
    None
):
    model = EvidenceEchoModelClient()

    result = await bounded(
        run_session(
            payloads=recorded_payloads(),
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the recorded-fixture composition",
    )

    turns = result.transcript.turns
    events = recorded_events()
    references = {event_reference(event) for event in events}
    group = group_start_events(events)
    assert group is not None and len(group.members) == RECORDED_LAP_ONE_EVENTS
    start_reference = event_reference(events[group.position])
    member_references = {
        reference
        for member in group.members
        for reference in evidence_references(member)
    }
    assert result.transcript.session_key == SESSION_KEY
    assert result.transcript.language == "en"
    assert turns, "the recorded session must air at least one turn"
    assert turns[0].speaker is Speaker.lead
    assert {turn.speaker for turn in turns} == {Speaker.lead, Speaker.color}
    # One typed outcome per supplied event, so a refusal or degradation stays visible.
    assert len(result.outcomes) == len(events)
    for turn in turns:
        assert turn.model_id == TEST_MODEL_ID
        assert turn.event_ref in references
        assert turn.evidence
        if turn.event_ref == start_reference:
            # F09i's declared exception, asserted rather than waived: the start turn draws
            # its evidence from the lap-1 members it aggregates, so its references belong to
            # those events and not to the single event whose identity its ``event_ref``
            # carries.
            assert set(turn.evidence) <= member_references
            continue
        assert all(
            reference.startswith(f"{turn.event_ref}.") for reference in turn.evidence
        )
        # The injected clock stamps every turn; no wall clock is read anywhere.
        assert turn.created_at == T0


@pytest.mark.anyio
async def test_run_session_carries_the_recorded_windows_story_into_the_prompt() -> None:
    """RED before F09g U1: the recorded end-to-end prompt carried telemetry, no story.

    The recorded session's start-to-lap-5 window is the design's measured one, so at least
    one prompt of the run must carry it: Zhou's gain, the two tied losses, Albon's thirteen
    position changes and long stop, the sector-3 double yellow and Sainz's fastest lap.
    """
    model = EvidenceEchoModelClient()

    await bounded(
        run_session(
            payloads=load_recorded_session(SESSION_KEY),
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the recorded window-story run",
    )

    stories = [
        request.prompt
        for request in model.requests
        if "ZHOU Guanyu, Kick Sauber, from P19 to P14" in request.prompt
    ]
    assert stories, (
        "the recorded run must carry the window's story into at least one prompt; no "
        "prompt named the design's measured biggest gain"
    )
    complete = [
        prompt
        for prompt in stories
        if "34.983" in prompt and "99.923" in prompt and "DOUBLE YELLOW" in prompt
    ]
    assert complete, (
        "the design's measured window has one prompt carrying all of its story items"
    )
    block = complete[0].split("CONTEXT", 1)[1].split("\n\n", 1)[0]
    assert "Alexander ALBON" in block and "13 position changes" in block, block
    assert "Esteban OCON" in block, block
    assert "sector 3" in block, block
    assert not any(character in block for character in "[](){}"), block
    assert re.search(r"[a-z_]+\[\d+\]\.[a-z0-9_]+", block) is None, block


@pytest.mark.anyio
async def test_run_session_threads_the_recorded_driver_directory_into_the_prompt() -> (
    None
):
    """The loader's ``drivers`` payload reaches the booth, and only a joined line is drawn.

    The loader returns the session's driver directory under its own key and ``run_session``
    derives the ``driver_number -> (full_name, team_name)`` map from the payload it already
    holds, so the EVENT block names the driver and the team instead of showing a bare
    number. Every rendered identity line is exactly a directory entry; anything the
    directory cannot resolve renders the declared fallback, never a half-join. The
    acceptance is unchanged: every aired turn still cites only references its own event
    supplied, so the join creates no newly citable token.

    F09i added one exception, asserted rather than waived: the **start turn** covers a whole
    group, so it draws no single ``driver:`` line. Its members' identities arrive instead as
    the VALUES of their own references, and each of those values must be a directory entry or
    the declared fallback, which keeps the no-half-join guarantee on the new surface too.
    """
    payloads = load_recorded_session(SESSION_KEY)
    directory = {
        record["driver_number"]: (record["full_name"], record["team_name"])
        for record in payloads["drivers"]
    }
    model = EvidenceEchoModelClient()

    result = await bounded(
        run_session(
            payloads=payloads,
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the recorded driver-directory run",
    )

    assert model.requests, "the recorded session must have produced a model call"
    expected = {
        f"driver: {full_name} ({team_name}, #{number})"
        for number, (full_name, team_name) in directory.items()
    }
    events = recorded_events()
    group = group_start_events(events)
    assert group is not None and len(group.members) == RECORDED_LAP_ONE_EVENTS
    start_marker = (
        f"rows: {RECORDED_LAP_ONE_EVENTS} lap-1 rows aggregated into this one turn"
    )
    joined_lines: list[str] = []
    for request in model.requests:
        driver_lines = [
            line for line in request.prompt.splitlines() if line.startswith("driver:")
        ]
        if start_marker in request.prompt:
            assert driver_lines == [], (
                "the group turn names no single driver; it renders one identity per member "
                f"as a value instead, got {driver_lines!r}"
            )
            _, _, values = request.prompt.partition("VALUES, in the same order")
            offered = [
                line.split(". ", 1)[1]
                for line in values.splitlines()
                if line[:1].isdigit() and ". " in line
            ]
            assert len(offered) == RECORDED_LAP_ONE_EVENTS, offered
            for value in offered:
                assert value == "unknown" or f"driver: {value}" in expected, (
                    "a group identity must be a directory entry or the declared fallback; "
                    f"got {value!r}"
                )
            continue
        assert len(driver_lines) == 1, (
            "every single-event prompt carries exactly one driver line; got "
            f"{driver_lines!r} in:\n{request.prompt}"
        )
        (line,) = driver_lines
        if line != "driver: unknown":
            assert line in expected, (
                f"a joined driver line must be a directory entry; got {line!r}"
            )
            joined_lines.append(line)
    assert joined_lines, (
        "the recorded directory must resolve at least one aired event, or the join is "
        "never exercised through the run path"
    )
    references = {event_reference(event) for event in events}
    start_reference = event_reference(events[group.position])
    member_references = {
        reference
        for member in group.members
        for reference in evidence_references(member)
    }
    for turn in result.transcript.turns:
        assert turn.event_ref in references
        assert turn.evidence
        if turn.event_ref == start_reference:
            assert set(turn.evidence) <= member_references
            continue
        assert all(
            reference.startswith(f"{turn.event_ref}.") for reference in turn.evidence
        )


@pytest.mark.anyio
async def test_run_session_alternates_the_two_seats_over_a_controlled_payload() -> None:
    events = small_events()
    assert [event.event_type for event in events] == [EventType.POSITION_CHANGE] * 3
    assert not any(event.event_type in PRIORITY_EVENT_TYPES for event in events)

    result = await bounded(
        run_session(
            payloads=SMALL_PAYLOADS,
            session_key=SESSION_KEY,
            model=EvidenceEchoModelClient(),
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the controlled alternation run",
    )

    turns = result.transcript.turns
    assert [turn.speaker for turn in turns] == [
        Speaker.lead,
        Speaker.color,
        Speaker.lead,
    ]
    assert [turn.event_ref for turn in turns] == [
        event_reference(event) for event in events
    ]
    assert [outcome.kind for outcome in result.outcomes] == [OutcomeKind.TURN] * 3


@pytest.mark.anyio
async def test_run_session_is_deterministic_across_two_runs() -> None:
    first = await bounded(
        run_session(
            payloads=recorded_payloads(),
            session_key=SESSION_KEY,
            model=EvidenceEchoModelClient(),
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the first recorded-fixture run",
    )
    second = await bounded(
        run_session(
            payloads=recorded_payloads(),
            session_key=SESSION_KEY,
            model=EvidenceEchoModelClient(),
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the second recorded-fixture run",
    )

    assert transcript_digest(first) == transcript_digest(second)
    assert first.transcript == second.transcript
    assert first.outcomes == second.outcomes


@pytest.mark.anyio
async def test_run_session_degrades_neutrally_when_the_provider_fails() -> None:
    result = await bounded(
        run_session(
            payloads=SMALL_PAYLOADS,
            session_key=SESSION_KEY,
            model=FailingModelClient(),
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the provider-outage run",
    )

    # A stated absence, never invented commentary.
    assert result.transcript.turns == ()
    assert [outcome.kind for outcome in result.outcomes] == [OutcomeKind.DEGRADED] * 3
    assert {outcome.failure_type for outcome in result.outcomes} == {"ModelServerError"}


@pytest.mark.anyio
async def test_run_session_does_not_print(capsys: pytest.CaptureFixture[str]) -> None:
    await bounded(
        run_session(
            payloads=SMALL_PAYLOADS,
            session_key=SESSION_KEY,
            model=EvidenceEchoModelClient(),
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the no-print composition run",
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# --- main: the required provider selection and the offline command path ---------


def test_main_requires_an_explicit_provider_selection() -> None:
    parameters = inspect.signature(main).parameters
    assert "provider" in parameters, "main must take a provider selection"
    assert parameters["provider"].default is inspect.Parameter.empty, (
        "main must take a required provider selection with NO default, so the offline path "
        "is chosen rather than fallen into and a live call cannot happen by omission"
    )
    with pytest.raises(TypeError) as caught:
        main()  # type: ignore[call-arg]  # the omission under test
    assert "provider" in str(caught.value), (
        "calling main with no provider must fail naming the missing selection; "
        f"got {caught.value}"
    )


@pytest.mark.anyio
async def test_main_runs_the_offline_fake_path_end_to_end_and_prints_the_transcript(
    make_settings: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    settings: Settings = make_settings(
        mode=Mode.replay.value,
        replay={"session_key": SESSION_KEY},
        booth={
            "model_id": TEST_MODEL_ID,
            "language": "en",
            "provider": ModelProvider.fake.value,
        },
    )
    events = small_events()
    responses = [
        ModelResponse(
            model_id=TEST_MODEL_ID,
            text=f"EVIDENCE: {evidence_references(event)[0]}\nOffline line {index}.",
            input_tokens=1,
            output_tokens=1,
        )
        for index, event in enumerate(events)
    ]

    result = await bounded(
        main(
            ModelProvider.fake,
            payloads=SMALL_PAYLOADS,
            settings=settings,
            clock=FrozenClock(T0),
            responses=responses,
        ),
        hazard="the offline fake main run",
    )

    printed = capsys.readouterr().out
    assert [turn.text for turn in result.transcript.turns] == [
        "Offline line 0.",
        "Offline line 1.",
        "Offline line 2.",
    ]
    assert [turn.speaker for turn in result.transcript.turns] == [
        Speaker.lead,
        Speaker.color,
        Speaker.lead,
    ]
    assert result.transcript.session_key == SESSION_KEY
    for turn in result.transcript.turns:
        assert turn.text in printed, (
            f"{turn.text!r} is missing from the printed transcript"
        )
        assert turn.speaker.value in printed


@pytest.mark.anyio
async def test_main_refuses_a_provider_that_disagrees_with_the_configuration(
    make_settings: Any,
) -> None:
    """The configured provider and the explicit selection may not silently disagree.

    This runs before any client is built, so the gateway branch is never entered; it only
    keeps the configuration default from quietly overriding the explicit command choice.
    """
    settings: Settings = make_settings(
        mode=Mode.replay.value,
        replay={"session_key": SESSION_KEY},
        booth={
            "model_id": TEST_MODEL_ID,
            "language": "en",
            "provider": ModelProvider.fake.value,
        },
    )

    # The message is asserted, not just the exception type. With the refusal removed this
    # selection falls through to the credential guard in ``_model_client``, which raises a
    # *different* ``ValueError``; a message-blind ``pytest.raises(ValueError)`` accepts that
    # unrelated failure, so the test kept passing while the refusal was gone.
    with pytest.raises(ValueError, match="does not match the configured provider"):
        await bounded(
            main(
                ModelProvider.gemini,
                payloads=SMALL_PAYLOADS,
                settings=settings,
                clock=FrozenClock(T0),
                gateway_base_url=DECLARED_WITH_VERSION,
            ),
            hazard="the provider-mismatch refusal",
        )


# --- The public surface and the no-model-id rule -------------------------------


#: The names this unit contributes to the package root.
F10_EXPORTED_NAMES = (
    "run_session",
    "native_base_url",
    "main",
    "load_recorded_session",
    "RecordedSourceError",
    "RecordedSourceMissingError",
    "RecordedSessionNotFoundError",
)

#: The source of the module actually imported, not of a copied path.
RUN_SOURCE = Path(inspect.getsourcefile(f1show.run) or "").resolve()


def test_every_f10_name_is_exported_and_resolvable_from_the_package_root() -> None:
    if not F10_EXPORTED_NAMES:
        pytest.fail("F10_EXPORTED_NAMES must carry names for this sweep to check")
    for name in F10_EXPORTED_NAMES:
        assert name in f1show.__all__, f"{name} is missing from f1show.__all__"
        assert getattr(f1show, name) is not None, (
            f"{name} is not resolvable from f1show"
        )


def test_the_run_module_names_no_real_model_id_literal() -> None:
    assert RUN_SOURCE.name == "run.py" and RUN_SOURCE.exists()
    source = RUN_SOURCE.read_text(encoding="utf-8").lower()
    for marker in ("gemini-", "gpt-", "claude", "llama"):
        assert marker not in source, (
            f"run.py must not name a real model ID like {marker!r}"
        )


def test_the_run_module_carries_no_clock_or_network_of_its_own() -> None:
    """The composition must not build a clock, an HTTP client or a store of its own."""
    source = RUN_SOURCE.read_text(encoding="utf-8")
    for forbidden in ("datetime.now", "time.time", "httpx.Client", "SQLiteStore"):
        assert forbidden not in source, f"run.py must not build its own {forbidden!r}"


def test_run_session_returns_the_transcript_the_caller_inspects() -> None:
    """The transcript is the deliverable and is reachable from the returned value."""
    signature = inspect.signature(run_session)
    parameters = set(signature.parameters)
    assert {"payloads", "session_key", "model", "clock", "settings"} <= parameters
    assert signature.return_annotation != inspect.Signature.empty


def test_the_fake_provider_is_typed_as_a_model_client() -> None:
    assert isinstance(EvidenceEchoModelClient(), ModelClient)


@pytest.mark.anyio
async def test_the_fake_cites_only_a_reference_line_and_refuses_a_prompt_without_one() -> (
    None
):
    """The double reads the reference-only prompt, and its own guard survives the change.

    The booth no longer prints ``reference = value``: each citable reference stands alone
    under ``EVIDENCE`` and its value sits on a separate numbered line. A pattern that still
    required the ``= value`` tail matches nothing and the fake refuses every call. The
    accepted prompt carries the real shape beside a numbered value line and a bulleted rule
    line; the refused prompt carries every shape that is *not* a reference, the old
    ``= value`` line included, so the end anchor is proved rather than assumed.
    """

    def request_for(prompt: str) -> ModelRequest:
        return ModelRequest(
            model_id=TEST_MODEL_ID,
            prompt=prompt,
            max_output_tokens=256,
            timeout_seconds=30.0,
        )

    client = EvidenceEchoModelClient()
    accepted = "\n".join(
        [
            "EVIDENCE:",
            "- laps[3].lap_duration",
            "VALUES, in the same order as the references above:",
            "1. 105.091",
            "- Do not repeat the previous turn.",
        ]
    )

    response = await bounded(
        client.generate(request_for(accepted)), hazard="the fake's read"
    )

    assert (
        response.text
        == "EVIDENCE: laps[3].lap_duration\nCommentary on laps[3].lap_duration."
    )

    not_a_reference = "\n".join(
        [
            "EVIDENCE:",
            "1. 105.091",
            "- laps[3].lap_duration = 105.091",
            "- Do not repeat the previous turn.",
        ]
    )
    with pytest.raises(AssertionError, match="no reference to cite"):
        await bounded(
            client.generate(request_for(not_a_reference)), hazard="the fake's refusal"
        )


# --- The recorded source: the loader that makes main one command ----------------

#: The record counts measured on the recorded session, per the provenance file. ``drivers``
#: is the session's entry list rather than an event family: it is loaded for the booth's
#: identity join, so it is counted here beside the five collector families. F09g U3b adds the
#: three championship families for the same reason - the booth's bounded championship block
#: derives from them - and none of them is a collector family either.
RECORDED_FAMILY_COUNTS = {
    "position": 403,
    "laps": 1059,
    "pit": 23,
    "stints": 43,
    "race_control": 120,
    "drivers": 20,
    "championship_drivers": 23,
    "championship_teams": 10,
    "session_result": 20,
    # F06b: the optional tactical family, loaded when the corpus carries the
    # file (session 9617 does; 9655 deliberately does not).
    "intervals": 21041,
}

#: The F09g U2 consequence, measured on the recorded session (1,648 detected events): the
#: derived caution signal catches **9** race-control rows, and consulting it in the priority
#: band changes the seat of **1,023** aired turns against the previous strict alternation.
#: The seat is the only field that changes; the turn count, order, text and evidence do not.
RECORDED_CAUTION_EVENTS = 9
RECORDED_SEAT_CHANGES = 1023

#: The recorded session's lap-1 rows: the start aggregation's own subject, one per driver.
#: F09i's aggregation replaces those twenty turns with one start turn and records a
#: ``covered_by_start`` outcome for each of the other nineteen.
RECORDED_LAP_ONE_EVENTS = 20


def test_the_project_default_recorded_directory_resolves_to_the_recorded_corpus() -> (
    None
):
    assert DEFAULT_FIXTURE_DIR.is_dir()
    assert DEFAULT_FIXTURE_DIR.name == "openf1"
    assert DEFAULT_FIXTURE_DIR.parent.name == "fixtures"


def test_recorded_source_loads_the_collector_families_with_the_session_filter() -> None:
    loaded = load_recorded_session(SESSION_KEY)

    # F09f: the loaded contract is the five collector families plus the session's driver
    # directory, which the booth joins to name the driver. F09g U3b deliberately changed
    # this pin a second time rather than deleting it: the contract now also carries the
    # three championship families the bounded championship block derives from. F06b
    # changed it a third time, again rather than deleting it: ``intervals`` is loaded
    # when the corpus carries the file, because the analyst's tactical context reads it.
    # The set is still asserted exactly, so a further accidental family fails here
    # rather than riding along.
    assert set(loaded) == set(FAMILY_ORDER) | {
        "drivers",
        "championship_drivers",
        "championship_teams",
        "session_result",
        "intervals",
    }
    assert {
        family: len(records) for family, records in loaded.items()
    } == RECORDED_FAMILY_COUNTS
    # The filter is explicit and proved on real records, not assumed: only this session's
    # rows come out even though sessions.json holds the whole season.
    assert all(
        record["session_key"] == SESSION_KEY
        for records in loaded.values()
        for record in records
    )
    # The loader feeds the collector exactly what a direct fixture read does.
    assert collect_session_events(SESSION_KEY, loaded) == recorded_events()


def test_recorded_source_loads_the_driver_directory_but_derives_no_event_from_it() -> (
    None
):
    """``drivers`` is loaded for the join yet stays an event-free family.

    F09f deliberately changed this pin rather than deleting it. The recorded ``drivers``
    family is now part of the loaded contract - the booth names the driver and the team
    from it - so the old ``drivers not in loaded`` assertion is no longer true. The
    invariant that actually matters is strengthened instead: the directory is available
    from the loader, and ``collect_session_events`` still derives **zero** extra events
    from it, which is proved by collecting the loaded payload with and without the family.
    ``sessions`` is still excluded, because nothing reads it. F06b loads ``intervals``
    when the corpus carries the file - the analyst's tactical context derives from it -
    and its absence (session 9655's deliberate reduction) is declared, never an error.
    """
    loaded = load_recorded_session(SESSION_KEY)

    assert "drivers" in loaded, (
        "the directory must be available from the loader, because the run path derives the "
        "driver identity map from the payload it already holds"
    )
    assert loaded["drivers"], (
        "an empty directory would make the join silently fall back"
    )
    assert all(record["session_key"] == SESSION_KEY for record in loaded["drivers"])
    collector_payloads = {
        family: records for family, records in loaded.items() if family in FAMILY_ORDER
    }
    assert collect_session_events(SESSION_KEY, loaded) == collect_session_events(
        SESSION_KEY, collector_payloads
    ), "the drivers family must derive no event when it is present"
    assert "intervals" in loaded, (
        "the recorded 9617 corpus carries intervals.json, so the tactical context's "
        "family must load with it"
    )
    assert "sessions" not in loaded
    intervals = load("intervals")
    assert len(intervals) == 21041
    assert all(record["session_key"] == SESSION_KEY for record in intervals)
    assert len(load("sessions")) == 123
    assert len(load("drivers")) == 20


def test_recorded_source_loads_the_championship_families_but_derives_no_event_from_them() -> (
    None
):
    """The three championship families join the loaded contract yet stay event-free.

    F09g U3b changed this pin rather than deleting it. The loader's declared contract now
    also carries ``championship_drivers`` (23 rows), ``championship_teams`` (10) and
    ``session_result`` (20), because the booth's bounded championship block derives its
    per-moment picture from them. The invariant that actually matters is the one the
    ``drivers`` family was strengthened with: each family is **available** from the loader
    under its own key, and ``collect_session_events`` still derives **zero** events from
    any of them, which is proved by collecting the loaded payload with and without them.
    """
    loaded = load_recorded_session(SESSION_KEY)

    for family in ("championship_drivers", "championship_teams", "session_result"):
        assert family in loaded, (
            f"{family} must be available from the loader, because the run path derives "
            "the championship source from the payload it already holds"
        )
        assert loaded[family], f"an empty {family} would make the derivation fall back"
        assert all(record["session_key"] == SESSION_KEY for record in loaded[family]), (
            f"{family} must be session-filtered like every other loaded family"
        )
    assert len(loaded["championship_drivers"]) == 23
    assert len(loaded["championship_teams"]) == 10
    assert len(loaded["session_result"]) == 20
    collector_payloads = {
        family: records for family, records in loaded.items() if family in FAMILY_ORDER
    }
    assert collect_session_events(SESSION_KEY, loaded) == collect_session_events(
        SESSION_KEY, collector_payloads
    ), "the championship families must derive no event when they are present"


def test_recorded_source_refuses_an_unknown_session() -> None:
    with pytest.raises(RecordedSessionNotFoundError) as caught:
        load_recorded_session(SESSION_KEY + 1)
    assert str(SESSION_KEY + 1) in str(caught.value)


def test_recorded_source_refuses_a_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    with pytest.raises(RecordedSourceMissingError) as caught:
        load_recorded_session(SESSION_KEY, fixtures_dir=missing)
    assert str(missing) in str(caught.value)


def test_recorded_source_refuses_a_missing_family_file(tmp_path: Path) -> None:
    with pytest.raises(RecordedSourceMissingError) as caught:
        load_recorded_session(SESSION_KEY, fixtures_dir=tmp_path)
    assert "position" in str(caught.value)


def _write_synthetic_corpus(
    directory: Path, *, drivers: Sequence[Mapping[str, object]] | None
) -> None:
    """Write a minimal recorded corpus into ``directory``.

    Every collector family holds one record whose only load-bearing property is the session
    key, because what these tests exercise is the loader's per-family file selection and its
    session filter, not the record shape the collector validates afterwards. The three
    championship families are written the same way: the loader requires one session-matching
    record per loaded family, and these tests never derive from them. ``drivers`` is
    written only when supplied, so a caller can model a corpus that is missing exactly that
    family. Nothing here touches the real fixtures: the corpus is built under pytest's
    ``tmp_path`` and thrown away with it.
    """
    for family in (
        *FAMILY_ORDER,
        "championship_drivers",
        "championship_teams",
        "session_result",
    ):
        (directory / f"{family}.json").write_text(
            json.dumps([{"session_key": SESSION_KEY}]), encoding="utf-8"
        )
    if drivers is not None:
        (directory / "drivers.json").write_text(
            json.dumps([dict(record) for record in drivers]), encoding="utf-8"
        )


def test_recorded_source_refuses_a_corpus_missing_only_the_driver_directory(
    tmp_path: Path,
) -> None:
    """The directory family is required, and the refusal must name it.

    Honest pin, not a RED-derived test: the behaviour already exists. The empty-directory
    test above stops on ``position`` and therefore never reaches the directory family, so
    this path had no coverage. Every other family here is present and session-matching, so
    the typed refusal can only come from the missing ``drivers.json``.
    """
    _write_synthetic_corpus(tmp_path, drivers=None)

    with pytest.raises(RecordedSourceMissingError) as caught:
        load_recorded_session(SESSION_KEY, fixtures_dir=tmp_path)

    message = str(caught.value)
    assert str(tmp_path / "drivers.json") in message, (
        f"the typed refusal must name the missing family file; got {message!r}"
    )


def test_recorded_source_filters_the_driver_directory_by_session(
    tmp_path: Path,
) -> None:
    """The directory is session-filtered like every other family, not merely trusted.

    Honest pin, not a RED-derived test: the loader already filters every loaded family. The
    recorded corpus holds 20 directory rows that all carry the requested session key, so a
    loader that stopped filtering the directory would still satisfy every pin asserted
    against the real fixtures. This synthetic corpus spans two session keys and gives the
    clause teeth: only the requested session's directory rows may come back, and the other
    session's row must be dropped rather than joined.
    """
    wanted: Mapping[str, object] = {
        "session_key": SESSION_KEY,
        "driver_number": 4,
        "full_name": "Lando Norris",
        "team_name": "McLaren",
    }
    other: Mapping[str, object] = {
        "session_key": SESSION_KEY + 1,
        "driver_number": 44,
        "full_name": "Lewis HAMILTON",
        "team_name": "Ferrari",
    }
    _write_synthetic_corpus(tmp_path, drivers=[wanted, other])

    loaded = load_recorded_session(SESSION_KEY, fixtures_dir=tmp_path)

    assert loaded["drivers"] == [wanted], (
        "the loader keeps only the requested session's directory rows; got "
        f"{loaded['drivers']!r}"
    )
    assert all(record["session_key"] == SESSION_KEY for record in loaded["drivers"]), (
        "no other session's driver may survive the filter"
    )


@pytest.mark.anyio
async def test_main_runs_the_full_command_from_the_recorded_source_with_a_fake_provider(
    make_settings: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """``main`` runs alone: no payloads injected, the recorded corpus read from the project."""
    settings: Settings = make_settings(
        mode=Mode.replay.value,
        replay={"session_key": SESSION_KEY},
        booth={
            "model_id": TEST_MODEL_ID,
            "language": "en",
            "provider": ModelProvider.fake.value,
        },
    )
    fake = EvidenceEchoModelClient()

    result = await bounded(
        main(ModelProvider.fake, settings=settings, clock=FrozenClock(T0), model=fake),
        hazard="the full recorded-source command run",
    )

    turns = result.transcript.turns
    printed = capsys.readouterr().out
    assert result.transcript.session_key == SESSION_KEY
    assert fake.requests, (
        "the recorded source must have produced at least one model call"
    )
    assert turns and turns[0].speaker is Speaker.lead
    # F09g U2 changed this expectation deliberately rather than deleting it. The old pin
    # asserted strict lead/colour alternation over the whole recorded session, which held
    # only because the priority band could match no recorded event: the collector emits
    # RACE_CONTROL for every race-control row. The band now consults the derived caution
    # signal, so a recorded flag or safety-car row pulls the lead into the next slot and the
    # alternation phase flips. The measured number of changed seats is pinned, and both the
    # change and its cause are asserted, so a band that quietly stopped firing fails here.
    strict = [
        Speaker.lead if index % 2 == 0 else Speaker.color for index in range(len(turns))
    ]
    seats = [turn.speaker for turn in turns]
    changed = sum(
        actual is not expected for actual, expected in zip(seats, strict, strict=True)
    )
    assert changed == RECORDED_SEAT_CHANGES, (
        f"the derived caution band changes {RECORDED_SEAT_CHANGES} recorded seats; this "
        f"run changed {changed}"
    )
    assert seats != strict, "the derived caution band must fire on the recorded session"
    assert any(
        left is Speaker.lead and right is Speaker.lead
        for left, right in zip(seats, seats[1:], strict=False)
    ), "a recorded caution row hands the lead two turns in a row"
    for turn in turns:
        assert turn.text in printed


# --- The derived caution band: the measured seat consequence (F09g U2) ---------


@pytest.mark.anyio
async def test_the_recorded_session_seats_are_deliberate_once_the_caution_band_fires() -> (
    None
):
    """The dead priority band, fixed and measured on the recorded session.

    The collector emits ``RACE_CONTROL`` for every race-control row, so the band's
    ``FLAG``/``SAFETY_CAR``/``VIRTUAL_SAFETY_CAR`` types matched nothing and the recorded
    seats were strict alternation. With the derived caution signal consulted, a recorded
    caution row hands the lead the next slot, which flips the phase nine times and changes a
    pinned number of aired seats. Only the seat changes: the order, text and evidence of the
    turns are untouched, so this is the seat band and not a transcript-shape change.

    F09i shortened that transcript by one turn per covered lap-1 member, so the pinned number
    of changed seats was **re-measured** rather than carried, and the two structural
    assertions below (non-alternation, and a lead-lead pair at a recorded caution) are what
    prove the band still fires on the same events.
    """
    events = recorded_events()
    cautions = [event for event in events if announces_caution(event)]
    assert len(cautions) == RECORDED_CAUTION_EVENTS, (
        "the derived caution signal catches exactly the recorded flag and safety-car rows"
    )
    assert {event.evidence.get("flag") for event in cautions} == {
        "YELLOW",
        "DOUBLE YELLOW",
        None,
    }
    model = EvidenceEchoModelClient()

    result = await bounded(
        run_session(
            payloads=recorded_payloads(),
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the recorded derived-caution seat run",
    )

    turns = result.transcript.turns
    strict = [
        Speaker.lead if index % 2 == 0 else Speaker.color for index in range(len(turns))
    ]
    seats = [turn.speaker for turn in turns]
    changed = sum(
        actual is not expected for actual, expected in zip(seats, strict, strict=True)
    )
    assert changed == RECORDED_SEAT_CHANGES
    # F09i: the start turn replaces the twenty lap-1 turns with one, so the transcript is
    # shorter by one turn per covered member while the outcomes stay one per event.
    group = group_start_events(events)
    assert group is not None and len(group.members) == RECORDED_LAP_ONE_EVENTS
    attempted = [
        event for index, event in enumerate(events) if index not in group.covered
    ]
    start_reference = event_reference(events[group.position])
    assert len(turns) == len(attempted), (
        "the caution band changes the seat, never the transcript shape"
    )
    assert [turn.event_ref for turn in turns] == [
        event_reference(event) for event in attempted
    ]
    # The MODE block is instruction text, and the prompt-shape pins hold on every one of
    # the recorded session's prompts: the declared line is present, the citation marker
    # still appears exactly twice, and the MODE block adds no bracket and no reference-shaped
    # token. (The whole-prompt token set also carries prior turns' own cited references, which
    # is the pre-existing context contract, so the new-block check is what proves no leak.)
    marker = f1show.booth._CITATION_MARKER
    assert len(model.requests) == len(attempted), (
        "one prompt per attempted recorded event"
    )
    for event, request in zip(attempted, model.requests, strict=True):
        lines = request.prompt.splitlines()
        start = next(
            index for index, line in enumerate(lines) if line.startswith("MODE:")
        )
        block = "\n".join(lines[start : start + 2])
        assert not any(character in block for character in BRACKETS), block
        assert REFERENCE_TOKEN.search(block) is None, block
        assert request.prompt.count(marker) == 2
        if event_reference(event) == start_reference:
            # The group turn's declared surface is one identity per member, so what it offers
            # is the identity form rather than a field reference: a narrower shape, and the
            # whole point of the decision this unit records. The check is scoped to the
            # EVIDENCE block on purpose: the prompt's whole token set also carries the
            # previous turns' own cited references, which is the pre-existing context
            # contract and not this turn's offered surface.
            for member in group.members:
                assert f"- {event_reference(member)}" in request.prompt
            _, _, after_marker = request.prompt.partition("EVIDENCE:")
            evidence_block, _, _ = after_marker.partition("VALUES, in the same order")
            assert REFERENCE_TOKEN.findall(evidence_block) == [], evidence_block
            continue
        assert set(evidence_references(event)) <= set(
            REFERENCE_TOKEN.findall(request.prompt)
        ), "the event's own references are still offered"


# --- The championship picture in the prompt: the bounded block (F09g U3b) -------


#: The declared championship-block heading in the assembled prompt.
CHAMPIONSHIP_HEADING = "CHAMPIONSHIP:"


def championship_block(prompt: str) -> str:
    """The CHAMPIONSHIP block of an assembled prompt, header included.

    Splitting on the header fails loudly when the block is absent, which is the RED this
    section needs: the recorded prompts must carry the block, not merely have room for it.
    """
    _, after = prompt.split(CHAMPIONSHIP_HEADING, 1)
    block, _ = after.split("\n\n", 1)
    return CHAMPIONSHIP_HEADING + block


@pytest.mark.anyio
async def test_the_recorded_session_carries_the_championship_picture_into_the_prompt() -> (
    None
):
    """The last recorded turn's block, quoted with its measured values.

    The final recorded event is a stint start for driver 31, so the last prompt's block
    states Esteban OCON at P18 on 5 points, Max VERSTAPPEN leading on 354 with a 349-point
    gap, and Alpine P9 on 13. Every value is the measured one: the running order at that
    moment is the full twenty-car field, the leader is the source's own start-checkpoint
    holder plus this race's points so far, and Alpine's 13 is its own ``championship_teams``
    row plus a zero race delta.
    """
    payloads = load_recorded_session(SESSION_KEY)
    model = EvidenceEchoModelClient()

    result = await bounded(
        run_session(
            payloads=payloads,
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the recorded championship-block run",
    )

    assert result.transcript.turns, "the recorded session must air turns"
    block = championship_block(model.requests[-1].prompt)
    assert "Esteban OCON" in block, block
    assert "P18 on 5 points" in block, block
    assert "Max VERSTAPPEN" in block, block
    assert "354 points" in block, block
    assert "gap of 349 points" in block, block
    assert "Alpine is P9 on 13 points" in block, block
    assert not any(character in block for character in BRACKETS), block
    assert REFERENCE_TOKEN.search(block) is None, block


@pytest.mark.anyio
async def test_no_reference_shaped_token_leaks_from_the_championship_block() -> None:
    """A whole-recorded-session sweep: the new block adds no citable token anywhere.

    For every one of the session's prompts the CHAMPIONSHIP block carries no bracket and no
    reference-shaped token, the citation marker still appears exactly twice, and removing
    the block leaves the prompt's reference-token set **unchanged**. That last equality is
    the sweep's teeth: a block that smuggled a ``family[index].field`` token would change
    the set, and a block that merely happened to be absent would fail the extraction above.
    """
    payloads = load_recorded_session(SESSION_KEY)
    model = EvidenceEchoModelClient()

    await bounded(
        run_session(
            payloads=payloads,
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the recorded championship-token sweep run",
    )

    marker = f1show.booth._CITATION_MARKER
    assert len(model.requests) > 1000, "the sweep must span the recorded session"
    for request in model.requests:
        block = championship_block(request.prompt)
        assert not any(character in block for character in BRACKETS), block
        assert REFERENCE_TOKEN.search(block) is None, block
        assert request.prompt.count(marker) == 2, block
        without = request.prompt.replace(f"{block}\n\n", "")
        assert set(REFERENCE_TOKEN.findall(request.prompt)) == set(
            REFERENCE_TOKEN.findall(without)
        ), "the championship block must not change the prompt's reference-token set"


# --- F06b: the optional intervals family and the run path's tactical wiring ------


def test_recorded_source_loads_intervals_when_the_corpus_carries_the_file(
    tmp_path: Path,
) -> None:
    """F06b's declared contract change: ``intervals`` is optional but read when present.

    The synthetic corpus spans two session keys, so the family is proved session-filtered
    like every other loaded family rather than merely trusted because the file exists.
    """
    _write_synthetic_corpus(
        tmp_path,
        drivers=[
            {
                "session_key": SESSION_KEY,
                "driver_number": 4,
                "full_name": "Lando Norris",
                "team_name": "McLaren",
            }
        ],
    )
    wanted: Mapping[str, object] = {
        "session_key": SESSION_KEY,
        "date": "2024-03-02T15:00:00+00:00",
        "driver_number": 4,
        "gap_to_leader": 1.0,
        "interval": 0.5,
    }
    other: Mapping[str, object] = {
        "session_key": SESSION_KEY + 1,
        "date": "2024-03-02T15:00:00+00:00",
        "driver_number": 44,
        "gap_to_leader": 2.0,
        "interval": 1.5,
    }
    (tmp_path / "intervals.json").write_text(
        json.dumps([wanted, other]), encoding="utf-8"
    )

    loaded = load_recorded_session(SESSION_KEY, fixtures_dir=tmp_path)

    assert loaded["intervals"] == [wanted], (
        "the loader keeps only the requested session's interval rows; got "
        f"{loaded['intervals']!r}"
    )


def test_recorded_source_tolerates_a_corpus_without_intervals(tmp_path: Path) -> None:
    """Session 9655 deliberately has no intervals file: declared absence, never an error."""
    _write_synthetic_corpus(
        tmp_path,
        drivers=[
            {
                "session_key": SESSION_KEY,
                "driver_number": 4,
                "full_name": "Lando Norris",
                "team_name": "McLaren",
            }
        ],
    )

    loaded = load_recorded_session(SESSION_KEY, fixtures_dir=tmp_path)

    assert "intervals" not in loaded


def test_the_second_session_loads_without_intervals() -> None:
    """The recorded 9655 corpus holds no intervals.json by the user's own reduction."""
    loaded = load_recorded_session(9655, fixtures_dir=DEFAULT_FIXTURE_DIR / "9655")

    assert "intervals" not in loaded
    assert loaded["laps"], "the second session's laps must still load"


@pytest.mark.anyio
async def test_run_session_wires_the_tactical_source_into_the_prompt() -> None:
    """F06b: the run path builds the tactical source from the payloads it already holds.

    The recorded corpus (session 9617) carries intervals, so the run's prompts carry the
    TACTICAL block; the block stays context, never a source, so the acceptance is
    unchanged and no reference-shaped token may ride in with it.
    """
    model = EvidenceEchoModelClient()

    await bounded(
        run_session(
            payloads=load_recorded_session(SESSION_KEY),
            session_key=SESSION_KEY,
            model=model,
            clock=FrozenClock(T0),
            settings=booth_settings(),
        ),
        hazard="the tactical wiring run",
    )

    tacticals = [
        request.prompt
        for request in model.requests
        if "TACTICAL:" in request.prompt
    ]
    assert tacticals, (
        "the recorded run must wire the tactical source: no prompt carried the block"
    )
    block = tacticals[0].split("TACTICAL:", 1)[1].split("\n\n", 1)[0]
    assert block.strip(), block
    assert not any(character in block for character in "[](){}"), block
    assert re.search(r"[a-z_]+\[\d+\]\.[a-z0-9_]+", block) is None, block
