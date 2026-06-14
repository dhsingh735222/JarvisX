import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    # Core
    APP_NAME: str = "JarvisX"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "change-me-in-production-please-use-a-random-64-char-string"
    ENCRYPTION_KEY: str = ""  # Fernet key, auto-generated on first run if empty
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR.parent / 'data' / 'jarvisx.db'}"
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # LLM Providers (used only if user has not stored their own keys via Settings UI)
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    DEFAULT_LLM_PROVIDER: str = "anthropic"  # anthropic | openai | google | ollama
    DEFAULT_LLM_MODEL: str = "claude-sonnet-4-5"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Voice
    WHISPER_MODEL_SIZE: str = "base"  # tiny, base, small, medium, large-v3
    WHISPER_DEVICE: str = "cpu"
    TTS_ENGINE: str = "pyttsx3"  # pyttsx3 (offline) | elevenlabs | openai
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"

    # Filesystem sandbox - root directory the assistant is allowed to operate on for file tools.
    # Defaults to the user's home directory.
    WORKSPACE_ROOT: str = os.path.expanduser("~")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
