import re

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.request_id import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    get_request_id,
    normalize_request_id,
)


REQUEST_ID_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def _request_id_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/state")
    async def read_request_state(request: Request):
        return {
            "state_request_id": request.state.request_id,
            "context_request_id": get_request_id(),
        }

    return app


def test_request_id_middleware_generates_safe_id_for_missing_header():
    client = TestClient(_request_id_test_app())

    response = client.get("/state")

    assert response.status_code == 200
    response_request_id = response.headers[REQUEST_ID_HEADER]
    assert REQUEST_ID_VALUE_RE.fullmatch(response_request_id)
    assert response.json() == {
        "state_request_id": response_request_id,
        "context_request_id": response_request_id,
    }
    assert get_request_id() is None


def test_request_id_middleware_preserves_safe_inbound_header():
    client = TestClient(_request_id_test_app())

    response = client.get(
        "/state",
        headers={REQUEST_ID_HEADER: "synthetic-trace_123"},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "synthetic-trace_123"
    assert response.json()["state_request_id"] == "synthetic-trace_123"


def test_request_id_middleware_replaces_unsafe_inbound_header():
    client = TestClient(_request_id_test_app())

    response = client.get(
        "/state",
        headers={REQUEST_ID_HEADER: "synthetic trace with spaces and symbols <>"},
    )

    assert response.status_code == 200
    response_request_id = response.headers[REQUEST_ID_HEADER]
    assert response_request_id != "synthetic trace with spaces and symbols <>"
    assert REQUEST_ID_VALUE_RE.fullmatch(response_request_id)


def test_normalize_request_id_rejects_overlong_values():
    unsafe_id = "a" * 65

    normalized = normalize_request_id(unsafe_id)

    assert normalized != unsafe_id
    assert REQUEST_ID_VALUE_RE.fullmatch(normalized)


def test_request_id_header_is_present_on_auth_middleware_unauthorized_response():
    from app.main import app

    client = TestClient(app)

    response = client.get(
        "/api/v1/claims/1/document",
        headers={REQUEST_ID_HEADER: "synthetic-auth-check"},
    )

    assert response.status_code == 401
    assert response.headers[REQUEST_ID_HEADER] == "synthetic-auth-check"
