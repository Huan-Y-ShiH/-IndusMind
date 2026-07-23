"""API Gateway — routes /api/v1/monitor/* to Module A."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["Gateway"])


def _error(code: int, msg: str) -> JSONResponse:
    """Consistent error envelope."""
    return JSONResponse(status_code=code, content={"code": code, "data": None, "msg": msg})


@router.api_route(
    "/{rest_of_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy(request: Request):
    """Transparently forward API calls to the correct backend."""
    proxy_svc = request.app.state.proxy
    target = proxy_svc.get_target(request.url.path)
    if target is None:
        return _error(404, f"No backend route for: {request.url.path}")
    return await proxy_svc.forward(request, target)
