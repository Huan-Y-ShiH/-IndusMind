"""内存任务表 + 串行诊断队列（演示用，不引入 Redis）。"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from indusmind.flows import run_diagnostic_flow
from indusmind.schemas.api import (
    DiagnoseJobRequest,
    DiagnoseJobStatus,
    DiagnoseResult,
    JobStatus,
    request_to_anomaly_event,
    state_to_diagnose_result,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

FlowRunner = Callable[..., Awaitable]


@dataclass
class JobRecord:
    job_id: str
    request: DiagnoseJobRequest
    status: JobStatus = "queued"
    progress: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    error: Optional[str] = None
    result: Optional[DiagnoseResult] = None

    def to_status(self) -> DiagnoseJobStatus:
        return DiagnoseJobStatus(
            job_id=self.job_id,
            event_id=self.request.event_id,
            status=self.status,
            progress=self.progress,
            created_at=self.created_at,
            updated_at=self.updated_at,
            error=self.error,
            result=self.result,
        )


class JobManager:
    """单并发诊断：同时最多 1 个 Flow；活跃任务过多时拒绝（429 busy）。"""

    def __init__(
        self,
        flow_runner: FlowRunner | None = None,
        max_concurrent: int = 1,
        max_active: int = 3,
    ):
        self._jobs: dict[str, JobRecord] = {}
        self._event_index: dict[str, str] = {}  # event_id -> job_id
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_active = max_active
        self._flow_runner = flow_runner or run_diagnostic_flow
        self._tasks: set[asyncio.Task] = set()

    def get(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def find_by_event(self, event_id: str) -> Optional[JobRecord]:
        job_id = self._event_index.get(event_id)
        return self._jobs.get(job_id) if job_id else None

    def _active_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status in {"queued", "running"})

    async def submit(self, request: DiagnoseJobRequest) -> tuple[JobRecord, bool]:
        """提交任务。返回 (record, created)。幂等：未失败的同 event_id 复用。

        活跃任务（queued+running）达到 max_active 时抛 RuntimeError('busy')。
        """
        async with self._lock:
            existing = self.find_by_event(request.event_id)
            if existing and existing.status != "failed":
                return existing, False
            if self._active_count() >= self._max_active:
                raise RuntimeError("busy")
            job_id = f"job_{uuid.uuid4().hex[:16]}"
            record = JobRecord(job_id=job_id, request=request)
            self._jobs[job_id] = record
            self._event_index[request.event_id] = job_id
            task = asyncio.create_task(self._run_job(job_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return record, True

    async def _run_job(self, job_id: str) -> None:
        record = self._jobs[job_id]
        async with self._semaphore:
            record.status = "running"
            record.progress = 50
            record.updated_at = utc_now_iso()
            try:
                event = request_to_anomaly_event(record.request)
                state = await self._flow_runner(event)
                record.result = state_to_diagnose_result(
                    state,
                    risk_level=record.request.risk_level,
                    rul_hours=record.request.rul_hours,
                )
                record.status = "succeeded"
                record.progress = 100
                record.error = None
            except Exception as exc:  # noqa: BLE001
                logger.exception("诊断任务失败 job_id=%s", job_id)
                record.status = "failed"
                record.progress = 100
                record.error = str(exc)
            finally:
                record.updated_at = utc_now_iso()


# 进程内单例，测试可替换
default_job_manager = JobManager()
