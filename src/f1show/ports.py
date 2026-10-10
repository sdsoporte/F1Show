"""Provisional injection boundaries shared by every F1Show role.

Each protocol is a **provisional seam**: it declares only what a role needs
today and grows at the task named in its docstring. Nothing here imports a
storage engine, an HTTP library or a model SDK, so replacing the single-writer
local store stays a swap of implementation rather than a rewrite.

``ModelRequest`` and ``ModelResponse`` are internal contracts in the same strict
style as ``f1show.events``; no model ID is written here, it comes from config.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from f1show.events import EventEnvelope


@runtime_checkable
class Clock(Protocol):
    """Provisional clock boundary; grows at F03.

    ``now()`` is always timezone-aware and UTC, and it is injectable so tests
    never depend on wall-clock time.
    """

    def now(self) -> datetime: ...


class HttpError(Exception):
    """Base of every HTTP failure raised at this boundary.

    A transport library's own exception never crosses the port: callers catch these
    types, so replacing the adapter cannot change a caller's error handling.
    """


class HttpTransportError(HttpError):
    """The request could not be completed: connection, protocol or send failure."""


class HttpTimeoutError(HttpError):
    """The request, or the overall deadline, expired before the answer was complete.

    Deliberately a sibling of ``HttpTransportError`` rather than a subtype: the retry
    policy must be able to tell a slow endpoint from a broken one.
    """


class HttpDecodeError(HttpError):
    """A successful status returned a body that is not one JSON document."""


class HttpResponseTooLargeError(HttpError):
    """A successful response body exceeded the configured byte bound."""


@dataclass(frozen=True)
class HttpResponse:
    """One completed HTTP exchange, as every role above the transport sees it.

    ``status_code`` and ``headers`` are always present, including for failures and
    redirects, so a 429 or a 503 stays visible instead of being flattened into an
    exception. ``headers`` is published as a read-only mapping with lower-case names,
    which is what lets ``Retry-After`` be read without guessing the server's
    capitalisation; ``header`` applies that lookup.

    ``payload`` is the parsed JSON of a success response. A JSON ``null`` parses to
    ``None``, which is why the status is the first thing a consumer must read: a
    non-2xx response also carries ``payload=None``, because its body is deliberately
    never read.
    """

    status_code: int
    headers: Mapping[str, str]
    payload: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "headers",
            MappingProxyType(
                {str(name).lower(): str(value) for name, value in self.headers.items()}
            ),
        )

    def header(self, name: str) -> str | None:
        """Return ``name`` case-insensitively, or ``None`` when it is absent."""
        return self.headers.get(name.lower())


@runtime_checkable
class HttpClient(Protocol):
    """Outbound HTTP boundary; grows at F03c-2 with pacing and retries.

    The single place the app reaches the network, so no role builds its own client.

    ``get_json`` makes exactly one attempt and returns the whole exchange - status,
    canonical headers and payload - instead of raising for an HTTP status, because a
    retry policy has to see a 429 or a 503 first. Only transport, timeout, decode and
    body-size failures raise, and they raise ``HttpError`` subtypes so no transport
    library's exception ever crosses this port. ``close`` releases what the
    implementation owns, is safe to repeat, and makes ``get_json`` refuse.
    """

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> HttpResponse: ...

    async def close(self) -> None: ...


@runtime_checkable
class Bus(Protocol):
    """Provisional event transport; grows at F05.

    Separate consumer groups each see every event independently, and one group
    falling behind must never stall another.
    """

    async def publish(self, stream: str, event: EventEnvelope) -> str: ...

    async def read(
        self, stream: str, group: str, consumer: str, *, count: int = 10
    ) -> tuple[tuple[str, EventEnvelope], ...]: ...

    async def ack(self, stream: str, group: str, message_id: str) -> None: ...


@runtime_checkable
class Store(Protocol):
    """Provisional local store boundary; grows at F03.

    **No storage-engine type appears in any signature or annotation.** That is
    the point of this port: replacing the single-writer local store stays a swap
    of implementation rather than a rewrite of every role.

    **Writing the same identity twice replaces that record rather than appending
    a second one**, so a re-read that overlaps an earlier window is safe; and a
    record without a non-empty ``record_id`` string is refused rather than given
    an invented identity. Both rules are part of the contract precisely so an
    in-memory double and a real store are genuinely interchangeable rather than
    merely similar.
    """

    async def write_source_batch(
        self,
        family: str,
        session_key: int,
        records: Sequence[Mapping[str, object]],
        *,
        observed_at: datetime,
    ) -> int: ...

    async def read_source_records(
        self,
        family: str,
        session_key: int,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Sequence[tuple[datetime, Mapping[str, object]]]:
        """Records in the inclusive ``[since, until]`` observation window, oldest
        first, each paired with the instant it was observed.

        The observation time crosses the port instead of staying hidden inside
        the range filter. A store that can filter by time but cannot report it
        forces every consumer either to re-derive chronology from payload fields
        it may not have, or to lose it outright; with no production consumer yet,
        this is the moment to correct the asymmetry rather than a workaround to
        live with. There is deliberately **one** read method and not two: a
        bare-payload variant would be a trap, because a future consumer would
        reach for the obvious name and silently lose chronology.
        """
        ...

    async def set_watermark(
        self, endpoint: str, session_key: int, *, observed_at: datetime
    ) -> int: ...

    async def get_watermark(self, endpoint: str, session_key: int) -> datetime | None: ...

    async def close(self) -> None: ...


class _Strict(BaseModel):
    """Internal contract: an unexpected field is a bug in our own pipeline."""

    model_config = ConfigDict(extra="forbid")


class ModelRequest(_Strict):
    """One model call, as sent across the model boundary.

    ``model_id`` is required and has no default, so an unset model is a
    configuration error, never a silent fallback; the prompt must carry text.
    """

    model_id: Annotated[str, Field(min_length=1)]
    prompt: Annotated[str, Field(min_length=1)]
    max_output_tokens: Annotated[int, Field(gt=0)]
    timeout_seconds: Annotated[float, Field(gt=0)]

    @field_validator("prompt")
    @classmethod
    def _strip_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("prompt must not be blank")
        return stripped


class ModelResponse(_Strict):
    """One model call, as returned across the model boundary.

    ``input_tokens`` and ``output_tokens`` are carried so F08 can measure usage.
    No accounting or budget logic lives here.
    """

    model_id: Annotated[str, Field(min_length=1)]
    text: str
    input_tokens: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]


@runtime_checkable
class ModelClient(Protocol):
    """Provisional model boundary; grows at F08."""

    async def generate(self, request: ModelRequest) -> ModelResponse: ...
