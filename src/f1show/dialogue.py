"""Dialogue contracts for the two-person commentary booth.

A turn carries the evidence references it may use and the model ID that produced
it. ``evidence`` must name at least one reference, the form of "personas may
only use what they are given", and ``model_id`` has **no default**, because the
value comes from configuration and must never be hardcoded. No real model ID
appears in this module.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class Speaker(str, Enum):
    """The two booth seats."""

    lead = "lead"
    color = "color"


class _Strict(BaseModel):
    """Internal contract: an unexpected field is a bug in our own pipeline."""

    model_config = ConfigDict(extra="forbid")


class Turn(_Strict):
    """One comment from one speaker.

    ``evidence`` must carry at least one non-empty reference: an unsourced claim
    is exactly what this contract exists to make impossible.
    """

    speaker: Speaker
    text: str
    evidence: tuple[str, ...]
    event_ref: str | None = None
    model_id: Annotated[str, Field(min_length=1)]
    created_at: AwareDatetime

    @field_validator("text")
    @classmethod
    def _strip_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped

    @field_validator("evidence")
    @classmethod
    def _non_empty_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("evidence must carry at least one reference")
        if any(not item.strip() for item in value):
            raise ValueError("evidence entries must not be empty")
        return value


class Transcript(_Strict):
    """An ordered session transcript.

    ``created_at`` must be non-decreasing across turns, so a transcript cannot
    reach a consumer silently out of order.
    """

    session_key: Annotated[int, Field(gt=0)]
    language: Annotated[str, Field(min_length=1)]
    turns: tuple[Turn, ...]

    @field_validator("turns")
    @classmethod
    def _in_order(cls, value: tuple[Turn, ...]) -> tuple[Turn, ...]:
        stamps = [turn.created_at for turn in value]
        if stamps != sorted(stamps):
            raise ValueError("turns must be in non-decreasing created_at order")
        return value
