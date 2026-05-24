from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUID_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./.data/quid.db"
    cors_origin_regex: str = r"^http://localhost(:\d+)?$"
    testing: bool = False
    log_level: str = "INFO"
    log_file: str = "./.data/quid.log"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-5.4-mini"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
