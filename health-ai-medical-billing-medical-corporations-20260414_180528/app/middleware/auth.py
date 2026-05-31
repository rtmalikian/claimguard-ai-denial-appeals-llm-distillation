from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.auth import ALLOWED_ROLES
from app.core.config import settings
from app.core.security import decode_token
from app.utils.error_responses import json_error_response


PUBLIC_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}
PUBLIC_API_PATHS = {f"{settings.API_V1_PREFIX}/auth/login"}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in PUBLIC_PATHS or path in PUBLIC_API_PATHS:
            return await call_next(request)

        if not path.startswith(settings.API_V1_PREFIX):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return self._unauthorized(request, "Missing bearer token", "authentication_required")

        payload = decode_token(token)
        if not payload:
            return self._unauthorized(request, "Invalid or expired token", "invalid_token")

        role = payload.get("role")
        subject = payload.get("sub")
        if not subject or role not in ALLOWED_ROLES:
            return self._unauthorized(request, "Invalid token claims", "invalid_token_claims")

        try:
            user_id = int(subject)
        except (TypeError, ValueError):
            return self._unauthorized(request, "Invalid token subject", "invalid_token_subject")

        request.state.user = {
            "id": user_id,
            "email": payload.get("email"),
            "full_name": payload.get("full_name"),
            "role": role,
        }
        return await call_next(request)

    @staticmethod
    def _unauthorized(request: Request, detail: str, error_code: str) -> JSONResponse:
        return json_error_response(
            status_code=401,
            detail=detail,
            error_code=error_code,
            message=detail,
            request=request,
            headers={"WWW-Authenticate": "Bearer"},
        )
