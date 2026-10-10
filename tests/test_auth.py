"""Offline acceptance tests for OpenF1 authentication and the live seam.

No network, no DNS, no real OpenF1 call: a scripted fake covers the provider's
caching, failure and concurrency rules, and an ``httpx.MockTransport`` proves the
real adapter path end to end. Every credential and token below is an obvious
placeholder.

The fake counts form POSTs, so "exchanged once", "refreshed exactly at the skew
boundary" and "at most one in-flight exchange" are observed as exact call counts
rather than inferred. The redaction checks are made non-vacuous by first proving
the secret really is reachable through the one deliberate accessor.
"""

# Every credential-shaped literal in this module is an obvious placeholder.
# ruff: noqa: S105, S107

from __future__ import annotations

import asyncio
import datetime as dt
import gc
from collections.abc import Mapping

import httpx
import pytest
from pydantic import SecretStr

from f1show import auth as auth_module
from f1show.auth import (
    DEFAULT_OPENF1_TOKEN_URL,
    TOKEN_REFRESH_SKEW_SECONDS,
    AccessToken,
    AuthenticatedHttpClient,
    AuthError,
    OpenF1TokenProvider,
    TokenDecodeError,
    TokenExchangeError,
    TokenPayload,
    TokenPayloadError,
    parse_token_payload,
)
from f1show.config import CredentialsSettings
from f1show.fakes import FakeHttpClient, FrozenClock
from f1show.http import HttpxJsonClient
from f1show.ports import (
    Clock,
    HttpClient,
    HttpDecodeError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
)
from f1show.redaction import REDACTED

TOKEN_URL = "https://example.invalid/token"
SOURCE_URL = "https://example.invalid/v1/sessions"
USERNAME = "placeholder-openf1-user"
PASSWORD = "placeholder-openf1-password"  # noqa: S105
ACCESS_TOKEN = "placeholder-access-token"  # noqa: S105
FORM = {"username": USERNAME, "password": PASSWORD}
MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=dt.timezone.utc)

#: A stalled token exchange must FAIL a test, never hang CI. Every unbounded wait in
#: the concurrency proof is bounded by this, and a timeout names the hang hazard.
EXCHANGE_HAZARD_TIMEOUT_SECONDS = 5.0


def credentials() -> CredentialsSettings:
    """Obviously fictional OpenF1 credentials, wrapped the way config stores them."""
    return CredentialsSettings(
        openf1_username=SecretStr(USERNAME), openf1_password=SecretStr(PASSWORD)
    )


def payload(*, token: str = ACCESS_TOKEN, expires_in: object = 3600,
            token_type: str = "bearer") -> dict[str, object]:
    return {"access_token": token, "expires_in": expires_in, "token_type": token_type}


def fake_with_token(*, expires_in: object = 3600, token: str = ACCESS_TOKEN) -> FakeHttpClient:
    fake = FakeHttpClient()
    fake.register_form(TOKEN_URL, payload(token=token, expires_in=expires_in), form=FORM)
    return fake


def build_provider(
    client: HttpClient, *, clock: Clock | None = None, token_url: str = TOKEN_URL
) -> OpenF1TokenProvider:
    return OpenF1TokenProvider(
        client=client,
        clock=clock if clock is not None else FrozenClock(MOMENT),
        credentials=credentials(),
        token_url=token_url,
    )


def assert_no_secret_in_text(obj: object, *secrets: str) -> None:
    rendered = f"{obj!r} {obj}"
    for secret in secrets:
        assert secret not in rendered, f"secret leaked through {type(obj).__name__}"


def assert_no_secret_in_error(error: BaseException, *secrets: str) -> None:
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        assert_no_secret_in_text(current, *secrets)
        for secret in secrets:
            assert secret not in repr(current.args)
        current = current.__cause__ or current.__context__


class GatedFormClient:
    """Delegate to a fake, but block a form POST until the test releases it.

    Used to hold one exchange in flight while several callers arrive, so the
    at-most-one proof observes genuinely overlapping callers.
    """

    def __init__(self, inner: FakeHttpClient) -> None:
        self.inner = inner
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.exchanges = 0

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return await self.inner.get_json(url, params=params, headers=headers)

    async def post_form_json(
        self, url: str, *, form: Mapping[str, str], headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        self.exchanges += 1
        self.started.set()
        await self.release.wait()
        return await self.inner.post_form_json(url, form=form, headers=headers)

    async def close(self) -> None:
        await self.inner.close()


class CloseCountingClient:
    """Delegate to a fake and count how many times the wrapper was closed."""

    def __init__(self, inner: FakeHttpClient) -> None:
        self.inner = inner
        self.closes = 0

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return await self.inner.get_json(url, params=params, headers=headers)

    async def post_form_json(
        self, url: str, *, form: Mapping[str, str], headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        return await self.inner.post_form_json(url, form=form, headers=headers)

    async def close(self) -> None:
        self.closes += 1
        await self.inner.close()


def test_default_token_url_is_the_documented_endpoint() -> None:
    assert DEFAULT_OPENF1_TOKEN_URL == "https://api.openf1.org/token"


def test_skew_is_a_positive_documented_constant() -> None:
    assert 0 < TOKEN_REFRESH_SKEW_SECONDS < 3600


def test_documented_string_expires_in_is_accepted() -> None:
    parsed = parse_token_payload(payload(expires_in="3600"))
    assert parsed.expires_in == 3600
    assert parsed.token_type == "bearer"
    assert parsed.access_token.get_secret_value() == ACCESS_TOKEN


def test_integer_expires_in_is_accepted() -> None:
    assert parse_token_payload(payload(expires_in=3600)).expires_in == 3600


@pytest.mark.parametrize("raw", ["bearer", "Bearer", "BEARER", "BeArEr"])
def test_token_type_is_case_insensitive(raw: str) -> None:
    assert parse_token_payload(payload(token_type=raw)).token_type == "bearer"


def test_unknown_fields_are_ignored_as_external_input() -> None:
    parsed = parse_token_payload({**payload(), "scope": "read", "refresh_token": "placeholder-x"})
    assert parsed.expires_in == 3600


@pytest.mark.parametrize("bad", ["abc", "", "3600.5", "0", "-1", 0, -1, None, True, 3600.5])
def test_invalid_lifetime_is_refused(bad: object) -> None:
    with pytest.raises(TokenPayloadError):
        parse_token_payload(payload(expires_in=bad))


@pytest.mark.parametrize("bad", ["", "   ", 123, None])
def test_empty_or_non_string_access_token_is_refused(bad: object) -> None:
    with pytest.raises(TokenPayloadError):
        parse_token_payload(payload(token=bad))  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["mac", "", "bearer token", 123])
def test_unsupported_token_type_is_refused(bad: object) -> None:
    with pytest.raises(TokenPayloadError):
        parse_token_payload(payload(token_type=bad))  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", [{}, {"expires_in": "3600", "token_type": "bearer"}, [], None])
def test_payload_that_is_not_a_token_document_is_refused(raw: object) -> None:
    with pytest.raises(TokenPayloadError):
        parse_token_payload(raw)


def test_payload_failure_carries_no_token_or_message() -> None:
    raw = {**payload(expires_in="not-a-number"), "message": "server said no"}
    with pytest.raises(TokenPayloadError) as caught:
        parse_token_payload(raw)
    assert_no_secret_in_error(caught.value, USERNAME, PASSWORD, ACCESS_TOKEN)
    assert "server said no" not in str(caught.value)


def test_parsed_payload_repr_masks_the_secret() -> None:
    parsed = parse_token_payload(payload())
    assert_no_secret_in_text(parsed, ACCESS_TOKEN, PASSWORD)


def test_access_token_repr_masks_but_the_accessor_reveals() -> None:
    token = AccessToken(payload=parse_token_payload(payload()), issued_at=MOMENT)
    assert_no_secret_in_text(token, ACCESS_TOKEN, PASSWORD)
    assert token.authorization_header() == f"Bearer {ACCESS_TOKEN}"


def test_access_token_expiry_boundary_is_the_skew_line() -> None:
    token = AccessToken(payload=parse_token_payload(payload(expires_in=3600)), issued_at=MOMENT)
    boundary = MOMENT + dt.timedelta(seconds=3600 - TOKEN_REFRESH_SKEW_SECONDS)
    assert token.expires_at == MOMENT + dt.timedelta(seconds=3600)
    assert token.is_valid_at(boundary - dt.timedelta(microseconds=1), skew_seconds=TOKEN_REFRESH_SKEW_SECONDS)
    assert not token.is_valid_at(boundary, skew_seconds=TOKEN_REFRESH_SKEW_SECONDS)


@pytest.mark.anyio
async def test_provider_exchanges_once_and_reuses_the_cache() -> None:
    fake = fake_with_token()
    provider = build_provider(fake)
    first = await provider.token()
    second = await provider.token()
    assert first.authorization_header() == f"Bearer {ACCESS_TOKEN}"
    assert second is first
    assert len(fake.post_calls) == 1


@pytest.mark.anyio
async def test_exchange_sends_the_credentials_in_the_form_and_no_bearer() -> None:
    fake = fake_with_token()
    await build_provider(fake).token()
    url, form, headers = fake.post_calls[0]
    assert url == TOKEN_URL
    assert form == FORM
    assert headers is None


@pytest.mark.anyio
async def test_refresh_at_the_skew_boundary_and_not_one_call_earlier() -> None:
    fake = fake_with_token()
    clock = FrozenClock(MOMENT)
    provider = build_provider(fake, clock=clock)
    await provider.token()
    assert len(fake.post_calls) == 1

    clock.advance(3600 - TOKEN_REFRESH_SKEW_SECONDS - 1)
    await provider.token()
    assert len(fake.post_calls) == 1  # one second before the line: still cached

    clock.advance(1)
    await provider.token()
    assert len(fake.post_calls) == 2  # exactly on the line: refreshed


@pytest.mark.anyio
async def test_at_most_one_in_flight_exchange_for_concurrent_callers() -> None:
    gated = GatedFormClient(fake_with_token())
    provider = build_provider(gated)
    callers = [asyncio.ensure_future(provider.token()) for _ in range(5)]
    try:
        await asyncio.wait_for(
            gated.started.wait(), timeout=EXCHANGE_HAZARD_TIMEOUT_SECONDS
        )
    except TimeoutError:
        pytest.fail(
            "HANG HAZARD: no token exchange started within "
            f"{EXCHANGE_HAZARD_TIMEOUT_SECONDS:g}s; the provider must begin exactly one "
            "exchange for its concurrent callers"
        )
    for _ in range(6):
        await asyncio.sleep(0)
    assert gated.exchanges == 1  # one exchange, still blocked, while five await it
    gated.release.set()
    try:
        tokens = await asyncio.wait_for(
            asyncio.gather(*callers), timeout=EXCHANGE_HAZARD_TIMEOUT_SECONDS
        )
    except TimeoutError:
        pytest.fail(
            "HANG HAZARD: the shared token exchange never completed within "
            f"{EXCHANGE_HAZARD_TIMEOUT_SECONDS:g}s"
        )
    assert gated.exchanges == 1
    assert {token.authorization_header() for token in tokens} == {f"Bearer {ACCESS_TOKEN}"}


@pytest.mark.anyio
async def test_non_2xx_exchange_is_a_typed_failure() -> None:
    fake = FakeHttpClient()
    fake.register_form(TOKEN_URL, None, form=FORM, status_code=401)
    with pytest.raises(TokenExchangeError) as caught:
        await build_provider(fake).token()
    assert isinstance(caught.value, AuthError)
    assert "401" in str(caught.value)
    assert_no_secret_in_error(caught.value, USERNAME, PASSWORD, ACCESS_TOKEN)


@pytest.mark.anyio
async def test_undecodable_body_is_a_typed_failure() -> None:
    fake = FakeHttpClient()
    fake.enqueue_form(TOKEN_URL, HttpDecodeError("the body was not one JSON document"), form=FORM)
    with pytest.raises(TokenDecodeError) as caught:
        await build_provider(fake).token()
    assert isinstance(caught.value, AuthError)
    assert_no_secret_in_error(caught.value, USERNAME, PASSWORD, ACCESS_TOKEN)


@pytest.mark.anyio
async def test_invalid_payload_is_a_typed_failure() -> None:
    fake = FakeHttpClient()
    fake.register_form(TOKEN_URL, payload(expires_in="not-a-number"), form=FORM)
    with pytest.raises(TokenPayloadError) as caught:
        await build_provider(fake).token()
    assert isinstance(caught.value, AuthError)
    assert_no_secret_in_error(caught.value, USERNAME, PASSWORD, ACCESS_TOKEN)


@pytest.mark.anyio
async def test_provider_and_client_reprs_never_reveal_a_secret() -> None:
    fake = fake_with_token()
    provider = build_provider(fake)
    client = AuthenticatedHttpClient(inner=fake, provider=provider)
    await provider.token()
    assert_no_secret_in_text(provider, USERNAME, PASSWORD, ACCESS_TOKEN)
    assert_no_secret_in_text(client, USERNAME, PASSWORD, ACCESS_TOKEN)


@pytest.mark.anyio
async def test_get_json_adds_exactly_one_bearer_authorization_header() -> None:
    fake = fake_with_token()
    fake.register(SOURCE_URL, {"ok": True}, params={"session_key": "1"})
    client = AuthenticatedHttpClient(inner=fake, provider=build_provider(fake))
    await client.get_json(SOURCE_URL, params={"session_key": "1"})
    headers = fake.request_headers[-1]
    assert headers is not None
    named = [name for name in headers if name.lower() == "authorization"]
    assert len(named) == 1
    assert headers[named[0]] == f"Bearer {ACCESS_TOKEN}"
    assert named[0] not in {"authorization", "AUTHORIZATION"}


@pytest.mark.anyio
async def test_get_json_keeps_caller_headers_and_appends_authorization() -> None:
    fake = fake_with_token()
    fake.register(SOURCE_URL, {"ok": True})
    client = AuthenticatedHttpClient(inner=fake, provider=build_provider(fake))
    await client.get_json(SOURCE_URL, headers={"X-Trace": "placeholder-trace"})
    headers = fake.request_headers[-1]
    assert headers is not None
    assert headers["X-Trace"] == "placeholder-trace"
    assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


@pytest.mark.parametrize("name", ["Authorization", "authorization", "AUTHORIZATION"])
@pytest.mark.anyio
async def test_get_json_refuses_a_caller_supplied_authorization(name: str) -> None:
    fake = fake_with_token()
    fake.register(SOURCE_URL, {"ok": True})
    client = AuthenticatedHttpClient(inner=fake, provider=build_provider(fake))
    with pytest.raises(ValueError):
        await client.get_json(SOURCE_URL, headers={name: "Bearer someone-elses-token"})
    assert fake.post_calls == []  # refused before any exchange
    assert fake.calls == []  # and before any source request


@pytest.mark.anyio
async def test_post_form_json_forwards_unchanged_without_a_bearer_header() -> None:
    fake = FakeHttpClient()  # no token registration: an exchange would fail loudly
    fake.register_form(SOURCE_URL, {"ok": True}, form={"a": "1"})
    client = AuthenticatedHttpClient(inner=fake, provider=build_provider(fake))
    response = await client.post_form_json(
        SOURCE_URL, form={"a": "1"}, headers={"X-Trace": "placeholder-trace"}
    )
    assert response.payload == {"ok": True}
    assert fake.post_calls == [(SOURCE_URL, {"a": "1"}, {"X-Trace": "placeholder-trace"})]
    assert all("authorization" not in (headers or {}) for _, _, headers in fake.post_calls)


def test_authenticated_client_satisfies_the_http_client_protocol() -> None:
    fake = FakeHttpClient()
    client = AuthenticatedHttpClient(inner=fake, provider=build_provider(fake))
    assert isinstance(client, HttpClient)


@pytest.mark.anyio
async def test_close_is_repeatable_and_releases_the_inner_exactly_once() -> None:
    inner = fake_with_token()
    inner.register(SOURCE_URL, {"ok": True})
    counting = CloseCountingClient(inner)
    client = AuthenticatedHttpClient(inner=counting, provider=build_provider(counting))
    await client.get_json(SOURCE_URL)
    assert counting.closes == 0  # a request never closes the client underneath
    await client.close()
    await client.close()
    assert counting.closes == 1
    # The wrapper's OWN guard must refuse first, with its own message; if the guard
    # were missing, the adopted inner client's "closed" error would be the observable
    # outcome instead, and these assertions would fail on the message mismatch.
    with pytest.raises(RuntimeError, match="AuthenticatedHttpClient is closed"):
        await client.get_json(SOURCE_URL)
    with pytest.raises(RuntimeError, match="AuthenticatedHttpClient is closed"):
        await client.post_form_json(SOURCE_URL, form={"a": "1"})


@pytest.mark.anyio
async def test_end_to_end_exchange_and_authenticated_get_over_mock_transport() -> None:
    token_requests = 0
    source_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if request.url.path == "/token":
            token_requests += 1
            assert request.headers["content-type"] == "application/x-www-form-urlencoded"
            body = request.content.decode()
            assert f"username={USERNAME}" in body
            assert f"password={PASSWORD}" in body
            assert "authorization" not in request.headers
            return httpx.Response(200, json=payload(expires_in="3600"))
        source_headers.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    raw = HttpxJsonClient(timeout_seconds=1.0, max_response_bytes=4096, transport=transport)
    provider = OpenF1TokenProvider(
        client=raw, clock=FrozenClock(MOMENT), credentials=credentials(), token_url=TOKEN_URL
    )
    client = AuthenticatedHttpClient(inner=raw, provider=provider)
    try:
        first = await client.get_json(SOURCE_URL)
        second = await client.get_json(SOURCE_URL)
    finally:
        await client.close()
    assert first.payload == {"ok": True}
    assert second.payload == {"ok": True}
    assert token_requests == 1  # the second read reused the cached token
    assert source_headers == [f"Bearer {ACCESS_TOKEN}"] * 2


class SecretThatMustNotBeUnwrapped:
    """A stand-in secret whose unwrapping is a test failure.

    ``AccessToken`` must emit a fixed mask, so any repr, str or format path that
    reaches for ``get_secret_value`` raises here instead of silently unredacting.
    """

    def get_secret_value(self) -> str:
        raise AssertionError("AccessToken repr/str must never unwrap the secret")

    def __repr__(self) -> str:
        return "SecretThatMustNotBeUnwrapped()"


class GatedFailingFormClient:
    """Hold one form POST in flight, then fail it; count the exchanges attempted.

    The gate lets its awaiting caller be cancelled while the exchange is still
    pending, and the count observes that the next call starts a fresh exchange
    rather than replaying the abandoned failure.
    """

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.exchanges = 0

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        raise AssertionError("the token provider never issues a GET")

    async def post_form_json(
        self, url: str, *, form: Mapping[str, str], headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        self.exchanges += 1
        self.started.set()
        await self.release.wait()
        raise HttpDecodeError("the body was not one JSON document")

    async def close(self) -> None:
        return None


def test_access_token_repr_never_unwraps_the_secret() -> None:
    # Non-vacuous: ``access_token`` is a wrapper that raises if unwrapped at all, so a
    # repr that reached for the secret would fail here instead of merely exposing it.
    payload_model = TokenPayload.model_construct(
        access_token=SecretThatMustNotBeUnwrapped(),
        expires_in=3600,
        token_type="bearer",  # noqa: S106 -- an obvious placeholder token type
    )
    token = AccessToken(payload=payload_model, issued_at=MOMENT)
    renderings = [
        repr(token),
        str(token),
        format(token),
        f"{token}",
        f"{token!r}",
    ]
    for rendered in renderings:
        assert ACCESS_TOKEN not in rendered
        assert REDACTED in rendered
        assert "bearer" in rendered
        assert "3600" in rendered
        assert MOMENT.isoformat() in rendered


@pytest.mark.anyio
async def test_abandoned_failed_exchange_is_consumed_and_never_reported() -> None:
    loop = asyncio.get_running_loop()
    reports: list[dict[str, object]] = []
    original_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: reports.append(context))
    try:
        client = GatedFailingFormClient()
        provider = build_provider(client)
        caller = asyncio.ensure_future(provider.token())
        await asyncio.wait_for(client.started.wait(), timeout=EXCHANGE_HAZARD_TIMEOUT_SECONDS)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        assert client.exchanges == 1  # the abandoned exchange was not restarted

        client.release.set()
        for _ in range(50):
            await asyncio.sleep(0)

        with pytest.raises(TokenDecodeError) as caught:
            await provider.token()
        assert isinstance(caught.value, AuthError)
        assert client.exchanges == 2  # the next call starts a fresh exchange

        gc.collect()
        await asyncio.sleep(0)
        assert reports == []  # no "shielded future" and no "never retrieved" report
    finally:
        loop.set_exception_handler(original_handler)


@pytest.mark.anyio
async def test_cancelling_one_caller_leaves_the_shared_exchange_intact() -> None:
    gated = GatedFormClient(fake_with_token())
    provider = build_provider(gated)
    doomed = asyncio.ensure_future(provider.token())
    survivor = asyncio.ensure_future(provider.token())
    await asyncio.wait_for(gated.started.wait(), timeout=EXCHANGE_HAZARD_TIMEOUT_SECONDS)
    doomed.cancel()
    with pytest.raises(asyncio.CancelledError):
        await doomed
    assert gated.exchanges == 1
    assert not survivor.cancelled()  # the cancellation stayed with its own caller
    gated.release.set()
    token = await asyncio.wait_for(survivor, timeout=EXCHANGE_HAZARD_TIMEOUT_SECONDS)
    assert token.authorization_header() == f"Bearer {ACCESS_TOKEN}"
    assert gated.exchanges == 1  # one exchange served both callers


TRANSPORT_DETAIL = "placeholder-transport-detail"  # never a real server message


@pytest.mark.parametrize(
    "http_failure",
    [
        HttpTransportError(TRANSPORT_DETAIL),
        HttpTimeoutError(TRANSPORT_DETAIL),
        HttpResponseTooLargeError(TRANSPORT_DETAIL),
    ],
    ids=["transport", "timeout", "too-large"],
)
@pytest.mark.anyio
async def test_http_failure_becomes_a_sanitized_auth_failure(
    http_failure: BaseException,
) -> None:
    fake = FakeHttpClient()
    fake.enqueue_form(TOKEN_URL, http_failure, form=FORM)
    with pytest.raises(auth_module.TokenTransportError) as caught:
        await build_provider(fake).token()
    assert isinstance(caught.value, AuthError)
    # Non-vacuous: the raw failure really carries the server text and the fake really
    # raised it, before we assert the typed failure does not.
    assert TRANSPORT_DETAIL in str(http_failure)
    assert fake.post_calls[0][0] == TOKEN_URL
    assert TRANSPORT_DETAIL not in str(caught.value)
    assert TOKEN_URL not in str(caught.value)
    assert type(http_failure).__name__ in str(caught.value)
    assert_no_secret_in_error(caught.value, USERNAME, PASSWORD, ACCESS_TOKEN, TRANSPORT_DETAIL)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_token_transport_error_is_exported_at_the_package_root() -> None:
    import f1show

    assert auth_module.TokenTransportError is f1show.TokenTransportError
    assert "TokenTransportError" in auth_module.__all__
    assert "TokenTransportError" in f1show.__all__
