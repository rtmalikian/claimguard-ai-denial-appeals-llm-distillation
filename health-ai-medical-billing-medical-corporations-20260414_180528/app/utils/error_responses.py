import logging
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.middleware.request_id import get_request_id


logger = logging.getLogger(__name__)

ERROR_CODE_BY_STATUS = {
    400: "bad_request",
    401: "authentication_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    413: "request_entity_too_large",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
}

MESSAGE_BY_STATUS = {
    400: "Bad request.",
    401: "Authentication is required.",
    403: "Access is forbidden.",
    404: "Resource not found.",
    405: "Method not allowed.",
    409: "Request conflicts with current state.",
    410: "Resource is no longer available.",
    413: "Request entity is too large.",
    422: "Request validation failed.",
    429: "Rate limit exceeded.",
    500: "An unexpected error occurred.",
}

DEFAULT_SAFE_CONTEXT = {
    "raw_exception_message_included": False,
    "raw_request_body_included": False,
    "raw_headers_included": False,
    "raw_query_params_included": False,
    "raw_path_params_included": False,
}


def _request_id(request: Request | None = None) -> str | None:
    if request is not None:
        request_id = getattr(request.state, "request_id", None)
        if isinstance(request_id, str):
            return request_id
    return get_request_id()


def _route_template(request: Request | None) -> str | None:
    if request is None:
        return None
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else None


def _status_error_code(status_code: int) -> str:
    return ERROR_CODE_BY_STATUS.get(status_code, f"http_{status_code}")


def _status_message(status_code: int) -> str:
    return MESSAGE_BY_STATUS.get(status_code, "HTTP request failed.")


def _safe_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    safe_errors = []
    for error in exc.errors():
        loc = error.get("loc", [])
        if isinstance(loc, Sequence) and not isinstance(loc, (str, bytes)):
            safe_loc = [part for part in loc if isinstance(part, (str, int))]
        else:
            safe_loc = []
        safe_errors.append(
            {
                "type": str(error.get("type", "validation_error")),
                "loc": safe_loc,
                "msg": str(error.get("msg", "Request validation failed.")),
            }
        )
    return safe_errors


def build_error_payload(
    *,
    status_code: int,
    detail: Any = None,
    error_code: str | None = None,
    message: str | None = None,
    request: Request | None = None,
    safe_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged_safe_context = dict(DEFAULT_SAFE_CONTEXT)
    if safe_context:
        merged_safe_context.update(dict(safe_context))

    resolved_error_code = error_code or _status_error_code(status_code)
    resolved_message = message or _status_message(status_code)

    if isinstance(detail, Mapping):
        detail_payload = dict(detail)
        resolved_error_code = str(
            detail_payload.get("error_code") or resolved_error_code
        )
        resolved_message = str(detail_payload.get("message") or resolved_message)
    elif isinstance(detail, str):
        detail_payload = detail
        resolved_message = message or detail
    elif isinstance(detail, list):
        detail_payload = detail
    elif detail is None:
        detail_payload = resolved_message
    else:
        detail_payload = resolved_message

    return {
        "error_code": resolved_error_code,
        "message": resolved_message,
        "status_code": status_code,
        "detail": detail_payload,
        "request_id": _request_id(request),
        "safe_context": merged_safe_context,
    }


def json_error_response(
    *,
    status_code: int,
    detail: Any = None,
    error_code: str | None = None,
    message: str | None = None,
    request: Request | None = None,
    headers: Mapping[str, str] | None = None,
    safe_context: Mapping[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            status_code=status_code,
            detail=detail,
            error_code=error_code,
            message=message,
            request=request,
            safe_context=safe_context,
        ),
        headers=dict(headers or {}),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    payload = build_error_payload(
        status_code=exc.status_code,
        detail=exc.detail,
        request=request,
    )
    logger.warning(
        "API HTTP exception response",
        extra={
            "api_error_response": {
                "error_code": payload["error_code"],
                "status_code": payload["status_code"],
                "request_id": payload["request_id"],
                "method": request.method,
                "route_template": _route_template(request),
                "exception_type": type(exc).__name__,
                "safe_context": payload["safe_context"],
            }
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        headers=getattr(exc, "headers", None) or {},
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    payload = build_error_payload(
        status_code=422,
        detail=_safe_validation_errors(exc),
        error_code="validation_error",
        message="Request validation failed.",
        request=request,
        safe_context={"raw_validation_input_included": False},
    )
    logger.warning(
        "API validation exception response",
        extra={
            "api_error_response": {
                "error_code": payload["error_code"],
                "status_code": payload["status_code"],
                "request_id": payload["request_id"],
                "method": request.method,
                "route_template": _route_template(request),
                "validation_error_count": len(payload["detail"]),
                "safe_context": payload["safe_context"],
            }
        },
    )
    return JSONResponse(status_code=422, content=payload)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    payload = build_error_payload(
        status_code=500,
        error_code="internal_server_error",
        message="An unexpected error occurred.",
        request=request,
    )
    logger.exception(
        "API unhandled exception response",
        extra={
            "api_error_response": {
                "error_code": payload["error_code"],
                "status_code": payload["status_code"],
                "request_id": payload["request_id"],
                "method": request.method,
                "route_template": _route_template(request),
                "exception_type": type(exc).__name__,
                "safe_context": payload["safe_context"],
            }
        },
    )
    return JSONResponse(status_code=500, content=payload)


async def rate_limit_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return json_error_response(
        status_code=429,
        error_code="rate_limit_exceeded",
        message="Rate limit exceeded.",
        detail="Rate limit exceeded.",
        request=request,
        safe_context={"raw_rate_limit_state_included": False},
    )
