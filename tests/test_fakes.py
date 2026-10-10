"""Offline acceptance tests for the shipped in-memory test doubles.

Every fake must satisfy the protocol it claims and must fail loudly rather than
invent an answer: an unregistered URL, an exhausted response queue and a closed
store all raise. Nothing here touches the network, the wall clock or the disk.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from f1show.events import EventEnvelope, EventType
from f1show.fakes import (
    FakeHttpClient,
    FakeMonotonicClock,
    FrozenClock,
    InMemoryBus,
    InMemoryStore,
    ScriptedModelClient,
)
from f1show.ports import (
    Bus,
    Clock,
    HttpClient,
    HttpResponse,
    HttpTimeoutError,
    ModelClient,
    ModelRequest,
    ModelResponse,
    MonotonicClock,
    Store,
)

UTC = dt.timezone.utc
MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=UTC)
MODEL_ID = "test-model-not-real"
TOKEN_URL = "https://example.invalid/token"  # noqa: S105 (fictional endpoint, not a credential)
FORM = {"grant_type": "client_credentials", "client_id": "placeholder-client"}
#: Obviously fictional; never a real credential.
CALL_HEADERS = {"Authorization": "Bearer placeholder-token-not-a-real-credential"}


def envelope(event_id: str) -> EventEnvelope:
    """Build a minimal valid event for bus tests."""
    fields: dict[str, Any] = {
        "schema_version": 1, "event_id": event_id, "event_type": EventType.POSITION_CHANGE,
        "session_key": 9462, "event_time": MOMENT, "payload": {"driver_number": 1},
        "provenance": {"endpoint": "/v1/position", "observed_at": MOMENT},
    }
    return EventEnvelope(**fields)


def model_request() -> ModelRequest:
    """Build the one request every model test sends."""
    return ModelRequest(
        model_id=MODEL_ID, prompt="describe the lap",
        max_output_tokens=64, timeout_seconds=5.0,
    )


def model_response(text: str) -> ModelResponse:
    """Build a queued response with fictional usage numbers."""
    return ModelResponse(model_id=MODEL_ID, text=text, input_tokens=3, output_tokens=5)


@pytest.mark.parametrize(
    ("protocol", "build"),
    [
        (Clock, lambda: FrozenClock(MOMENT)),
        (HttpClient, FakeHttpClient),
        (Bus, InMemoryBus),
        (Store, InMemoryStore),
        (ModelClient, ScriptedModelClient),
    ],
)
def test_every_fake_satisfies_its_protocol(protocol: Any, build: Any) -> None:
    assert isinstance(build(), protocol)


def test_frozen_clock_is_deterministic_and_moves_only_by_hand() -> None:
    clock = FrozenClock(MOMENT)
    assert clock.now() == MOMENT
    assert clock.now() == clock.now()
    assert clock.advance(5) == MOMENT + dt.timedelta(seconds=5)
    assert clock.now() == MOMENT + dt.timedelta(seconds=5)
    with pytest.raises(ValueError):
        FrozenClock(dt.datetime(2024, 3, 2, 15, 0, 0))


def test_frozen_clock_rejects_a_negative_advance() -> None:
    clock = FrozenClock(MOMENT)
    with pytest.raises(ValueError) as excinfo:
        clock.advance(-1)
    assert "negative" in str(excinfo.value).lower()
    assert clock.now() == MOMENT


def test_frozen_clock_normalises_any_aware_offset_to_utc() -> None:
    offset = dt.timezone(dt.timedelta(hours=5, minutes=30))
    clock = FrozenClock(MOMENT.astimezone(offset))
    assert clock.now() == MOMENT
    assert clock.now().tzinfo is dt.timezone.utc


@pytest.mark.anyio
async def test_fake_http_returns_a_success_response_and_records_calls() -> None:
    """The port returns a typed response now, so the payload is asserted through
    ``.payload``; the URL-``params`` lookup and the call recording are unchanged."""
    client = FakeHttpClient()
    url = "https://example.invalid/v1/sessions"
    client.register(url, [{"session_key": 9462}], params={"year": "2024"})
    response = await client.get_json(url, params={"year": "2024"})
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    assert response.headers == {}
    assert response.payload == [{"session_key": 9462}]
    assert client.calls == [(url, {"year": "2024"})]


@pytest.mark.anyio
async def test_fake_http_never_lets_caller_mutation_poison_later_answers() -> None:
    client = FakeHttpClient()
    url = "https://example.invalid/v1/sessions"
    payload: dict[str, Any] = {"session_key": 9462, "tags": ["fast"]}
    headers = {"Retry-After": "2"}
    client.register(url, payload, headers=headers)
    # Mutating the fixtures handed to the fake must not reach stored state.
    payload["tags"].append("poisoned")
    headers["Retry-After"] = "999"
    first = await client.get_json(url)
    assert first.payload == {"session_key": 9462, "tags": ["fast"]}
    assert first.header("retry-after") == "2"
    # Mutating a returned payload must not reach stored state either.
    returned = first.payload["tags"]
    assert isinstance(returned, list)
    returned.append("also-poisoned")
    second = await client.get_json(url)
    assert second.payload == {"session_key": 9462, "tags": ["fast"]}
    assert second.header("Retry-After") == "2"


@pytest.mark.anyio
async def test_fake_http_can_register_a_non_2xx_status_with_headers() -> None:
    client = FakeHttpClient()
    url = "https://example.invalid/v1/sessions"
    client.register(url, None, status_code=503, headers={"Retry-After": "9"})
    response = await client.get_json(url)
    assert response.status_code == 503
    assert response.payload is None
    assert response.header("retry-after") == "9"


@pytest.mark.anyio
async def test_fake_http_delivers_scripted_outcomes_in_order_then_refuses() -> None:
    """A scripted queue wins over the static registration and never falls back or
    repeats: once it is drained the fake refuses instead of inventing an answer."""
    client = FakeHttpClient()
    url = "https://example.invalid/v1/sessions"
    client.register(url, "static")
    client.enqueue(url, HttpResponse(429, {"Retry-After": "1"}))
    client.enqueue(url, HttpResponse(200, {"Content-Type": "application/json"}, [{"record_id": "1"}]))
    first = await client.get_json(url)
    assert (first.status_code, first.header("retry-after")) == (429, "1")
    second = await client.get_json(url)
    assert (second.status_code, second.payload) == (200, [{"record_id": "1"}])
    with pytest.raises(RuntimeError, match="exhausted"):
        await client.get_json(url)
    assert len(client.calls) == 3, "the refused attempt is still recorded"


@pytest.mark.anyio
async def test_fake_http_raises_a_scripted_typed_error_and_records_the_call() -> None:
    client = FakeHttpClient()
    url = "https://example.invalid/v1/sessions"
    client.enqueue(url, HttpTimeoutError("scripted deadline"))
    with pytest.raises(HttpTimeoutError, match="scripted deadline"):
        await client.get_json(url)
    assert client.calls == [(url, None)]


def test_fake_http_refuses_a_scripted_outcome_that_is_not_a_response_or_error() -> None:
    client = FakeHttpClient()
    with pytest.raises(TypeError):
        client.enqueue("https://example.invalid/v1/x", "not-an-outcome")


@pytest.mark.anyio
async def test_fake_http_close_is_idempotent_and_refuses_further_reads() -> None:
    client = FakeHttpClient()
    url = "https://example.invalid/v1/sessions"
    client.register(url, [])
    await client.close()
    await client.close()
    with pytest.raises(RuntimeError):
        await client.get_json(url)
    assert client.calls == [], "a closed client records no call"



@pytest.mark.anyio
async def test_fake_http_raises_on_an_unregistered_url() -> None:

    client = FakeHttpClient()
    with pytest.raises(LookupError) as excinfo:
        await client.get_json("https://example.invalid/v1/never-registered")
    # Assert the deliberate guard specifically: ``KeyError`` is a ``LookupError``
    # subclass, so a bare ``pytest.raises(LookupError)`` cannot tell the explicit
    # refusal apart from an accidental dict miss.
    assert type(excinfo.value) is LookupError
    assert "never-registered" in str(excinfo.value)


# --- F03d-1: additive form-POST and request-header observability. Every existing
# --- behaviour above stays untouched; these probes only cover the new surface.


@pytest.mark.anyio
async def test_fake_http_form_post_records_the_form_and_headers_and_returns_the_answer() -> None:
    client = FakeHttpClient()
    client.register_form(
        TOKEN_URL, {"access_token": "placeholder"}, form=FORM, headers={"Content-Type": "application/json"}
    )
    response = await client.post_form_json(TOKEN_URL, form=FORM, headers=CALL_HEADERS)
    assert isinstance(response, HttpResponse)
    assert (response.status_code, response.payload) == (200, {"access_token": "placeholder"})
    assert response.header("content-type") == "application/json"
    assert client.post_calls == [(TOKEN_URL, dict(FORM), dict(CALL_HEADERS))]
    assert client.request_headers == [dict(CALL_HEADERS)]
    assert client.calls == [], "a form POST must not appear in the get_json call list"


@pytest.mark.anyio
async def test_fake_http_form_post_scripts_outcomes_in_order_then_refuses() -> None:
    client = FakeHttpClient()
    client.register_form(TOKEN_URL, "static", form=FORM)
    client.enqueue_form(TOKEN_URL, HttpResponse(429, {"Retry-After": "1"}), form=FORM)
    client.enqueue_form(
        TOKEN_URL, HttpResponse(200, {"Content-Type": "application/json"}, {"a": 1}), form=FORM
    )
    first = await client.post_form_json(TOKEN_URL, form=FORM)
    assert (first.status_code, first.header("retry-after")) == (429, "1")
    second = await client.post_form_json(TOKEN_URL, form=FORM)
    assert (second.status_code, second.payload) == (200, {"a": 1})
    with pytest.raises(RuntimeError, match="exhausted"):
        await client.post_form_json(TOKEN_URL, form=FORM)
    assert len(client.post_calls) == 3, "the refused attempt is still recorded"


@pytest.mark.anyio
async def test_fake_http_form_post_raises_on_an_unregistered_form() -> None:
    client = FakeHttpClient()
    with pytest.raises(LookupError) as excinfo:
        await client.post_form_json(TOKEN_URL, form=FORM)
    assert type(excinfo.value) is LookupError
    assert "/token" in str(excinfo.value)


@pytest.mark.anyio
async def test_fake_http_get_and_form_registrations_are_independent() -> None:
    client = FakeHttpClient()
    client.register(TOKEN_URL, "get-answer", params=FORM)
    client.register_form(TOKEN_URL, "form-answer", form=FORM)
    assert (await client.get_json(TOKEN_URL, params=FORM)).payload == "get-answer"
    assert (await client.post_form_json(TOKEN_URL, form=FORM)).payload == "form-answer"


@pytest.mark.parametrize("bad_headers", ["x", [("a", "b")], {"a": 1}, {1: "a"}])
@pytest.mark.anyio
async def test_fake_http_refuses_bad_request_headers_without_recording_a_call(
    bad_headers: Any,
) -> None:
    client = FakeHttpClient()
    with pytest.raises(TypeError):
        await client.get_json(TOKEN_URL, headers=bad_headers)
    with pytest.raises(TypeError):
        await client.post_form_json(TOKEN_URL, form=FORM, headers=bad_headers)
    assert (client.calls, client.post_calls, client.request_headers) == ([], [], [])


@pytest.mark.parametrize("bad_form", ["x", [("a", "b")], {"a": 1}, {1: "a"}, None])
@pytest.mark.anyio
async def test_fake_http_refuses_a_bad_form_without_recording_a_call(bad_form: Any) -> None:
    client = FakeHttpClient()
    with pytest.raises(TypeError):
        await client.post_form_json(TOKEN_URL, form=bad_form)
    assert (client.post_calls, client.request_headers) == ([], [])


@pytest.mark.anyio
async def test_fake_http_records_headers_verbatim_or_none_without_rewriting_names() -> None:
    client = FakeHttpClient()
    client.register(TOKEN_URL, [])
    await client.get_json(TOKEN_URL)
    assert client.request_headers == [None], "a call with no headers is recorded as None"
    await client.get_json(TOKEN_URL, headers={"X-Trace": "t"})
    assert client.request_headers[-1] == {"X-Trace": "t"}, "header names are never rewritten"
    assert client.calls == [(TOKEN_URL, None), (TOKEN_URL, None)]


@pytest.mark.anyio
async def test_fake_http_form_post_refuses_a_closed_client() -> None:
    client = FakeHttpClient()
    await client.close()
    await client.close()
    with pytest.raises(RuntimeError):
        await client.post_form_json(TOKEN_URL, form=FORM)
    assert client.post_calls == [], "a closed client records no form call"


@pytest.mark.anyio
async def test_fake_http_copies_a_form_payload_so_mutable_fixtures_cannot_poison_it() -> None:
    client = FakeHttpClient()
    payload: dict[str, Any] = {"access_token": "t", "scope": ["a"]}
    form = dict(FORM)
    headers = dict(CALL_HEADERS)
    client.register_form(TOKEN_URL, payload, form=form, headers=headers)
    payload["scope"].append("poison")
    form["grant_type"] = "poison"
    headers["Authorization"] = "poison"
    response = await client.post_form_json(TOKEN_URL, form=FORM, headers=CALL_HEADERS)
    assert response.payload == {"access_token": "t", "scope": ["a"]}
    assert client.post_calls == [(TOKEN_URL, dict(FORM), dict(CALL_HEADERS))]
    assert client.request_headers == [dict(CALL_HEADERS)]


@pytest.mark.anyio
async def test_bus_delivers_every_event_to_each_group_independently() -> None:
    bus = InMemoryBus()
    assert await bus.publish("events", envelope("evt-1")) == "1"
    assert await bus.publish("events", envelope("evt-2")) == "2"
    for group in ("analyst", "historian"):
        read = await bus.read("events", group, "c1")
        assert [event.event_id for _, event in read] == ["evt-1", "evt-2"]


@pytest.mark.anyio
async def test_bus_cursor_does_not_pass_unacked_messages() -> None:
    bus = InMemoryBus()
    await bus.publish("events", envelope("evt-1"))
    await bus.publish("events", envelope("evt-2"))
    first = await bus.read("events", "analyst", "c1")
    assert [mid for mid, _ in first] == ["1", "2"]
    assert [mid for mid, _ in await bus.read("events", "analyst", "c1")] == ["1", "2"]
    await bus.ack("events", "analyst", first[0][0])
    after = await bus.read("events", "analyst", "c1")
    assert [event.event_id for _, event in after] == ["evt-2"]


@pytest.mark.anyio
async def test_bus_acks_in_one_group_are_invisible_to_another() -> None:
    bus = InMemoryBus()
    await bus.publish("events", envelope("evt-1"))
    analyst = await bus.read("events", "analyst", "c1")
    await bus.ack("events", "analyst", analyst[0][0])
    historian = await bus.read("events", "historian", "c2")
    assert [event.event_id for _, event in historian] == ["evt-1"]
    assert await bus.read("events", "analyst", "c1") == ()


@pytest.mark.anyio
async def test_bus_does_not_redeliver_a_message_acked_out_of_order() -> None:
    bus = InMemoryBus()
    for event_id in ("evt-1", "evt-2", "evt-3"):
        await bus.publish("events", envelope(event_id))
    first = await bus.read("events", "analyst", "c1")
    assert [mid for mid, _ in first] == ["1", "2", "3"]
    # Ack a later message while an earlier one stays unacked. The cursor cannot
    # advance past evt-1, so the acked-set check is the only thing that can stop
    # evt-2 from being redelivered.
    await bus.ack("events", "analyst", "2")
    assert [mid for mid, _ in await bus.read("events", "analyst", "c1")] == ["1", "3"]


@pytest.mark.anyio
async def test_store_round_trips_records_isolated_by_family_and_session() -> None:
    store = InMemoryStore()
    assert (
        await store.write_source_batch(
            "drivers", 9462, [{"record_id": "1", "driver_number": 1}], observed_at=MOMENT
        )
        == 1
    )
    await store.write_source_batch(
        "drivers", 9463, [{"record_id": "2", "driver_number": 2}], observed_at=MOMENT
    )
    await store.write_source_batch(
        "laps", 9462, [{"record_id": "3", "lap_number": 3}], observed_at=MOMENT
    )
    assert await store.read_source_records("drivers", 9462) == (
        (MOMENT, {"record_id": "1", "driver_number": 1}),
    )
    assert await store.read_source_records("drivers", 9463) == (
        (MOMENT, {"record_id": "2", "driver_number": 2}),
    )
    assert await store.read_source_records("laps", 9462) == (
        (MOMENT, {"record_id": "3", "lap_number": 3}),
    )


@pytest.mark.anyio
async def test_store_upserts_by_identity_instead_of_appending() -> None:
    """The real store upserts on (family, session_key, record_id).

    A double that appended would let tests pass that the real store would not, so
    the replacement is part of the port contract rather than an implementation
    detail.
    """
    store = InMemoryStore()
    late = MOMENT + dt.timedelta(seconds=10)
    await store.write_source_batch(
        "drivers", 9462, [{"record_id": "1", "driver_number": 1}], observed_at=MOMENT
    )
    await store.write_source_batch(
        "drivers", 9462, [{"record_id": "1", "team_name": "X"}], observed_at=late
    )
    stored = await store.read_source_records("drivers", 9462)
    assert len(stored) == 1
    assert stored[0][0] == late
    assert stored[0][1]["team_name"] == "X"
    # The replacement carries the later observation time, so the window moved with it.
    assert await store.read_source_records("drivers", 9462, since=late) == stored


@pytest.mark.anyio
async def test_store_refuses_a_record_without_an_identity() -> None:
    store = InMemoryStore()
    with pytest.raises(ValueError, match="record_id"):
        await store.write_source_batch("drivers", 9462, [{"driver_number": 1}], observed_at=MOMENT)


@pytest.mark.anyio
async def test_store_window_filters_by_observation_time() -> None:
    store = InMemoryStore()
    late = MOMENT + dt.timedelta(seconds=10)
    await store.write_source_batch(
        "laps", 9462, [{"record_id": "1", "lap_number": 1}], observed_at=MOMENT
    )
    await store.write_source_batch(
        "laps", 9462, [{"record_id": "2", "lap_number": 2}], observed_at=late
    )
    assert await store.read_source_records("laps", 9462, since=late) == (
        (late, {"record_id": "2", "lap_number": 2}),
    )
    assert await store.read_source_records("laps", 9462, until=MOMENT) == (
        (MOMENT, {"record_id": "1", "lap_number": 1}),
    )


@pytest.mark.anyio
async def test_store_returns_copies_that_cannot_reach_stored_state() -> None:
    store = InMemoryStore()
    nested: dict[str, Any] = {"record_id": "1", "driver_number": 1, "tags": ["fast"]}
    await store.write_source_batch("drivers", 9462, [nested], observed_at=MOMENT)
    # Mutating the caller's own nested value must not reach stored state.
    nested["tags"].append("mutated")
    stored = await store.read_source_records("drivers", 9462)
    assert stored[0][1]["tags"] == ["fast"]
    # Mutating a returned record must not reach stored state either.
    returned_tags = stored[0][1]["tags"]
    assert isinstance(returned_tags, list)
    returned_tags.append("also-mutated")
    again = await store.read_source_records("drivers", 9462)
    assert again[0][1]["tags"] == ["fast"]


@pytest.mark.anyio
async def test_store_watermark_is_per_endpoint_and_session() -> None:
    store = InMemoryStore()
    assert await store.get_watermark("/v1/laps", 9462) is None
    assert await store.set_watermark("/v1/laps", 9462, observed_at=MOMENT) == 1
    assert await store.get_watermark("/v1/laps", 9462) == MOMENT
    assert await store.get_watermark("/v1/laps", 9463) is None
    assert await store.get_watermark("/v1/position", 9462) is None


@pytest.mark.anyio
async def test_store_raises_after_close() -> None:
    store = InMemoryStore()
    await store.close()
    await store.close()
    # Every guarded method on the store must refuse once it is closed.
    with pytest.raises(RuntimeError):
        await store.write_source_batch("laps", 9462, [{"lap_number": 1}], observed_at=MOMENT)
    with pytest.raises(RuntimeError):
        await store.read_source_records("laps", 9462)
    with pytest.raises(RuntimeError):
        await store.set_watermark("/v1/laps", 9462, observed_at=MOMENT)
    with pytest.raises(RuntimeError):
        await store.get_watermark("/v1/laps", 9462)


@pytest.mark.anyio
async def test_scripted_model_returns_queued_responses_in_order_and_records_requests() -> None:
    client = ScriptedModelClient([model_response("first"), model_response("second")])
    request = model_request()
    assert (await client.generate(request)).text == "first"
    assert (await client.generate(request)).text == "second"
    assert client.requests == [request, request]


@pytest.mark.anyio
async def test_scripted_model_raises_when_the_queue_is_exhausted() -> None:
    client = ScriptedModelClient()
    request = model_request()
    with pytest.raises(RuntimeError):
        await client.generate(request)
    assert client.requests == [request]


def test_fake_monotonic_clock_satisfies_the_pacing_seam() -> None:
    assert isinstance(FakeMonotonicClock(), MonotonicClock)


@pytest.mark.anyio
async def test_fake_monotonic_clock_advances_only_by_the_requested_sleep() -> None:
    clock = FakeMonotonicClock(start=10.0)
    assert clock.monotonic() == 10.0
    await clock.sleep(0.25)
    await clock.sleep(2.0)
    assert clock.monotonic() == 12.25
    assert clock.sleeps == [0.25, 2.0]


@pytest.mark.anyio
async def test_fake_monotonic_clock_rejects_a_negative_sleep() -> None:
    clock = FakeMonotonicClock()
    with pytest.raises(ValueError):
        await clock.sleep(-1.0)
    assert (clock.monotonic(), clock.sleeps) == (0.0, [])


@pytest.mark.anyio
async def test_the_monotonic_fake_never_moves_the_frozen_utc_clock() -> None:
    utc = FrozenClock(MOMENT)
    monotonic = FakeMonotonicClock(start=100.0)
    await monotonic.sleep(30.0)
    assert monotonic.monotonic() == 130.0
    assert utc.now() == MOMENT, "pacing time and observation time are separate seams"
