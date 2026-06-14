import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import ApiKey, User
from app.security import decrypt_value
from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech

router = APIRouter(prefix="/api/voice", tags=["voice"])
settings = get_settings()


class SpeakRequest(BaseModel):
    text: str


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        text = transcribe_audio(tmp_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        os.unlink(tmp_path)
    return {"text": text}


@router.post("/speak")
def speak(payload: SpeakRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    engine = user.tts_engine or settings.TTS_ENGINE
    api_key: str | None = None

    if engine in ("elevenlabs", "openai"):
        row = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == engine).first()
        if row:
            api_key = decrypt_value(row.encrypted_value)
        elif engine == "elevenlabs":
            api_key = settings.ELEVENLABS_API_KEY
        elif engine == "openai":
            api_key = settings.OPENAI_API_KEY
        if not api_key:
            engine = "pyttsx3"

    try:
        audio, content_type = synthesize_speech(payload.text, engine=engine, api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {exc}") from exc

    return Response(content=audio, media_type=content_type)
