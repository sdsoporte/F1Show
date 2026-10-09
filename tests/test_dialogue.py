"""Offline acceptance tests for the commentary dialogue contracts.

A turn with no evidence is the structural form of "personas may only use what
they are given", and a transcript must be ordered. Every model ID below is
fictional; no real model ID is named and no model call is made.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from f1show.dialogue import Speaker, Transcript, Turn

UTC = dt.timezone.utc
T0 = dt.datetime(2024, 3, 2, 15, 0, 5, tzinfo=UTC)
T1 = dt.datetime(2024, 3, 2, 15, 0, 12, tzinfo=UTC)

#: A fictional model ID: the real value comes from configuration only.
TEST_MODEL_ID = "test-model"


def without(mapping: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Return a copy of ``mapping`` without ``keys``, for required-field tests."""
    return {key: value for key, value in mapping.items() if key not in keys}


def turn(**overrides: Any) -> Turn:
    """Build a valid turn, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "speaker": Speaker.lead,
        "text": "Verstappen leads by two tenths.",
        "evidence": ("evt-0001",),
        "model_id": TEST_MODEL_ID,
        "created_at": T0,
    }
    fields.update(overrides)
    return Turn(**fields)


def transcript(**overrides: Any) -> Transcript:
    """Build a valid in-order transcript, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "session_key": 9462,
        "language": "en",
        "turns": (turn(), turn(speaker=Speaker.color, text="Back to you.", created_at=T1)),
    }
    fields.update(overrides)
    return Transcript(**fields)


def test_speaker_is_exactly_lead_and_color() -> None:
    assert [member.value for member in Speaker] == ["lead", "color"]


def test_a_fully_grounded_turn_parses_and_text_is_stored_stripped() -> None:
    built = turn(text="  Verstappen leads.  ", event_ref="evt-0001")
    assert (built.text, built.evidence, built.model_id) == (
        "Verstappen leads.", ("evt-0001",), TEST_MODEL_ID
    )
    assert built.event_ref == "evt-0001"
    assert turn().event_ref is None


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_blank_text_is_rejected(blank: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        turn(text=blank)
    assert "text" in str(excinfo.value)


@pytest.mark.parametrize("evidence", [(), ("evt-0001", ""), ("evt-0001", "   ")])
def test_empty_evidence_and_empty_entries_are_rejected(evidence: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError) as excinfo:
        turn(evidence=evidence)
    assert "evidence" in str(excinfo.value)


def test_model_id_is_required_with_no_default_and_not_blank() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Turn(**without(turn().model_dump(), "model_id", "event_ref"))
    assert "model_id" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        turn(model_id="")
    assert "model_id" in str(excinfo.value)


def test_turn_rejects_an_unknown_field() -> None:
    with pytest.raises(ValidationError) as excinfo:
        turn(temperature=0.7)
    assert "temperature" in str(excinfo.value)


def test_naive_created_at_is_rejected_and_aware_is_accepted() -> None:
    with pytest.raises(ValidationError) as excinfo:
        turn(created_at=dt.datetime(2024, 3, 2, 15, 0, 5))
    assert "timezone" in str(excinfo.value)
    assert turn(created_at=T0).created_at == T0


def test_in_order_and_equal_timestamps_are_accepted() -> None:
    assert [item.speaker for item in transcript().turns] == [Speaker.lead, Speaker.color]
    assert len(transcript(turns=(turn(), turn(speaker=Speaker.color, created_at=T0))).turns) == 2


def test_an_out_of_order_transcript_is_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        transcript(turns=(turn(created_at=T1), turn(speaker=Speaker.color, created_at=T0)))
    assert "order" in str(excinfo.value)


def test_transcript_identifiers_and_fields_are_validated() -> None:
    with pytest.raises(ValidationError) as excinfo:
        transcript(session_key=0)
    assert "session_key" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        transcript(language="")
    assert "language" in str(excinfo.value)
    with pytest.raises(ValidationError) as excinfo:
        transcript(generated_by="x")
    assert "generated_by" in str(excinfo.value)
