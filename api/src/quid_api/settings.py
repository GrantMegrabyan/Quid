from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProductionConfigError(RuntimeError):
    """Raised when production mode is requested with unsafe or missing config."""


class TestingConfigError(RuntimeError):
    """Raised when the destructive testing router is enabled unsafely."""


# Substrings that mark a database URL as a throwaway test/e2e database. The
# testing router (which wipes all data) may only run against one of these
# unless testing_allow_unsafe_db is explicitly set.
_TEST_DB_MARKERS = ("test", "e2e", ":memory:")


def _looks_like_test_database(database_url: str) -> bool:
    return any(marker in database_url.lower() for marker in _TEST_DB_MARKERS)


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
    # Shared secret required on every /api/v1/testing/* request (sent as the
    # X-Testing-Token header). The testing router wipes ALL data, so even when
    # it is mounted (testing=True) it stays locked unless this token is set and
    # matches. Empty token => the router refuses every request (fail closed).
    testing_token: str | None = None
    # Escape hatch: allow testing=True against a database URL that does not look
    # like a throwaway test/e2e DB. Off by default so the destructive testing
    # router can never be pointed at a real database by accident.
    testing_allow_unsafe_db: bool = False
    log_level: str = "INFO"
    log_file: str = "./.data/quid.log"
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_chunk_size: int = 25
    refund_window_days: int = 60

    # --- Amazon combined-order matching (pass 2) safeguards ---------------
    # The combined-order pass sums 2..N nearby unmatched orders to find a
    # single bank charge. To keep it bounded on large histories it (a) works
    # within tight date windows, never globally, and (b) is hard-capped. Both
    # caps are generous enough that ordinary small histories are unaffected;
    # they only engage on pathological inputs (hundreds/thousands of orders
    # clustered in one date window). When a cap engages it is logged.
    #
    # Max eligible orders considered inside a single date-window partition.
    # A partition larger than this is skipped (logged) rather than risking a
    # combinatorial explosion.
    amazon_combined_max_window_orders: int = 60
    # Hard ceiling on the total number of candidate combinations generated
    # across all partitions in one pass. Generation stops once reached
    # (logged); behaviour for inputs under the ceiling is unchanged.
    amazon_combined_max_combinations: int = 50_000

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

    def validate_testing(self) -> None:
        """Fail fast when the destructive testing router is enabled unsafely.

        The /api/v1/testing/* router wipes ALL expenses and categories. When it
        is mounted (testing=True) we refuse to start against a database URL that
        does not look like a throwaway test/e2e database, unless the operator
        has explicitly opted in via QUID_TESTING_ALLOW_UNSAFE_DB=true.

        No-op when testing is disabled.
        """
        if not self.testing:
            return
        if self.testing_allow_unsafe_db:
            return
        if not _looks_like_test_database(self.database_url):
            raise TestingConfigError(
                "QUID_TESTING is enabled but QUID_DATABASE_URL does not look like a "
                "test/e2e database (expected one of "
                f"{', '.join(_TEST_DB_MARKERS)!r} in the URL). The testing router "
                "wipes ALL data. Point QUID_DATABASE_URL at a throwaway test DB, or "
                "set QUID_TESTING_ALLOW_UNSAFE_DB=true to override this guard.\n"
                f"  configured QUID_DATABASE_URL={self.database_url!r}"
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
