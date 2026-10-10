"""Pacing and bounded retries for the one outbound HTTP boundary.

Two independent clocks are involved and they must not be confused. ``Clock`` (UTC)
stamps observations; the *monotonic* seam times every wait. Pacing and backoff only
compare differences, so they run on the monotonic source, and a policy asks ``Clock``
for the current UTC instant in exactly one place: resolving an HTTP-date
``Retry-After``.

Pacing is a **global** budget, not a per-endpoint one. The documented free tier is a
property of the client, not of the URL, so one :class:`RateLimiter` is meant to be
shared by every endpoint a sync writer calls; giving each endpoint its own limiter
would grant a 3-per-second allowance per URL and breach the real limit.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import parsedate_to_datetime

from f1show.ports import (
    Clock,
    HttpClient,
    HttpResponse,
    HttpTimeoutError,
    HttpTransportError,
    MonotonicClock,
)

_SECONDS_PER_SECOND = 1.0
_SECONDS_PER_MINUTE = 60.0

#: Statuses worth retrying: a timeout-ish status, the rate-limit status and the
#: 5xx family that is expected to be transient. A 4xx other than 408/429 is a
#: request problem and repeating it cannot help.
_DEFAULT_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


def _require_positive_int(value: object, name: str) -> int:
    """Return ``value`` as a positive ``int``, explicitly refusing ``bool``.

    ``True`` is an ``int`` in Python, but a boolean limit is a bug rather than a
    value of 1, so bools are rejected rather than silently accepted.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int, got {value!r}")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def _require_positive_seconds(value: object, name: str) -> float:
    """Return ``value`` as a positive finite number of seconds."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number of seconds, got {value!r}")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{name} must be a positive finite number of seconds, got {value!r}")
    return seconds


@dataclass(frozen=True)
class PacingPolicy:
    """Both documented request windows of the unauthenticated OpenF1 free tier.

    The defaults are the published free limits - 3 requests per second and 30 per
    minute (``docs/EXTERNAL-CONTRACTS.md``) - and both apply at once, so a burst that
    fits the minute limit still has to fit the second one.
    """

    per_second: int = 3
    per_minute: int = 30

    def __post_init__(self) -> None:
        per_second = _require_positive_int(self.per_second, "per_second")
        per_minute = _require_positive_int(self.per_minute, "per_minute")
        if per_second > per_minute:
            raise ValueError(
                f"per_second ({per_second}) must not exceed per_minute ({per_minute}): "
                "a second window stricter than the minute window is contradictory"
            )


@dataclass(frozen=True)
class RetryPolicy:
    """A bounded retry budget, exponential backoff and the statuses worth retrying.

    ``max_attempts`` counts the first try, so the default of 3 means at most two
    retries. Backoff is ``base_backoff_seconds * 2 ** (failed_attempt - 1)``, capped at
    ``max_backoff_seconds``, and carries **no jitter**: this module owns no random
    source, and inventing one would make every offline test non-deterministic. The
    ``Retry-After`` header, when present and parseable, is the server's own advice and
    is never undercut.

    ``max_retry_after_seconds`` bounds a single wait. A server asking for longer is
    honoured by *not* retrying and not sleeping at all, because a non-2xx response is
    data at this port: turning it into a wait, or into an exception, would hide the
    status and headers a caller needs.
    """

    max_attempts: int = 3
    base_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 8.0
    max_retry_after_seconds: float = 60.0
    retryable_statuses: frozenset[int] = field(default=_DEFAULT_RETRYABLE_STATUSES)

    def __post_init__(self) -> None:
        _require_positive_int(self.max_attempts, "max_attempts")
        base = _require_positive_seconds(self.base_backoff_seconds, "base_backoff_seconds")
        maximum = _require_positive_seconds(self.max_backoff_seconds, "max_backoff_seconds")
        _require_positive_seconds(self.max_retry_after_seconds, "max_retry_after_seconds")
        if maximum < base:
            raise ValueError(
                f"max_backoff_seconds ({maximum}) must be at least "
                f"base_backoff_seconds ({base})"
            )
        statuses = frozenset(self.retryable_statuses)
        for status in statuses:
            _require_positive_int(status, "retryable_statuses entry")
        object.__setattr__(self, "retryable_statuses", statuses)


class RateLimiter:
    """One shared sliding-window request budget.

    One instance is one budget for the whole client: create a single limiter and hand
    it to every adapter. Two endpoints with two limiters each get their own allowance
    and the real limit is breached.

    The history is a single ledger shared by both windows, so the second and the
    minute limit are enforced over the same grants, and the wait is the *maximum* of
    the two windows' requirements. The slot is recorded only when a caller actually
    returns from :meth:`wait_for_slot`, so an aborted wait does not consume budget.
    Time comes exclusively from the injected monotonic clock.
    """

    def __init__(self, pacing: PacingPolicy, clock: MonotonicClock) -> None:
        self._pacing = pacing
        self._clock = clock
        self._granted: deque[float] = deque()

    async def wait_for_slot(self) -> None:
        """Block until both windows admit one more request, then record it."""
        while True:
            now = self._clock.monotonic()
            wait = self._required_wait(now)
            if wait <= 0:
                self._granted.append(now)
                return
            await self.sleep(wait)

    async def sleep(self, seconds: float) -> None:
        """Spend a wait on the one monotonic seam this policy owns.

        Exposed so the retry backoff sleeps on the *same* monotonic source as the
        windows: one injected clock times every duration the policy spends, which
        keeps pacing and backoff mutually visible and every offline test exact.
        """
        await self._clock.sleep(seconds)

    def _required_wait(self, now: float) -> float:
        # Nothing older than the widest window can affect either window again.
        while self._granted and self._granted[0] <= now - _SECONDS_PER_MINUTE:
            self._granted.popleft()
        return max(
            self._window_wait(now, limit=self._pacing.per_second, window=_SECONDS_PER_SECOND),
            self._window_wait(now, limit=self._pacing.per_minute, window=_SECONDS_PER_MINUTE),
        )

    def _window_wait(self, now: float, *, limit: int, window: float) -> float:
        """Seconds to wait so that at most ``limit`` grants sit in a ``window``."""
        if len(self._granted) < limit:
            return 0.0
        # Keep the newest (limit - 1) grants; the one before them must fall out of
        # the window before this request can be admitted.
        oldest_to_keep = self._granted[len(self._granted) - limit]
        return oldest_to_keep + window - now


class RetryingHttpClient:
    """The ``HttpClient`` port with pacing, bounded retries and typed error rules.

    Every attempt - including the first - takes a slot from the shared limiter
    *before* the inner client is touched, so the budget covers retries as well as
    first calls. A 2xx is returned at once. A retryable status waits
    ``max(backoff, server advice)`` and is retried; when the attempts run out the last
    response is returned, because a non-2xx status is data at this port and converting
    it to an exception would drop the status and headers.

    ``HttpTransportError`` and ``HttpTimeoutError`` follow the same wait and re-raise
    the last error once the attempts run out. ``HttpDecodeError`` and
    ``HttpResponseTooLargeError`` describe a deterministic body problem: repeating the
    request would only reproduce them, so they propagate on the first occurrence.
    ``asyncio.CancelledError`` is never caught, is never converted, and cannot produce
    another attempt.

    ``close`` is idempotent, delegates to the inner client exactly once, and makes a
    later ``get_json`` raise - provably before the inner client is reached, because the
    open check is the first statement of ``get_json``.
    """

    def __init__(
        self,
        inner: HttpClient,
        *,
        limiter: RateLimiter,
        retry_policy: RetryPolicy | None = None,
        clock: Clock,
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self._retry_policy = RetryPolicy() if retry_policy is None else retry_policy
        self._clock = clock
        self._closed = False

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> HttpResponse:
        """Make up to ``max_attempts`` paced attempts and return the exchange."""
        self._require_open()
        policy = self._retry_policy
        attempt = 0
        while True:
            attempt += 1
            await self._limiter.wait_for_slot()
            try:
                response = await self._inner.get_json(url, params=params)
            except (HttpTransportError, HttpTimeoutError):
                wait = self._backoff_wait(attempt)
                if attempt >= policy.max_attempts or wait > policy.max_retry_after_seconds:
                    raise
                await self._limiter.sleep(wait)
                continue
            if 200 <= response.status_code < 300:
                return response
            if response.status_code not in policy.retryable_statuses:
                return response
            if attempt >= policy.max_attempts:
                return response
            wait = self._retry_wait(response, attempt)
            if wait > policy.max_retry_after_seconds:
                # Over budget: no retry and no sleep. The response is the answer.
                return response
            await self._limiter.sleep(wait)

    async def close(self) -> None:
        """Close the inner client exactly once; safe to repeat."""
        if self._closed:
            return
        self._closed = True
        await self._inner.close()

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("RetryingHttpClient is closed")

    def _backoff_wait(self, failed_attempt: int) -> float:
        """Deterministic exponential backoff for the attempt that just failed.

        Doubling stops the moment the configured cap is reached, so a large attempt
        count can never build an unbounded integer or overflow converting one to a
        float: the loop is bounded by the doublings the cap actually needs, which
        stays in the low thousands even across the widest finite float range.
        """
        policy = self._retry_policy
        base = policy.base_backoff_seconds
        cap = policy.max_backoff_seconds
        wait = base
        for _ in range(failed_attempt - 1):
            if wait >= cap:
                break
            wait *= 2.0
        return min(wait, cap)

    def _retry_wait(self, response: HttpResponse, failed_attempt: int) -> float:
        """``max(backoff, server advice)``: never retry earlier than advised."""
        backoff = self._backoff_wait(failed_attempt)
        advice = self._server_advice(response)
        return backoff if advice is None else max(backoff, advice)

    def _server_advice(self, response: HttpResponse) -> float | None:
        """Seconds the server asked us to wait, or ``None`` when it said nothing usable.

        ``Retry-After`` is read case-insensitively through the port's ``header`` helper.
        The RFC 7231 delta-seconds form (``1*DIGIT``) is honoured however large it is: a
        value beyond ``max_retry_after_seconds`` is reported as ``math.inf`` so the
        over-budget rule declines the retry, and a long run of leading zeros is handled
        without ever converting the whole string to ``int`` (Python refuses very long
        digit strings) or to ``float`` (which overflows to ``inf`` past about 308
        significant digits). The HTTP-date form is converted against the injected UTC
        clock as ``max(0, parsed - now)``. Text that is neither valid delta-seconds nor a
        parseable date - empty, prose, a negative value, or the non-numeric ``nan``/
        ``inf`` extensions - is treated as absent so the deterministic backoff applies.
        """
        raw = response.header("Retry-After")
        if raw is None:
            return None
        text = raw.strip()
        if not text:
            return None
        if text.isascii() and text.isdigit():
            return self._delay_seconds(text)
        seconds: float | None
        try:
            seconds = float(text)
        except ValueError:
            seconds = None
        if seconds is not None:
            if not math.isfinite(seconds) or seconds < 0:
                return None
            return seconds
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (parsed - self._clock.now()).total_seconds())

    def _delay_seconds(self, digits: str) -> float:
        """Normalise a valid ``1*DIGIT`` delta-seconds value without huge conversion.

        A value strictly greater than ``max_retry_after_seconds`` is reported as
        ``math.inf``: the caller then takes the over-budget path, which is the only thing
        that matters and needs no exact magnitude. Comparing significant digit counts
        decides that before any conversion, so neither ``int`` nor ``float`` ever sees the
        full string. Values at or below the ceiling are small enough to convert safely.
        """
        significant = digits.lstrip("0")
        if not significant:
            return 0.0
        ceiling_digits = len(str(int(self._retry_policy.max_retry_after_seconds)))
        if len(significant) > ceiling_digits:
            return math.inf
        try:
            return float(int(significant))
        except OverflowError:
            return math.inf
