"""Text-to-speech. Defaults to fully-offline `pyttsx3` (uses the OS's built
in voices on macOS/Windows/Linux); falls back to ElevenLabs or OpenAI cloud
voices when an API key is configured."""

from __future__ import annotations

import os
import tempfile

from app.config import get_settings

settings = get_settings()


def synthesize_speech(text: str, engine: str | None = None, api_key: str | None = None) -> tuple[bytes, str]:
    """Returns (audio_bytes, content_type)."""
    engine = engine or settings.TTS_ENGINE
    if engine == "elevenlabs" and api_key:
        return _synthesize_elevenlabs(text, api_key)
    if engine == "openai" and api_key:
        return _synthesize_openai(text, api_key)
    return _synthesize_pyttsx3(text)


def _synthesize_pyttsx3(text: str) -> tuple[bytes, str]:
    import pyttsx3

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine = pyttsx3.init()
        engine.save_to_file(text, path)
        engine.runAndWait()
        with open(path, "rb") as f:
            data = f.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)
    return data, "audio/wav"


def _synthesize_elevenlabs(text: str, api_key: str) -> tuple[bytes, str]:
    import httpx

    voice_id = settings.ELEVENLABS_VOICE_ID
    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, "audio/mpeg"


def _synthesize_openai(text: str, api_key: str) -> tuple[bytes, str]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
    return response.read(), "audio/mpeg"
