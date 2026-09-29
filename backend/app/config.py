from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    database_url: str = "postgresql+asyncpg://vocal:vocal@localhost:5432/vocal"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.3
    groq_reasoning_effort: str = "low"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "lauki_knowledge"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: Path = Path.home() / ".cache" / "fastembed"
    knowledge_dir: Path = REPO_ROOT / "data" / "knowledge"
    rag_top_k: int = 4

    # Shared secret ElevenLabs sends as a Bearer token when calling the custom LLM endpoint.
    custom_llm_api_key: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_webhook_secret: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    public_backend_url: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
