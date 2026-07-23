"""Simple token-based authentication middleware."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Bearer token on every request (when configured)."""

    async def dispatch(self, request: Request, call_next):
        # Skip if token auth is disabled
        if not settings.api_token:
            return await call_next(request)

        # Skip configured paths (exact match or prefix match)
        path = request.url.path
        if path == "/health" or any(path.startswith(p) for p in ("/ws/",)):
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        expected = f"Bearer {settings.api_token}"

        if auth_header != expected:
            return JSONResponse(
                status_code=401,
                content={
                    "code": 401,
                    "data": None,
                    "msg": "Unauthorized: invalid or missing API token",
                },
            )

        return await call_next(request)
