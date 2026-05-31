import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, parse_cors_allowed_origins
from app.main import app


def test_parse_single_cors_origin():
    assert parse_cors_allowed_origins("http://localhost:5173") == ["http://localhost:5173"]


def test_parse_multiple_cors_origins():
    assert parse_cors_allowed_origins(
        "http://localhost:5173, https://billing.example.com "
    ) == ["http://localhost:5173", "https://billing.example.com"]


@pytest.mark.parametrize(
    "raw_origin",
    [
        "*",
        "localhost:5173",
        "http://",
        "http://localhost:5173/path",
        "http://localhost:5173?debug=true",
        "http://localhost:5173#fragment",
    ],
)
def test_parse_invalid_cors_origins(raw_origin):
    with pytest.raises(ValueError):
        parse_cors_allowed_origins(raw_origin)


def test_settings_exposes_validated_cors_origins():
    settings = Settings(CORS_ALLOWED_ORIGINS="http://localhost:5173,https://billing.example.com")
    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "https://billing.example.com",
    ]


def test_allowed_origin_preflight_has_cors_headers():
    client = TestClient(app)
    response = client.options(
        "/api/v1/analytics/summary",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_disallowed_origin_preflight_is_not_allowed():
    client = TestClient(app)
    response = client.options(
        "/api/v1/analytics/summary",
        headers={
            "Origin": "https://evil.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_health_response_has_security_headers():
    client = TestClient(app)
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_protected_unauthorized_response_has_security_and_cors_headers():
    client = TestClient(app)
    response = client.get(
        "/api/v1/analytics/summary",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["x-frame-options"] == "DENY"


def test_docs_remain_public_with_docs_compatible_csp():
    client = TestClient(app)
    response = client.get("/docs")

    assert response.status_code == 200
    assert "https://cdn.jsdelivr.net" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"

