"""Evidence-attributed enrichment records.

An enrichment is a *finding*: it names where the fact came from and when the
source was read. A mandatory ``Attribution`` and at least one entry in ``facts``
make an ungrounded finding impossible to build — the structural form of "unknown
records stay absent", so a fact nobody could source is a skipped trivia line
rather than an empty record emitted as if it were a finding.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class EnrichmentKind(str, Enum):
    """The enrichment families, extensible as F07 adds more."""

    DRIVER_HISTORY = "driver_history"
    CIRCUIT_HISTORY = "circuit_history"


class _Strict(BaseModel):
    """Internal contract: an unexpected field is a bug in our own pipeline."""

    model_config = ConfigDict(extra="forbid")


class Attribution(_Strict):
    """Where a fact came from. An unattributed fact is not acceptable."""

    source: Annotated[str, Field(min_length=1)]
    source_url: Annotated[str, Field(min_length=1)]
    as_of: AwareDatetime


class EnrichmentRecord(_Strict):
    """One attributed finding.

    ``facts`` must carry at least one entry, so an empty enrichment cannot be
    emitted as if it were a result. ``event_ref`` is optional: history may be
    fetched ahead of the event it will later decorate.
    """

    kind: EnrichmentKind
    subject_id: Annotated[str, Field(min_length=1)]
    attribution: Attribution
    facts: dict[str, object]
    event_ref: str | None = None

    @field_validator("facts")
    @classmethod
    def _at_least_one_fact(cls, value: dict[str, object]) -> dict[str, object]:
        if not value:
            raise ValueError(
                "facts must carry at least one entry; an empty enrichment is not a finding"
            )
        return value
