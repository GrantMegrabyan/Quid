from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from quid_api.errors import RepositoryError, RepositoryErrorCode, http_status_for
from quid_api.routers import (
    ai_rules,
    amazon_orders,
    analytics,
    app_settings,
    categories,
    expenses,
    health,
    import_log,
    import_rules,
    testing,
)
from quid_api.settings import Settings, get_settings


def configure_logging(level: str, log_file: str | None = None) -> None:
    resolved = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    quid = logging.getLogger("quid_api")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path = str(log_path.resolve())
        has_file_handler = any(
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == Path(resolved_path)
            for handler in root.handlers
        )
        if not has_file_handler:
            file_handler = RotatingFileHandler(
                resolved_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            quid.info("logging.file.enabled path=%s", resolved_path)
    root.setLevel(resolved)
    quid.setLevel(resolved)


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach a small set of safe, static response headers to every response.

    Intentionally conservative: only headers that are safe for an API/JSON
    backend and won't break the local dev frontend. No HSTS here (it is
    HTTPS/deployment-specific and best set at the TLS terminator).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


def _error_body(code: RepositoryErrorCode | str, message: str) -> dict[str, str]:
    code_value = code.value if isinstance(code, RepositoryErrorCode) else code
    return {"code": code_value, "message": message}


async def _repository_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RepositoryError)
    return JSONResponse(
        status_code=http_status_for(exc.code),
        content=_error_body(exc.code, exc.message),
    )


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body",))
        parts.append(f"{loc}: {err.get('msg', 'invalid')}" if loc else err.get("msg", "invalid"))
    message = "; ".join(parts) or "Request body failed validation."
    return JSONResponse(
        status_code=422,
        content=_error_body(RepositoryErrorCode.VALIDATION, message),
    )


def _integrity_error_message(exc: IntegrityError) -> str:
    detail = str(exc.orig).lower()
    if "unique constraint failed" in detail:
        return "That record already exists."
    if "foreign key constraint failed" in detail:
        return "Referenced record does not exist."
    if "not null constraint failed" in detail:
        return "A required field is missing."
    if "check constraint failed" in detail:
        return "A value failed validation."
    return "The request conflicts with existing data."


async def _integrity_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, IntegrityError)
    # The request-scoped AsyncSession is created by ``get_session`` via
    # ``async with``; when the exception escapes the route, dependency cleanup
    # closes the session and returns the connection. We do not have the active
    # session here, so we only sanitize the response.
    logging.getLogger("quid_api").warning("integrity_error handled path=%s", request.url.path)
    return JSONResponse(
        status_code=422,
        content=_error_body(RepositoryErrorCode.VALIDATION, _integrity_error_message(exc)),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level, cfg.log_file)
    # Fail fast before serving a single request if production config is unsafe.
    cfg.validate_production()
    # Refuse to start if the destructive testing router is enabled against a
    # database that does not look like a throwaway test/e2e DB.
    cfg.validate_testing()

    docs_enabled = cfg.is_docs_enabled
    app = FastAPI(
        title="Quid API",
        version="0.1.0",
        description="Expense tracker backend.",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # In production, restrict to an explicit CORS allow-list; in development
    # keep the permissive localhost regex unchanged.
    if cfg.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=cfg.cors_origin_regex,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # TrustedHostMiddleware only when an allow-list is configured (always so in
    # production, where validate_production() guarantees it is non-empty).
    if cfg.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=cfg.allowed_hosts)

    if cfg.security_headers_enabled:
        app.add_middleware(SecurityHeadersMiddleware)

    app.add_exception_handler(RepositoryError, _repository_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(IntegrityError, _integrity_error_handler)

    app.include_router(health.router)
    app.include_router(categories.router)
    app.include_router(ai_rules.router)
    app.include_router(import_rules.router)
    app.include_router(import_log.router)
    app.include_router(expenses.router)
    app.include_router(amazon_orders.router)
    app.include_router(app_settings.router)
    app.include_router(analytics.router)

    if cfg.testing:
        app.include_router(testing.router)

    return app


def asgi_factory() -> FastAPI:
    return create_app()


app: Any = create_app()
