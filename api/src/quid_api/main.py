from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from quid_api.errors import RepositoryError, RepositoryErrorCode, http_status_for
from quid_api.routers import categories, expenses, health, import_rules, testing
from quid_api.settings import Settings, get_settings


def configure_logging(level: str) -> None:
    resolved = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    quid = logging.getLogger("quid_api")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    quid.setLevel(resolved)


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


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)
    app = FastAPI(
        title="Quid API",
        version="0.1.0",
        description="Expense tracker backend.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=cfg.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(RepositoryError, _repository_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)

    app.include_router(health.router)
    app.include_router(categories.router)
    app.include_router(import_rules.router)
    app.include_router(expenses.router)

    if cfg.testing:
        app.include_router(testing.router)

    return app


def asgi_factory() -> FastAPI:
    return create_app()


app: Any = create_app()
