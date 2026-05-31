import contextvars
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_MAX_LENGTH = 64
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


def _new_request_id() -> str:
    return uuid.uuid4().hex


def normalize_request_id(raw_request_id: str | None) -> str:
    if not raw_request_id:
        return _new_request_id()
    candidate = raw_request_id.strip()
    if len(candidate) > REQUEST_ID_MAX_LENGTH:
        return _new_request_id()
    if not REQUEST_ID_PATTERN.fullmatch(candidate):
        return _new_request_id()
    return candidate


def get_request_id() -> str | None:
    return _request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = _request_id_ctx.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            _request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
