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
from datetime import datetime
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


@runtime_checkable
class HttpClient(Protocol):
    """Provisional outbound HTTP boundary; grows at F03.

    The single place the app reaches the network, so no role builds its own client.
    """

    async def get_json(
        self, url: str, *, params: Mapping[str, str] | None = None
    ) -> object: ...


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
    ) -> Sequence[Mapping[str, object]]: ...

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
