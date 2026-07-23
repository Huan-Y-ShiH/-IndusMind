"""Proxy service — manages HTTP client pool and route-based forwarding."""

import httpx
import logging
from fastapi import Request
from fastapi.responses import StreamingResponse

from api.config import settings

logger = logging.getLogger(__name__)


class ProxyService:
    """HTTP reverse proxy with a route table.

    Manages a shared httpx.AsyncClient pool and dispatches requests
    to backend services based on path prefix rules.
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        # Route table: path prefix → backend base URL
        self._routes: list[tuple[str, str]] = [
            ("/api/v1/monitor", settings.monitor_url),
        ]

    # ── Lifecycle ────────────────────────────────────────────────

    async def startup(self):
        """Initialize the shared httpx client pool."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

    async def shutdown(self):
        """Gracefully close the client pool."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Routing ──────────────────────────────────────────────────

    def get_target(self, path: str) -> str | None:
        """Match path against the route table. Returns backend URL or None."""
        for prefix, target in self._routes:
            if path.startswith(prefix):
                return target
        return None

    # ── Forwarding ───────────────────────────────────────────────

    async def forward(self, request: Request, target_base: str) -> StreamingResponse:
        """Forward an incoming request to a backend service."""
        target_url = f"{target_base}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        body = await request.body()

        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers["x-forwarded-for"] = request.client.host if request.client else "unknown"
        headers["x-forwarded-proto"] = request.url.scheme
        headers["x-forwarded-host"] = request.headers.get("host", "localhost:8003")

        req = self._client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )
        response = await self._client.send(req, stream=True)

        return StreamingResponse(
            content=response.aiter_bytes(),
            status_code=response.status_code,
            headers=dict(response.headers),
        )
