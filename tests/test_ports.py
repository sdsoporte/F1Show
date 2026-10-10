"""Offline acceptance tests for the injection boundaries and the model contracts.

The structural test at the bottom is the guard that keeps the store port
honest: the whole point of ``Store`` is that no storage engine appears in it, so
swapping the single-writer local store stays a change of implementation. No
network, no disk and no model call is involved.
"""

from __future__ import annotations

import pathlib
from typing import Any, get_type_hints

import pytest
from pydantic import ValidationError

from f1show.ports import (
    HttpDecodeError,
    HttpError,
    HttpClient,
    HttpResponse,
    HttpResponseTooLargeError,
    HttpTimeoutError,
    HttpTransportError,
    ModelRequest,
    ModelResponse,
    Store,
)

#: Obviously fictional: a real model ID must come from typed configuration.
MODEL_ID = "test-model-not-real"

PORTS_SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src" / "f1show" / "ports.py"
STORAGE_ENGINES = ("sqlite3", "sqlite", "duckdb")
STORE_METHODS = ("write_source_batch", "read_source_records", "set_watermark", "get_watermark", "close")


def model_request(**overrides: Any) -> ModelRequest:
    """Build a valid request, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "model_id": MODEL_ID,
        "prompt": "who is leading",
        "max_output_tokens": 64,
        "timeout_seconds": 5.0,
    }
    fields.update(overrides)
    return ModelRequest(**fields)


def model_response(**overrides: Any) -> ModelResponse:
    """Build a valid response, then apply the overrides under test."""
    fields: dict[str, Any] = {
        "model_id": MODEL_ID, "text": "ok", "input_tokens": 3, "output_tokens": 5,
    }
    fields.update(overrides)
    return ModelResponse(**fields)


def test_model_request_requires_a_model_id_with_no_default() -> None:
    assert model_request().model_id == MODEL_ID
    without_model_id = {"prompt": "x", "max_output_tokens": 64, "timeout_seconds": 5.0}
    with pytest.raises(ValidationError) as excinfo:
        ModelRequest(**without_model_id)
    assert "model_id" in str(excinfo.value)


@pytest.mark.parametrize(
    ("field", "bad"),
    [("max_output_tokens", 0), ("max_output_tokens", -1), ("timeout_seconds", 0), ("timeout_seconds", -0.5)],
)
def test_model_request_bounds_must_be_positive(field: str, bad: float) -> None:
    with pytest.raises(ValidationError) as excinfo:
        model_request(**{field: bad})
    assert field in str(excinfo.value)


@pytest.mark.parametrize("bad", ["", "   "])
def test_model_request_prompt_must_not_be_blank(bad: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        model_request(prompt=bad)
    assert "prompt" in str(excinfo.value)


def test_model_response_requires_a_non_empty_model_id() -> None:
    good = model_response()
    assert (good.text, good.input_tokens, good.output_tokens) == ("ok", 3, 5)
    with pytest.raises(ValidationError) as excinfo:
        model_response(model_id="")
    assert "model_id" in str(excinfo.value)


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("bad", [-1, -100])
def test_model_response_token_counts_must_not_be_negative(field: str, bad: int) -> None:
    with pytest.raises(ValidationError) as excinfo:
        model_response(**{field: bad})
    assert field in str(excinfo.value)


def test_model_contracts_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError) as excinfo:
        model_request(not_a_field_of_ours=True)
    assert "not_a_field_of_ours" in str(excinfo.value)
    with pytest.raises(ValidationError):
        model_response(not_a_field_of_ours=True)


def test_ports_source_names_no_storage_engine() -> None:
    lowered = PORTS_SOURCE.read_text(encoding="utf-8").lower()
    for engine in STORAGE_ENGINES:
        assert engine not in lowered, f"ports.py must not name the {engine!r} storage engine"


def test_no_store_method_annotation_names_a_storage_engine() -> None:
    for name in STORE_METHODS:
        annotations = getattr(Store, name).__annotations__
        rendered = " ".join(str(value) for value in annotations.values()).lower()
        for engine in STORAGE_ENGINES:
            assert engine not in rendered, f"Store.{name} leaks the {engine!r} storage engine"


def test_ports_source_names_no_http_transport_library() -> None:
    """The HTTP port stays engine-free for the same reason the store port does:
    a transport library mentioned here would tempt every role to import it."""
    lowered = PORTS_SOURCE.read_text(encoding="utf-8").lower()
    assert "httpx" not in lowered, "ports.py must not name the httpx transport library"


def test_http_response_canonicalises_headers_for_case_insensitive_lookup() -> None:
    response = HttpResponse(status_code=429, headers={"Retry-After": "3", "X-A": "1"})
    assert response.headers == {"retry-after": "3", "x-a": "1"}
    assert response.header("Retry-After") == "3"
    assert response.header("retry-after") == "3"
    assert response.header("RETRY-AFTER") == "3"
    assert response.header("absent") is None
    assert (response.status_code, response.payload) == (429, None)


def test_http_response_headers_are_read_only_and_payload_is_the_callers() -> None:
    payload = [{"record_id": "1"}]
    response = HttpResponse(status_code=200, headers={"a": "1"}, payload=payload)
    with pytest.raises(TypeError):
        response.headers["a"] = "2"  # type: ignore[index]
    # The payload crosses the boundary as the caller's own value, unlike the fake's,
    # which deep-copies on registration and on read.
    assert response.payload is payload


def test_http_error_types_are_distinct_typed_siblings() -> None:
    """Every HTTP failure is an ``HttpError``, and no subtype swallows another, so
    the retry policy in the next unit can tell a timeout from a transport failure."""
    errors = [HttpTransportError, HttpTimeoutError, HttpDecodeError, HttpResponseTooLargeError]
    assert len(set(errors)) == 4
    for error in errors:
        assert issubclass(error, HttpError)
        assert error is not HttpError
        for other in errors:
            assert other is error or not issubclass(error, other)


def test_http_client_port_declares_a_typed_response_and_a_close() -> None:
    assert get_type_hints(HttpClient.get_json)["return"] is HttpResponse
    assert any(name == "params" for name in get_type_hints(HttpClient.get_json))
    assert get_type_hints(HttpClient.close)["return"] is type(None)
