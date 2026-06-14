"""Speech-to-text using faster-whisper (runs fully offline after the model
has been downloaded once)."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings

settings = get_settings()


@lru_cache
def _get_model():
    from faster_whisper import WhisperModel

    return WhisperModel(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE, compute_type="int8")


def transcribe_audio(file_path: str) -> str:
    model = _get_model()
    segments, _info = model.transcribe(file_path, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()
