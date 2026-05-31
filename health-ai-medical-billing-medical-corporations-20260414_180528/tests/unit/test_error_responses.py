import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.middleware.request_id import REQUEST_ID_HEADER, RequestIDMiddleware
from app.utils.error_responses import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


class SyntheticPayload(BaseModel):
    units: int


def _error_response_test_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/plain-http-error")
    async def plain_http_error():
        raise HTTPException(status_code=404, detail="Synthetic resource not found")

    @app.get("/structured-http-error")
    async def structured_http_error():
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "synthetic_structured_error",
                "message": "Synthetic structured error.",
                "safe_context": {"raw_document_text_included": False},
            },
        )

    @app.post("/validation-error")
    async def validation_error(payload: SyntheticPayload):
        return payload

    @app.get("/unhandled-error")
    async def unhandled_error():
        raise RuntimeError("synthetic internal failure text")

    return app


def test_http_exception_response_adds_error_code_and_request_id():
    client = TestClient(_error_response_test_app())

    response = client.get(
        "/plain-http-error",
        headers={REQUEST_ID_HEADER: "synthetic-error-check"},
    )

    assert response.status_code == 404
    assert response.headers[REQUEST_ID_HEADER] == "synthetic-error-check"
    body = response.json()
    assert body["error_code"] == "not_found"
    assert body["message"] == "Synthetic resource not found"
    assert body["detail"] == "Synthetic resource not found"
    assert body["request_id"] == "synthetic-error-check"
    assert body["safe_context"]["raw_exception_message_included"] is False
    assert body["safe_context"]["raw_request_body_included"] is False


def test_structured_http_exception_detail_is_preserved():
    client = TestClient(_error_response_test_app())

    response = client.get("/structured-http-error")

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "synthetic_structured_error"
    assert body["message"] == "Synthetic structured error."
    assert body["detail"]["safe_context"]["raw_document_text_included"] is False
    assert body["safe_context"]["raw_headers_included"] is False


def test_validation_error_response_strips_raw_input():
    client = TestClient(_error_response_test_app())

    response = client.post(
        "/validation-error",
        json={"units": "synthetic-private-input"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert body["message"] == "Request validation failed."
    assert body["safe_context"]["raw_validation_input_included"] is False
    assert body["detail"][0]["loc"] == ["body", "units"]
    assert "input" not in body["detail"][0]
    assert "synthetic-private-input" not in response.text


def test_unhandled_exception_response_is_safe(caplog):
    client = TestClient(_error_response_test_app(), raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.utils.error_responses"):
        response = client.get(
            "/unhandled-error",
            headers={REQUEST_ID_HEADER: "synthetic-unhandled-check"},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "internal_server_error"
    assert body["message"] == "An unexpected error occurred."
    assert body["detail"] == "An unexpected error occurred."
    assert body["request_id"] == "synthetic-unhandled-check"
    assert "synthetic internal failure text" not in response.text
    error_logs = [
        record.api_error_response
        for record in caplog.records
        if hasattr(record, "api_error_response")
    ]
    assert error_logs[-1]["exception_type"] == "RuntimeError"
    assert error_logs[-1]["safe_context"]["raw_exception_message_included"] is False


def test_auth_middleware_error_response_has_code_and_preserves_detail():
    from app.main import app

    client = TestClient(app)

    response = client.get(
        "/api/v1/analytics/summary",
        headers={REQUEST_ID_HEADER: "synthetic-auth-error"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "authentication_required"
    assert body["message"] == "Missing bearer token"
    assert body["detail"] == "Missing bearer token"
    assert body["request_id"] == "synthetic-auth-error"
    assert response.headers[REQUEST_ID_HEADER] == "synthetic-auth-error"
