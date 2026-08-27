from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    # NoDecode: pydantic-settings otherwise tries to JSON-decode a list-typed
    # env var before _split_csv below ever runs, which raises on a plain
    # comma-separated string instead of falling through to the validator.
    # Verified against a real chat completion call on 2026-08-27 — the
    # previous list (llama-3.1/gemma-2/mistral-7b) had aged out of
    # OpenRouter's free tier entirely (404 on every one), silently forcing
    # every QA/Critic call through the "all models failed" degrade path.
    # Check openrouter.ai/models periodically; free-tier availability rotates.
    openrouter_fallback_models: Annotated[list[str], NoDecode] = [
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "z-ai/glm-5.2:free",
    ]
    # Separate list: must be vision-capable models, used only by the OCR agent.
    openrouter_vision_fallback_models: Annotated[list[str], NoDecode] = [
        "minimax/minimax-m3:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "google/gemma-4-26b-a4b-it:free",
    ]

    # Phase 4 hard task — tools/fb_graph_api_tools.py. Empty by default: the
    # Social Intelligence Agent falls back to the CSV path (social_csv_tools.py)
    # whenever fb_page_access_token isn't set, same "degrade, don't crash"
    # pattern as the OpenRouter key.
    fb_page_access_token: str = ""
    fb_page_id: str = ""
    fb_api_version: str = "v21.0"

    # Web search tool (tools/web_search_tools.py). Empty by default: the tool
    # raises a clear error if called with no key configured rather than
    # silently returning nothing.
    tavily_api_key: str = ""

    @field_validator(
        "openrouter_fallback_models", "openrouter_vision_fallback_models", mode="before"
    )
    @classmethod
    def _split_csv(cls, value: object) -> object:
        # lets the *_FALLBACK_MODELS env vars be plain comma-separated values
        # instead of requiring JSON array syntax.
        if isinstance(value, str):
            return [model.strip() for model in value.split(",") if model.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
