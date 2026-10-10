"""Offline acceptance tests for the pacing and retry policy.

No network and no wall-clock sleeping: the shared rate limiter and the retry
backoff both run on an injected monotonic clock, so every wait is a recorded
virtual duration instead of real elapsed time. The only place the two clocks meet
is an HTTP-date ``Retry-After``, which is resolved against a frozen UTC clock.

One parameterized body runs the retry-and-pacing semantics over BOTH inner
clients - the shipped ``FakeHttpClient`` and a ``MockTransport``-backed
``HttpxJsonClient`` - so a divergence between the fake and the real adapter
cannot hide behind a single implementation.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import email.utils
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from f1show.fakes import FakeHttpClient, FakeMonotonicClock, FrozenClock
from f1show.http import HttpxJsonClient
from f1show.ports import (
    HttpDecodeError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
)
from f1show.request_policy import (
    PacingPolicy,
    RateLimiter,
    RetryPolicy,
    RetryingHttpClient,
)

URL = "https://example.invalid/v1/sessions"
OTHER_URL = "https://example.invalid/v1/drivers"
TOKEN_URL = "https://example.invalid/token"  # noqa: S105 (fictional endpoint, not a credential)
PARAMS = {"session_key": "9462"}
FORM = {"grant_type": "client_credentials", "client_id": "placeholder-client"}
CALL_HEADERS = {"Authorization": "Bearer placeholder-token-not-a-real-credential"}
MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=dt.timezone.utc)


def response(
    status: int, *, headers: Mapping[str, str] | None = None, payload: Any = None
) -> HttpResponse:
    """Build one source answer with canonical (lower-case) headers."""
    return HttpResponse(
        status_code=status,
        headers=dict(headers) if headers is not None else {},
        payload=payload,
    )


@dataclass(frozen=True)
class Outcome:
    """One scripted source answer, expressed once and served by both inner clients."""

    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    payload: Any = None


def build_inner(
    implementation: str, outcomes: Sequence[Outcome]
) -> tuple[Any, Callable[[], int]]:
    """Build one inner client that serves the scripted outcomes in order.

    Returns the client plus a probe that reports how many attempts it actually
    received, so the same assertions hold for both implementations.
    """
    if implementation == "fake":
        fake = FakeHttpClient()
        for outcome in outcomes:
            fake.enqueue(
                URL,
                response(outcome.status, headers=outcome.headers, payload=outcome.payload),
                params=PARAMS,
            )
        return fake, lambda: len(fake.calls)

    queue = list(outcomes)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        # An exhausted queue raises IndexError, which fails the test loudly.
        next_outcome = queue.pop(0)
        return httpx.Response(
            next_outcome.status, headers=next_outcome.headers, json=next_outcome.payload
        )

    adapter = HttpxJsonClient(
        timeout_seconds=5.0, max_response_bytes=4096, transport=httpx.MockTransport(handler)
    )
    return adapter, lambda: len(seen)


def fake_retrying(
    outcomes: Sequence[HttpResponse | BaseException],
    *,
    per_second: int = 3,
    per_minute: int = 30,
    policy: RetryPolicy | None = None,
    utc_clock: FrozenClock | None = None,
) -> tuple[RetryingHttpClient, FakeHttpClient, FakeMonotonicClock]:
    """Build a retrying client over the fake, with both clocks observable."""
    inner = FakeHttpClient()
    for outcome in outcomes:
        inner.enqueue(URL, outcome, params=PARAMS)
    monotonic = FakeMonotonicClock()
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(per_second=per_second, per_minute=per_minute), monotonic),
        retry_policy=policy if policy is not None else RetryPolicy(),
        clock=utc_clock if utc_clock is not None else FrozenClock(MOMENT),
    )
    return client, inner, monotonic


def fake_retrying_form(
    outcomes: Sequence[HttpResponse | BaseException],
    *,
    per_second: int = 3,
    per_minute: int = 30,
    policy: RetryPolicy | None = None,
    utc_clock: FrozenClock | None = None,
) -> tuple[RetryingHttpClient, FakeHttpClient, FakeMonotonicClock]:
    """The form-POST twin of ``fake_retrying``: the same policy, a different method."""
    inner = FakeHttpClient()
    for outcome in outcomes:
        inner.enqueue_form(TOKEN_URL, outcome, form=FORM)
    monotonic = FakeMonotonicClock()
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(per_second=per_second, per_minute=per_minute), monotonic),
        retry_policy=policy if policy is not None else RetryPolicy(),
        clock=utc_clock if utc_clock is not None else FrozenClock(MOMENT),
    )
    return client, inner, monotonic


class BlockingMonotonicClock:
    """A monotonic seam that parks inside ``sleep`` so a test can cancel it."""

    def __init__(self) -> None:
        self._now = 0.0
        self.entered = asyncio.Event()

    def monotonic(self) -> float:
        return self._now

    async def sleep(self, seconds: float) -> None:
        self.entered.set()
        await asyncio.Event().wait()


class CountingInner:
    """Delegates to a fake and records how the retrying client drove it."""
    def __init__(self, inner: FakeHttpClient) -> None:
        self.inner = inner
        self.close_calls = 0

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return await self.inner.get_json(url, params=params, headers=headers)

    async def post_form_json(
        self,
        url: str,
        *,
        form: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return await self.inner.post_form_json(url, form=form, headers=headers)

    async def close(self) -> None:
        self.close_calls += 1
        await self.inner.close()


class TimestampingInner(FakeHttpClient):
    """A fake that records the virtual instant of every attempt it receives.

    A sleep count alone cannot prove a retry was scheduled *early*; the call
    timeline can, because an over-budget advice must leave the single attempt at
    ``t=0`` and never move the clock.
    """

    def __init__(self, clock: FakeMonotonicClock) -> None:
        super().__init__()
        self._clock = clock
        self.timestamps: list[float] = []

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        self.timestamps.append(self._clock.monotonic())
        return await super().get_json(url, params=params, headers=headers)


# --- policy values ------------------------------------------------------------


def test_pacing_policy_defaults_to_the_documented_free_tier() -> None:
    policy = PacingPolicy()
    assert (policy.per_second, policy.per_minute) == (3, 30)


@pytest.mark.parametrize("field_name", ["per_second", "per_minute"])
@pytest.mark.parametrize("bad", [0, -1, True, 2.5, "3"])
def test_pacing_policy_rejects_non_positive_or_non_integer_limits(
    field_name: str, bad: Any
) -> None:
    with pytest.raises(ValueError):
        PacingPolicy(**{field_name: bad})


def test_pacing_policy_rejects_a_per_second_limit_above_the_per_minute_limit() -> None:
    with pytest.raises(ValueError):
        PacingPolicy(per_second=31, per_minute=30)


def test_retry_policy_carries_the_documented_defaults() -> None:
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.base_backoff_seconds == 0.5
    assert policy.max_backoff_seconds == 8.0
    assert policy.max_retry_after_seconds == 60.0
    assert policy.retryable_statuses == frozenset({408, 429, 500, 502, 503, 504})


@pytest.mark.parametrize("bad", [0, -1, True, 2.0])
def test_retry_policy_requires_at_least_one_attempt(bad: Any) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=bad)


@pytest.mark.parametrize(
    "field_name", ["base_backoff_seconds", "max_backoff_seconds", "max_retry_after_seconds"]
)
@pytest.mark.parametrize("bad", [0, -0.5, float("inf"), float("nan")])
def test_retry_policy_seconds_must_be_positive_and_finite(field_name: str, bad: Any) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(**{field_name: bad})


def test_retry_policy_rejects_a_max_backoff_below_the_base() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(base_backoff_seconds=2.0, max_backoff_seconds=1.0)


@pytest.mark.parametrize("bad_status", [True, 0, -1])
def test_retry_policy_rejects_a_malformed_retryable_status(bad_status: Any) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(retryable_statuses=frozenset({bad_status}))


# --- pacing -------------------------------------------------------------------


@pytest.mark.anyio
async def test_first_slot_is_immediate_and_the_next_slot_sleeps_the_exact_window() -> None:
    monotonic = FakeMonotonicClock()
    limiter = RateLimiter(PacingPolicy(per_second=1, per_minute=30), monotonic)
    await limiter.wait_for_slot()
    assert monotonic.sleeps == []
    assert monotonic.monotonic() == 0.0
    await limiter.wait_for_slot()
    assert monotonic.sleeps == [1.0]
    assert monotonic.monotonic() == 1.0


@pytest.mark.anyio
async def test_both_windows_apply_at_once_and_the_longer_wait_wins() -> None:
    monotonic = FakeMonotonicClock()
    limiter = RateLimiter(PacingPolicy(per_second=2, per_minute=3), monotonic)
    await limiter.wait_for_slot()  # t=0
    await limiter.wait_for_slot()  # t=0: the second window admits two at once
    await limiter.wait_for_slot()  # per-second: 1.0; per-minute: none
    assert (monotonic.sleeps, monotonic.monotonic()) == ([1.0], 1.0)
    await limiter.wait_for_slot()  # per-second: 0.0; per-minute: 59.0
    assert (monotonic.sleeps, monotonic.monotonic()) == ([1.0, 59.0], 60.0)
    await limiter.wait_for_slot()  # both windows have room again
    assert (monotonic.sleeps, monotonic.monotonic()) == ([1.0, 59.0], 60.0)


@pytest.mark.anyio
async def test_one_shared_limiter_budgets_two_endpoints_together() -> None:
    """Pacing is a client-wide budget, so a second endpoint yields to the first."""
    monotonic = FakeMonotonicClock()
    limiter = RateLimiter(PacingPolicy(per_second=1, per_minute=30), monotonic)
    inner = FakeHttpClient()
    inner.register(URL, [], params=PARAMS)
    inner.register(OTHER_URL, [], params=PARAMS)
    first = RetryingHttpClient(
        inner, limiter=limiter, retry_policy=RetryPolicy(), clock=FrozenClock(MOMENT)
    )
    second = RetryingHttpClient(
        inner, limiter=limiter, retry_policy=RetryPolicy(), clock=FrozenClock(MOMENT)
    )
    await first.get_json(URL, params=PARAMS)
    assert monotonic.sleeps == []
    await second.get_json(OTHER_URL, params=PARAMS)
    assert monotonic.sleeps == [1.0], "the second endpoint waited on the first endpoint's slot"


# --- retries ------------------------------------------------------------------


@pytest.mark.parametrize("implementation", ["fake", "adapter"])
@pytest.mark.anyio
async def test_retry_and_pacing_are_identical_over_both_inner_clients(
    implementation: str,
) -> None:
    """One shared body: retry a 500, then the retry must take its own pacing slot."""
    inner, calls = build_inner(
        implementation, [Outcome(500), Outcome(200, payload=[{"session_key": 9462}])]
    )
    monotonic = FakeMonotonicClock()
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(per_second=1, per_minute=30), monotonic),
        retry_policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.25, max_backoff_seconds=8.0),
        clock=FrozenClock(MOMENT),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert (result.status_code, result.payload) == (200, [{"session_key": 9462}])
    # 0.25s backoff, then the pacing wait the second attempt still owes.
    assert monotonic.sleeps == [0.25, 0.75]
    assert calls() == 2
    await client.close()


@pytest.mark.anyio
async def test_a_retryable_status_is_retried_after_the_exact_deterministic_backoff() -> None:
    client, inner, monotonic = fake_retrying(
        [response(500), response(200, payload=[{"session_key": 9462}])],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [0.5]
    assert len(inner.calls) == 2


@pytest.mark.anyio
async def test_backoff_doubles_per_failed_attempt_without_jitter() -> None:
    client, inner, monotonic = fake_retrying(
        [response(500), response(500), response(200)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [0.5, 1.0]
    assert len(inner.calls) == 3


@pytest.mark.anyio
async def test_backoff_is_capped_at_the_configured_maximum() -> None:
    client, inner, monotonic = fake_retrying(
        [response(503), response(503), response(200)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=3.0, max_backoff_seconds=5.0),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [3.0, 5.0], "6.0 must be capped to the configured 5.0"
    assert len(inner.calls) == 3


@pytest.mark.anyio
async def test_exhausting_attempts_returns_the_last_retryable_response_instead_of_raising() -> None:
    client, inner, monotonic = fake_retrying(
        [response(503), response(503), response(503)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 503
    assert monotonic.sleeps == [0.5, 1.0]
    assert len(inner.calls) == 3


@pytest.mark.anyio
async def test_retry_after_delta_seconds_wins_over_a_smaller_backoff() -> None:
    client, inner, monotonic = fake_retrying(
        [response(429, headers={"Retry-After": "2"}), response(200)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [2.0], "never retry earlier than the server advised"
    assert len(inner.calls) == 2


@pytest.mark.anyio
async def test_an_over_budget_retry_after_causes_no_retry_and_no_sleep() -> None:
    client, inner, monotonic = fake_retrying(
        [response(429, headers={"Retry-After": "120"}), response(200)],
        policy=RetryPolicy(
            max_attempts=3,
            base_backoff_seconds=0.5,
            max_backoff_seconds=8.0,
            max_retry_after_seconds=60.0,
        ),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 429
    assert result.header("Retry-After") == "120"
    assert monotonic.sleeps == []
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_retry_after_http_date_is_resolved_against_the_utc_clock() -> None:
    advised = email.utils.format_datetime(MOMENT + dt.timedelta(seconds=5), usegmt=True)
    client, inner, monotonic = fake_retrying(
        [response(429, headers={"Retry-After": advised}), response(200)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
        utc_clock=FrozenClock(MOMENT),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [5.0]
    assert len(inner.calls) == 2


@pytest.mark.anyio
async def test_a_past_http_date_never_retries_before_the_backoff() -> None:
    advised = email.utils.format_datetime(MOMENT - dt.timedelta(seconds=30), usegmt=True)
    client, inner, monotonic = fake_retrying(
        [response(503, headers={"Retry-After": advised}), response(200)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
        utc_clock=FrozenClock(MOMENT),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [0.5]
    assert len(inner.calls) == 2


@pytest.mark.parametrize("advice", ["soon", "", "-1", "nan", "inf"])
@pytest.mark.anyio
async def test_an_unparseable_retry_after_falls_back_to_the_backoff(advice: str) -> None:
    client, inner, monotonic = fake_retrying(
        [response(429, headers={"Retry-After": advice}), response(200)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [0.5]
    assert len(inner.calls) == 2


@pytest.mark.anyio
async def test_a_non_retryable_status_returns_immediately() -> None:
    client, inner, monotonic = fake_retrying([response(400), response(200)])
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 400
    assert monotonic.sleeps == []
    assert len(inner.calls) == 1


@pytest.mark.parametrize(
    "error", [HttpDecodeError("body is not one JSON document"), HttpResponseTooLargeError("too big")]
)
@pytest.mark.anyio
async def test_deterministic_body_failures_are_never_retried(error: Exception) -> None:
    client, inner, monotonic = fake_retrying(
        [error, response(200)], policy=RetryPolicy(max_attempts=3)
    )
    with pytest.raises(type(error)):
        await client.get_json(URL, params=PARAMS)
    assert monotonic.sleeps == []
    assert len(inner.calls) == 1


@pytest.mark.parametrize("error_type", [HttpTransportError, HttpTimeoutError])
@pytest.mark.anyio
async def test_transport_and_timeout_errors_are_retried_then_re_raised(
    error_type: type[Exception],
) -> None:
    client, inner, monotonic = fake_retrying(
        [error_type("boom"), error_type("boom")],
        policy=RetryPolicy(max_attempts=2, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    with pytest.raises(error_type):
        await client.get_json(URL, params=PARAMS)
    assert monotonic.sleeps == [0.5]
    assert len(inner.calls) == 2


@pytest.mark.parametrize("error_type", [HttpTransportError, HttpTimeoutError])
@pytest.mark.anyio
async def test_a_transient_error_recovers_on_the_next_attempt(error_type: type[Exception]) -> None:
    client, inner, monotonic = fake_retrying(
        [error_type("boom"), response(200)], policy=RetryPolicy(max_attempts=3)
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [0.5]
    assert len(inner.calls) == 2


@pytest.mark.anyio
async def test_every_retry_attempt_passes_back_through_the_limiter() -> None:
    client, inner, monotonic = fake_retrying(
        [response(500), response(200)],
        per_second=1,
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.25, max_backoff_seconds=8.0),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [0.25, 0.75], "the retry took its own pacing slot"
    assert len(inner.calls) == 2


@pytest.mark.anyio
async def test_cancellation_during_a_backoff_sleep_propagates_and_stops_the_loop() -> None:
    inner = FakeHttpClient()
    inner.enqueue(URL, response(500), params=PARAMS)
    inner.enqueue(URL, response(200), params=PARAMS)
    parking = BlockingMonotonicClock()
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(), parking),
        retry_policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
        clock=FrozenClock(MOMENT),
    )
    task = asyncio.create_task(client.get_json(URL, params=PARAMS))
    await asyncio.wait_for(parking.entered.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()
    assert len(inner.calls) == 1, "a cancelled backoff must not produce another attempt"


@pytest.mark.anyio
async def test_close_is_idempotent_delegates_once_and_refuses_requests_before_the_inner() -> None:
    inner = FakeHttpClient()
    inner.register(URL, [{"session_key": 9462}], params=PARAMS)
    counting = CountingInner(inner)
    client = RetryingHttpClient(
        counting,
        limiter=RateLimiter(PacingPolicy(), FakeMonotonicClock()),
        retry_policy=RetryPolicy(),
        clock=FrozenClock(MOMENT),
    )
    assert (await client.get_json(URL, params=PARAMS)).status_code == 200
    assert len(inner.calls) == 1
    await client.close()
    await client.close()
    assert counting.close_calls == 1, "close must reach the inner client exactly once"
    with pytest.raises(RuntimeError):
        await client.get_json(URL, params=PARAMS)
    assert len(inner.calls) == 1, "a post-close request must never reach the inner client"
    await client.close()
    assert counting.close_calls == 1
    with pytest.raises(RuntimeError):
        await inner.get_json(URL, params=PARAMS)


# --- F03c-2-R1 D1: valid huge delta-seconds must be over budget, not absent ---

#: Every entry is a syntactically valid RFC 7231 ``1*DIGIT`` value that must read as
#: over budget. The first four overflow ``float()`` to ``inf`` on the pre-fix bytes,
#: which is exactly the defect: absent advice falls back to a 0.5s backoff.
HUGE_VALID_DELAYS = [
    pytest.param("9" * 309, id="309-nines-float-overflow-boundary"),
    pytest.param("9" * 400, id="400-nines"),
    pytest.param("9" * 5000, id="5000-nines-past-the-int-digit-limit"),
    pytest.param("0" * 4300 + "9" * 309, id="leading-zeros-then-309-nines"),
    pytest.param("0" * 5000 + "10000", id="long-leading-zeros-over-budget"),
    pytest.param("61", id="one-past-the-ceiling"),
]


@pytest.mark.parametrize("advice", HUGE_VALID_DELAYS)
@pytest.mark.anyio
async def test_a_valid_huge_delay_seconds_header_is_over_budget_not_absent(
    advice: str,
) -> None:
    """A valid ``1*DIGIT`` value past the ceiling is over budget, never absent.

    It must not reach ``float()`` (which overflows to ``inf`` past ~308 significant
    digits) nor a whole-string ``int()`` (which Python refuses past its digit limit),
    and long leading zeros must not hide a huge or a small value.
    """
    monotonic = FakeMonotonicClock()
    inner = TimestampingInner(monotonic)
    inner.enqueue(URL, response(429, headers={"Retry-After": advice}), params=PARAMS)
    inner.enqueue(URL, response(200), params=PARAMS)
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(), monotonic),
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_backoff_seconds=0.5,
            max_backoff_seconds=8.0,
            max_retry_after_seconds=60.0,
        ),
        clock=FrozenClock(MOMENT),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 429, "the last response is data, not a retry"
    assert len(inner.calls) == 1, "an over-budget advice must not retry"
    assert monotonic.sleeps == [], "an over-budget advice must not sleep"
    assert inner.timestamps == [0.0], "no retry was ever scheduled"


@pytest.mark.parametrize(
    ("advice", "expected_sleep"),
    [
        pytest.param("0" * 5000 + "2", 2.0, id="long-leading-zeros-then-2"),
        pytest.param("0" * 5000, 0.5, id="all-zero-long-value-keeps-the-backoff"),
        pytest.param("60", 60.0, id="exactly-the-ceiling-is-allowed"),
    ],
)
@pytest.mark.anyio
async def test_small_delay_seconds_behind_long_leading_zeros_are_honoured(
    advice: str, expected_sleep: float
) -> None:
    """Leading zeros are not significant: the same values behave as if unpadded.

    ``0`` repair defaults to the backoff, a padded small value is honoured, and a
    value exactly at the ceiling is still allowed to retry.
    """
    client, inner, monotonic = fake_retrying(
        [response(429, headers={"Retry-After": advice}), response(200)],
        policy=RetryPolicy(
            max_attempts=3,
            base_backoff_seconds=0.5,
            max_backoff_seconds=8.0,
            max_retry_after_seconds=60.0,
        ),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 200
    assert monotonic.sleeps == [expected_sleep]
    assert len(inner.calls) == 2


# --- F03c-2-R1 D2: exponential backoff saturates before any overflow ---

#: Far past the ~1025-failure point where ``base * 2**steps`` overflows a float.
_LARGE_ATTEMPTS = 1100
#: Large enough that the rate windows never add a pacing sleep to ``monotonic.sleeps``.
_NO_PACING = 10**9


@pytest.mark.anyio
async def test_a_large_attempt_budget_saturates_backoff_without_overflow_on_statuses() -> None:
    """A >1025-attempt status run must return the last 503, never raise OverflowError."""
    client, inner, monotonic = fake_retrying(
        [response(503)] * _LARGE_ATTEMPTS,
        per_second=_NO_PACING,
        per_minute=_NO_PACING,
        policy=RetryPolicy(
            max_attempts=_LARGE_ATTEMPTS, base_backoff_seconds=0.5, max_backoff_seconds=8.0
        ),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 503
    assert len(inner.calls) == _LARGE_ATTEMPTS
    assert len(monotonic.sleeps) == _LARGE_ATTEMPTS - 1, "no sleep follows the final attempt"
    assert monotonic.sleeps[:4] == [0.5, 1.0, 2.0, 4.0]
    assert set(monotonic.sleeps[4:]) == {8.0}, "backoff saturates at the existing cap"


@pytest.mark.anyio
async def test_a_large_attempt_budget_re_raises_the_final_error_object_without_overflow() -> None:
    """Exhaustion must re-raise the last typed error itself, not an OverflowError."""
    error = HttpTransportError("persistent transport failure")
    client, inner, monotonic = fake_retrying(
        [error] * _LARGE_ATTEMPTS,
        per_second=_NO_PACING,
        per_minute=_NO_PACING,
        policy=RetryPolicy(
            max_attempts=_LARGE_ATTEMPTS, base_backoff_seconds=0.5, max_backoff_seconds=8.0
        ),
    )
    with pytest.raises(HttpTransportError) as excinfo:
        await client.get_json(URL, params=PARAMS)
    assert excinfo.value is error, "the final typed error must keep its identity"
    assert len(inner.calls) == _LARGE_ATTEMPTS
    assert monotonic.sleeps[-1] == 8.0


@pytest.mark.anyio
async def test_extreme_finite_base_and_cap_saturate_without_huge_ratio_allocation() -> None:
    """The widest finite exponent range saturates without an unbounded pow.

    ``base`` is tiny and ``cap`` is huge, so the doubling count is ~1994 and a
    naive ``base * 2**steps`` would overflow converting the integer to a float.
    The ceiling is raised to ``cap`` so the over-budget rule does not end the run
    early; nothing here uses real time or a real request.
    """
    attempts = 2100
    base = 1e-300
    cap = 1e300
    client, inner, monotonic = fake_retrying(
        [response(503)] * attempts,
        per_second=_NO_PACING,
        per_minute=_NO_PACING,
        policy=RetryPolicy(
            max_attempts=attempts,
            base_backoff_seconds=base,
            max_backoff_seconds=cap,
            max_retry_after_seconds=cap,
        ),
    )
    result = await client.get_json(URL, params=PARAMS)
    assert result.status_code == 503
    assert len(inner.calls) == attempts
    assert all(math.isfinite(wait) for wait in monotonic.sleeps), "no wait may be infinite"
    assert monotonic.sleeps[-1] == cap, "backoff saturates exactly at the configured cap"


# --- F03d-1: the retrying client must pace and retry a form POST exactly as it does
# --- a GET, on the same shared limiter and the same policy values.


@pytest.mark.anyio
async def test_retrying_get_forwards_request_headers_to_the_inner_client() -> None:
    inner = FakeHttpClient()
    inner.register(URL, [{"session_key": 9462}], params=PARAMS)
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(), FakeMonotonicClock()),
        retry_policy=RetryPolicy(),
        clock=FrozenClock(MOMENT),
    )
    result = await client.get_json(URL, params=PARAMS, headers=CALL_HEADERS)
    assert result.status_code == 200
    assert inner.request_headers == [dict(CALL_HEADERS)]


@pytest.mark.anyio
async def test_get_and_post_share_one_pacing_budget() -> None:
    inner = FakeHttpClient()
    inner.register(URL, [], params=PARAMS)
    inner.register_form(TOKEN_URL, [], form=FORM)
    monotonic = FakeMonotonicClock()
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(per_second=1, per_minute=30), monotonic),
        retry_policy=RetryPolicy(),
        clock=FrozenClock(MOMENT),
    )
    await client.get_json(URL, params=PARAMS)
    assert monotonic.sleeps == []
    await client.post_form_json(TOKEN_URL, form=FORM, headers=CALL_HEADERS)
    assert monotonic.sleeps == [1.0], "the POST waited on the GET's slot: one shared budget"
    assert inner.request_headers[-1] == dict(CALL_HEADERS)


@pytest.mark.anyio
async def test_post_form_json_backs_off_and_takes_its_own_pacing_slot_on_retry() -> None:
    client, inner, monotonic = fake_retrying_form(
        [response(500), response(200, payload={"access_token": "t"})],
        per_second=1,
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.25, max_backoff_seconds=8.0),
    )
    result = await client.post_form_json(TOKEN_URL, form=FORM)
    assert (result.status_code, result.payload) == (200, {"access_token": "t"})
    assert monotonic.sleeps == [0.25, 0.75], "same backoff, and the retry takes its own slot"
    assert len(inner.post_calls) == 2


@pytest.mark.parametrize(
    ("status", "expected_calls", "expected_sleeps"),
    [
        pytest.param(500, 2, [0.5], id="retryable-500"),
        pytest.param(408, 2, [0.5], id="retryable-408"),
        pytest.param(400, 1, [], id="non-retryable-400"),
        pytest.param(302, 1, [], id="redirect-not-retried"),
    ],
)
@pytest.mark.anyio
async def test_post_form_json_uses_the_same_retryable_status_classification(
    status: int, expected_calls: int, expected_sleeps: list[float]
) -> None:
    client, inner, monotonic = fake_retrying_form(
        [response(status), response(200)], policy=RetryPolicy(max_attempts=3)
    )
    result = await client.post_form_json(TOKEN_URL, form=FORM)
    assert len(inner.post_calls) == expected_calls
    assert monotonic.sleeps == expected_sleeps
    assert result.status_code == (200 if expected_calls == 2 else status)


@pytest.mark.anyio
async def test_post_form_json_never_retries_earlier_than_the_server_advice() -> None:
    client, inner, monotonic = fake_retrying_form(
        [response(429, headers={"Retry-After": "2"}), response(200)],
        policy=RetryPolicy(max_attempts=3, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    result = await client.post_form_json(TOKEN_URL, form=FORM)
    assert result.status_code == 200
    assert monotonic.sleeps == [2.0]
    assert len(inner.post_calls) == 2


@pytest.mark.parametrize("error_type", [HttpTransportError, HttpTimeoutError])
@pytest.mark.anyio
async def test_post_form_json_retries_transport_and_timeout_then_re_raises(
    error_type: type[Exception],
) -> None:
    client, inner, monotonic = fake_retrying_form(
        [error_type("boom"), error_type("boom")],
        policy=RetryPolicy(max_attempts=2, base_backoff_seconds=0.5, max_backoff_seconds=8.0),
    )
    with pytest.raises(error_type):
        await client.post_form_json(TOKEN_URL, form=FORM)
    assert monotonic.sleeps == [0.5]
    assert len(inner.post_calls) == 2


@pytest.mark.parametrize(
    "error", [HttpDecodeError("body is not one JSON document"), HttpResponseTooLargeError("too big")]
)
@pytest.mark.anyio
async def test_post_form_json_never_retries_a_deterministic_body_failure(error: Exception) -> None:
    client, inner, monotonic = fake_retrying_form([error, response(200)], policy=RetryPolicy(3))
    with pytest.raises(type(error)):
        await client.post_form_json(TOKEN_URL, form=FORM)
    assert monotonic.sleeps == []
    assert len(inner.post_calls) == 1


@pytest.mark.anyio
async def test_close_refuses_a_form_post_before_the_inner_client_is_reached() -> None:
    inner = FakeHttpClient()
    inner.register_form(TOKEN_URL, {"access_token": "t"}, form=FORM)
    client = RetryingHttpClient(
        inner,
        limiter=RateLimiter(PacingPolicy(), FakeMonotonicClock()),
        retry_policy=RetryPolicy(),
        clock=FrozenClock(MOMENT),
    )
    await client.close()
    await client.close()
    with pytest.raises(RuntimeError):
        await client.post_form_json(TOKEN_URL, form=FORM)
    assert inner.post_calls == [], "a post-close request must never reach the inner client"
