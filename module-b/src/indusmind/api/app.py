"""FastAPI 应用：本地 Agent 引擎外壳（默认端口 8002）。"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from indusmind.api.auth import require_api_key
from indusmind.api.jobs import JobManager, default_job_manager
from indusmind.config import env
from indusmind.schemas.api import (
    ApiEnvelope,
    DiagnoseJobAccepted,
    DiagnoseJobRequest,
)


def _cors_origins() -> list[str]:
    raw = (env("CORS_ORIGINS", "*") or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(job_manager: JobManager | None = None) -> FastAPI:
    manager = job_manager or default_job_manager
    app = FastAPI(title="IndusMind Agent Engine", version="0.1.0")
    app.state.job_manager = manager

    # 浏览器跨域联调：必须允许 OPTIONS 预检，否则前端会卡在 405
    origins = _cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*", "X-Api-Key", "Content-Type", "Authorization"],
        expose_headers=["*"],
        max_age=600,
    )

    @app.exception_handler(HTTPException)
    async def http_exc_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "data": None, "msg": str(detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # 精简字段路径，方便前端对照 handoff 文档改 body
        paths = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()) if x != "body")
            paths.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "data": {"errors": exc.errors()},
                "msg": "validation error: " + "; ".join(paths),
            },
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "service": "indusmind-agent"}

    @app.post(
        "/api/v1/diagnose/jobs",
        status_code=202,
        dependencies=[Depends(require_api_key)],
    )
    async def create_diagnose_job(body: DiagnoseJobRequest) -> dict[str, Any]:
        try:
            record, created = await manager.submit(body)
        except RuntimeError as exc:
            if str(exc) == "busy":
                raise HTTPException(
                    status_code=429,
                    detail={"code": 429, "data": None, "msg": "busy"},
                ) from exc
            raise
        accepted = DiagnoseJobAccepted(
            job_id=record.job_id,
            event_id=record.request.event_id,
            status=record.status if record.status != "running" else record.status,
            poll_url=f"/api/v1/diagnose/jobs/{record.job_id}",
        )
        # 幂等复用时若已在跑/完成，仍返回当前状态
        if not created and record.status in {"running", "succeeded"}:
            accepted.status = record.status
        return ApiEnvelope(
            code=0,
            data=accepted.model_dump(),
            msg="accepted" if created else "idempotent",
        ).model_dump()

    @app.get(
        "/api/v1/diagnose/jobs/{job_id}",
        dependencies=[Depends(require_api_key)],
    )
    async def get_diagnose_job(job_id: str) -> dict[str, Any]:
        record = manager.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"code": 404, "data": None, "msg": "job not found"},
            )
        return ApiEnvelope(code=0, data=record.to_status().model_dump(), msg="success").model_dump()

    return app


app = create_app()
