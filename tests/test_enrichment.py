"""Offline acceptance tests for evidence-attributed enrichment records.

An enrichment with no attribution, or with no fact at all, must be impossible to
construct: that is the structural form of "unknown records stay absent". No
network and no model call is involved.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from f1show.enrichment import Attribution, EnrichmentKind, EnrichmentRecord

UTC = dt.timezone.utc
AS_OF = dt.datetime(2024, 3, 2, 12, 0, 0, tzinfo=UTC)
SOURCE_URL = "https://api.jolpi.ca/ergast/f1/2024/drivers.json"


def without(mapping: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Return a copy of ``mapping`` without ``keys``, for required-field tests."""
    return {key: value for key, value in mapping.items() if key not in keys}


def record(**overrides: Any) -> EnrichmentRecord:
    """Build a valid enrichment record, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "kind": EnrichmentKind.DRIVER_HISTORY,
        "subject_id": "VER",
        "attribution": {"source": "Jolpica", "source_url": SOURCE_URL, "as_of": AS_OF},
        "facts": {"championships": 4},
    }
    fields.update(overrides)
    return EnrichmentRecord(**fields)


def test_enrichment_kind_is_this_projects_taxonomy() -> None:
    assert [member.value for member in EnrichmentKind] == ["driver_history", "circuit_history"]


def test_a_fully_attributed_record_parses() -> None:
    built = record(event_ref="evt-0001")
    assert (built.subject_id, built.facts, built.event_ref) == ("VER", {"championships": 4}, "evt-0001")
    assert built.attribution.source_url == SOURCE_URL


def test_enrichment_record_rejects_unknown_and_missing_fields() -> None:
    with pytest.raises(ValidationError) as excinfo:
        record(confidence=0.9)
    assert "confidence" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        EnrichmentRecord(**without(record().model_dump(), "facts", "event_ref"))
    assert "facts" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        record(facts={})
    assert "facts" in str(excinfo.value)


def test_empty_source_and_source_url_are_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        record(attribution={"source": "", "source_url": SOURCE_URL, "as_of": AS_OF})
    assert "source" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        record(attribution={"source": "Jolpica", "source_url": "", "as_of": AS_OF})
    assert "source_url" in str(excinfo.value)


def test_naive_as_of_is_rejected_and_aware_is_accepted() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Attribution(source="Jolpica", source_url=SOURCE_URL, as_of=dt.datetime(2024, 3, 2, 12))
    assert "timezone" in str(excinfo.value)
    assert Attribution(source="Jolpica", source_url=SOURCE_URL, as_of=AS_OF).as_of == AS_OF


def test_attribution_is_mandatory_and_subject_is_not_blank() -> None:
    with pytest.raises(ValidationError) as excinfo:
        EnrichmentRecord(**without(record().model_dump(), "attribution", "event_ref"))
    assert "attribution" in str(excinfo.value)
    partial = {"source": "Jolpica", "as_of": AS_OF}
    with pytest.raises(ValidationError) as excinfo:
        Attribution(**partial)
    assert "source_url" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        record(subject_id="")
    assert "subject_id" in str(excinfo.value)
