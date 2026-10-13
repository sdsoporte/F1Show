"""Unit tests for the audio synthesis module (f1show.audio)."""

from __future__ import annotations

import pathlib
import pytest

from f1show.audio import (
    EdgeTTSAudioSynthesizer,
    FakeAudioSynthesizer,
    rate_for_mode,
    resolve_voice,
)
from f1show.dialogue import Speaker
from f1show.mode import TurnMode


def test_resolve_voice_es_ar() -> None:
    assert resolve_voice(Speaker.lead, language="es-AR") == "es-AR-TomasNeural"
    assert resolve_voice(Speaker.color, language="es-AR") == "es-UY-MateoNeural"


def test_resolve_voice_es_419() -> None:
    assert resolve_voice(Speaker.lead, language="es-419") == "es-MX-JorgeNeural"
    assert resolve_voice(Speaker.color, language="es-419") == "es-US-AlonsoNeural"


def test_resolve_voice_fallback() -> None:
    # Unmapped dialect falls back to es-AR default
    assert resolve_voice(Speaker.lead, language="unknown-LANG") == "es-AR-TomasNeural"
    assert resolve_voice(Speaker.color, language="unknown-LANG") == "es-UY-MateoNeural"


def test_resolve_voice_override() -> None:
    assert resolve_voice(Speaker.lead, override="custom_voice") == "custom_voice"
    assert resolve_voice(Speaker.lead, override="  custom_voice  ") == "custom_voice"


def test_rate_for_mode() -> None:
    assert rate_for_mode(TurnMode.CLIMAX) == "+10%"
    assert rate_for_mode(TurnMode.BUILD) == "+0%"
    assert rate_for_mode(None) == "+0%"


@pytest.mark.anyio
async def test_fake_synthesizer_synthesize() -> None:
    fake = FakeAudioSynthesizer()
    data = await fake.synthesize(
        "Se largó la carrera",
        speaker=Speaker.lead,
        language="es-AR",
        mode=TurnMode.CLIMAX,
    )
    assert isinstance(data, bytes)
    assert b"es-AR-TomasNeural" in data
    assert b"+10%" in data
    assert b"Se larg\xc3\xb3 la carrera" in data
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["speaker"] == Speaker.lead
    assert call["rate"] == "+10%"
    assert call["voice"] == "es-AR-TomasNeural"


@pytest.mark.anyio
async def test_fake_synthesizer_rejects_blank() -> None:
    fake = FakeAudioSynthesizer()
    with pytest.raises(ValueError, match="text must not be blank"):
        await fake.synthesize("   ", speaker=Speaker.lead)


@pytest.mark.anyio
async def test_fake_synthesizer_synthesize_to_file(tmp_path: pathlib.Path) -> None:
    fake = FakeAudioSynthesizer()
    out_file = tmp_path / "sub" / "turn.mp3"
    result_path = await fake.synthesize_to_file(
        "Auto en boxes",
        out_file,
        speaker=Speaker.color,
        language="es-419",
        mode=TurnMode.BUILD,
    )
    assert result_path == out_file
    assert out_file.exists()
    content = out_file.read_bytes()
    assert b"es-US-AlonsoNeural" in content
    assert b"+0%" in content


@pytest.mark.anyio
async def test_edge_tts_synthesizer_rejects_blank(tmp_path: pathlib.Path) -> None:
    synth = EdgeTTSAudioSynthesizer()
    with pytest.raises(ValueError, match="text must not be blank"):
        await synth.synthesize("", speaker=Speaker.lead)

    dummy_file = tmp_path / "dummy.mp3"
    with pytest.raises(ValueError, match="text must not be blank"):
        await synth.synthesize_to_file("   ", dummy_file, speaker=Speaker.lead)
