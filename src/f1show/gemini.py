"""The Gemini gateway: one thin SDK adapter and the safeguards layered over any client.

The two classes here have deliberately separate jobs, and that split is what makes the
safeguards testable offline:

* :class:`GoogleGenAIClient` is a **thin adapter** over an **injected** async
  ``google-genai`` client. It maps :class:`~f1show.ports.ModelRequest` into the SDK's
  async generation call and the SDK's answer back into ``ModelResponse``. It constructs
  no SDK client, reads no credential, stores none and formats none: the caller builds
  ``genai.Client(api_key=...)`` at wiring time, which is the same composition-ownership
  precedent ``f1show.auth`` follows. It owns **no retry policy** of its own, because the
  injected client may already be a wrapper and doubling the rules would multiply the
  real request budget.
* :class:`SafeguardedModelClient` is the **policy layer** over any ``ModelClient``: one
  deadline per attempt, a bounded in-flight gate, a bounded attempt budget with
  deterministic backoff, measured usage accounting and one alerted threshold. It follows
  ``f1show.request_policy``'s wrapper convention - **the caller owns the inner client**,
  and this wrapper never opens, closes or replaces it, so there is no ``close`` here to
  call. A nested wrapper multiplies the attempt budget; the outermost one owns retries.

Four rules bind both classes.

* **Measured usage is NOT a hard spend limit, and no cost stop exists before F13.**
  F08 measures, reports and alerts: :class:`ModelUsage` accumulates per requested model,
  an optional observer sees each call, and an optional caller-supplied token threshold
  raises one warning. Nothing here refuses, truncates or caps a call on cost grounds.
  Per-session spend is uncapped by user decision and the pilot total is approved at F13.
* **``model_id`` is injected and has no default**, so no model ID literal can enter this
  module or the configuration it is called from. Which also means this module cannot be
  asked to guess one.
* **No prompt, credential or raw provider payload escapes.** No raised error, ``repr``
  or log line carries the prompt text or a credential; a provider failure's own message
  is never read, formatted or chained, because a provider that echoes the request would
  otherwise echo the prompt into our telemetry. The provider's HTTP status is the only
  thing repeated from a failure.
* **No live model call, no network access, no credential use.** This module is exercised
  offline against scripted doubles and against the installed SDK's own objects.

What is *not* established here, stated plainly rather than implied: the adapter's
reading of the SDK is pinned by an offline contract probe, not by live use. Real 429
response shapes, whether ``usage_metadata`` is always present, and truncation semantics
stay unverified until F13's separately granted live call. Two further honest limits: the
port carries only prompt and candidate counts, so a thinking model's ``thoughts`` tokens
are not represented in ``ModelUsage``; and a response with no usage metadata is reported
as zero tokens for that call - an under-report, never an invented number.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field

from f1show.ports import ModelClient, ModelRequest, ModelResponse, MonotonicClock
from f1show.request_policy import RetryPolicy

if TYPE_CHECKING:
    from google.genai import Client

__all__ = [
    "GoogleGenAIClient",
    "ModelError",
    "ModelRateLimitedError",
    "ModelResponseError",
    "ModelServerError",
    "ModelTimeoutError",
    "ModelTransportError",
    "ModelUsage",
    "SafeguardedModelClient",
]

#: The module's own logger, named so an operator can attach the shipped redacting filter
#: (``f1show.redaction.attach_redacting_filter``) to it. Every message below is
#: secret-free by construction; the filter is defence in depth, not the only barrier.
_LOGGER = logging.getLogger(__name__)

#: How many significant digits of a server-advised ``Retry-After`` are accepted. The
#: value is informational here (the deterministic backoff governs the wait), so an
#: absurd magnitude is dropped rather than converted into a float that overflows to
#: infinity with no meaning.
_MAX_ADVISED_DELAY_DIGITS = 9


class ModelError(Exception):
    """Base of every failure raised at the model boundary.

    A caller catches this type rather than an SDK or transport library's own exception,
    so the adapter can be reimplemented without changing a caller's error handling. The
    message names the failure kind and, at most, the provider's HTTP status or the
    exception's class name; the provider's own text is never repeated.

    ``retryable`` is a class-level property of the *type*, not a per-instance or
    caller-tunable flag, and it is what the policy layer reads instead of an HTTP
    status: rate-limited, server, timeout and transport failures are retryable, while a
    malformed or blank answer is not, because repeating it would only reproduce it.
    ``status_code`` carries the provider's status when one is known, and ``None``
    otherwise.
    """

    retryable: bool = False

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ModelTimeoutError(ModelError):
    """A single attempt did not finish in time.

    Raised for the policy layer's own per-attempt deadline and for a provider-reported
    request timeout (status 408). Both are the same behaviour to a caller - the answer
    did not arrive in time - and both are retryable.
    """

    retryable = True


class ModelRateLimitedError(ModelError):
    """The provider rate-limited the call (status 429).

    ``retry_after_seconds`` is the provider's ``Retry-After`` advice in its
    delta-seconds form when the response carried one, and ``None`` otherwise. It is
    carried for the caller and for a report; it deliberately does **not** alter this
    module's wait, which stays the deterministic bounded backoff, because honouring it
    would need a second ceiling the registered design does not have.
    """

    retryable = True

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        status_code: int | None = 429,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after_seconds = retry_after_seconds


class ModelServerError(ModelError):
    """The provider failed on its side (a 5xx status); retryable as expected transient."""

    retryable = True


class ModelTransportError(ModelError):
    """The call never produced a provider answer: connection, protocol or send failure."""

    retryable = True


class ModelResponseError(ModelError):
    """A provider answer that is not usable text, or no answer at all.

    A missing, blank or non-text response is refused here instead of becoming an empty
    turn. It is deliberately **not** retryable: a deterministic body or shape problem
    would only be reproduced by another attempt.
    """


class ModelUsage(BaseModel):
    """Measured token usage for one model call, or for the calls it accumulates.

    Strict and immutable, like every other internal record: an unknown field is a bug in
    our own pipeline. ``attempts`` is the number of attempts a single call used, and the
    sum of them in an accumulated record.

    ``total_tokens`` is carried as the record's own number instead of being derived from
    the two components at construction, so a caller that knows a provider's wider total -
    one that includes tokens outside the returned text, as a thinking model reports - can
    record it without misstating input and output. The policy layer only ever has the
    port's two counts, so it sums them. Either way this is a **measurement**: it caps
    nothing, stops nothing, and no cost ceiling exists here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_id: Annotated[str, Field(min_length=1)]
    input_tokens: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    total_tokens: Annotated[int, Field(ge=0)]
    attempts: Annotated[int, Field(ge=1)]


def _positive_int(value: object, name: str) -> int:
    """Return ``value`` as a positive ``int``, explicitly refusing ``bool``.

    ``True`` is an ``int`` in Python, but a boolean limit is a bug rather than a value of
    1, so bools are rejected instead of silently accepted, as in ``f1show.request_policy``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def _token_count(response: object, name: str) -> int:
    """Read one non-negative integer token count from the SDK's usage metadata, or 0.

    An absent metadata block, or a count that is missing or not a non-negative integer,
    is reported as zero. That is an under-report, never an invented number, and it never
    refuses an otherwise usable answer: discarding a paid-for generation because
    accounting is missing would be the worse failure.
    """
    usage = getattr(response, "usage_metadata", None)
    value = getattr(usage, name, None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _server_advised_delay(exc: BaseException) -> float | None:
    """The delta-seconds of a provider's ``Retry-After``, or ``None`` when unusable.

    The SDK keeps the transport response on its error, and every transport response
    exposes a case-insensitive header lookup, so the advice is read through that. Only
    the delta-seconds form is accepted: the HTTP-date form would have to be resolved
    against a clock, and this adapter owns no clock precisely so the policy layer's
    injected monotonic source stays the only one. Absent, non-numeric, negative, dated
    and absurd values are all reported as absent advice rather than guessed at.
    """
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    get_header = getattr(headers, "get", None)
    if not callable(get_header):
        return None
    raw = get_header("retry-after")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text.isascii() or not text.isdigit():
        return None
    significant = text.lstrip("0")
    if not significant:
        return 0.0
    if len(significant) > _MAX_ADVISED_DELAY_DIGITS:
        return None
    return float(significant)


def _classify_provider_failure(exc: BaseException) -> ModelError | None:
    """Map one provider failure to a typed, sanitized error, or ``None`` when unknown.

    ``None`` means "a failure class this adapter does not claim to understand", and the
    caller re-raises the original error untouched. That is deliberate: an unclassified
    failure is our own bug, and relabelling it as a transport failure would both hide it
    and invite the policy layer to retry it.

    The provider's own message is never read or formatted. Only the status code and the
    exception's class name are repeated, because a provider error body can echo the
    prompt back at us and a credential could sit in the same payload.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, int) and not isinstance(code, bool):
        if code == 429:
            return ModelRateLimitedError(
                "the model provider rate-limited the request (status 429)",
                retry_after_seconds=_server_advised_delay(exc),
            )
        if code == 408:
            return ModelTimeoutError(
                "the model provider reported a request timeout (status 408)", status_code=408
            )
        if 500 <= code < 600:
            return ModelServerError(
                f"the model provider failed with status {code}", status_code=code
            )
        return ModelError(
            f"the model provider refused the request with status {code}", status_code=code
        )
    # ``TimeoutError`` is an ``OSError``, so it must be told apart from a transport
    # failure before the broader check below.
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return ModelTimeoutError(f"the model call timed out ({type(exc).__name__})")
    if isinstance(exc, (httpx.TransportError, OSError)):
        return ModelTransportError(f"the model call could not be completed ({type(exc).__name__})")
    return None


class GoogleGenAIClient:
    """The ``ModelClient`` port as a thin adapter over an injected async ``google-genai`` client.

    The caller builds and owns the SDK client - ``genai.Client(api_key=...)`` at wiring
    time from ``CredentialsSettings.gemini_api_key`` - and this adapter never constructs,
    opens, closes or replaces it. It also never reads, stores or formats a credential:
    the only thing it does with the client is call ``client.aio.models.generate_content``.
    Nothing here inspects the client's configuration, so its ``repr`` (which a real SDK
    client may fill with an api key) is never rendered.

    Mapping, in one direction and back:

    * ``model_id`` -> the SDK ``model`` argument. It is injected with no default, so no
      model ID literal can live in this module.
    * ``prompt`` -> the SDK ``contents`` argument.
    * ``max_output_tokens`` -> a plain ``config`` mapping, the SDK's documented dict form.
    * the SDK's ``text`` -> ``ModelResponse.text``, preserved verbatim, including
      whitespace: only *blankness* is a refusal criterion.
    * ``usage_metadata.prompt_token_count`` and ``candidates_token_count`` -> the input
      and output counts.
    * ``ModelResponse.model_id`` echoes the **requested** id. The provider's own model
      naming (``model_version``) is never read, trusted or rewritten into our transcript.

    A missing, blank or non-text answer becomes :class:`ModelResponseError` rather than an
    empty turn. There is **no retry and no second timeout knob here**: retries belong to
    the injected policy layer, and ``request.timeout_seconds`` is enforced by
    :class:`SafeguardedModelClient`, so used alone this adapter has no deadline of ours
    against the SDK's own default.
    """

    def __init__(self, inner_client: Client) -> None:
        self._inner_client = inner_client

    def __repr__(self) -> str:
        # The inner client's own repr is deliberately not rendered: it may hold a key.
        return f"GoogleGenAIClient(inner_client={type(self._inner_client).__name__})"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Make exactly one SDK call and map its answer, or raise a typed failure."""
        response = await self._generate_once(request)
        return self._to_model_response(request, response)

    async def _generate_once(self, request: ModelRequest) -> object:
        """One SDK call, with every provider failure converted to a typed one.

        The raise happens after the handler has exited, so the original provider
        exception - whose message may embed the prompt - is neither ``__cause__`` nor
        ``__context__`` of the error the caller receives.
        """
        failure: ModelError
        try:
            return await self._inner_client.aio.models.generate_content(
                model=request.model_id,
                contents=request.prompt,
                config={"max_output_tokens": request.max_output_tokens},
            )
        except Exception as exc:
            typed = _classify_provider_failure(exc)
            if typed is None:
                raise
            failure = typed
        raise failure

    def _to_model_response(self, request: ModelRequest, response: object) -> ModelResponse:
        """Map one SDK response into the port's answer, refusing anything unusable."""
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ModelResponseError(
                "the model provider returned no usable text; an empty turn is refused"
            )
        return ModelResponse(
            model_id=request.model_id,
            text=text,
            input_tokens=_token_count(response, "prompt_token_count"),
            output_tokens=_token_count(response, "candidates_token_count"),
        )


def _add_usage(previous: ModelUsage, addition: ModelUsage) -> ModelUsage:
    """Sum two usages of the same model into one immutable accumulated record."""
    return ModelUsage(
        model_id=previous.model_id,
        input_tokens=previous.input_tokens + addition.input_tokens,
        output_tokens=previous.output_tokens + addition.output_tokens,
        total_tokens=previous.total_tokens + addition.total_tokens,
        attempts=previous.attempts + addition.attempts,
    )


class SafeguardedModelClient:
    """The ``ModelClient`` port with a deadline, a gate, bounded retries and usage accounting.

    **Ownership.** The caller owns the inner client, and this wrapper neither opens,
    closes nor replaces it during or after a request. There is deliberately no ``close``:
    the port has none, and releasing a caller-owned object is the caller's act, not this
    wrapper's. A nested policy layer multiplies the attempt budget, because each layer
    spends its own; the outermost wrapper is the one whose budget a caller is counting.

    **One deadline per attempt.** ``asyncio.timeout(request.timeout_seconds)`` wraps a
    single provider call and becomes :class:`ModelTimeoutError`. No second SDK-level
    timeout knob is invented, because two budgets would be two behaviours to reason
    about. The gate and the backoff sleep sit outside that deadline on purpose: queueing
    is not provider latency, so it must not be reported as a provider timeout, and a
    caller sleeping between attempts must not hold a slot another caller could use. The
    consequence is stated rather than hidden: the deadline bounds one provider call, not
    the whole ``generate`` call, so a caller that needs a total deadline bounds this
    coroutine itself with its own ``asyncio.timeout``.

    **A bounded gate.** ``asyncio.Semaphore(max_concurrency)``, and the size has no
    default: a default would either serialise silently or unlimit silently, and both are
    worse than an explicit number at the call site.

    **A bounded attempt budget.** ``policy.max_attempts`` attempts, with the wait for the
    attempt that just failed being
    ``policy.base_backoff_seconds * 2 ** (failed_attempt - 1)``, capped at
    ``policy.max_backoff_seconds``, with **no jitter**, spent through the injected
    ``MonotonicClock`` and never a private clock. ``RetryPolicy`` is reused as the single
    source of those three values. Its ``retryable_statuses`` and
    ``max_retry_after_seconds`` fields are deliberately unused here: retryability is
    decided by the typed failures above, never by an HTTP status, and there is no
    HTTP-date or ``Retry-After`` arithmetic on this path. Only rate-limited, server,
    timeout and transport failures are retried; a malformed or blank answer and any
    untyped failure are not. When the budget runs out, the **last** typed failure is
    raised.

    **Measurement, not a ceiling.** Usage accumulates per *requested* model id (the audit
    key is what the caller asked for, never an inner client's relabelling), the optional
    ``on_usage`` observer is called once per successful call, and the optional
    ``alert_after_tokens`` threshold raises exactly one warning through the module's
    redacting-filter-ready logger. Warn once, at the crossing: a crossed threshold is a
    state, not an event to repeat on every later call. The threshold compares the
    accumulated total across **every** model called through this wrapper, while
    :attr:`usage_totals` stays per model. **This is not a hard spend limit and no cost
    stop exists before F13.**
    """

    def __init__(
        self,
        inner: ModelClient,
        *,
        clock: MonotonicClock,
        max_concurrency: int,
        policy: RetryPolicy,
        alert_after_tokens: int | None = None,
        on_usage: Callable[[ModelUsage], None] | None = None,
    ) -> None:
        self._inner = inner
        self._clock = clock
        self._max_concurrency = _positive_int(max_concurrency, "max_concurrency")
        self._gate = asyncio.Semaphore(self._max_concurrency)
        self._policy = policy
        self._alert_after_tokens = (
            None
            if alert_after_tokens is None
            else _positive_int(alert_after_tokens, "alert_after_tokens")
        )
        if on_usage is not None and not callable(on_usage):
            raise TypeError("on_usage must be callable when it is provided")
        self._on_usage = on_usage
        self._usage: dict[str, ModelUsage] = {}
        self._total_tokens = 0
        self._alerted = False

    def __repr__(self) -> str:
        # Never the inner client's repr, which may hold a credential.
        return (
            f"SafeguardedModelClient(inner={type(self._inner).__name__}, "
            f"max_concurrency={self._max_concurrency}, "
            f"alert_after_tokens={self._alert_after_tokens!r}, "
            f"measured_tokens={self._total_tokens})"
        )

    @property
    def usage_totals(self) -> tuple[ModelUsage, ...]:
        """Accumulated measured usage per requested model id, ordered by model id.

        Empty until the first successful call. Per model id because a single blended
        total would hide which model was actually called, and the id itself is the
        request's: an inner client can relabel an answer, but it cannot relabel what the
        caller asked for. **A measurement, not a spend limit.**
        """
        return tuple(self._usage[model_id] for model_id in sorted(self._usage))

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Attempt the call under the whole policy, and account for a success exactly once."""
        policy = self._policy
        attempt = 0
        while True:
            attempt += 1
            failure: ModelError
            try:
                response = await self._attempt(request)
            except TimeoutError:
                failure = ModelTimeoutError(
                    "the model call did not finish within request.timeout_seconds"
                )
            except ModelError as error:
                failure = error
            else:
                self._record(request, response, attempt)
                return response
            if not failure.retryable or attempt >= policy.max_attempts:
                raise failure
            await self._clock.sleep(self._backoff(attempt))

    async def _attempt(self, request: ModelRequest) -> ModelResponse:
        """One attempt: a slot from the gate, then one provider call under its deadline."""
        async with self._gate:
            async with asyncio.timeout(request.timeout_seconds):
                return await self._inner.generate(request)

    def _backoff(self, failed_attempt: int) -> float:
        """``base * 2 ** (failed_attempt - 1)`` capped at the policy's maximum.

        The loop mirrors ``RetryingHttpClient._backoff_wait``'s arithmetic - doubling only
        until the cap is reached, so a long attempt budget can never build an unbounded
        integer or overflow converting one to a float - and it is deliberately the only
        place this module computes a wait. There is no random source here, so every
        offline test sees the same durations the caller will.
        """
        maximum = self._policy.max_backoff_seconds
        wait = self._policy.base_backoff_seconds
        for _ in range(failed_attempt - 1):
            if wait >= maximum:
                break
            wait *= 2.0
        return min(wait, maximum)

    def _record(self, request: ModelRequest, response: ModelResponse, attempts: int) -> None:
        """Accumulate the measured usage, report it once, then check the alert threshold."""
        usage = ModelUsage(
            model_id=request.model_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.input_tokens + response.output_tokens,
            attempts=attempts,
        )
        previous = self._usage.get(usage.model_id)
        self._usage[usage.model_id] = usage if previous is None else _add_usage(previous, usage)
        self._total_tokens += usage.total_tokens
        self._observe(usage)
        self._warn_when_crossed(usage.model_id)

    def _observe(self, usage: ModelUsage) -> None:
        """Call the caller's observer with the per-call usage, never losing the answer.

        An observer that raises must not discard a successful and already-paid-for
        answer - and, worse, an exception from here could be retried by an outer policy
        and spend twice for one answer. The failure is logged by class name only, so an
        observer that embeds provider text in its own message cannot turn that text into
        a log line.
        """
        observer = self._on_usage
        if observer is None:
            return
        try:
            observer(usage)
        except Exception as exc:  # noqa: BLE001 -- a reporter must never fail the call
            _LOGGER.warning(
                "the model usage observer failed (%s); the measured answer is still returned",
                type(exc).__name__,
            )

    def _warn_when_crossed(self, model_id: str) -> None:
        """Warn once, on the call whose accumulated total reaches the caller's threshold.

        Reaching the threshold counts as crossing it. The warning fires once because a
        crossed threshold is a state, not a repeated event; a caller that wants a
        per-call reminder can derive it from :attr:`usage_totals` itself.
        """
        threshold = self._alert_after_tokens
        if threshold is None or self._alerted or self._total_tokens < threshold:
            return
        self._alerted = True
        _LOGGER.warning(
            "measured model usage reached %d tokens for model %s, reaching the caller's "
            "alert threshold of %s; measured usage is not a hard spend limit and no cost "
            "stop exists before F13",
            self._total_tokens,
            model_id,
            threshold,
        )
