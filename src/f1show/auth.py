"""The OpenF1 OAuth2 token exchange and the live authentication seam.

Live OpenF1 access is an authenticated tier. The documented exchange is a single
``POST`` to :data:`DEFAULT_OPENF1_TOKEN_URL` whose body is
``application/x-www-form-urlencoded`` with ``username`` and ``password`` fields, and
whose answer is ``{"expires_in": "3600", "access_token": "...", "token_type": "bearer"}`.
The documented ``expires_in`` is a **string**, so the payload model accepts both the
string and the integer form and invents no other type.

Three rules shape the module:

* **A failure never carries a secret.** No raised error's message, ``repr``, ``args``,
  ``__cause__`` or ``__context__`` chain may contain a credential or a token, and no
  response body or server message is repeated.
* **Time comes from the injected ``Clock``.** Refresh arithmetic uses the same UTC seam
  as every observation, never a private clock or ``time.time()``.
* **This module adds no retry policy of its own.** The injected client may already be
  ``RetryingHttpClient``; pacing and retries belong there, and duplicating them here
  would multiply the real request budget.

Nothing here is verified against the live service. The exchange, the real expiry
behaviour and real responses remain unverified without the paid subscription, and live
validation belongs to F13 under its own authorization.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import math
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, field_validator

from f1show.config import CredentialsSettings
from f1show.ports import (
    Clock,
    HttpClient,
    HttpDecodeError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
    copy_request_headers,
)
from f1show.redaction import REDACTED

#: The documented token endpoint. It lives here rather than in ``config.py``
#: because it is a protocol constant of the exchange, not an operator setting.
DEFAULT_OPENF1_TOKEN_URL = "https://api.openf1.org/token"  # noqa: S105 -- an endpoint, not a credential

#: How early a cached token is treated as spent. A token is refreshed once the
#: current instant reaches ``issued_at + expires_in - skew``, so a request that
#: starts just before nominal expiry still travels on a token that is valid when
#: it arrives. One minute is the documented expiry bucket the source publishes.
TOKEN_REFRESH_SKEW_SECONDS = 60.0

__all__ = [
    "DEFAULT_OPENF1_TOKEN_URL",
    "TOKEN_REFRESH_SKEW_SECONDS",
    "AccessToken",
    "AuthError",
    "AuthenticatedHttpClient",
    "OpenF1TokenProvider",
    "TokenDecodeError",
    "TokenExchangeError",
    "TokenPayload",
    "TokenPayloadError",
    "TokenTransportError",
    "parse_token_payload",
]


class AuthError(Exception):
    """Base of every failure raised at the authentication boundary.

    A caller catches this type rather than an HTTP or validation library's own
    exception, so the exchange can be reimplemented without changing a caller's
    error handling.
    """


class TokenExchangeError(AuthError):
    """The exchange reached the server and was refused with a non-2xx status.

    It carries the status only. The response body is deliberately neither read nor
    repeated, and no server message is preserved.
    """


class TokenDecodeError(AuthError):
    """A 2xx exchange returned a body that is not one JSON document."""


class TokenTransportError(AuthError):
    """The exchange never produced a usable response.

    A transport failure, a timeout or an oversized body ended the attempt before a
    decodable answer, so it is an authentication failure here rather than a raw
    ``HttpError`` escaping the module. The message names only the failure kind and,
    at most, the port's own error class; no credential, token, URL, header, body or
    server message is carried, and ``__cause__`` and ``__context__`` stay empty.
    """


class TokenPayloadError(AuthError):
    """A decodable body did not satisfy the token payload contract.

    The message names the refused fields and their rule types only; no input value
    or response field is repeated.
    """


def _positive_seconds(value: object, name: str) -> float:
    """Return ``value`` as a positive finite number of seconds, or refuse it."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number of seconds, got {type(value).__name__}")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{name} must be a positive, finite number of seconds, got {value!r}")
    return seconds


class TokenPayload(BaseModel):
    """One documented token response, validated as external input.

    ``access_token`` is held as a ``SecretStr``, so the model's own ``repr`` and
    ``str`` mask it. ``expires_in`` accepts the documented string form and the
    integer form, and refuses anything that is not a whole, positive number of
    seconds. ``token_type`` is matched case-insensitively and normalised to
    ``bearer``. Unknown fields are ignored: the source may add fields at any time
    and an unmodelled field is not a reason to reject a usable token.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    access_token: SecretStr
    expires_in: int
    token_type: str

    @field_validator("access_token", mode="before")
    @classmethod
    def _require_token(cls, value: object) -> SecretStr:
        text = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(text, str) or not text.strip():
            raise ValueError("access_token must be a non-empty string")
        return SecretStr(text.strip())

    @field_validator("expires_in", mode="before")
    @classmethod
    def _require_whole_positive_lifetime(cls, value: object) -> int:
        if isinstance(value, bool):
            raise ValueError("expires_in must be a whole, positive number of seconds")
        if isinstance(value, int):
            seconds = value
        elif isinstance(value, str) and value.strip().isdigit():
            seconds = int(value.strip())
        else:
            raise ValueError("expires_in must be a whole, positive number of seconds")
        if seconds <= 0:
            raise ValueError("expires_in must be a whole, positive number of seconds")
        return seconds

    @field_validator("token_type", mode="before")
    @classmethod
    def _require_bearer(cls, value: object) -> str:
        if not isinstance(value, str) or value.strip().lower() != "bearer":
            raise ValueError("token_type must be bearer")
        return "bearer"


def _validation_summary(error: ValidationError) -> str:
    """Name the refused fields and rules, never an input value or server message."""
    parts = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        parts.append(f"{location}:{item['type']}")
    return "; ".join(parts) or "unrecognised payload"


def parse_token_payload(raw: object) -> TokenPayload:
    """Validate one decoded token response, or raise a value-free failure.

    The ``ValidationError`` is deliberately not the cause of the returned error:
    pydantic captures the input it refused, so the raise happens after the handler
    has exited, which leaves the new failure's ``__cause__`` and ``__context__``
    both empty and unreadable from the outside.
    """
    summary = ""
    try:
        return TokenPayload.model_validate(raw)
    except ValidationError as exc:
        summary = _validation_summary(exc)
    raise TokenPayloadError(f"the token payload was refused ({summary})")


@dataclass(frozen=True)
class AccessToken:
    """A validated token plus the instant it was issued.

    The secret is reachable only through :meth:`authorization_header`; ``repr``,
    ``str`` and every format operation emit a fixed mask without ever unwrapping the
    secret, so a diagnostic can name the token's state and lifetime without its value.
    """

    payload: TokenPayload
    issued_at: dt.datetime

    def __post_init__(self) -> None:
        if self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None:
            raise ValueError("issued_at must be timezone-aware; naive time is ambiguous")

    def __repr__(self) -> str:
        # The secret is never unwrapped: the mask is emitted literally, so no repr,
        # str or format path can leak a token even if redaction were bypassed.
        return (
            f"AccessToken(token_type={self.payload.token_type!r}, "
            f"expires_in={self.payload.expires_in!r}, "
            f"issued_at={self.issued_at.isoformat()!r}, "
            f"access_token={REDACTED!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def expires_at(self) -> dt.datetime:
        """The nominal expiry instant, before the refresh skew is applied."""
        return self.issued_at + dt.timedelta(seconds=self.payload.expires_in)

    def is_valid_at(self, now: dt.datetime, *, skew_seconds: float) -> bool:
        """Whether the token still has more than ``skew_seconds`` of life at ``now``.

        Exactly on the line is *not* valid: ``now == expires_at - skew`` refreshes, so
        the boundary is deterministic rather than dependent on sub-second timing.
        """
        return now < self.expires_at - dt.timedelta(seconds=skew_seconds)

    def authorization_header(self) -> str:
        """The one request header value the token exists to produce.

        This is the single deliberate accessor for the secret; callers that only
        need to diagnose a token must use ``repr`` instead.
        """
        return f"Bearer {self.payload.access_token.get_secret_value()}"


class OpenF1TokenProvider:
    """Exchanges credentials for a cached token and keeps exactly one in flight.

    The provider calls ``post_form_json`` on the caller's own client only when no
    valid cached token exists, and it adds no retry policy: the injected client may
    already be the paced, retrying wrapper, and doubling those rules would multiply
    the real request budget. The password is read from its ``SecretStr`` only while
    the form is built, and is never stored as plain text, cached, logged or returned.

    Concurrent callers share one exchange task, so a burst of first requests
    produces one exchange rather than one per caller. A failed exchange is not
    cached, so a later call can retry it. Each caller waits on its own relayed
    future rather than on ``asyncio.shield``: the relay always retrieves the shared
    exchange's outcome, so an exchange abandoned by a cancelled caller cannot
    surface as an unretrieved task exception or a loop-level report, and no private
    interpreter logging behaviour is relied on.
    """

    def __init__(
        self,
        *,
        client: HttpClient,
        clock: Clock,
        credentials: CredentialsSettings,
        token_url: str = DEFAULT_OPENF1_TOKEN_URL,
        skew_seconds: float = TOKEN_REFRESH_SKEW_SECONDS,
    ) -> None:
        username = credentials.openf1_username
        password = credentials.openf1_password
        if username is None or password is None:
            raise ValueError(
                "OpenF1 credentials must provide openf1_username and openf1_password"
            )
        if not isinstance(token_url, str) or not token_url.strip():
            raise ValueError("token_url must be a non-empty string")
        self._client = client
        self._clock = clock
        self._username = username
        self._password = password
        self._token_url = token_url
        self._skew_seconds = _positive_seconds(skew_seconds, "skew_seconds")
        self._token: AccessToken | None = None
        self._exchange: asyncio.Future[AccessToken] | None = None

    def __repr__(self) -> str:
        state = "cached" if self._token is not None else "empty"
        return f"OpenF1TokenProvider(token_state={state!r}, token_url={self._token_url!r})"

    async def token(self) -> AccessToken:
        """Return a valid token, exchanging credentials at most once at a time."""
        cached = self._cached_valid()
        if cached is not None:
            return cached
        exchange = self._exchange
        if exchange is not None and exchange.done():
            # A completed exchange that did not leave a valid token is discarded so
            # the next caller can start a fresh one instead of replaying a stale
            # result. The relay that settled it consumed any failure already.
            if self._exchange is exchange:
                self._exchange = None
            exchange = None
        if exchange is None:
            exchange = asyncio.ensure_future(self._exchange_credentials())
            self._exchange = exchange
        try:
            token = await self._relay(exchange)
        except BaseException:
            # One caller's cancellation must not cancel the shared exchange, and a
            # completed exchange is detached so it cannot poison a later attempt.
            # The relay consumes the outcome even when this caller never returns.
            if exchange.done() and self._exchange is exchange:
                self._exchange = None
            raise
        if self._exchange is exchange:
            self._exchange = None
        return token

    async def _relay(self, exchange: asyncio.Future[AccessToken]) -> AccessToken:
        """Await ``exchange`` without letting this caller's cancellation cancel it.

        A per-caller waiter is settled from a done callback, so cancelling the caller
        cancels only the waiter. The relay always calls ``exchange.exception()``
        first, even when its waiter is already gone, so an abandoned failure is
        consumed instead of being left for the loop to report. It also handles an
        exchange that is already done when the callback is attached: asyncio
        schedules that callback immediately.
        """
        waiter: asyncio.Future[AccessToken] = asyncio.get_running_loop().create_future()

        def _settle(done: asyncio.Future[AccessToken]) -> None:
            if done.cancelled():
                if not waiter.done():
                    waiter.cancel()
                return
            failure = done.exception()  # always consume, even with no caller left
            if waiter.done():
                return
            if failure is not None:
                waiter.set_exception(failure)
            else:
                waiter.set_result(done.result())

        exchange.add_done_callback(_settle)
        return await waiter

    def _cached_valid(self) -> AccessToken | None:
        token = self._token
        if token is not None and token.is_valid_at(
            self._clock.now(), skew_seconds=self._skew_seconds
        ):
            return token
        return None

    async def _exchange_credentials(self) -> AccessToken:
        response = await self._post_credentials()
        if not 200 <= response.status_code < 300:
            raise TokenExchangeError(
                f"the OpenF1 token exchange failed with HTTP status {response.status_code}"
            )
        token = AccessToken(
            payload=parse_token_payload(response.payload), issued_at=self._clock.now()
        )
        self._token = token
        return token

    async def _post_credentials(self) -> HttpResponse:
        """POST the credential form, converting every HTTP failure to a typed failure.

        A transport, timeout, oversized-body or undecodable response fails the
        exchange, so it becomes an ``AuthError`` subtype instead of escaping as a raw
        ``HttpError``. Only the failure kind is named; no credential, token, URL,
        header, body or server message crosses the boundary. Each raise happens after
        its handler has exited, so the original error is neither ``__cause__`` nor
        ``__context__`` of the new one.
        """
        failure: AuthError
        try:
            return await self._client.post_form_json(
                self._token_url, form=self._credentials_form()
            )
        except HttpDecodeError:
            failure = TokenDecodeError(
                "the OpenF1 token exchange returned an undecodable body"
            )
        except (HttpTransportError, HttpTimeoutError, HttpResponseTooLargeError) as exc:
            failure = TokenTransportError(
                f"the OpenF1 token exchange could not be completed ({type(exc).__name__})"
            )
        # Reached only after a handler has exited: raising here keeps the original
        # error's own chain out of __cause__ and __context__ as well as out of the message.
        raise failure

    def _credentials_form(self) -> dict[str, str]:
        """Build the urlencoded form, the only place a secret is ever unwrapped."""
        return {
            "username": self._username.get_secret_value(),
            "password": self._password.get_secret_value(),
        }


class AuthenticatedHttpClient:
    """The ``HttpClient`` port with a bearer token injected into ``get_json``.

    It adds exactly one ``Authorization: Bearer <token>`` header, only to
    ``get_json``. A caller that supplied its own ``Authorization`` header is refused
    with ``ValueError`` before any exchange, because silently overriding or mixing
    credentials is a security decision this wrapper does not make. ``post_form_json``
    is forwarded unchanged: the token endpoint authenticates with credentials in the
    body and never with a bearer header.

    The wrapper adopts the caller-supplied inner client. ``get_json`` and
    ``post_form_json`` never open, replace or close it during a request, and the
    single ownership act is ``close``: it releases the inner client exactly once and
    is safe to repeat, following ``RetryingHttpClient``'s convention. After closing,
    both methods refuse before the inner client is reached.

    Ownership is the caller's to compose. Because ``close`` releases the adopted
    inner client, a caller that shares that same inner client with the token provider
    makes the provider unusable once this wrapper is closed: closing here closes the
    provider's client too. Give each owner its own inner client, or close this
    wrapper only once the provider is done with it.
    """

    def __init__(self, *, inner: HttpClient, provider: OpenF1TokenProvider) -> None:
        self._inner = inner
        self._provider = provider
        self._closed = False

    def __repr__(self) -> str:
        return (
            f"AuthenticatedHttpClient(inner={type(self._inner).__name__}, "
            f"closed={self._closed})"
        )

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Add one bearer header to the caller's request and forward it."""
        self._require_open()
        copied = copy_request_headers(headers)
        if copied is not None:
            for name in copied:
                if name.lower() == "authorization":
                    raise ValueError(
                        "get_json refuses a caller-supplied Authorization header; "
                        "the bearer token is added by this client, and mixing "
                        "credentials is not allowed"
                    )
        token = await self._provider.token()
        merged = dict(copied) if copied is not None else {}
        merged["Authorization"] = token.authorization_header()
        return await self._inner.get_json(url, params=params, headers=merged)

    async def post_form_json(
        self,
        url: str,
        *,
        form: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Forward the form POST unchanged; the token endpoint's body authenticates it."""
        self._require_open()
        return await self._inner.post_form_json(url, form=form, headers=headers)

    async def close(self) -> None:
        """Close the adopted inner client exactly once; safe to repeat."""
        if self._closed:
            return
        self._closed = True
        await self._inner.close()

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("AuthenticatedHttpClient is closed")
