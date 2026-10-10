"""Offline acceptance tests for the typed HTTP port, the shipped fake and the
owned httpx adapter.

Nothing here reaches the network: the adapter always runs on an injected
``httpx`` transport (``MockTransport`` or a purpose-built stall), so a real
provider is never contacted. Deadline cases use controlled asynchronous stalls
instead of long wall-clock sleeps, and every stalled test is wrapped in a
short outer ``asyncio.timeout`` so a regression fails instead of hanging.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from f1show.fakes import FakeHttpClient
from f1show.http import HttpxJsonClient
from f1show.ports import (
    HttpClient,
    HttpDecodeError,
    HttpError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
)

URL = "https://example.invalid/v1/sessions"
TOKEN_URL = "https://example.invalid/token"  # noqa: S105 (fictional endpoint, not a credential)
PARAMS = {"session_key": "9462"}
FORM = {"grant_type": "client_credentials", "client_id": "placeholder-client"}
#: Obviously fictional and searchable, so a leak test can look for it anywhere.
#: Never a real credential.
PLACEHOLDER_TOKEN = "placeholder-token-not-a-real-credential"  # noqa: S105 (deliberately fake)
CALL_HEADERS = {"Authorization": f"Bearer {PLACEHOLDER_TOKEN}", "X-Trace": "trace-1"}
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"
#: Short but comfortably above scheduling noise, so the deadline fires fast.
DEADLINE = 0.2
#: Outer safety net for stalled tests: a missing deadline fails, it never hangs.
STALL_SAFETY = 5.0
JSON_LIST = [{"session_key": 9462, "year": 2024}]


@dataclass(frozen=True)
class Outcome:
    """One scripted source answer, expressed once and served by both clients."""

    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    payload: Any = None
    #: Raw body text used when the body is deliberately *not* JSON. A ``None``
    #: payload with no ``raw_body`` would encode as an empty body, which is why
    #: the non-JSON cases always state their text explicitly.
    raw_body: str | None = None


def _mock_response(outcome: Outcome) -> httpx.Response:
    if outcome.raw_body is not None:
        return httpx.Response(outcome.status, headers=outcome.headers, text=outcome.raw_body)
    return httpx.Response(outcome.status, headers=outcome.headers, json=outcome.payload)


def adapter_client(
    outcome: Outcome,
    *,
    timeout_seconds: float = 5.0,
    max_response_bytes: int = 1024,
    transport: httpx.AsyncBaseTransport | None = None,
) -> HttpxJsonClient:
    """Build the real adapter over an injected offline transport."""
    if transport is None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _mock_response(outcome)

        transport = httpx.MockTransport(handler)
    return HttpxJsonClient(
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        transport=transport,
    )


def fake_client(outcome: Outcome) -> FakeHttpClient:
    """Build the fake answering the same scripted answer as the adapter."""
    client = FakeHttpClient()
    client.register(
        URL,
        outcome.payload,
        params=PARAMS,
        status_code=outcome.status,
        headers=outcome.headers,
    )
    return client


def build(implementation: str, outcome: Outcome) -> Any:
    """Build one implementation that answers both a GET and a form POST."""
    if implementation == "adapter":
        return adapter_client(outcome)
    client = fake_client(outcome)
    client.register_form(
        TOKEN_URL,
        outcome.payload,
        form=FORM,
        status_code=outcome.status,
        headers=outcome.headers,
    )
    return client


@dataclass
class Probed:
    """One implementation plus the request facts the shared bodies need."""

    client: Any
    sent: Callable[[], int]
    headers: Callable[[], dict[str, str]]


def build_probed(implementation: str, outcome: Outcome) -> Probed:
    """Build a client plus probes for request count and the last request's headers.

    Header names are lowercased in the probe only so one body fits both
    implementations: httpx canonicalises on the wire, the fake deliberately does not.
    """
    if implementation == "adapter":
        transport = RecordingTransport(lambda request: _mock_response(outcome))
        client = HttpxJsonClient(
            timeout_seconds=5.0, max_response_bytes=1024, transport=transport
        )
        return Probed(
            client=client,
            sent=lambda: len(transport.requests),
            headers=lambda: (
                {name.lower(): value for name, value in transport.requests[-1].headers.items()}
                if transport.requests
                else {}
            ),
        )
    fake = fake_client(outcome)
    fake.register_form(
        TOKEN_URL,
        outcome.payload,
        form=FORM,
        status_code=outcome.status,
        headers=outcome.headers,
    )
    return Probed(
        client=fake,
        sent=lambda: len(fake.calls) + len(fake.post_calls),
        headers=lambda: (
            {name.lower(): value for name, value in (fake.request_headers[-1] or {}).items()}
            if fake.request_headers
            else {}
        ),
    )


class RecordingTransport(httpx.MockTransport):
    """A MockTransport that records requests and counts its own closures."""

    def __init__(self, handler: Any) -> None:
        super().__init__(handler)
        self.requests: list[httpx.Request] = []
        self.close_calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await super().handle_async_request(request)

    async def aclose(self) -> None:
        self.close_calls += 1
        await super().aclose()


class RaisingTransport(httpx.AsyncBaseTransport):
    """A transport that fails the way a real one can, without a network."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise self.error


class StallBody(httpx.AsyncByteStream):
    """A body that produces bytes forever, slowly enough that a per-chunk read
    timeout would never fire: only an overall deadline can end it."""

    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.chunks = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            self.chunks += 1
            yield b" "
            await asyncio.sleep(self.delay)

    async def aclose(self) -> None:
        pass


@pytest.mark.parametrize("implementation", ["adapter", "fake"])
@pytest.mark.parametrize(
    ("outcome", "expected_payload"),
    [
        pytest.param(Outcome(200, {"Retry-After": "2"}, JSON_LIST), JSON_LIST, id="json-success"),
        pytest.param(
            Outcome(429, {"Retry-After": "1"}, None, "rate limited"),
            None,
            id="non-json-429",
        ),
    ],
)
@pytest.mark.anyio
async def test_adapter_and_fake_share_one_http_contract(
    implementation: str, outcome: Outcome, expected_payload: Any
) -> None:
    """The shared contract body: GET and form POST, headers, payloads, close.

    F03a showed that asserting the same semantics twice, once per
    implementation, is how a divergence survives review, so both implementations
    run this single body. F03d extends it to the additive form-POST surface.
    """
    client = build(implementation, outcome)
    response = await client.get_json(URL, params=PARAMS)
    assert isinstance(response, HttpResponse)
    assert response.status_code == outcome.status
    assert response.header("Retry-After") == outcome.headers["Retry-After"]
    assert response.header("retry-after") == outcome.headers["Retry-After"]
    assert response.payload == expected_payload

    if isinstance(expected_payload, list):
        returned = response.payload
        assert isinstance(returned, list)
        returned.append({"poison": True})
        again = await client.get_json(URL, params=PARAMS)
        assert again.payload == expected_payload, "a returned payload must be a copy"

    posted = await client.post_form_json(TOKEN_URL, form=FORM)
    assert isinstance(posted, HttpResponse)
    assert posted.status_code == outcome.status
    assert posted.payload == expected_payload
    assert posted.header("Retry-After") == outcome.headers["Retry-After"]

    await client.close()
    await client.close()  # closing twice stays harmless
    with pytest.raises(RuntimeError):
        await client.get_json(URL, params=PARAMS)


@pytest.mark.anyio
async def test_adapter_satisfies_the_port_and_sends_nothing_while_being_built() -> None:
    transport = RecordingTransport(lambda request: _mock_response(Outcome(200, payload=JSON_LIST)))
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    try:
        assert isinstance(client, HttpClient)
        assert transport.requests == [], "construction must not touch the network"
    finally:
        await client.close()


@pytest.mark.anyio
async def test_adapter_wires_explicit_per_operation_timeouts_on_every_request() -> None:
    seen: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions.get("timeout"))
        return _mock_response(Outcome(200, payload=JSON_LIST))

    client = HttpxJsonClient(
        timeout_seconds=0.5, max_response_bytes=1024, transport=httpx.MockTransport(handler)
    )
    try:
        await client.get_json(URL)
    finally:
        await client.close()
    assert seen == [{"connect": 0.5, "read": 0.5, "write": 0.5, "pool": 0.5}]


@pytest.mark.anyio
async def test_adapter_sends_no_implicit_credentials_or_cookies() -> None:
    transport = RecordingTransport(lambda request: _mock_response(Outcome(200, payload=JSON_LIST)))
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    try:
        await client.get_json(URL, params=PARAMS)
    finally:
        await client.close()
    assert len(transport.requests) == 1
    request = transport.requests[0]
    # Only the mandatory Host header: no client-level defaults, no cookies, no
    # authorization, so nothing is inherited from the environment or a jar.
    assert dict(request.headers) == {"host": "example.invalid"}
    assert request.url.userinfo == b""
    assert request.url.params["session_key"] == "9462"


@pytest.mark.anyio
async def test_adapter_refuses_a_url_that_embeds_credentials() -> None:
    transport = RecordingTransport(lambda request: _mock_response(Outcome(200, payload=JSON_LIST)))
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    try:
        with pytest.raises(ValueError, match="credentials"):
            await client.get_json("https://user:secret@example.invalid/v1/sessions")
    finally:
        await client.close()
    assert transport.requests == [], "a credential-bearing URL must never be sent"


@pytest.mark.anyio
async def test_adapter_does_not_follow_redirects_and_attempts_exactly_once_per_call() -> None:
    transport = RecordingTransport(
        lambda request: httpx.Response(302, headers={"location": "https://elsewhere.invalid/v1/x"})
    )
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    try:
        response = await client.get_json(URL, params=PARAMS)
        assert response.status_code == 302
        assert response.payload is None
        await client.get_json(URL, params=PARAMS)
    finally:
        await client.close()
    assert len(transport.requests) == 2, "one attempt per call, and no redirect follow"


@pytest.mark.anyio
async def test_adapter_keeps_a_non_2xx_status_visible_without_reading_the_error_body() -> None:
    class ErrorBody(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.reads = 0

        async def __aiter__(self) -> AsyncIterator[bytes]:
            self.reads += 1
            yield b"<html>503 service unavailable</html>"

        async def aclose(self) -> None:
            pass

    body = ErrorBody()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503, headers={"Retry-After": "7"}, stream=body, request=request
        )

    client = HttpxJsonClient(
        timeout_seconds=5.0, max_response_bytes=4, transport=httpx.MockTransport(handler)
    )
    try:
        response = await client.get_json(URL)
    finally:
        await client.close()
    assert response.status_code == 503
    assert response.header("retry-after") == "7"
    assert response.payload is None, "a non-2xx payload is deliberately unavailable"
    assert body.reads == 0, "an error body is never read, so no huge page can dominate"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        pytest.param(Outcome(200, raw_body=""), None, id="empty-body"),
        pytest.param(Outcome(200, raw_body="<html>not json</html>"), None, id="malformed-json"),
    ],
)
@pytest.mark.anyio
async def test_adapter_rejects_an_empty_or_malformed_success_body(
    outcome: Outcome, expected: None
) -> None:
    assert expected is None
    client = adapter_client(outcome)
    try:
        with pytest.raises(HttpDecodeError):
            await client.get_json(URL)
    finally:
        await client.close()


@pytest.mark.parametrize(
    ("body", "expected"),
    [("null", None), ("[]", []), ('[{"a": 1}]', [{"a": 1}])],
    ids=["json-null", "empty-array", "one-record"],
)
@pytest.mark.anyio
async def test_adapter_keeps_json_null_and_an_empty_array_distinct(
    body: str, expected: Any
) -> None:
    client = adapter_client(Outcome(200, raw_body=body))
    try:
        response = await client.get_json(URL)
    finally:
        await client.close()
    assert response.payload == expected


@pytest.mark.anyio
async def test_adapter_stops_reading_a_success_body_at_the_byte_bound() -> None:
    class Chunky(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.yielded = 0

        async def __aiter__(self) -> AsyncIterator[bytes]:
            for _ in range(100):
                self.yielded += 1
                yield b'{"pad":"' + b"x" * 20 + b'"}'

        async def aclose(self) -> None:
            pass

    body = Chunky()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=body,
            request=request,
        )

    client = HttpxJsonClient(
        timeout_seconds=5.0, max_response_bytes=50, transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(HttpResponseTooLargeError):
            await client.get_json(URL)
    finally:
        await client.close()
    assert body.yielded <= 3, "the reader must stop at the bound, not buffer 100 chunks"


@pytest.mark.anyio
async def test_adapter_bounds_decoded_bytes_not_the_compressed_transfer_size() -> None:
    compressed = gzip.compress(json.dumps({"pad": "x" * 500}).encode())
    assert len(compressed) < 100, "the compressed body must fit, so only decoded bytes can trip it"

    class Raw(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield compressed

        async def aclose(self) -> None:
            pass

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip", "content-type": "application/json"},
            stream=Raw(),
            request=request,
        )

    client = HttpxJsonClient(
        timeout_seconds=5.0, max_response_bytes=100, transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(HttpResponseTooLargeError):
            await client.get_json(URL)
    finally:
        await client.close()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(httpx.ConnectError("connection refused"), HttpTransportError, id="connect"),
        pytest.param(httpx.ReadTimeout("no answer"), HttpTimeoutError, id="read-timeout"),
        pytest.param(httpx.ConnectTimeout("no route"), HttpTimeoutError, id="connect-timeout"),
        pytest.param(httpx.InvalidURL("bad url"), HttpTransportError, id="invalid-url"),
    ],
)
@pytest.mark.anyio
async def test_adapter_normalises_httpx_failures_into_typed_port_errors(
    error: Exception, expected: type[HttpError]
) -> None:
    client = HttpxJsonClient(
        timeout_seconds=5.0, max_response_bytes=64, transport=RaisingTransport(error)
    )
    try:
        with pytest.raises(expected) as excinfo:
            await client.get_json(URL)
    finally:
        await client.close()
    assert isinstance(excinfo.value, HttpError)
    assert not isinstance(excinfo.value, httpx.HTTPError), "no httpx exception may cross the port"


@pytest.mark.anyio
async def test_adapter_enforces_the_overall_deadline_when_headers_never_arrive() -> None:
    class Hanging(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    client = HttpxJsonClient(
        timeout_seconds=DEADLINE, max_response_bytes=64, transport=Hanging()
    )
    try:
        async with asyncio.timeout(STALL_SAFETY):
            with pytest.raises(HttpTimeoutError):
                await client.get_json(URL)
    finally:
        await client.close()


@pytest.mark.anyio
async def test_adapter_deadline_covers_a_body_that_keeps_dripping() -> None:
    body = StallBody()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "application/json"}, stream=body, request=request
        )

    client = HttpxJsonClient(
        timeout_seconds=DEADLINE,
        max_response_bytes=10_000,
        transport=httpx.MockTransport(handler),
    )
    try:
        async with asyncio.timeout(STALL_SAFETY):
            with pytest.raises(HttpTimeoutError):
                await client.get_json(URL)
    finally:
        await client.close()
    assert body.chunks <= 10, "the deadline must end a body that a per-chunk timeout would allow"


@pytest.mark.anyio
async def test_adapter_owns_its_transport_and_closes_it_once() -> None:
    transport = RecordingTransport(lambda request: _mock_response(Outcome(200, payload=JSON_LIST)))
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    await client.close()
    await client.close()
    assert transport.close_calls == 1
    with pytest.raises(RuntimeError):
        await client.get_json(URL)


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_adapter_rejects_a_timeout_that_is_not_positive_and_finite(bad: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        HttpxJsonClient(timeout_seconds=bad, max_response_bytes=64)


@pytest.mark.parametrize("bad", [True, "10", None])
def test_adapter_rejects_a_timeout_that_is_not_a_number(bad: Any) -> None:
    with pytest.raises(TypeError, match="timeout_seconds"):
        HttpxJsonClient(timeout_seconds=bad, max_response_bytes=64)


@pytest.mark.parametrize("bad", [0, -1])
def test_adapter_rejects_a_response_bound_that_is_not_positive(bad: int) -> None:
    with pytest.raises(ValueError, match="max_response_bytes"):
        HttpxJsonClient(timeout_seconds=1.0, max_response_bytes=bad)


@pytest.mark.parametrize("bad", [True, 1.5, "64", None])
def test_adapter_rejects_a_response_bound_that_is_not_an_integer(bad: Any) -> None:
    with pytest.raises(TypeError, match="max_response_bytes"):
        HttpxJsonClient(timeout_seconds=1.0, max_response_bytes=bad)


# --- F03c-1-R1: a response close must never displace, hide or outlive the call's
# --- own outcome. Every probe below is an outer hang guard, never the adapter's
# --- enforcement; the adapter's own allowance is asserted through the stream flags
# --- and the annotated notes.

#: A stalled close must end within the adapter's allowance (0.2s request + 0.2s
#: cleanup here), so a 2s guard only proves that a regression fails instead of hanging.
CLOSE_PROBE = 2.0


class MarkerError(Exception):
    """A sentinel this suite raises to identify one call's own primary failure."""


class ControllableBody(httpx.AsyncByteStream):
    """A response body whose read and close behaviour the test controls.

    ``read_error`` fails the body read; ``read_error_after`` fails it after the chunks
    have been streamed, which is the mid-read case a foreign transport can produce;
    ``error`` fails the close; ``stall`` makes the
    close wait cooperatively, so a bounded cleanup can still cancel it; ``drip`` makes
    the read produce bytes forever. The flags record what happened, which is how a test
    tells the adapter's own allowance apart from its outer hang guard.
    """

    def __init__(
        self,
        *,
        chunks: tuple[bytes, ...] = (),
        read_error: BaseException | None = None,
        read_error_after: BaseException | None = None,
        error: BaseException | None = None,
        stall: bool = False,
        drip: bool = False,
        drip_delay: float = 0.05,
    ) -> None:
        self._chunks = chunks
        self._read_error = read_error
        self._read_error_after = read_error_after
        self._error = error
        self._stall = stall
        self._drip = drip
        self._drip_delay = drip_delay
        self.started = asyncio.Event()
        self.chunks_yielded = 0
        self.close_entered = False
        self.close_cancelled = False
        self.close_failed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if self._read_error is not None:
            raise self._read_error
        self.started.set()
        if self._drip:
            while True:
                self.chunks_yielded += 1
                yield b" "
                await asyncio.sleep(self._drip_delay)
        for chunk in self._chunks:
            yield chunk
        if self._read_error_after is not None:
            raise self._read_error_after

    async def aclose(self) -> None:
        self.close_entered = True
        if self._stall:
            try:
                await asyncio.Event().wait()
            except BaseException:
                self.close_cancelled = True
                raise
        if self._error is not None:
            self.close_failed = True
            raise self._error


def streamed_client(
    body: ControllableBody,
    *,
    status: int = 200,
    timeout_seconds: float = 5.0,
    max_response_bytes: int = 1024,
) -> HttpxJsonClient:
    """A client over one mocked response that streams ``body``."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers={"content-type": "application/json"},
            stream=body,
            request=request,
        )

    return HttpxJsonClient(
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        transport=httpx.MockTransport(handler),
    )


class ControlledCloseTransport(httpx.AsyncBaseTransport):
    """A transport whose own close the test controls."""

    def __init__(self, *, error: BaseException | None = None, stall: bool = False) -> None:
        self._error = error
        self._stall = stall
        self.close_calls = 0
        self.close_cancelled = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async def aclose(self) -> None:
        self.close_calls += 1
        if self._stall:
            try:
                await asyncio.Event().wait()
            except BaseException:
                self.close_cancelled = True
                raise
        if self._error is not None:
            raise self._error


@pytest.mark.anyio
async def test_a_failing_close_never_replaces_the_empty_body_verdict() -> None:
    body = ControllableBody(error=RuntimeError("close exploded"))
    client = streamed_client(body)
    try:
        with pytest.raises(HttpDecodeError) as excinfo:
            await client.get_json(URL)
    finally:
        await client.close()
    assert body.close_entered, "the response must still be closed"
    assert "close exploded" not in str(excinfo.value)
    notes = " ".join(getattr(excinfo.value, "__notes__", ()))
    assert "close exploded" not in notes, "the closer's own message must not enter a note"
    assert "RuntimeError" in notes, "the secondary close failure is named by type only"


@pytest.mark.anyio
async def test_a_close_failure_after_a_successful_read_is_typed_not_a_leak_or_a_silent_pass() -> None:
    body = ControllableBody(chunks=(b'[{"record_id": "1"}]',), error=RuntimeError("close exploded"))
    client = streamed_client(body)
    try:
        # The caller is already handling an unrelated failure; ours must not adopt it.
        try:
            raise ValueError("caller owned")
        except ValueError:
            with pytest.raises(HttpTransportError) as excinfo:
                await client.get_json(URL)
        assert isinstance(excinfo.value, HttpError)
        assert "close exploded" not in str(excinfo.value)
        assert "caller owned" not in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, RuntimeError), "the true cause stays chained"
        assert not isinstance(excinfo.value.__cause__, ValueError)
    finally:
        await client.close()


@pytest.mark.parametrize(
    ("body_kwargs", "expected"),
    [
        pytest.param({"error": RuntimeError("close exploded")}, HttpTransportError, id="close-raises"),
        pytest.param({"stall": True}, HttpTimeoutError, id="close-stalls"),
    ],
)
@pytest.mark.anyio
async def test_a_close_problem_on_an_unread_error_response_is_a_typed_failure(
    body_kwargs: dict[str, Any], expected: type[HttpError]
) -> None:
    body = ControllableBody(chunks=(b"<html/>",), **body_kwargs)
    client = streamed_client(body, status=503, timeout_seconds=0.2)
    try:
        async with asyncio.timeout(CLOSE_PROBE):
            with pytest.raises(expected) as excinfo:
                await client.get_json(URL)
        assert body.close_entered
        assert "close exploded" not in str(excinfo.value)
        if "stall" in body_kwargs:
            assert body.close_cancelled, "the cleanup allowance cancelled the stalled close"
            assert "cleanup allowance" in str(excinfo.value)
    finally:
        await client.close()


@pytest.mark.anyio
async def test_the_deadline_and_the_close_allowance_together_bound_a_stalled_close() -> None:
    body = ControllableBody(drip=True, stall=True)
    client = streamed_client(body, timeout_seconds=0.2)
    try:
        async with asyncio.timeout(CLOSE_PROBE):
            with pytest.raises(HttpTimeoutError) as excinfo:
                await client.get_json(URL)
        assert body.close_cancelled, "the stalled close was cancelled by the cleanup allowance"
        notes = " ".join(getattr(excinfo.value, "__notes__", ()))
        assert "0.2s cleanup allowance" in notes, "the adapter's own allowance ended the close"
    finally:
        await client.close()


@pytest.mark.anyio
async def test_an_external_cancel_propagates_and_does_not_wait_on_a_stalled_close() -> None:
    body = ControllableBody(drip=True, stall=True)
    # A far deadline makes the explicit cancel the only thing that can end the read.
    client = streamed_client(body, timeout_seconds=30.0)
    task = asyncio.create_task(client.get_json(URL))
    try:
        await asyncio.wait_for(body.started.wait(), 1.0)
        task.cancel()
        # Poll instead of awaiting the task inside the guard: awaiting it would make the
        # guard's own cancellation reach the stalled closer and hide an unbounded cleanup.
        async with asyncio.timeout(CLOSE_PROBE):
            while not task.done():
                await asyncio.sleep(0.01)
        outcome: BaseException | None = None
        try:
            await task
        except asyncio.CancelledError as exc:
            outcome = exc
        assert isinstance(outcome, asyncio.CancelledError), "cancellation must propagate"
        assert task.cancelled(), "the task must finish cancelled, not stay pending"
        assert body.close_cancelled, "the stalled close was cancelled by the allowance"
    finally:
        if not task.done():
            task.cancel()
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(task, 1.0)
        await client.close()


@pytest.mark.anyio
async def test_the_primary_failure_keeps_its_instance_and_is_annotated_by_type_only() -> None:
    primary = MarkerError("adapter primary")
    body = ControllableBody(read_error=primary, error=RuntimeError("close exploded"))
    client = streamed_client(body)
    try:
        with pytest.raises(HttpTransportError) as excinfo:
            await client.get_json(URL)
    finally:
        await client.close()
    # A foreign read failure is normalised (F03c-1-R2), and the call's own failure is
    # still the primary: the close failure annotates it instead of displacing it, and the
    # foreign exception itself is preserved as the cause rather than lost.
    assert excinfo.value.__cause__ is primary, "the call's own failure must survive cleanup"
    assert "close exploded" not in str(excinfo.value)
    notes = " ".join(getattr(excinfo.value, "__notes__", ()))
    assert "close exploded" not in notes
    assert "RuntimeError" in notes, "the secondary close failure is named by type only"
    assert body.close_entered


@pytest.mark.parametrize(
    ("transport_kwargs", "expected"),
    [
        pytest.param({"error": RuntimeError("transport close exploded")}, HttpTransportError, id="close-raises"),
        pytest.param({"stall": True}, HttpTimeoutError, id="close-stalls"),
    ],
)
@pytest.mark.anyio
async def test_the_owned_client_close_is_typed_and_bounded(
    transport_kwargs: dict[str, Any], expected: type[HttpError]
) -> None:
    transport = ControlledCloseTransport(**transport_kwargs)
    client = HttpxJsonClient(timeout_seconds=0.2, max_response_bytes=64, transport=transport)
    async with asyncio.timeout(CLOSE_PROBE):
        with pytest.raises(expected) as excinfo:
            await client.close()
    assert transport.close_calls == 1
    assert "transport close exploded" not in str(excinfo.value)
    if "stall" in transport_kwargs:
        assert transport.close_cancelled
    # A reported close failure is refused afterwards and is never silently retried.
    with pytest.raises(RuntimeError):
        await client.get_json(URL)
    await client.close()
    assert transport.close_calls == 1, "a reported close is not retried behind the caller's back"


# --- F03c-1-R2: a foreign exception raised by an injected transport -- on the send or
# --- while the body is streamed -- is a contract violation that must still become a
# --- typed ``f1show.ports`` error. The parse step stays outside that normalisation, so
# --- a malformed payload cannot masquerade as a transport failure, and a cancellation
# --- keeps propagating as itself. Every stalled test keeps its outer hang guard.


class ForeignRaisingTransport(httpx.AsyncBaseTransport):
    """A transport that breaks its own contract with a non-httpx exception."""

    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.close_calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise self.error

    async def aclose(self) -> None:
        self.close_calls += 1


@pytest.mark.anyio
async def test_a_foreign_exception_while_sending_becomes_a_typed_transport_failure() -> None:
    boom = RuntimeError("send boom")
    client = HttpxJsonClient(
        timeout_seconds=5.0,
        max_response_bytes=64,
        transport=ForeignRaisingTransport(boom),
    )
    try:
        with pytest.raises(HttpTransportError) as excinfo:
            await client.get_json(URL, params=PARAMS)
    finally:
        await client.close()
    error = excinfo.value
    assert not isinstance(error, httpx.HTTPError), "no httpx exception may cross the port"
    assert error.__cause__ is boom, "the transport's own exception stays chained"
    assert "send boom" not in str(error), "the foreign message must not cross the port"
    assert "session_key" not in str(error), "the query string must not reach the message"
    assert URL in str(error), "the message still names the sanitised endpoint"


@pytest.mark.anyio
async def test_a_foreign_exception_mid_read_becomes_a_typed_transport_failure() -> None:
    boom = RuntimeError("mid-read boom")
    body = ControllableBody(chunks=(b'{"partial":',), read_error_after=boom)
    client = streamed_client(body)
    try:
        async with asyncio.timeout(CLOSE_PROBE):
            with pytest.raises(HttpTransportError) as excinfo:
                await client.get_json(URL, params=PARAMS)
    finally:
        await client.close()
    error = excinfo.value
    assert not isinstance(error, httpx.HTTPError), "no httpx exception may cross the port"
    assert error.__cause__ is boom, "the transport's own exception stays chained"
    assert "mid-read boom" not in str(error), "the foreign message must not cross the port"
    assert "session_key" not in str(error), "the query string must not reach the message"
    assert URL in str(error), "the message still names the sanitised endpoint"
    assert body.close_entered, "the still-open response is closed after normalisation"


@pytest.mark.anyio
async def test_a_malformed_success_body_is_still_a_decode_error_not_a_transport_failure() -> None:
    client = adapter_client(Outcome(200, raw_body="<html>not json</html>"))
    try:
        with pytest.raises(HttpDecodeError) as excinfo:
            await client.get_json(URL)
    finally:
        await client.close()
    assert not isinstance(excinfo.value, HttpTransportError), (
        "the parse step must stay outside transport-error normalisation"
    )
    assert "not valid JSON" in str(excinfo.value)


@pytest.mark.anyio
async def test_a_cancellation_during_the_read_still_propagates_as_itself() -> None:
    cancel = asyncio.CancelledError()
    body = ControllableBody(chunks=(b"x",), read_error_after=cancel)
    client = streamed_client(body)
    try:
        async with asyncio.timeout(CLOSE_PROBE):
            with pytest.raises(asyncio.CancelledError) as excinfo:
                await client.get_json(URL)
        assert excinfo.value is cancel, "a cancellation is not a transport failure"
    finally:
        await client.close()


@pytest.mark.anyio
async def test_a_non_2xx_response_keeps_status_and_headers_without_reading_a_raising_body() -> None:
    body = ControllableBody(chunks=(b"<html/>",), read_error_after=RuntimeError("never read"))
    client = streamed_client(body, status=503)
    try:
        response = await client.get_json(URL)
    finally:
        await client.close()
    assert response.status_code == 503
    assert response.header("content-type") == "application/json"
    assert response.payload is None, "a non-2xx payload stays unavailable"
    assert not body.started.is_set(), "a non-2xx body is never streamed, so nothing can raise"


# --- F03d-1: the additive form-POST and request-header surface. Every implementation
# --- of the port must obey the same rules, so the shared bodies stay parameterized.

BAD_HEADERS = [
    pytest.param("not-a-mapping", id="str"),
    pytest.param([("a", "b")], id="list-of-pairs"),
    pytest.param({"a": 1}, id="non-str-value"),
    pytest.param({1: "a"}, id="non-str-name"),
    pytest.param({"a": None}, id="none-value"),
]
BAD_FORMS = [
    pytest.param("grant_type=x", id="str"),
    pytest.param([("a", "b")], id="list-of-pairs"),
    pytest.param({"a": 1}, id="non-str-value"),
    pytest.param({1: "a"}, id="non-str-name"),
    pytest.param(None, id="none"),
]


@pytest.mark.parametrize("implementation", ["adapter", "fake"])
@pytest.mark.parametrize("bad_headers", BAD_HEADERS)
@pytest.mark.anyio
async def test_both_implementations_refuse_bad_request_headers_before_any_request(
    implementation: str, bad_headers: Any
) -> None:
    probed = build_probed(implementation, Outcome(200, payload=JSON_LIST))
    try:
        with pytest.raises(TypeError):
            await probed.client.get_json(URL, params=PARAMS, headers=bad_headers)
        with pytest.raises(TypeError):
            await probed.client.post_form_json(TOKEN_URL, form=FORM, headers=bad_headers)
        assert probed.sent() == 0, "a refused header mapping must never reach the request"
    finally:
        await probed.client.close()


@pytest.mark.parametrize("implementation", ["adapter", "fake"])
@pytest.mark.parametrize("bad_form", BAD_FORMS)
@pytest.mark.anyio
async def test_both_implementations_refuse_a_bad_form_before_any_request(
    implementation: str, bad_form: Any
) -> None:
    probed = build_probed(implementation, Outcome(200, payload=JSON_LIST))
    try:
        with pytest.raises(TypeError):
            await probed.client.post_form_json(TOKEN_URL, form=bad_form)
        assert probed.sent() == 0, "a refused form must never reach the request"
    finally:
        await probed.client.close()


@pytest.mark.parametrize("implementation", ["adapter", "fake"])
@pytest.mark.anyio
async def test_both_implementations_put_the_called_headers_on_the_request(
    implementation: str,
) -> None:
    """Headers reach the request on GET and POST, and none is invented when absent."""
    probed = build_probed(implementation, Outcome(200, payload=JSON_LIST))
    try:
        await probed.client.get_json(URL, params=PARAMS)
        assert "x-trace" not in probed.headers()
        assert "authorization" not in probed.headers()

        await probed.client.get_json(URL, params=PARAMS, headers=CALL_HEADERS)
        assert probed.headers()["x-trace"] == "trace-1"
        assert probed.headers()["authorization"] == f"Bearer {PLACEHOLDER_TOKEN}"

        await probed.client.post_form_json(TOKEN_URL, form=FORM, headers=CALL_HEADERS)
        assert probed.headers()["authorization"] == f"Bearer {PLACEHOLDER_TOKEN}"
    finally:
        await probed.client.close()


@pytest.mark.anyio
async def test_adapter_posts_a_urlencoded_form_with_the_documented_content_type() -> None:
    transport = RecordingTransport(
        lambda request: _mock_response(Outcome(200, payload={"access_token": "x"}))
    )
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    try:
        await client.post_form_json(TOKEN_URL, form=FORM)
    finally:
        await client.close()
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.headers["content-type"] == FORM_CONTENT_TYPE
    assert request.content == b"grant_type=client_credentials&client_id=placeholder-client"
    assert request.url.path == "/token"


@pytest.mark.anyio
async def test_adapter_keeps_a_caller_supplied_content_type_on_a_form_post() -> None:
    transport = RecordingTransport(lambda request: _mock_response(Outcome(200, payload=JSON_LIST)))
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    supplied = "application/x-www-form-urlencoded; charset=utf-8"
    try:
        await client.post_form_json(TOKEN_URL, form=FORM, headers={"Content-Type": supplied})
    finally:
        await client.close()
    assert transport.requests[0].headers["content-type"] == supplied


@pytest.mark.anyio
async def test_adapter_returns_a_post_redirect_without_following_it() -> None:
    transport = RecordingTransport(
        lambda request: httpx.Response(302, headers={"location": "https://elsewhere.invalid/token"})
    )
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    try:
        response = await client.post_form_json(TOKEN_URL, form=FORM)
    finally:
        await client.close()
    assert response.status_code == 302
    assert response.payload is None
    assert response.header("location") == "https://elsewhere.invalid/token"
    assert len(transport.requests) == 1, "one attempt per call, and no redirect follow"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(httpx.ConnectError("connection refused"), HttpTransportError, id="connect"),
        pytest.param(httpx.ReadTimeout("no answer"), HttpTimeoutError, id="read-timeout"),
        pytest.param(httpx.ConnectTimeout("no route"), HttpTimeoutError, id="connect-timeout"),
    ],
)
@pytest.mark.anyio
async def test_adapter_normalises_post_transport_failures_into_typed_port_errors(
    error: Exception, expected: type[HttpError]
) -> None:
    client = HttpxJsonClient(
        timeout_seconds=5.0, max_response_bytes=64, transport=RaisingTransport(error)
    )
    try:
        with pytest.raises(expected) as excinfo:
            await client.post_form_json(TOKEN_URL, form=FORM)
    finally:
        await client.close()
    assert isinstance(excinfo.value, HttpError)
    assert not isinstance(excinfo.value, httpx.HTTPError), "no httpx exception may cross the port"


@pytest.mark.parametrize(
    ("outcome", "max_bytes", "expected"),
    [
        pytest.param(
            Outcome(200, raw_body="<html>not json</html>"), 1024, HttpDecodeError, id="decode"
        ),
        pytest.param(
            Outcome(200, raw_body='{"pad":"' + "x" * 40 + '"}'),
            10,
            HttpResponseTooLargeError,
            id="size",
        ),
    ],
)
@pytest.mark.anyio
async def test_adapter_keeps_post_body_failures_typed(
    outcome: Outcome, max_bytes: int, expected: type[HttpError]
) -> None:
    client = adapter_client(outcome, max_response_bytes=max_bytes)
    try:
        with pytest.raises(expected):
            await client.post_form_json(TOKEN_URL, form=FORM)
    finally:
        await client.close()


@pytest.mark.anyio
async def test_adapter_enforces_the_deadline_on_a_post_that_never_answers() -> None:
    class Hanging(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    client = HttpxJsonClient(timeout_seconds=DEADLINE, max_response_bytes=64, transport=Hanging())
    try:
        async with asyncio.timeout(STALL_SAFETY):
            with pytest.raises(HttpTimeoutError):
                await client.post_form_json(TOKEN_URL, form=FORM)
    finally:
        await client.close()


def assert_no_placeholder_leak(error: BaseException) -> None:
    """Walk the whole cause/context chain and refuse the placeholder anywhere."""
    node: BaseException | None = error
    steps = 0
    while node is not None:
        assert PLACEHOLDER_TOKEN not in str(node)
        assert PLACEHOLDER_TOKEN not in repr(node)
        assert PLACEHOLDER_TOKEN not in repr(node.args)
        steps += 1
        assert steps < 10, "the cause chain must be finite"
        node = node.__cause__ if node.__cause__ is not None else node.__context__


@pytest.mark.anyio
async def test_request_headers_never_leave_the_request_that_carried_them() -> None:
    """Request headers reach the wire, then exist nowhere the caller can observe."""
    transport = RecordingTransport(lambda request: _mock_response(Outcome(200, payload=JSON_LIST)))
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    try:
        await client.get_json(URL, params=PARAMS, headers=CALL_HEADERS)
        await client.post_form_json(TOKEN_URL, form=FORM, headers=CALL_HEADERS)
        # Non-vacuous: the placeholder really is sent on both requests.
        assert transport.requests[0].headers["authorization"] == f"Bearer {PLACEHOLDER_TOKEN}"
        assert transport.requests[1].headers["authorization"] == f"Bearer {PLACEHOLDER_TOKEN}"
        assert PLACEHOLDER_TOKEN not in repr(client)
        assert PLACEHOLDER_TOKEN not in repr(vars(client))
    finally:
        await client.close()

    failing = HttpxJsonClient(
        timeout_seconds=5.0,
        max_response_bytes=1024,
        transport=RaisingTransport(httpx.ConnectError("connection refused")),
    )
    try:
        with pytest.raises(HttpError) as get_error:
            await failing.get_json(URL, params=PARAMS, headers=CALL_HEADERS)
        assert_no_placeholder_leak(get_error.value)
        with pytest.raises(HttpError) as post_error:
            await failing.post_form_json(TOKEN_URL, form=FORM, headers=CALL_HEADERS)
        assert_no_placeholder_leak(post_error.value)
        assert PLACEHOLDER_TOKEN not in repr(failing)
        assert PLACEHOLDER_TOKEN not in repr(vars(failing))
    finally:
        await failing.close()


class ParkingTransport(httpx.AsyncBaseTransport):
    """A transport that records the request and lets the test mutate the input
    mapping while the request is genuinely in flight."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.entered.set()
        await self.release.wait()
        return httpx.Response(200, json=JSON_LIST)


@pytest.mark.anyio
async def test_a_caller_mutation_while_a_request_is_in_flight_cannot_change_it() -> None:
    transport = ParkingTransport()
    client = HttpxJsonClient(timeout_seconds=5.0, max_response_bytes=1024, transport=transport)
    headers = {"X-Trace": "first"}
    try:
        task = asyncio.create_task(client.get_json(URL, params=PARAMS, headers=headers))
        async with asyncio.timeout(STALL_SAFETY):
            await transport.entered.wait()
        headers["X-Trace"] = "mutated"
        transport.release.set()
        await task
    finally:
        await client.close()
    assert transport.requests[0].headers["x-trace"] == "first"
