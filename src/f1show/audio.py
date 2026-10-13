"""Audio synthesis for the two-person commentary booth.

Turns aired commentary into spoken broadcast audio. This module separates voice
identity resolution and prosody modulation from network transport.

Two rules shape this module:

* **Speaker and language determine the voice.** Alex (lead) and Sam (colour) have
  distinct neural voice personas per dialect:
  - ``es-AR`` (default): Alex -> ``es-AR-TomasNeural``, Sam -> ``es-UY-MateoNeural``.
  - ``es-419``: Alex -> ``es-MX-JorgeNeural``, Sam -> ``es-US-AlonsoNeural``.
  - Other variants (``es-MX``, ``es-ES``, ``en``) carry their own matched pairs.
* **Turn mode drives rate prosody.** Climax turns (overtakes, incidents, pit stops)
  accelerate speaking rate (+10%), while routine build turns retain standard pace (+0%).
* **Blank or whitespace text is refused.**
* **Offline testability.** An injectable :class:`AudioSynthesizer` protocol and
  a deterministic :class:`FakeAudioSynthesizer` allow offline testing with zero
  network calls.
"""

from __future__ import annotations

import pathlib
from collections.abc import Mapping
from typing import Protocol

from f1show.dialogue import Speaker
from f1show.mode import TurnMode

#: Declared voice catalogue mapping language code -> speaker -> neural voice name.
VOICE_MAP: Mapping[str, Mapping[Speaker, str]] = {
    "es-AR": {
        Speaker.lead: "es-AR-TomasNeural",
        Speaker.color: "es-UY-MateoNeural",
    },
    "es-419": {
        Speaker.lead: "es-MX-JorgeNeural",
        Speaker.color: "es-US-AlonsoNeural",
    },
    "es-MX": {
        Speaker.lead: "es-MX-JorgeNeural",
        Speaker.color: "es-MX-DaliaNeural",
    },
    "es-ES": {
        Speaker.lead: "es-ES-AlvaroNeural",
        Speaker.color: "es-ES-XimenaNeural",
    },
    "en": {
        Speaker.lead: "en-US-GuyNeural",
        Speaker.color: "en-US-ChristopherNeural",
    },
}

DEFAULT_LANGUAGE = "es-AR"


def resolve_voice(
    speaker: Speaker,
    *,
    language: str = DEFAULT_LANGUAGE,
    override: str | None = None,
) -> str:
    """Resolve the neural voice name for a given speaker and dialect.

    Falls back to the declared default language if a dialect is not mapped.
    """
    if override and override.strip():
        return override.strip()

    lang_voices = VOICE_MAP.get(language.strip()) or VOICE_MAP[DEFAULT_LANGUAGE]
    return lang_voices[speaker]


def rate_for_mode(mode: TurnMode | None) -> str:
    """Determine speech rate modulation based on turn prosody mode."""
    if mode is TurnMode.CLIMAX:
        return "+10%"
    return "+0%"


class AudioSynthesizer(Protocol):
    """Protocol for audio synthesis providers."""

    async def synthesize(
        self,
        text: str,
        *,
        speaker: Speaker,
        language: str = DEFAULT_LANGUAGE,
        mode: TurnMode | None = None,
        rate: str | None = None,
    ) -> bytes: ...

    async def synthesize_to_file(
        self,
        text: str,
        destination: str | pathlib.Path,
        *,
        speaker: Speaker,
        language: str = DEFAULT_LANGUAGE,
        mode: TurnMode | None = None,
        rate: str | None = None,
    ) -> pathlib.Path: ...


class EdgeTTSAudioSynthesizer:
    """Production audio synthesizer using Edge Neural TTS."""

    async def synthesize(
        self,
        text: str,
        *,
        speaker: Speaker,
        language: str = DEFAULT_LANGUAGE,
        mode: TurnMode | None = None,
        rate: str | None = None,
    ) -> bytes:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text must not be blank")

        import edge_tts

        voice = resolve_voice(speaker, language=language)
        effective_rate = rate if rate is not None else rate_for_mode(mode)

        communicate = edge_tts.Communicate(clean_text, voice, rate=effective_rate)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])

        return b"".join(chunks)

    async def synthesize_to_file(
        self,
        text: str,
        destination: str | pathlib.Path,
        *,
        speaker: Speaker,
        language: str = DEFAULT_LANGUAGE,
        mode: TurnMode | None = None,
        rate: str | None = None,
    ) -> pathlib.Path:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text must not be blank")

        dest_path = pathlib.Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        import edge_tts

        voice = resolve_voice(speaker, language=language)
        effective_rate = rate if rate is not None else rate_for_mode(mode)

        communicate = edge_tts.Communicate(clean_text, voice, rate=effective_rate)
        await communicate.save(str(dest_path))
        return dest_path


class FakeAudioSynthesizer:
    """Deterministic, testable fake synthesizer that makes zero network calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def synthesize(
        self,
        text: str,
        *,
        speaker: Speaker,
        language: str = DEFAULT_LANGUAGE,
        mode: TurnMode | None = None,
        rate: str | None = None,
    ) -> bytes:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text must not be blank")

        voice = resolve_voice(speaker, language=language)
        effective_rate = rate if rate is not None else rate_for_mode(mode)

        self.calls.append(
            {
                "text": clean_text,
                "speaker": speaker,
                "voice": voice,
                "language": language,
                "mode": mode,
                "rate": effective_rate,
            }
        )
        return f"FAKE_AUDIO:{voice}:{effective_rate}:{clean_text}".encode()

    async def synthesize_to_file(
        self,
        text: str,
        destination: str | pathlib.Path,
        *,
        speaker: Speaker,
        language: str = DEFAULT_LANGUAGE,
        mode: TurnMode | None = None,
        rate: str | None = None,
    ) -> pathlib.Path:
        data = await self.synthesize(
            text, speaker=speaker, language=language, mode=mode, rate=rate
        )
        dest_path = pathlib.Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(data)
        return dest_path
