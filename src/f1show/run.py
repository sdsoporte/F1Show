"""The thin single-process orchestration: one replay run, one transcript (F10).

This module is the **composition root** and nothing else. It wires three units that are
already built and tested - the F04 collector (``collect_session_events``), the F09 booth
(``CommentaryBooth``) and the F08 model boundary - into one call, and it performs no I/O
of its own: it builds no HTTP client, opens no store, reads no clock and names no model ID.
The replayed records, the clock, the model client and the configuration are all handed in,
so the whole path runs offline against a fake provider and stays deterministic.

**The transcript is the deliverable.** :func:`run_session` returns the booth's result: the
two personas' turns in order, each carrying exactly the evidence its own event offered and
the model ID that produced it, plus one typed outcome per supplied event. Degradation stays
neutral - an unavailable provider yields no turn and a typed ``DEGRADED`` outcome, never
fabricated commentary - so a reader can see the product's claim rather than infer it.

**One declared value, two dialects.** The gateway is addressed through one configured base
URL, but its two surfaces disagree about where the version segment belongs: the
OpenAI-compatible surface wants it in the base (``/v1/models`` answers 200), while the
native ``google-genai`` SDK appends its own versioned path when an api key is set and so
needs a base *without* one. Passing the declaration straight to the SDK composes
``/v1/v1beta/`` and the gateway answers 404. :func:`native_base_url` resolves that by
stripping a trailing version segment **in memory**; the declared value itself is never
changed, because its ``/v1`` is load-bearing for the other surface. The derivation is a
pure function of the string it is handed, and ``tests/test_run.py`` proves it against both
declared forms with the composed URL captured from the wire rather than rebuilt.

**No model ID appears here.** The identifier is supplied at runtime from configuration; the
ids a gateway advertises are aliases, not provider contracts.

**The provider is an explicit choice, never an accident.** :func:`main` takes a required
provider selection with no default, so a live generation cannot happen by omission; the
offline path is chosen rather than fallen into, and the gateway branch is not exercised
offline because a real generation needs its own separately granted call.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from f1show.booth import BoothResult, CommentaryBooth
from f1show.collector import FAMILY_ORDER, collect_session_events
from f1show.config import BoothSettings, ModelProvider, Settings
from f1show.dialogue import Transcript
from f1show.fakes import ScriptedModelClient
from f1show.gemini import GoogleGenAIClient
from f1show.ports import Clock, ModelClient, ModelResponse

__all__ = [
    "DEFAULT_FIXTURE_DIR",
    "RecordedSessionNotFoundError",
    "RecordedSourceError",
    "RecordedSourceMissingError",
    "load_recorded_session",
    "main",
    "native_base_url",
    "run_session",
]

#: The recorded session's entry list. It derives no event, so it is not a collector
#: family, but the booth joins ``full_name`` and ``team_name`` from it to name the driver
#: in the prompt. It is loaded under its own key rather than mixed into the event families.
_DRIVER_DIRECTORY_FAMILY = "drivers"

#: The families a recorded session must hold one JSON file for: the five collector
#: families plus the driver directory the booth joins.
_LOADED_FAMILIES = (*FAMILY_ORDER, _DRIVER_DIRECTORY_FAMILY)

#: A trailing path segment that names an API version, e.g. ``v1``, ``v2`` or ``v1beta``.
#: The native SDK supplies its own, so exactly this segment is stripped before it is
#: handed the base URL.
_VERSION_SEGMENT = re.compile(r"^v\d+[a-z0-9]*$", re.IGNORECASE)

#: The bounded-context defaults for one whole session. The window is hours, not minutes,
#: because a race runs about two hours and the window's job is to drop grossly stale
#: events, not to shorten a session.
DEFAULT_MAX_CONTEXT_TURNS = 4
DEFAULT_CONTEXT_CHAR_BUDGET = 4000
DEFAULT_CONTEXT_WINDOW_SECONDS = 21600.0
DEFAULT_MAX_OUTPUT_TOKENS = 256
DEFAULT_TIMEOUT_SECONDS = 30.0

#: The recorded fixture corpus: the MVP's production artifact, read from the repository
#: next to this package. A path derived from this file, never an absolute string literal
#: and never a credential; an operator may point elsewhere through ``fixtures_dir``.
DEFAULT_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "openf1"
)


class RecordedSourceError(RuntimeError):
    """The recorded fixture corpus could not supply the requested session."""


class RecordedSourceMissingError(RecordedSourceError):
    """The fixture directory, or a required family file inside it, is absent."""


class RecordedSessionNotFoundError(RecordedSourceError):
    """The corpus holds no record of the requested session in a required family."""


def load_recorded_session(
    session_key: int,
    *,
    fixtures_dir: str | pathlib.Path = DEFAULT_FIXTURE_DIR,
) -> dict[str, list[dict[str, object]]]:
    """Read the recorded fixture corpus, grouped by family and filtered by session.

    The corpus is the project's production artifact: one JSON file per family under
    ``fixtures/openf1/``. The five families ``collect_session_events`` consumes are
    loaded, ``intervals`` and ``sessions`` are deliberately not because nothing reads
    them, and the session's ``drivers`` entry list is loaded too under its own key: it
    derives no event, but the booth joins ``full_name`` and ``team_name`` from it so the
    prompt names the driver, so it belongs to the declared loaded contract rather than to
    a run path that reads the corpus twice. Every record is filtered to ``session_key``
    here rather than assumed to be, because ``sessions.json`` holds the whole season. A
    missing directory, a missing family file or a session with no records is a typed
    failure, never a silently empty payload.
    """
    directory = pathlib.Path(fixtures_dir)
    if not directory.is_dir():
        raise RecordedSourceMissingError(
            f"the recorded fixture directory {directory} does not exist; point fixtures_dir "
            "at a fixtures/openf1 directory, or omit it for the project default"
        )
    payloads: dict[str, list[dict[str, object]]] = {}
    for family in _LOADED_FAMILIES:
        path = directory / f"{family}.json"
        if not path.is_file():
            raise RecordedSourceMissingError(
                f"the recorded family file {path} is missing; the corpus must hold one JSON "
                f"file per loaded family ({', '.join(_LOADED_FAMILIES)})"
            )
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RecordedSourceError(
                f"the recorded family file {path} is not readable JSON: {error}"
            ) from error
        if not isinstance(records, list):
            raise RecordedSourceError(
                f"the recorded family file {path} must hold a JSON list of records"
            )
        selected = [
            dict(record)
            for record in records
            if isinstance(record, Mapping)
            and _is_session(record.get("session_key"), session_key)
        ]
        if not selected:
            raise RecordedSessionNotFoundError(
                f"the recorded family {family!r} holds no record for session {session_key}; an "
                "unknown session is refused rather than commentated as an empty transcript"
            )
        payloads[family] = selected
    return payloads


def _is_session(value: object, session_key: int) -> bool:
    """Whether a recorded ``session_key`` is the requested session, refusing ``bool``."""
    return (
        isinstance(value, int) and not isinstance(value, bool) and value == session_key
    )


def native_base_url(declared: str) -> str:
    """Return the base URL the native Google SDK needs for ``declared``.

    A pure function of the string it is handed: it never reads a credential and never
    changes the declared value held in configuration. The native SDK appends its own
    versioned path when an api key is set, so a declaration that already carries a
    version segment composes a doubled one (``/v1/v1beta/``) that the gateway answers
    with 404. Stripping exactly a **trailing version segment** leaves any other path
    alone - a rule that always dropped the last segment would silently mangle a
    version-less declaration, which is why both forms are exercised in the tests.
    """
    if not declared.strip():
        raise ValueError(
            "the declared base URL must not be blank; a blank base composes a request "
            "to nowhere rather than failing loudly at the call site"
        )
    parts = urlsplit(declared)
    segments = [segment for segment in parts.path.split("/") if segment]
    if segments and _VERSION_SEGMENT.match(segments[-1]):
        segments.pop()
    path = "/" + "/".join(segments) if segments else ""
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


async def run_session(
    *,
    payloads: Mapping[str, Sequence[Mapping[str, object]]],
    session_key: int,
    model: ModelClient,
    clock: Clock,
    settings: BoothSettings,
    max_context_turns: int = DEFAULT_MAX_CONTEXT_TURNS,
    context_char_budget: int = DEFAULT_CONTEXT_CHAR_BUDGET,
    context_window_seconds: float = DEFAULT_CONTEXT_WINDOW_SECONDS,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> BoothResult:
    """Run one session's replayed records through the collector and the booth.

    ``payloads`` is the replay output - the recorded raw records of one session grouped by
    family, exactly the shape ``collect_session_events`` consumes. Every collaborator is
    injected: the records, the session key, the model client, the clock and the booth
    settings, plus the bounded-context knobs. Nothing here builds a client, opens a store
    or reads a clock of its own, and nothing is printed: the returned :class:`BoothResult`
    carries the transcript together with one typed outcome per event, so a refusal or a
    provider outage is a stated absence rather than an invisible gap.
    """
    events = collect_session_events(session_key, payloads)
    booth = CommentaryBooth(
        model=model,
        events=events,
        settings=settings,
        clock=clock,
        max_context_turns=max_context_turns,
        context_char_budget=context_char_budget,
        context_window_seconds=context_window_seconds,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        driver_directory=_driver_directory(payloads),
    )
    return await booth.run()


def _driver_directory(
    payloads: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[int, tuple[str, str]]:
    """The session's driver directory, keyed by ``driver_number``.

    The recorded ``drivers`` family is the session's entry list, not an event family: the
    collector derives no event from it and the event itself carries only the number, so
    the join is read here and handed to the booth. A record missing the number, the name
    or the team is skipped rather than half-joined, and the booth renders its declared
    fallback for any driver the directory cannot resolve.
    """
    directory: dict[int, tuple[str, str]] = {}
    for record in payloads.get(_DRIVER_DIRECTORY_FAMILY, ()):
        number = record.get("driver_number")
        full_name = record.get("full_name")
        team_name = record.get("team_name")
        if (
            isinstance(number, int)
            and not isinstance(number, bool)
            and isinstance(full_name, str)
            and isinstance(team_name, str)
        ):
            directory[number] = (full_name, team_name)
    return directory


async def main(
    provider: ModelProvider,
    *,
    payloads: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    settings: Settings,
    clock: Clock,
    responses: Sequence[ModelResponse] = (),
    model: ModelClient | None = None,
    gateway_base_url: str | None = None,
    fixtures_dir: str | pathlib.Path = DEFAULT_FIXTURE_DIR,
) -> BoothResult:
    """Run one offline replay session and print its transcript.

    ``provider`` is a **required** selection with no default: the offline path is chosen
    rather than fallen into, and a live generation cannot happen by omission. The explicit
    selection must agree with ``settings.booth.provider`` so the configuration default can
    never quietly override the command choice. ``payloads`` may be injected (the test path)
    or omitted, in which case the recorded fixture corpus is read from ``fixtures_dir`` so
    the command runs on its own. ``model`` injects an offline fake; ``responses`` scripts
    the shipped :class:`~f1show.fakes.ScriptedModelClient`. The ``gemini`` branch builds the
    native client from the configured credential and the declared gateway base URL,
    derived per dialect in memory by :func:`native_base_url`.
    """
    if settings.booth.provider is not provider:
        raise ValueError(
            f"the selected provider {provider.value!r} does not match the configured "
            f"provider {settings.booth.provider.value!r}; a silent disagreement between "
            "the command selection and the configuration is refused"
        )
    client = _model_client(
        provider,
        settings=settings,
        responses=responses,
        model=model,
        gateway_base_url=gateway_base_url,
    )
    session_key = settings.replay.session_key
    if session_key is None:
        raise ValueError(
            "main needs an explicit replay session key; the replay-mode config validator "
            "enforces one, so this guard only fires if that invariant is bypassed"
        )
    replayed = (
        payloads
        if payloads is not None
        else load_recorded_session(session_key, fixtures_dir=fixtures_dir)
    )
    result = await run_session(
        payloads=replayed,
        session_key=session_key,
        model=client,
        clock=clock,
        settings=settings.booth,
    )
    print(_render_transcript(result.transcript))
    return result


def _model_client(
    provider: ModelProvider,
    *,
    settings: Settings,
    responses: Sequence[ModelResponse],
    model: ModelClient | None,
    gateway_base_url: str | None,
) -> ModelClient:
    """Build the model client for one explicit provider selection.

    The two branches refuse each other's configuration rather than ignoring it: a script
    or an injected model belongs to the offline fake only, and a declared gateway base
    URL belongs to the gateway branch only.
    """
    if provider is ModelProvider.fake:
        if gateway_base_url is not None:
            raise ValueError(
                "the fake provider runs offline and takes no gateway base URL; pass "
                "gateway_base_url only with the gemini provider"
            )
        if model is not None and responses:
            raise ValueError(
                "supply either an injected offline model or a response script, not both"
            )
        return model if model is not None else ScriptedModelClient(responses)
    if model is not None:
        raise ValueError(
            "the gemini provider makes a real generation; an injected model is refused"
        )
    if responses:
        raise ValueError(
            "the responses script belongs to the fake provider only; the gemini provider "
            "makes a real generation, so a script is refused rather than ignored"
        )
    if gateway_base_url is None:
        raise ValueError(
            "the gemini provider needs the declared gateway base URL; it is derived in "
            "memory per dialect and never read from a credential"
        )
    credential = settings.credentials.gemini_api_key
    if credential is None:
        raise ValueError(
            "the gemini provider needs credentials.gemini_api_key; the config validator "
            "enforces this, so this guard only fires if that invariant is bypassed"
        )
    # Imported here so the offline path never loads the SDK at all.
    from google.genai import Client as GenaiClient

    inner = GenaiClient(
        api_key=credential.get_secret_value(),
        http_options={"base_url": native_base_url(gateway_base_url)},
    )
    return GoogleGenAIClient(inner)


def _render_transcript(transcript: Transcript) -> str:
    """Render a transcript as the deterministic lines the command prints."""
    lines: list[str] = []
    for turn in transcript.turns:
        lines.append(f"{turn.speaker.value}: {turn.text}")
        lines.append(f"  evidence: {', '.join(turn.evidence)}")
    if not lines:
        lines.append("(no turns were aired)")
    return "\n".join(lines)
