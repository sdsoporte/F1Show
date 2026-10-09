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
    FrozenClock,
    InMemoryBus,
    InMemoryStore,
    ScriptedModelClient,
)
from f1show.ports import (
    Bus,
    Clock,
    HttpClient,
    ModelClient,
    ModelRequest,
    ModelResponse,
    Store,
)

UTC = dt.timezone.utc
MOMENT = dt.datetime(2024, 3, 2, 15, 0, 0, tzinfo=UTC)
MODEL_ID = "test-model-not-real"


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
async def test_fake_http_returns_registered_payload_and_records_calls() -> None:
    client = FakeHttpClient()
    url = "https://example.invalid/v1/sessions"
    client.register(url, [{"session_key": 9462}], params={"year": "2024"})
    assert await client.get_json(url, params={"year": "2024"}) == [{"session_key": 9462}]
    assert client.calls == [(url, {"year": "2024"})]


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
    assert await store.write_source_batch("drivers", 9462, [{"driver_number": 1}], observed_at=MOMENT) == 1
    await store.write_source_batch("drivers", 9463, [{"driver_number": 2}], observed_at=MOMENT)
    await store.write_source_batch("laps", 9462, [{"lap_number": 3}], observed_at=MOMENT)
    assert await store.read_source_records("drivers", 9462) == ({"driver_number": 1},)
    assert await store.read_source_records("drivers", 9463) == ({"driver_number": 2},)
    assert await store.read_source_records("laps", 9462) == ({"lap_number": 3},)


@pytest.mark.anyio
async def test_store_window_filters_by_observation_time() -> None:
    store = InMemoryStore()
    late = MOMENT + dt.timedelta(seconds=10)
    await store.write_source_batch("laps", 9462, [{"lap_number": 1}], observed_at=MOMENT)
    await store.write_source_batch("laps", 9462, [{"lap_number": 2}], observed_at=late)
    assert await store.read_source_records("laps", 9462, since=late) == ({"lap_number": 2},)
    assert await store.read_source_records("laps", 9462, until=MOMENT) == ({"lap_number": 1},)


@pytest.mark.anyio
async def test_store_returns_copies_that_cannot_reach_stored_state() -> None:
    store = InMemoryStore()
    nested: dict[str, Any] = {"driver_number": 1, "tags": ["fast"]}
    await store.write_source_batch("drivers", 9462, [nested], observed_at=MOMENT)
    # Mutating the caller's own nested value must not reach stored state.
    nested["tags"].append("mutated")
    stored = await store.read_source_records("drivers", 9462)
    assert stored[0]["tags"] == ["fast"]
    # Mutating a returned record must not reach stored state either.
    returned_tags = stored[0]["tags"]
    assert isinstance(returned_tags, list)
    returned_tags.append("also-mutated")
    again = await store.read_source_records("drivers", 9462)
    assert again[0]["tags"] == ["fast"]


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
