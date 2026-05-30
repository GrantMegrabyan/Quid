from __future__ import annotations

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from httpx import ASGITransport, AsyncClient

from quid_api.main import SecurityHeadersMiddleware, create_app
from quid_api.settings import ProductionConfigError, Settings


def _prod_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "production",
        "allowed_hosts": "api.example.com",
        "cors_allowed_origins": "https://app.example.com",
        "testing": False,
        "openrouter_api_key": None,
    }
    base.update(overrides)
    return Settings.model_validate(base)


def _middleware_classes(app) -> list[type]:
    return [m.cls for m in app.user_middleware]


# --- Settings parsing -----------------------------------------------------


def test_csv_fields_parse_from_string():
    s = Settings.model_validate(
        {
            "allowed_hosts": "a.com, b.com ,, c.com",
            "cors_allowed_origins": "https://x.com,https://y.com",
        }
    )
    assert s.allowed_hosts == ["a.com", "b.com", "c.com"]
    assert s.cors_allowed_origins == ["https://x.com", "https://y.com"]


def test_default_is_development_not_production():
    s = Settings()
    assert s.is_production is False
    assert s.is_docs_enabled is True  # docs always on in dev


def test_production_docs_off_by_default():
    s = _prod_settings()
    assert s.is_production is True
    assert s.is_docs_enabled is False


def test_production_docs_can_be_explicitly_enabled():
    s = _prod_settings(docs_enabled=True)
    assert s.is_docs_enabled is True


# --- validate_production: rejects unsafe config ---------------------------


def test_validate_production_noop_in_development():
    # No allowed hosts / origins, but development => must not raise.
    Settings(environment="development").validate_production()


def test_production_rejects_missing_allowed_hosts():
    with pytest.raises(ProductionConfigError, match="QUID_ALLOWED_HOSTS"):
        _prod_settings(allowed_hosts="").validate_production()


def test_production_rejects_wildcard_allowed_hosts():
    with pytest.raises(ProductionConfigError, match="ALLOWED_HOSTS"):
        _prod_settings(allowed_hosts="*").validate_production()


def test_production_rejects_missing_cors_origins():
    with pytest.raises(ProductionConfigError, match="QUID_CORS_ALLOWED_ORIGINS"):
        _prod_settings(cors_allowed_origins="").validate_production()


def test_production_rejects_wildcard_cors_origins():
    with pytest.raises(ProductionConfigError, match="CORS_ALLOWED_ORIGINS"):
        _prod_settings(cors_allowed_origins="*").validate_production()


def test_production_rejects_testing_flag():
    with pytest.raises(ProductionConfigError, match="QUID_TESTING"):
        _prod_settings(testing=True).validate_production()


def test_production_reports_multiple_problems_at_once():
    with pytest.raises(ProductionConfigError) as excinfo:
        _prod_settings(allowed_hosts="", cors_allowed_origins="").validate_production()
    msg = str(excinfo.value)
    assert "QUID_ALLOWED_HOSTS" in msg
    assert "QUID_CORS_ALLOWED_ORIGINS" in msg


def test_valid_production_config_passes():
    # Should not raise.
    _prod_settings().validate_production()


# --- create_app wiring ----------------------------------------------------


def test_create_app_fails_fast_on_unsafe_production():
    with pytest.raises(ProductionConfigError):
        create_app(settings=_prod_settings(allowed_hosts=""))


def test_production_installs_trustedhost_and_security_middleware():
    app = create_app(settings=_prod_settings())
    classes = _middleware_classes(app)
    assert TrustedHostMiddleware in classes
    assert SecurityHeadersMiddleware in classes
    assert CORSMiddleware in classes


def test_production_disables_docs_and_openapi():
    app = create_app(settings=_prod_settings())
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_production_docs_enabled_restores_routes():
    app = create_app(settings=_prod_settings(docs_enabled=True))
    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"


def test_development_keeps_docs_and_no_trustedhost():
    app = create_app(settings=Settings(environment="development"))
    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"
    # No allowed_hosts configured in dev => TrustedHostMiddleware not added.
    assert TrustedHostMiddleware not in _middleware_classes(app)


def test_security_headers_can_be_disabled():
    app = create_app(settings=Settings(security_headers_enabled=False))
    assert SecurityHeadersMiddleware not in _middleware_classes(app)


# --- runtime middleware behaviour -----------------------------------------


async def test_security_headers_present_on_response():
    app = create_app(settings=Settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "no-referrer"
    assert res.headers["Cross-Origin-Opener-Policy"] == "same-origin"


async def test_trusted_host_allows_configured_host():
    app = create_app(settings=_prod_settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://api.example.com") as client:
        res = await client.get("/health")
    assert res.status_code == 200


async def test_trusted_host_rejects_unknown_host():
    app = create_app(settings=_prod_settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://evil.example.com") as client:
        res = await client.get("/health")
    assert res.status_code == 400


async def test_production_openapi_route_is_404():
    app = create_app(settings=_prod_settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://api.example.com") as client:
        res = await client.get("/openapi.json")
    assert res.status_code == 404
