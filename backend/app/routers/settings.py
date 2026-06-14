from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import ApiKey, User
from app.schemas import ApiKeyIn, ApiKeyOut, SettingsOut, SettingsUpdate
from app.security import encrypt_value

router = APIRouter(prefix="/api/settings", tags=["settings"])
settings = get_settings()

KNOWN_PROVIDERS = ["anthropic", "openai", "google", "elevenlabs"]


@router.get("", response_model=SettingsOut)
def get_user_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = {r.provider: r for r in db.query(ApiKey).filter(ApiKey.user_id == user.id).all()}
    api_keys = [
        ApiKeyOut(provider=p, configured=p in rows, updated_at=rows[p].updated_at if p in rows else None)
        for p in KNOWN_PROVIDERS
    ]
    return SettingsOut(
        llm_provider=user.llm_provider or settings.DEFAULT_LLM_PROVIDER,
        llm_model=user.llm_model or settings.DEFAULT_LLM_MODEL,
        tts_engine=user.tts_engine or settings.TTS_ENGINE,
        api_keys=api_keys,
    )


@router.put("", response_model=SettingsOut)
def update_user_settings(
    payload: SettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if payload.llm_provider is not None:
        user.llm_provider = payload.llm_provider
    if payload.llm_model is not None:
        user.llm_model = payload.llm_model
    if payload.tts_engine is not None:
        user.tts_engine = payload.tts_engine
    db.commit()
    return get_user_settings(db=db, user=user)


@router.put("/api-keys", response_model=ApiKeyOut)
def upsert_api_key(payload: ApiKeyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == payload.provider).first()
    encrypted = encrypt_value(payload.value)
    if row:
        row.encrypted_value = encrypted
    else:
        row = ApiKey(user_id=user.id, provider=payload.provider, encrypted_value=encrypted)
        db.add(row)
    db.commit()
    db.refresh(row)
    return ApiKeyOut(provider=row.provider, configured=True, updated_at=row.updated_at)


@router.delete("/api-keys/{provider}", status_code=204)
def delete_api_key(provider: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.provider == provider).first()
    if row:
        db.delete(row)
        db.commit()
    return None


@router.get("/workspace")
def get_workspace_info(user: User = Depends(get_current_user)):
    return {"workspace_root": settings.WORKSPACE_ROOT}
