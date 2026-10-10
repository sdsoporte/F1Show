"""The owned, offline-testable implementation of the outbound HTTP boundary.

Only this module knows which HTTP library is used, and no transport library's
exception crosses the port: everything becomes an ``f1show.ports`` error. The same rule
binds an injected ``httpx.AsyncBaseTransport``. Normalisation is narrow, and the
distinction is stated here rather than left implicit:

* The one send and the streamed body read are the transport-origin calls, and a failure
  raised by either becomes ``HttpTransportError``. A *foreign* exception -- one that is
  not an httpx error, a timeout or a cancellation -- means the injected transport broke
  its own contract (a real httpx transport raises ``httpx.*``), so it is converted
  rather than propagated: the port's message carries the sanitised endpoint and the
  exception's class only, and the original is preserved as ``__cause__``.
* An expired deadline stays ``HttpTimeoutError``, a cancellation stays
  ``asyncio.CancelledError``, an already-typed port error is never re-wrapped, and a
  process-control ``BaseException`` (``KeyboardInterrupt``, ``SystemExit``) passes
  through untouched.
* The JSON parse step sits deliberately outside that normalisation: our own parse
  failure stays ``HttpDecodeError``, so an internal bug or a malformed payload can never
  masquerade as a transport failure.

The adapter owns one async client, sends exactly one stateless attempt per call, and
bounds the request (headers and body) and the decoded body, with a separate finite
allowance for closing an exchange. That allowance bounds *cooperative* awaiting only: a
closer that blocks the event loop synchronously cannot be preempted at all, and no
allowance can bound it. The class repeats that limit where it applies instead of
implying a guarantee it cannot keep.

It carries no credentials of its own: the request is built explicitly, so no
client-level default header, cookie or authorization is attached; the environment is
not trusted for proxies, netrc or TLS material; a redirect is reported rather than
followed; and a URL that embeds credentials is refused instead of being turned into
an implicit ``Authorization`` header. Pacing, retries and rate scheduling deliberately
live in the next unit.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Mapping

import httpx

from f1show.ports import (
    HttpDecodeError,
    HttpError,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
    copy_form_fields,
    copy_request_headers,
)

#: Cleanup never gets more than this, whatever the request timeout is, so no wait can
#: hide behind a vague "overall" claim.
_MAX_CLOSE_SECONDS = 1.0

#: The documented content type of the OpenF1 token exchange.
_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def _positive_seconds(value: object, name: str) -> float:
    """Return ``value`` as a positive finite number of seconds, or refuse it."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number of seconds, got {type(value).__name__}")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{name} must be a positive, finite number of seconds, got {value!r}")
    return seconds


def _positive_integer(value: object, name: str) -> int:
    """Return ``value`` as a positive integer, or refuse it; a bool is not one."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
    return value


def _target(url: str | httpx.URL) -> str:
    """The endpoint with userinfo and query removed.

    An error may name where a request went without repeating anything that could be a
    credential, so the query string and any userinfo never reach a message.
    """
    try:
        parsed = httpx.URL(url)
    except Exception:
        return "<unparsable URL>"
    host = parsed.host or "<unknown-host>"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}{parsed.path}"


class HttpxJsonClient:
    """One owned async HTTP client behind the single ``get_json`` read.

    ``timeout_seconds`` is applied twice on purpose: as an explicit per-operation
    timeout on every request (connect, read, write and pool) and as the request budget
    covering headers *and* body. A per-operation timeout alone cannot bound an exchange,
    because it restarts on every chunk.

    Closing a response or the client is a separate phase with its own finite allowance,
    ``min(timeout_seconds, 1s)``, so no unbounded wait hides behind the word "overall".
    One ``get_json`` therefore spends at most ``timeout_seconds`` on the request and at
    most one allowance on cleanup, and both an expired request budget and an expired
    cleanup allowance are reported as ``HttpTimeoutError``. The allowance bounds
    *cooperative* awaiting, which is what a transport or stream that yields to the event
    loop does; a close that blocks the event loop synchronously cannot be preempted at all.

    ``max_response_bytes`` bounds the *decoded* body, so a compressed page that expands
    past the bound is rejected while it is read instead of after it was buffered.
    ``transport`` exists so tests can inject an offline transport; whatever is injected
    is owned by this object and closed with it, so there is no shared-ownership
    ambiguity.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # Validate before allocating anything, so a bad bound never leaves a client behind.
        self._timeout_seconds = _positive_seconds(timeout_seconds, "timeout_seconds")
        self._max_response_bytes = _positive_integer(max_response_bytes, "max_response_bytes")
        #: Finite cleanup allowance, derived from the validated request timeout.
        self._close_allowance_seconds = min(self._timeout_seconds, _MAX_CLOSE_SECONDS)
        self._closed = False
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(self._timeout_seconds),
            # No proxy, netrc or TLS configuration is inherited from the environment.
            trust_env=False,
            # A redirect is returned as a 3xx response, never silently re-sent elsewhere.
            follow_redirects=False,
        )

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Make exactly one GET attempt and return its response.

        An HTTP status never raises, not even a 4xx or a 5xx: the retry policy needs the
        status and headers to decide. Only a transport failure, a missed deadline, an
        undecodable successful body or an oversized body raises.

        ``headers`` adds optional request headers. Their shape is validated by the
        shared port rule - a non-mapping, or a non-``str`` key or value, is a
        ``TypeError`` before anything is sent - and their values are never stored on
        this client nor named in a message.

        Closing the response is bounded by the cleanup allowance and can never change the
        call's own outcome: a close failure annotates whatever failed first, and after an
        otherwise successful read that close failure becomes the call's typed ``HttpError``
        instead of a silent success.
        """
        self._require_open()
        return await self._perform(
            "GET", "get_json", url, params=params, headers=copy_request_headers(headers)
        )

    async def post_form_json(
        self,
        url: str,
        *,
        form: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Post one ``application/x-www-form-urlencoded`` form and return its response.

        The documented content type is set unless the caller already supplied a
        ``Content-Type`` header of its own. ``form`` and ``headers`` follow the same
        shape rule as ``get_json``: a non-mapping, or a non-``str`` key or value, is
        refused with ``TypeError`` before anything is sent. Everything else - response
        construction, typed failures, the byte bound, the deadline and cleanup - is the
        same shared path, so an HTTP status never raises and a 3xx is returned rather
        than followed.
        """
        self._require_open()
        return await self._perform(
            "POST",
            "post_form_json",
            url,
            form=copy_form_fields(form),
            headers=copy_request_headers(headers),
        )

    async def _perform(
        self,
        method: str,
        caller: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        form: Mapping[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Run one attempt with the semantics both public methods share.

        The request is built inside the normalisation so an unparsable URL still becomes
        a typed failure, and the credential refusal stays a plain ``ValueError``. A
        message carries only the sanitised endpoint and an exception's class, never a
        request header value.
        """
        response: httpx.Response | None = None
        result: HttpResponse | None = None
        close_failure: HttpError | None = None
        primary: BaseException | None = None
        try:
            try:
                request = httpx.Request(method, url, params=params, data=form, headers=headers)
                if request.url.username or request.url.password:
                    raise ValueError(
                        f"{caller} refuses a URL that embeds credentials; no request was sent"
                    )
                if form is not None and request.headers.get("content-type") is None:
                    request.headers["content-type"] = _FORM_CONTENT_TYPE
                async with asyncio.timeout(self._timeout_seconds):
                    response = await self._send(request)
                    result, close_failure = await self._consume(request, response)
            except TimeoutError as exc:
                raise HttpTimeoutError(
                    f"request to {_target(url)} exceeded the {self._timeout_seconds:g}s deadline"
                ) from exc
            except httpx.TimeoutException as exc:
                raise HttpTimeoutError(
                    f"request to {_target(url)} timed out ({type(exc).__name__})"
                ) from exc
            except httpx.TransportError as exc:
                raise HttpTransportError(
                    f"request to {_target(url)} failed in transport ({type(exc).__name__})"
                ) from exc
            except (httpx.InvalidURL, httpx.StreamError) as exc:
                # Neither is an ``httpx.HTTPError``; both must still be normalised here.
                raise HttpTransportError(
                    f"request to {_target(url)} could not be sent ({type(exc).__name__})"
                ) from exc
            except httpx.HTTPError as exc:
                raise HttpTransportError(
                    f"request to {_target(url)} failed before a response was complete "
                    f"({type(exc).__name__})"
                ) from exc
        except BaseException as exc:
            # This call's own failure, captured explicitly: the caller's ambient exception
            # state is never adopted as ours.
            primary = exc

        if response is not None and not response.is_closed:
            cleanup_failure = await self._close_response(response)
            if cleanup_failure is not None:
                if primary is not None:
                    primary.add_note(self._close_note(cleanup_failure))
                elif close_failure is None:
                    close_failure = cleanup_failure

        if primary is not None:
            raise primary
        if close_failure is not None:
            raise close_failure
        if result is None:
            # An internal invariant, not a real path: a call ends with a result or a failure.
            raise AssertionError(f"{caller} finished without a result and without a failure")
        return result

    async def close(self) -> None:
        """Close the owned client and its transport within the cleanup allowance.

        Safe to repeat. A close that fails or exceeds the allowance is reported as a typed
        ``HttpError`` and is never retried; from the moment closing starts this object
        refuses further reads, and after a reported failure the owned client's resources
        may not have been released. That limitation is stated rather than hidden.
        """
        if self._closed:
            return
        self._closed = True
        try:
            async with asyncio.timeout(self._close_allowance_seconds):
                await self._client.aclose()
        except TimeoutError as exc:
            raise HttpTimeoutError(
                "closing the HTTP client exceeded the "
                f"{self._close_allowance_seconds:g}s cleanup allowance"
            ) from exc
        except Exception as exc:
            raise HttpTransportError(
                f"closing the HTTP client failed ({type(exc).__name__})"
            ) from exc

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("HttpxJsonClient is closed")

    async def _send(self, request: httpx.Request) -> httpx.Response:
        """Send the single attempt, normalising a transport that breaks its contract.

        This is the transport-origin call outside the body read. An httpx failure, an
        expired deadline and a cancellation keep their own handling in ``get_json``; a
        foreign exception from an injected transport is a contract violation, so it
        becomes a typed ``HttpTransportError`` here instead of crossing the port untyped.
        """
        try:
            return await self._client.send(request, stream=True)
        except BaseException as exc:
            if self._is_foreign_transport_failure(exc):
                raise self._foreign_transport_error(
                    request.url, exc, "failed in transport"
                ) from exc
            raise

    async def _consume(
        self, request: httpx.Request, response: httpx.Response
    ) -> tuple[HttpResponse | None, HttpError | None]:
        """Turn a completed response into the port's typed value.

        Returns the typed response plus a close failure when httpx closed the stream at
        the end of a completed read and that close failed. The close failure is returned
        as data rather than raised, so it can neither displace the reason the read ended
        nor pass as a success; the caller decides which of the two it is.

        A non-2xx response is returned with its body deliberately unread, so a 429 or a
        503 stays visible with its headers and a huge error page cannot dominate; its
        payload is ``None``. A successful response must carry exactly one JSON
        document: an empty body is a contract violation rather than a null document, and
        while a JSON ``null`` parses to ``None``, the status is what tells the two apart.
        """
        headers = dict(response.headers)
        if not 200 <= response.status_code < 300:
            return HttpResponse(status_code=response.status_code, headers=headers, payload=None), None
        body, close_failure = await self._read_bounded(request, response)
        if not body:
            error = HttpDecodeError(
                f"a successful response from {_target(request.url)} carried no body; "
                "a JSON endpoint that sends nothing is a contract violation, "
                "not a null document"
            )
            self._annotate(error, close_failure)
            raise error
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            error = HttpDecodeError(
                f"a successful response from {_target(request.url)} was not valid JSON"
            )
            self._annotate(error, close_failure)
            raise error from exc
        typed = HttpResponse(status_code=response.status_code, headers=headers, payload=payload)
        return typed, close_failure

    async def _read_bounded(
        self, request: httpx.Request, response: httpx.Response
    ) -> tuple[bytes, HttpError | None]:
        """Read the decoded body, stopping the moment it passes the byte bound.

        httpx closes the stream as soon as a read completes, so a failure raised from an
        already-closed response is a *close* failure; it is returned as data so it cannot
        be mistaken for the read's own outcome.
        """
        chunks: list[bytes] = []
        total = 0
        try:
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > self._max_response_bytes:
                    raise HttpResponseTooLargeError(
                        f"a successful response from {_target(request.url)} exceeded "
                        f"{self._max_response_bytes} decoded bytes"
                    )
                chunks.append(chunk)
        except BaseException as exc:
            if self._is_implicit_close_failure(response, exc):
                return b"".join(chunks), self._close_failure(exc)
            if self._is_foreign_transport_failure(exc):
                raise self._foreign_transport_error(
                    request.url, exc, "failed while reading the response body"
                ) from exc
            raise
        return b"".join(chunks), None

    @staticmethod
    def _is_foreign_transport_failure(exc: BaseException) -> bool:
        """Whether ``exc`` is a transport failure that no port type already covers.

        Only a regular ``Exception`` is a candidate: an httpx error, a timeout, a
        cancellation and every process-control ``BaseException`` keep their own
        propagation, and a failure that already carries a port type is never re-wrapped.
        """
        return isinstance(exc, Exception) and not isinstance(
            exc, (HttpError, httpx.HTTPError, TimeoutError, asyncio.CancelledError)
        )

    @staticmethod
    def _foreign_transport_error(
        url: str | httpx.URL, exc: BaseException, detail: str
    ) -> HttpTransportError:
        """A typed transport failure for a contract-violating foreign exception.

        The message carries only the sanitised endpoint and the exception's class, never
        its own text; the caller preserves the value itself as ``__cause__``.
        """
        return HttpTransportError(f"request to {_target(url)} {detail} ({type(exc).__name__})")

    @staticmethod
    def _is_implicit_close_failure(response: httpx.Response, exc: BaseException) -> bool:
        """Whether ``exc`` came from httpx closing the stream at the end of a read.

        httpx marks the response closed *before* it awaits the stream's close and only
        closes after a read has completed, so an already-closed response means the failure
        belongs to closing. A cancellation and every already-typed failure are never
        reinterpreted: they stay the call's own outcome.
        """
        return response.is_closed and not isinstance(
            exc, (HttpError, httpx.HTTPError, TimeoutError, asyncio.CancelledError)
        )

    async def _close_response(self, response: httpx.Response) -> HttpError | None:
        """Close the response inside the cleanup allowance, converting failures to data.

        Returns a typed error when closing failed or exceeded the allowance, and ``None``
        when the response was already closed or closed cleanly, so cleanup can never
        displace the reason the call ended. No ``Exception`` escapes from here; a
        cancellation is not an ``Exception`` and still propagates.
        """
        if response.is_closed:
            return None
        try:
            async with asyncio.timeout(self._close_allowance_seconds):
                await response.aclose()
        except Exception as exc:
            return self._close_failure(exc)
        return None

    def _close_failure(self, exc: BaseException) -> HttpError:
        """A typed close failure; the underlying message is never repeated."""
        if isinstance(exc, TimeoutError):
            error: HttpError = HttpTimeoutError(
                "closing the response exceeded the "
                f"{self._close_allowance_seconds:g}s cleanup allowance"
            )
        else:
            error = HttpTransportError(f"closing the response failed ({type(exc).__name__})")
        error.__cause__ = exc
        return error

    def _close_note(self, close_error: HttpError) -> str:
        """A note safe to attach: type-level only, never a message, URL or header."""
        if isinstance(close_error, HttpTimeoutError):
            return (
                "the response stream also did not close within the "
                f"{self._close_allowance_seconds:g}s cleanup allowance"
            )
        cause = close_error.__cause__
        name = type(cause).__name__ if cause is not None else "unknown"
        return f"the response stream also failed to close ({name})"

    def _annotate(self, error: BaseException, close_failure: HttpError | None) -> None:
        """Annotate a primary failure with a close failure, preserving the primary."""
        if close_failure is not None:
            error.add_note(self._close_note(close_failure))
