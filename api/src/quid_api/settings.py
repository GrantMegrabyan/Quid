from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProductionConfigError(RuntimeError):
    """Raised when production mode is requested with unsafe or missing config."""


def _split_csv(value: str | list[str] | None) -> list[str]:
    """Parse a comma-separated string (or list) into a clean list of entries.

    Empty/whitespace-only entries are dropped. Accepts a list too so that
    programmatic construction (e.g. in tests) can pass a list directly.
    """
    if value is None:
        return []
    parts = value.split(",") if isinstance(value, str) else value
    return [item.strip() for item in parts if item and item.strip()]


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
    openrouter_chunk_size: int = 25
    refund_window_days: int = 60

    # --- Production hardening ---------------------------------------------
    # Deployment environment. "development" (default) keeps the permissive
    # localhost behaviour; "production" turns on fail-fast safety checks and
    # disables docs/OpenAPI unless explicitly re-enabled.
    environment: str = "development"
    # Hosts allowed via TrustedHostMiddleware (comma-separated in env). Empty
    # means "any host", which is fine for local dev but rejected in production.
    allowed_hosts: list[str] = []
    # Exact CORS origins allowed in production (comma-separated in env). In
    # development cors_origin_regex governs CORS instead; in production this
    # explicit allow-list is required and the regex is ignored.
    cors_allowed_origins: list[str] = []
    # Expose FastAPI /docs, /redoc and /openapi.json. Off by default in
    # production (see is_docs_enabled), always on in development.
    docs_enabled: bool = False
    # Attach the safe response-header middleware (X-Content-Type-Options, etc).
    security_headers_enabled: bool = True

    @field_validator("allowed_hosts", "cors_allowed_origins", mode="before")
    @classmethod
    def _coerce_csv(cls, value: str | list[str] | None) -> list[str]:
        return _split_csv(value)

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def is_docs_enabled(self) -> bool:
        """Docs are always on outside production; in production only when
        explicitly enabled via QUID_DOCS_ENABLED."""
        return self.docs_enabled if self.is_production else True

    def validate_production(self) -> None:
        """Fail fast when production mode is configured unsafely.

        No-op outside production so local development behaviour is unchanged.
        """
        if not self.is_production:
            return
        problems: list[str] = []
        if not self.allowed_hosts:
            problems.append(
                "QUID_ALLOWED_HOSTS must be set in production "
                "(comma-separated list of trusted hostnames)."
            )
        elif "*" in self.allowed_hosts:
            problems.append(
                "QUID_ALLOWED_HOSTS must not contain '*' in production "
                "(wildcard hosts defeat TrustedHostMiddleware)."
            )
        if not self.cors_allowed_origins:
            problems.append(
                "QUID_CORS_ALLOWED_ORIGINS must be set in production "
                "(comma-separated list of exact allowed browser origins)."
            )
        elif "*" in self.cors_allowed_origins:
            problems.append(
                "QUID_CORS_ALLOWED_ORIGINS must not contain '*' in production "
                "(a wildcard with credentials is unsafe)."
            )
        if self.testing:
            problems.append("QUID_TESTING must be false in production.")
        if problems:
            raise ProductionConfigError(
                "Unsafe production configuration:\n  - " + "\n  - ".join(problems)
            )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
