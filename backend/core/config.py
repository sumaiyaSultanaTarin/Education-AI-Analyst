from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Ordered fallback list — free-tier OpenRouter models throttle/rotate,
    # so the client tries each in turn rather than assuming one is always up.
    openrouter_fallback_models: list[str] = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ]

    @field_validator("openrouter_fallback_models", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        # lets OPENROUTER_FALLBACK_MODELS be a plain comma-separated .env value
        # instead of requiring JSON array syntax.
        if isinstance(value, str):
            return [model.strip() for model in value.split(",") if model.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
