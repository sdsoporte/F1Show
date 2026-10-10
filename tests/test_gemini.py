"""Offline acceptance tests for the F08 Gemini gateway and its safeguards.

Everything here runs offline and for free. No network call is made, no SDK client is
constructed, no credential is read and no real model ID is named. The adapter is
exercised through a small **local** fake whose async surface mirrors our reading of
``google-genai``'s ``client.aio.models``; the fake is not the SDK, and
:func:`sdk_adapter` states that stand-in role with a type-checker-only cast. The two
contract probes at the end of this file check that reading against the installed
``google-genai==2.29.0`` by building **real** SDK objects from dictionaries. A probe is a
version-pinned assumption about a third party, never proof of live provider behaviour:
real 429 shapes, ``usage_metadata`` presence and truncation semantics stay unverified
offline and belong to F13, the separately granted live step.

The policy layer runs against the shipped ``ScriptedModelClient`` and
``FakeMonotonicClock`` plus local scripted doubles, so every wait is an exact virtual
duration instead of real elapsed time. The one real wait is the deadline under test.

Every concurrency, ordering or gated wait is bounded with ``asyncio.wait_for`` plus
``pytest.fail`` naming the hazard, because a suite that hangs instead of failing is the
defect a previous unit shipped and this one must not repeat.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

import httpx
import pytest
from google.genai import client as genai_client
from google.genai import errors as genai_errors
from google.genai import models as genai_models
from google.genai import types as genai_types
from pydantic import ValidationError

import f1show
from f1show.fakes import FakeMonotonicClock, ScriptedModelClient
from f1show.gemini import (
    GoogleGenAIClient,
    ModelError,
    ModelRateLimitedError,
    ModelResponseError,
    ModelServerError,
    ModelTimeoutError,
    ModelTransportError,
    ModelUsage,
    SafeguardedModelClient,
)
from f1show.ports import ModelClient, ModelRequest, ModelResponse
from f1show.redaction import attach_redacting_filter
from f1show.request_policy import RetryPolicy

#: Fictional model identifiers, of the same deliberately fake shape as
#: ``tests/test_dialogue.py``. The real value is injected from configuration, and no
#: real Gemini model ID appears in this file or in the module under test.
TEST_MODEL_ID = "test-model"
OTHER_MODEL_ID = "test-model-other"
#: The name the *provider* reports. The adapter must echo the requested id instead.
PROVIDER_MODEL_NAME = "sdk-reported-model-version"

#: Searchable placeholders: obviously fictional, so a leakage assertion can search for
#: them in an error, a repr or a log record. Never a real prompt or credential.
PROMPT = "placeholder prompt for the F08 gateway: describe the current race lap"
CREDENTIAL = "placeholder-api-key-not-a-real-credential"  # noqa: S105 (deliberately fake)

MAX_OUTPUT_TOKENS = 64
TIMEOUT_SECONDS = 5.0
#: The one real wall-clock wait in this file: the deadline under test. Every await that
#: could stall is wrapped in :func:`bounded` with :data:`HAZARD_TIMEOUT_SECONDS`.
DEADLINE_SECONDS = 0.05
HAZARD_TIMEOUT_SECONDS = 5.0
#: The module's own logger, named so an operator can attach the shipped redacting filter.
LOGGER_NAME = "f1show.gemini"


def model_request(**overrides: Any) -> ModelRequest:
    """Build a valid request, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "model_id": TEST_MODEL_ID,
        "prompt": PROMPT,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
    }
    fields.update(overrides)
    return ModelRequest(**fields)


def model_response(**overrides: Any) -> ModelResponse:
    """Build a valid inner answer, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "model_id": TEST_MODEL_ID,
        "text": "Verstappen leads by two tenths.",
        "input_tokens": 11,
        "output_tokens": 7,
    }
    fields.update(overrides)
    return ModelResponse(**fields)


def retry_policy(**overrides: Any) -> RetryPolicy:
    """Build the shared attempt budget, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "max_attempts": 3,
        "base_backoff_seconds": 0.5,
        "max_backoff_seconds": 8.0,
    }
    fields.update(overrides)
    return RetryPolicy(**fields)


def safeguarded(inner: Any, **overrides: Any) -> SafeguardedModelClient:
    """Build the policy layer over ``inner`` with a virtual clock and an explicit gate."""
    fields: dict[str, Any] = {
        "clock": FakeMonotonicClock(),
        "max_concurrency": 2,
        "policy": retry_policy(),
    }
    fields.update(overrides)
    return SafeguardedModelClient(inner, **fields)


def sdk_adapter(sdk: Any) -> GoogleGenAIClient:
    """Wrap one fake SDK client in the adapter, cast to the SDK's own client type.

    The fake mirrors the SDK's async surface without being a ``genai.Client`` - the real
    class cannot be built offline without a credential, and our fake is the only double
    whose surface the contract probes can pin - so the cast is a type-checker-only
    acknowledgement of that stand-in role.
    """
    return GoogleGenAIClient(cast(genai_client.Client, sdk))


def adapter(outcomes: Sequence[Any] = (), *, api_key: str | None = None) -> GoogleGenAIClient:
    """Build the adapter over a fresh local fake of the SDK's async surface."""
    return sdk_adapter(FakeSdkClient(outcomes, api_key=api_key))


async def bounded[T](
    awaitable: Awaitable[T], *, hazard: str, timeout: float = HAZARD_TIMEOUT_SECONDS
) -> T:
    """Await ``awaitable`` under a hard test-side bound, so a stall fails instead of hanging.

    ``asyncio.wait_for`` raises the builtin ``TimeoutError`` for *its own* deadline;
    ``ModelTimeoutError`` is a different type, so an expected timeout under test is
    never mistaken for a hazard.
    """
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except TimeoutError:
        pytest.fail(
            f"HANG HAZARD: {hazard} did not finish within {timeout:g}s; a wait that can "
            "hang is a defect, so this fails instead of blocking the suite"
        )


def assert_no_secret_in_error(error: BaseException, *secrets: str) -> None:
    """Walk the whole exception chain and assert no secret appears anywhere in it.

    Follows ``__cause__`` and ``__context__`` rather than only the raised error, so a
    chained provider failure cannot smuggle a prompt or a credential past the check.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for secret in secrets:
            assert secret not in str(current)
            assert secret not in repr(current)
            assert secret not in repr(current.args)
        current = current.__cause__ or current.__context__


def assert_no_secret_in_records(records: Sequence[logging.LogRecord], *secrets: str) -> None:
    """Assert no captured record carries a secret in its message, args or repr."""
    for record in records:
        for secret in secrets:
            assert secret not in record.getMessage()
            assert secret not in repr(record.args)
            assert secret not in repr(record)


async def yield_until(condition: Callable[[], bool], *, cycles: int = 200) -> None:
    """Yield to the event loop until ``condition`` holds, or fail loudly after ``cycles``.

    A bounded hand-off to a task that must reach a known state before the test acts on
    it. It fails instead of waiting forever, so a task that never starts is reported
    rather than silently hanging the suite.
    """
    for _ in range(cycles):
        if condition():
            return
        await asyncio.sleep(0)
    pytest.fail(f"the awaited state was never reached within {cycles} event-loop cycles")


# --- Local doubles. None of these is the SDK: they mirror our reading of its surface
# --- (the contract probes below check that reading against the installed version).


@dataclass(frozen=True)
class FakeUsageMetadata:
    """Mirrors the SDK usage-metadata attribute names the adapter reads."""

    prompt_token_count: int | None = None
    candidates_token_count: int | None = None
    total_token_count: int | None = None


class FakeSdkResponse:
    """Mirrors the response attributes the adapter reads, including a provider name.

    ``model_version`` is the provider's own naming, deliberately different from the
    requested id: the adapter must never adopt it.
    """

    def __init__(
        self,
        *,
        text: Any = "Verstappen leads by two tenths.",
        usage: FakeUsageMetadata | None = None,
        model_version: str | None = PROVIDER_MODEL_NAME,
    ) -> None:
        self.text = text
        self.usage_metadata = usage
        self.model_version = model_version


class FakeSdkModels:
    """Mirrors ``client.aio.models``: one async ``generate_content``, keyword-only.

    This mirrors OUR READING of the google-genai async surface, not the SDK itself, and
    proves nothing about live behaviour. Scripted outcomes are served strictly in order
    and the queue refuses when drained, so the adapter can never fall back silently.
    """

    def __init__(self, outcomes: Sequence[Any] = ()) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    async def generate_content(
        self, *, model: str, contents: str, config: dict[str, Any] | None = None
    ) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if not self._outcomes:
            raise RuntimeError("FakeSdkModels has no scripted outcome left; no fallback")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeSdkAio:
    """Mirrors the SDK's async namespace: ``client.aio.models``."""

    def __init__(self, outcomes: Sequence[Any] = ()) -> None:
        self.models = FakeSdkModels(outcomes)


class FakeSdkClient:
    """Mirrors the injected ``genai.Client`` shape: an async ``.aio`` namespace.

    Its ``repr`` is deliberately hostile: a real SDK client may expose its api key
    through ``repr``, so the adapter and the wrapper must never render it. That is what
    makes the credential-leakage assertion non-vacuous.
    """

    def __init__(self, outcomes: Sequence[Any] = (), *, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.aio = FakeSdkAio(outcomes)

    def __repr__(self) -> str:
        return f"FakeSdkClient(api_key={self.api_key!r})"


class FakeApiError(Exception):
    """Mirrors the SDK ``APIError`` surface the classifier duck-types: ``.code``.

    ``.response`` is the transport response the SDK keeps, which is where a
    ``Retry-After`` value can be read from.
    """

    def __init__(self, code: int, message: str, response: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.response = response


class ScriptedFailureModelClient:
    """Serves scripted typed failures and answers in order, recording every attempt.

    ``fakes.ScriptedModelClient`` only queues answers and refuses a typed failure
    script; this local double exists so the policy layer can be shown a failure
    sequence without editing the shipped fake.
    """

    def __init__(self, outcomes: Sequence[Any]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[ModelRequest] = []

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self._outcomes:
            raise RuntimeError("ScriptedFailureModelClient queue is exhausted; no fallback")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class HangingModelClient:
    """Hangs (until a deadline cancels it) for ``hang_calls`` calls, then answers."""

    def __init__(self, *, hang_calls: int, response: ModelResponse | None = None) -> None:
        self._hang_calls = hang_calls
        self._response = response if response is not None else model_response()
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls <= self._hang_calls:
            # Only a deadline can end this wait: it is an event that is never set, so
            # the test spends no wall-clock time beyond the deadline under test.
            await asyncio.Event().wait()
        return self._response


class ConcurrencyProbeModelClient:
    """Records the peak number of simultaneous ``generate`` calls and holds each one.

    Every caller is held until the test releases the gate, so the peak is observed with
    genuinely overlapping calls instead of hoped-for scheduling.
    """

    def __init__(self) -> None:
        self.peak = 0
        self.calls = 0
        self._in_flight = 0
        self.entered = asyncio.Semaphore(0)
        self.release = asyncio.Event()

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self._in_flight += 1
        self.peak = max(self.peak, self._in_flight)
        self.entered.release()
        try:
            await self.release.wait()
        finally:
            self._in_flight -= 1
        return model_response()


# --- The adapter: request/response mapping and the typed failure taxonomy.


@pytest.mark.anyio
async def test_the_adapter_maps_the_request_and_the_response_through_the_sdk_surface() -> None:
    """The request's id, prompt and output bound travel to the SDK; the answer comes back.

    ``model_id`` is echoed from the REQUEST even though the provider reports its own
    name, which is asserted explicitly so a future rewrite cannot start trusting the
    provider's naming in our transcript.
    """
    sdk = FakeSdkClient(
        [FakeSdkResponse(text="Verstappen leads.", usage=FakeUsageMetadata(11, 7, 18))],
        api_key=CREDENTIAL,
    )
    result = await GoogleGenAIClient(sdk).generate(model_request())

    assert sdk.aio.models.calls == [
        {
            "model": TEST_MODEL_ID,
            "contents": PROMPT,
            "config": {"max_output_tokens": MAX_OUTPUT_TOKENS},
        }
    ]
    assert isinstance(result, ModelResponse)
    assert result.text == "Verstappen leads."
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert result.model_id == TEST_MODEL_ID
    assert result.model_id != PROVIDER_MODEL_NAME


@pytest.mark.anyio
async def test_the_adapter_reports_zero_tokens_when_the_metadata_is_absent() -> None:
    """A missing usage metadata never discards a usable answer and invents no count."""
    sdk = FakeSdkClient([FakeSdkResponse(text="Answer.", usage=None)])
    result = await GoogleGenAIClient(sdk).generate(model_request())
    assert (result.text, result.input_tokens, result.output_tokens) == ("Answer.", 0, 0)

    partial = FakeSdkClient([FakeSdkResponse(text="Answer.", usage=FakeUsageMetadata(11, None, 18))])
    result = await GoogleGenAIClient(partial).generate(model_request())
    assert (result.input_tokens, result.output_tokens) == (11, 0)


@pytest.mark.anyio
async def test_the_adapter_owns_no_retry_policy_of_its_own() -> None:
    """One scripted 429 is one SDK call: retries belong to the injected policy layer."""
    sdk = FakeSdkClient([FakeApiError(429, "quota exceeded")])
    with pytest.raises(ModelError):
        await GoogleGenAIClient(sdk).generate(model_request())
    assert len(sdk.aio.models.calls) == 1


@pytest.mark.parametrize(
    ("failure", "expected_type", "retryable"),
    [
        pytest.param(FakeApiError(429, "quota"), ModelRateLimitedError, True, id="429"),
        pytest.param(FakeApiError(500, "boom"), ModelServerError, True, id="500"),
        pytest.param(FakeApiError(503, "unavailable"), ModelServerError, True, id="503"),
        pytest.param(FakeApiError(408, "request timeout"), ModelTimeoutError, True, id="408"),
        pytest.param(FakeApiError(400, "bad request"), ModelError, False, id="400"),
        pytest.param(FakeApiError(404, "not found"), ModelError, False, id="404"),
        pytest.param(httpx.ConnectError("refused"), ModelTransportError, True, id="connect"),
        pytest.param(httpx.ReadTimeout("slow"), ModelTimeoutError, True, id="httpx-timeout"),
        pytest.param(ConnectionResetError("reset"), ModelTransportError, True, id="oserror"),
        pytest.param(TimeoutError("deadline"), ModelTimeoutError, True, id="builtin-timeout"),
    ],
)
@pytest.mark.anyio
async def test_the_adapter_maps_provider_failures_to_the_typed_taxonomy(
    failure: BaseException, expected_type: type[ModelError], retryable: bool
) -> None:
    """Retryability is a property of the typed error, never of an HTTP status read here.

    The exact type is asserted rather than only the base class, so a mislabelled
    subclass cannot satisfy the test.
    """
    sdk = FakeSdkClient([failure])
    with pytest.raises(ModelError) as caught:
        await GoogleGenAIClient(sdk).generate(model_request())
    assert type(caught.value) is expected_type
    assert caught.value.retryable is retryable
    assert len(sdk.aio.models.calls) == 1


@pytest.mark.anyio
async def test_the_adapter_propagates_an_unclassified_failure_instead_of_mislabelling_it() -> None:
    """A failure of no known class is a bug: it propagates as itself, never as transport."""

    class UnrelatedBug(Exception):
        """Not an SDK error, not an httpx error, not an OSError."""

    with pytest.raises(UnrelatedBug):
        await adapter([UnrelatedBug("our own bug")]).generate(model_request())


@pytest.mark.parametrize(
    ("text", "case_id"),
    [
        pytest.param(None, "missing", id="missing"),
        pytest.param("", "empty", id="empty-string"),
        pytest.param("   \n\t", "whitespace", id="blank"),
        pytest.param(123, "not-text", id="non-text"),
    ],
)
@pytest.mark.anyio
async def test_the_adapter_refuses_a_missing_blank_or_non_text_response(
    text: Any, case_id: str
) -> None:
    """An empty turn is refused, and refusing it costs exactly one SDK call.

    The refusal is a ``ModelResponseError``: retrying it would only reproduce it, which
    the policy layer's own no-retry test then confirms end to end.
    """
    sdk = FakeSdkClient([FakeSdkResponse(text=text)])
    with pytest.raises(ModelResponseError):
        await GoogleGenAIClient(sdk).generate(model_request())
    assert len(sdk.aio.models.calls) == 1, case_id


@pytest.mark.anyio
async def test_the_adapter_refuses_a_response_object_with_no_text_attribute() -> None:
    """A response shape we do not recognise is a refusal, never an invented empty turn."""

    class BareResponse:
        """A response with no ``text`` attribute at all."""

    with pytest.raises(ModelResponseError):
        await adapter([BareResponse()]).generate(model_request())


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param({"retry-after": "3"}, 3.0, id="delta-seconds"),
        pytest.param({"retry-after": " 7 "}, 7.0, id="padded"),
        pytest.param({"retry-after": "0"}, 0.0, id="zero"),
        pytest.param({"retry-after": "soon"}, None, id="not-a-number"),
        pytest.param({"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}, None, id="http-date"),
        pytest.param({"retry-after": "9" * 30}, None, id="absurd"),
        pytest.param({"x-other": "3"}, None, id="absent"),
    ],
)
@pytest.mark.anyio
async def test_the_adapter_records_only_a_delta_seconds_servers_advice(
    headers: dict[str, str], expected: float | None
) -> None:
    """The optional delay is carried for the caller; anything unusable is simply absent.

    An HTTP-date form is deliberately not resolved: that needs a clock this adapter does
    not own, and inventing a second time source is exactly what the design forbids.
    """
    failure = FakeApiError(429, "quota", response=httpx.Response(429, headers=headers))
    with pytest.raises(ModelRateLimitedError) as caught:
        await adapter([failure]).generate(model_request())
    assert caught.value.retry_after_seconds == expected
    assert caught.value.status_code == 429


# --- Contract probes: the installed third-party surface, and real SDK objects.


def test_contract_probe_the_pinned_google_genai_surface_exists() -> None:
    """A version-pinned assumption about ``google-genai==2.29.0``, not proof of behaviour.

    The callables, the config field and the response/usage field names this mapping
    depends on are asserted against the INSTALLED distribution. The probe constructs no
    client, reads no credential and makes no call. What it cannot prove: real 429 body
    shapes, whether ``usage_metadata`` is always present, and truncation semantics.
    """
    assert inspect.iscoroutinefunction(genai_models.AsyncModels.generate_content)
    parameters = inspect.signature(genai_models.AsyncModels.generate_content).parameters
    assert {"model", "contents", "config"} <= set(parameters)
    assert parameters["config"].default is None
    # The injected shape is a client with an async namespace holding the models surface.
    assert "aio" in dir(genai_client.Client)
    assert "models" in dir(genai_client.AsyncClient)

    # The output bound the adapter passes by keyword is a real config field.
    config = genai_types.GenerateContentConfig.model_validate(
        {"max_output_tokens": MAX_OUTPUT_TOKENS}
    )
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS
    # The adapter hands the SDK a plain mapping. This is the private parameter model the
    # public method builds, validated from a mapping here on purpose: if it stopped
    # coercing a mapping, the adapter's config would silently stop travelling.
    parameters_model = genai_types._GenerateContentParameters.model_validate(
        {
            "model": TEST_MODEL_ID,
            "contents": PROMPT,
            "config": {"max_output_tokens": MAX_OUTPUT_TOKENS},
        }
    )
    assert parameters_model.config is not None
    assert parameters_model.config.max_output_tokens == MAX_OUTPUT_TOKENS

    # The response attributes the adapter reads, and the usage field names it depends on.
    assert hasattr(genai_types.GenerateContentResponse, "text")
    assert "usage_metadata" in genai_types.GenerateContentResponse.model_fields
    assert "model_version" in genai_types.GenerateContentResponse.model_fields
    usage_fields = set(genai_types.GenerateContentResponseUsageMetadata.model_fields)
    assert {"prompt_token_count", "candidates_token_count", "total_token_count"} <= usage_fields

    # The error surface the duck-typed classifier depends on: `.code` is the status.
    assert issubclass(genai_errors.ClientError, genai_errors.APIError)
    assert issubclass(genai_errors.ServerError, genai_errors.APIError)
    assert genai_errors.ClientError(429, {"message": "placeholder"}).code == 429
    assert genai_errors.ServerError(503, {"message": "placeholder"}).code == 503
    assert genai_errors.APIError(429, {"message": "placeholder"}).response is None


@pytest.mark.anyio
async def test_the_adapter_reads_real_sdk_objects_offline() -> None:
    """The strongest offline link: REAL SDK response and error objects, no call made.

    The objects are built from dictionaries, so the adapter's duck-typing is checked
    against the installed SDK rather than only against our own fake. Live behaviour is
    still unproven, and the probe above says so.
    """
    real_answer = genai_types.GenerateContentResponse.model_validate(
        {
            "candidates": [{"content": {"parts": [{"text": "Verstappen leads."}]}}],
            "usage_metadata": {
                "prompt_token_count": 11,
                "candidates_token_count": 7,
                "total_token_count": 18,
            },
            "model_version": PROVIDER_MODEL_NAME,
        }
    )
    result = await adapter([real_answer]).generate(model_request())
    assert (result.text, result.input_tokens, result.output_tokens) == ("Verstappen leads.", 11, 7)
    assert result.model_id == TEST_MODEL_ID

    real_blank = genai_types.GenerateContentResponse.model_validate(
        {"candidates": [{"content": {"parts": [{"text": ""}]}}]}
    )
    with pytest.raises(ModelResponseError):
        await adapter([real_blank]).generate(model_request())

    real_empty = genai_types.GenerateContentResponse()
    with pytest.raises(ModelResponseError):
        await adapter([real_empty]).generate(model_request())

    real_429 = genai_errors.ClientError(429, {"message": "placeholder provider payload"})
    with pytest.raises(ModelRateLimitedError):
        await adapter([real_429]).generate(model_request())

    real_503 = genai_errors.ServerError(503, {"message": "placeholder provider payload"})
    with pytest.raises(ModelServerError) as caught:
        await adapter([real_503]).generate(model_request())
    assert caught.value.status_code == 503


# --- The policy layer: retries, backoff, exhaustion and the no-retry rule.


@pytest.mark.anyio
async def test_a_rate_limited_call_is_retried_and_its_attempt_count_is_measured() -> None:
    inner = ScriptedFailureModelClient(
        [ModelRateLimitedError("rate limited"), model_response()]
    )
    clock = FakeMonotonicClock()
    client = safeguarded(inner, clock=clock)

    result = await client.generate(model_request())

    assert result.text == "Verstappen leads by two tenths."
    assert inner.calls == 2
    assert clock.sleeps == [0.5], "one retry sleeps exactly the base backoff"
    assert clock.monotonic() == 0.5, "the injected clock is the only clock that moved"
    usages = client.usage_totals
    assert len(usages) == 1 and usages[0].attempts == 2


@pytest.mark.anyio
async def test_a_server_failure_is_retried() -> None:
    inner = ScriptedFailureModelClient([ModelServerError("boom", status_code=503), model_response()])
    clock = FakeMonotonicClock()
    result = await safeguarded(inner, clock=clock).generate(model_request())
    assert result.text == "Verstappen leads by two tenths."
    assert inner.calls == 2
    assert clock.sleeps == [0.5]


@pytest.mark.anyio
async def test_a_transport_failure_is_retried() -> None:
    inner = ScriptedFailureModelClient([ModelTransportError("broken pipe"), model_response()])
    clock = FakeMonotonicClock()
    result = await safeguarded(inner, clock=clock).generate(model_request())
    assert result.text == "Verstappen leads by two tenths."
    assert inner.calls == 2
    assert clock.sleeps == [0.5]


@pytest.mark.anyio
async def test_a_deadline_becomes_a_typed_timeout_and_is_retried() -> None:
    """Each attempt gets its own deadline, and an expired attempt is a retryable failure."""
    inner = HangingModelClient(hang_calls=1)
    clock = FakeMonotonicClock()
    client = safeguarded(inner, clock=clock, policy=retry_policy(max_attempts=2))

    result = await bounded(
        client.generate(model_request(timeout_seconds=DEADLINE_SECONDS)),
        hazard="a deadline that never expired or a retry that never ran",
    )

    assert result.text == "Verstappen leads by two tenths."
    assert inner.calls == 2
    assert clock.sleeps == [0.5]


@pytest.mark.anyio
async def test_an_exhausted_deadline_is_a_model_timeout_error() -> None:
    inner = HangingModelClient(hang_calls=99)
    clock = FakeMonotonicClock()
    client = safeguarded(inner, clock=clock, policy=retry_policy(max_attempts=2))

    with pytest.raises(ModelTimeoutError) as caught:
        await bounded(
            client.generate(model_request(timeout_seconds=DEADLINE_SECONDS)),
            hazard="the deadline never converted into a typed timeout",
        )

    assert caught.value.retryable is True
    assert inner.calls == 2, "a timeout takes the retry path and is budgeted like any attempt"
    assert clock.sleeps == [0.5]


@pytest.mark.anyio
async def test_a_response_failure_is_never_retried() -> None:
    """A malformed or blank answer would only be reproduced: it fails after one attempt."""
    inner = ScriptedFailureModelClient([ModelResponseError("no usable text")])
    clock = FakeMonotonicClock()
    with pytest.raises(ModelResponseError):
        await safeguarded(inner, clock=clock).generate(model_request())
    assert inner.calls == 1
    assert clock.sleeps == [], "a non-retryable failure never waits"


@pytest.mark.anyio
async def test_a_blank_provider_answer_is_never_retried_through_the_whole_stack() -> None:
    """End to end: the adapter refuses the blank turn and the policy layer does not retry it."""
    sdk = FakeSdkClient([FakeSdkResponse(text="")] * 3)
    clock = FakeMonotonicClock()
    client = safeguarded(GoogleGenAIClient(sdk), clock=clock, policy=retry_policy(max_attempts=3))

    with pytest.raises(ModelResponseError):
        await bounded(
            client.generate(model_request()), hazard="a non-retryable refusal that never returned"
        )

    assert len(sdk.aio.models.calls) == 1
    assert clock.sleeps == []
    assert client.usage_totals == ()


@pytest.mark.anyio
async def test_a_cancelled_call_is_never_retried_and_records_no_usage() -> None:
    """An outer cancel must not become another attempt, and must not invent usage.

    ``asyncio.CancelledError`` is deliberately not caught by the policy layer: retrying a
    call the caller has abandoned would keep spending on a provider nobody is waiting
    for.
    """
    inner = HangingModelClient(hang_calls=99)
    clock = FakeMonotonicClock()
    client = safeguarded(inner, clock=clock, policy=retry_policy(max_attempts=3))
    task = asyncio.ensure_future(client.generate(model_request()))

    await bounded(
        yield_until(lambda: inner.calls == 1),
        hazard="the first attempt never reached the inner client",
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await bounded(task, hazard="a cancelled call never finished unwinding")

    assert inner.calls == 1, "a cancelled call is not retried"
    assert clock.sleeps == [], "a cancelled call never reaches the backoff"
    assert client.usage_totals == ()


@pytest.mark.anyio
async def test_attempts_are_exhausted_after_exactly_max_attempts_with_the_last_failure() -> None:
    inner = ScriptedFailureModelClient(
        [
            ModelRateLimitedError("rate limited"),
            ModelServerError("boom", status_code=503),
            ModelServerError("still down", status_code=500),
        ]
    )
    clock = FakeMonotonicClock()

    with pytest.raises(ModelServerError) as caught:
        await bounded(
            safeguarded(inner, clock=clock, policy=retry_policy(max_attempts=3)).generate(
                model_request()
            ),
            hazard="an attempt loop that never terminated",
        )

    assert caught.value.status_code == 500, "the LAST typed failure is the one raised"
    assert inner.calls == 3, "exactly max_attempts attempts are made, never one more"
    assert clock.sleeps == [0.5, 1.0]


@pytest.mark.anyio
async def test_backoff_doubles_and_is_capped_with_no_jitter() -> None:
    """Exact virtual durations: doubling from the base, capped, and never randomised."""
    inner = ScriptedFailureModelClient([ModelRateLimitedError("rate limited")] * 5)
    clock = FakeMonotonicClock()
    policy = retry_policy(max_attempts=5, base_backoff_seconds=1.0, max_backoff_seconds=2.0)

    with pytest.raises(ModelRateLimitedError):
        await bounded(
            safeguarded(inner, clock=clock, policy=policy).generate(model_request()),
            hazard="a backoff sequence that never finished",
        )

    assert clock.sleeps == [1.0, 2.0, 2.0, 2.0]
    assert clock.monotonic() == 7.0

    # The same script yields the same waits: a random source would make this flaky, and
    # a non-deterministic policy is one no offline test can pin down.
    second_clock = FakeMonotonicClock()
    with pytest.raises(ModelRateLimitedError):
        await bounded(
            safeguarded(
                ScriptedFailureModelClient([ModelRateLimitedError("rate limited")] * 5),
                clock=second_clock,
                policy=policy,
            ).generate(model_request()),
            hazard="a second backoff sequence that never finished",
        )
    assert second_clock.sleeps == clock.sleeps


@pytest.mark.anyio
async def test_the_server_advised_delay_does_not_change_the_deterministic_backoff() -> None:
    """The advice is recorded on the error; the wait stays the bounded deterministic one.

    ``RetryPolicy.max_retry_after_seconds`` is deliberately unused on this path: the
    wait is already bounded by ``max_backoff_seconds``, and honouring a provider delay
    here would need a second ceiling the registered design does not have.
    """
    advice = FakeApiError(
        429, "quota", response=httpx.Response(429, headers={"retry-after": "3"})
    )
    sdk = FakeSdkClient([advice, FakeSdkResponse(text="Verstappen leads.")])
    clock = FakeMonotonicClock()
    client = safeguarded(
        GoogleGenAIClient(sdk), clock=clock, policy=retry_policy(max_attempts=2)
    )

    result = await client.generate(model_request())

    assert result.text == "Verstappen leads."
    assert clock.sleeps == [0.5], "3s of advice must not replace the 0.5s base backoff"


@pytest.mark.anyio
async def test_an_untyped_failure_is_not_retried_and_is_not_relabelled() -> None:
    """Only the typed failures are retried; our own bug surfaces immediately."""

    class InnerBug(RuntimeError):
        """A non-typed failure from the inner client."""

    inner = ScriptedFailureModelClient([InnerBug("inner bug")])
    clock = FakeMonotonicClock()
    with pytest.raises(InnerBug):
        await safeguarded(inner, clock=clock).generate(model_request())
    assert inner.calls == 1
    assert clock.sleeps == []


# --- The gate: bounded concurrency, never silently serialising or unlimiting.


@pytest.mark.parametrize("max_concurrency", [1, 2, 3])
@pytest.mark.anyio
async def test_the_gate_bounds_concurrency_and_still_admits_every_caller(
    max_concurrency: int,
) -> None:
    """The peak is exactly the configured bound: not more, and not one-at-a-time either.

    A serialising implementation would peak at 1 and fail this test for a bound above 1,
    which is what makes the assertion about the upper bound alone insufficient.
    """
    probe = ConcurrencyProbeModelClient()
    client = safeguarded(probe, max_concurrency=max_concurrency)
    callers = [asyncio.ensure_future(client.generate(model_request())) for _ in range(5)]

    async def wait_until_full() -> None:
        for _ in range(max_concurrency):
            await probe.entered.acquire()

    await bounded(
        wait_until_full(),
        hazard=(
            f"only fewer than {max_concurrency} callers entered the inner client, so the "
            "gate serialised calls that should have overlapped"
        ),
    )
    assert probe.peak == max_concurrency, "the gate admits exactly its configured bound"
    probe.release.set()
    results = await bounded(
        asyncio.gather(*callers), hazard="callers waiting on the gate never completed"
    )
    assert len(results) == 5
    assert probe.calls == 5
    assert probe.peak == max_concurrency, "the peak never exceeded the bound"


# --- Usage accounting and the alerting path.


@pytest.mark.anyio
async def test_usage_accumulates_per_model_and_reports_the_attempts_used() -> None:
    observed: list[ModelUsage] = []
    inner = ScriptedModelClient(
        [
            model_response(input_tokens=11, output_tokens=7),
            model_response(input_tokens=5, output_tokens=3),
            model_response(model_id=OTHER_MODEL_ID, input_tokens=1, output_tokens=2),
        ]
    )
    client = safeguarded(inner, on_usage=observed.append)

    await client.generate(model_request())
    await client.generate(model_request())
    await client.generate(model_request(model_id=OTHER_MODEL_ID))

    totals = client.usage_totals
    assert [usage.model_id for usage in totals] == [TEST_MODEL_ID, OTHER_MODEL_ID]
    first = totals[0]
    assert (first.input_tokens, first.output_tokens, first.total_tokens) == (16, 10, 26)
    assert first.attempts == 2
    second = totals[1]
    assert (second.input_tokens, second.output_tokens, second.total_tokens) == (1, 2, 3)
    assert second.attempts == 1

    assert [usage.model_id for usage in observed] == [TEST_MODEL_ID, TEST_MODEL_ID, OTHER_MODEL_ID]
    assert [usage.total_tokens for usage in observed] == [18, 8, 3]
    assert all(usage.attempts == 1 for usage in observed), "the observer sees the per-call usage"


@pytest.mark.anyio
async def test_usage_is_keyed_on_the_requested_model_not_an_inner_clients_label() -> None:
    """The audit key is what the caller asked for; the adapter echoes it by contract."""
    inner = ScriptedModelClient([model_response(model_id="inner-relabelled-model")])
    client = safeguarded(inner)

    await client.generate(model_request())

    assert [usage.model_id for usage in client.usage_totals] == [TEST_MODEL_ID]


@pytest.mark.anyio
async def test_a_failed_call_records_no_usage_and_reports_nothing() -> None:
    observed: list[ModelUsage] = []
    inner = ScriptedFailureModelClient([ModelServerError("boom", status_code=500)])
    client = safeguarded(inner, policy=retry_policy(max_attempts=1), on_usage=observed.append)

    with pytest.raises(ModelServerError):
        await client.generate(model_request())

    assert client.usage_totals == ()
    assert observed == [], "a failed call must not be reported as usage"


@pytest.mark.anyio
async def test_the_alert_fires_when_the_accumulated_total_reaches_the_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One token below is silence; reaching the threshold is the crossing; it fires once."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    inner = ScriptedModelClient(
        [
            model_response(input_tokens=60, output_tokens=39),
            model_response(input_tokens=1, output_tokens=0),
            model_response(input_tokens=1, output_tokens=1),
        ]
    )
    client = safeguarded(inner, alert_after_tokens=100)

    await client.generate(model_request())
    assert caplog.records == [], "99 tokens against a 100 token threshold is not a crossing"

    await client.generate(model_request())
    assert len(caplog.records) == 1, "reaching the threshold is the crossing"
    message = caplog.records[0].getMessage()
    assert "100" in message, "the alert names the threshold it crossed"
    assert str(client.usage_totals[0].total_tokens) in message, (
        "the alert names the accumulated total it measured"
    )

    await client.generate(model_request())
    assert len(caplog.records) == 1, "a crossed threshold is a state, not a repeated event"


@pytest.mark.anyio
async def test_no_alert_is_emitted_without_a_configured_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    inner = ScriptedModelClient([model_response(input_tokens=10_000, output_tokens=10_000)])
    client = safeguarded(inner, alert_after_tokens=None)

    await client.generate(model_request())

    assert caplog.records == []
    assert client.usage_totals[0].total_tokens == 20_000, "the measurement is still recorded"


@pytest.mark.anyio
async def test_a_failing_usage_observer_does_not_discard_a_successful_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An observer is reporting, not the answer: its failure must not lose a paid call.

    The observer's own message carries the prompt placeholder on purpose, so the log
    assertion proves only the failure's class name is reported, never its text.
    """
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    def observer(usage: ModelUsage) -> None:
        raise RuntimeError(f"observer exploded on {PROMPT}")

    client = safeguarded(ScriptedModelClient([model_response()]), on_usage=observer)

    result = await client.generate(model_request())

    assert result.text == "Verstappen leads by two tenths."
    assert client.usage_totals[0].total_tokens == 18
    assert len(caplog.records) == 1
    assert "RuntimeError" in caplog.records[0].getMessage()
    assert_no_secret_in_records(caplog.records, PROMPT, CREDENTIAL)


@pytest.mark.anyio
async def test_the_module_logger_can_be_protected_by_the_shipped_redacting_filter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Our warnings travel through the nameable module logger, so the filter reaches them.

    The model id is registered as the secret: the record must arrive redacted, which is
    only possible if our warning goes through this logger's filter chain. This is the
    integration the design calls "the redacting logger"; the module's own messages are
    already secret-free by construction, which the leakage tests below assert.
    """
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    logger = logging.getLogger(LOGGER_NAME)
    installed = attach_redacting_filter(logger, [TEST_MODEL_ID])
    try:
        inner = ScriptedModelClient([model_response(input_tokens=6, output_tokens=6)])
        client = safeguarded(inner, alert_after_tokens=10)

        await client.generate(model_request())
    finally:
        logger.removeFilter(installed)

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "[REDACTED]" in message, "the filter ran on our record"
    assert TEST_MODEL_ID not in message
    assert "12" in message, "the measurement itself survives redaction"


# --- Non-leakage: the prompt and the credential, in errors, reprs and log records.


@pytest.mark.anyio
async def test_no_prompt_or_credential_reaches_an_error_or_a_repr() -> None:
    """Non-vacuous: the placeholders are first shown where they legitimately are.

    The prompt lives in the request, the credential lives on the injected SDK client
    (whose repr is deliberately hostile and does expose it), and the provider failure
    echoes the prompt in its own message. None of that may reach a raised error, its
    chain, or the repr of either class.
    """
    failure = FakeApiError(
        429,
        f"429 QUOTA_EXCEEDED: the request {PROMPT} was refused",
        response=httpx.Response(429, headers={"retry-after": "3"}),
    )
    sdk = FakeSdkClient([failure], api_key=CREDENTIAL)
    wrapper = safeguarded(GoogleGenAIClient(sdk), policy=retry_policy(max_attempts=1))

    request = model_request()
    assert request.prompt == PROMPT, "the prompt is legitimately in the request"
    assert sdk.api_key == CREDENTIAL, "the credential is legitimately on the injected client"
    assert CREDENTIAL in repr(sdk), "the hostile repr legitimately exposes it"

    with pytest.raises(ModelRateLimitedError) as caught:
        await bounded(wrapper.generate(request), hazard="a typed failure that never surfaced")

    assert_no_secret_in_error(caught.value, PROMPT, CREDENTIAL)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None

    adapter_repr = repr(GoogleGenAIClient(sdk))
    wrapper_repr = repr(wrapper)
    for rendered in (adapter_repr, wrapper_repr):
        assert PROMPT not in rendered
        assert CREDENTIAL not in rendered
    assert "FakeSdkClient" in adapter_repr, "the repr names the inner client's class only"

    assert sdk.aio.models.calls[0]["contents"] == PROMPT, "the prompt does travel to the SDK"
    assert "api_key" not in sdk.aio.models.calls[0], "this module never passes a credential"


@pytest.mark.anyio
async def test_no_prompt_or_credential_reaches_a_log_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The alerting path logs a real measurement and still carries neither placeholder."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    inner = ScriptedModelClient([model_response(input_tokens=6, output_tokens=6)])
    client = safeguarded(inner, alert_after_tokens=10)

    await client.generate(model_request())

    assert len(caplog.records) == 1, "the non-vacuous premise: a record really was emitted"
    assert TEST_MODEL_ID in caplog.records[0].getMessage()
    assert_no_secret_in_records(caplog.records, PROMPT, CREDENTIAL)


# --- The public surface: the port, the exports and the explicit constructor contract.


def test_model_usage_is_a_strict_immutable_record() -> None:
    usage = ModelUsage(
        model_id=TEST_MODEL_ID, input_tokens=11, output_tokens=7, total_tokens=18, attempts=1
    )
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.attempts) == (
        11,
        7,
        18,
        1,
    )
    with pytest.raises(ValidationError):
        ModelUsage(
            model_id=TEST_MODEL_ID,
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
            attempts=1,
            unexpected="field",
        )
    with pytest.raises(ValidationError):
        ModelUsage(
            model_id=TEST_MODEL_ID,
            input_tokens=-1,
            output_tokens=1,
            total_tokens=0,
            attempts=1,
        )
    with pytest.raises(ValidationError):
        ModelUsage(model_id="", input_tokens=1, output_tokens=1, total_tokens=2, attempts=1)
    with pytest.raises(ValidationError):
        ModelUsage(
            model_id=TEST_MODEL_ID, input_tokens=1, output_tokens=1, total_tokens=2, attempts=0
        )
    with pytest.raises(ValidationError):
        usage.attempts = 5  # type: ignore[misc]


def test_the_typed_failures_share_one_base_and_an_explicit_retryability_rule() -> None:
    for failure_type in (
        ModelTimeoutError,
        ModelRateLimitedError,
        ModelServerError,
        ModelTransportError,
        ModelResponseError,
    ):
        assert issubclass(failure_type, ModelError)
    retryable = {
        ModelError: False,
        ModelTimeoutError: True,
        ModelRateLimitedError: True,
        ModelServerError: True,
        ModelTransportError: True,
        ModelResponseError: False,
    }
    for failure_type, expected in retryable.items():
        assert failure_type.retryable is expected


def test_both_clients_satisfy_the_model_client_port() -> None:
    """A structural check only: it says nothing about behaviour, which is asserted above."""
    assert isinstance(GoogleGenAIClient(FakeSdkClient()), ModelClient)
    assert isinstance(safeguarded(ScriptedModelClient()), ModelClient)


def test_the_gate_and_the_retry_policy_have_no_silent_defaults() -> None:
    """A default gate would either serialise silently or unlimit silently; there is none."""
    parameters = inspect.signature(SafeguardedModelClient.__init__).parameters
    for name in ("max_concurrency", "policy"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is inspect.Parameter.empty
    assert (
        inspect.signature(GoogleGenAIClient.__init__).parameters["inner_client"].default
        is inspect.Parameter.empty
    )

    for rejected in (0, -1, True, 1.5):
        with pytest.raises((TypeError, ValueError)):
            safeguarded(ScriptedModelClient(), max_concurrency=rejected)
    for rejected_tokens in (0, -5, True):
        with pytest.raises((TypeError, ValueError)):
            safeguarded(ScriptedModelClient(), alert_after_tokens=rejected_tokens)
    with pytest.raises(TypeError):
        safeguarded(ScriptedModelClient(), on_usage="not callable")


def test_the_package_root_exposes_the_new_public_names() -> None:
    new_names = (
        "GoogleGenAIClient",
        "ModelError",
        "ModelRateLimitedError",
        "ModelResponseError",
        "ModelServerError",
        "ModelTimeoutError",
        "ModelTransportError",
        "ModelUsage",
        "SafeguardedModelClient",
    )
    for name in new_names:
        assert name in f1show.__all__
        assert getattr(f1show, name).__module__ == "f1show.gemini"
