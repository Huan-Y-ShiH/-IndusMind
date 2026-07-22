"""云端前端 ↔ 本地 Agent 对外契约（异步诊断任务）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from indusmind.flows.state import DiagnosticFlowState
from indusmind.schemas.events import (
    AnomalyEvent,
    FeatureAttribution,
    PseudoAttribution,
)

RiskLevel = Literal["low", "medium", "high", "critical"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class ApiEnvelope(BaseModel):
    code: int = 0
    data: Any = None
    msg: str = "success"


class FeatureAttributionIn(BaseModel):
    feature: str
    contribution: float
    direction: Literal["high", "low"]


class PseudoAttributionIn(BaseModel):
    feature: str
    direction: Literal["high", "low"]
    deviation_strength: float


class DiagnoseJobRequest(BaseModel):
    """POST /api/v1/diagnose/jobs 请求体。"""

    event_id: str
    device_id: str
    timestamp: str
    model_version: str
    anomaly_type: str
    device_model: Optional[str] = "CMAPSS-Turbofan"
    anomaly_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rul_hours: Optional[float] = None
    rul_series: Optional[list[float]] = None
    risk_level: Optional[RiskLevel] = None
    feature_attribution: list[FeatureAttributionIn] = Field(default_factory=list)
    pseudo_attribution: list[PseudoAttributionIn] = Field(default_factory=list)
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    callback_url: Optional[str] = None  # 预留，本期忽略


class DiagnoseJobAccepted(BaseModel):
    job_id: str
    event_id: str
    status: JobStatus = "queued"
    poll_url: str


class DiagnosisOut(BaseModel):
    root_cause: str
    l1: str
    l2: Optional[str] = None
    l3: Optional[str] = None
    confidence: float = 0.0
    need_human_review: bool = False
    logic_path: list[str] = Field(default_factory=list)
    mechanism: Optional[str] = None
    evidence: Optional[str] = None
    evidence_level: Optional[str] = None


class SolutionOut(BaseModel):
    urgency: Literal["immediate", "planned_within_7d", "monitor"] = "monitor"
    action_plan: list[str] = Field(default_factory=list)
    matched_tickets: list[str] = Field(default_factory=list)


class DiagnoseResult(BaseModel):
    event_id: str
    device_id: str
    device_model: Optional[str] = None
    rul_hours: Optional[float] = None
    risk_level: Optional[RiskLevel] = None
    anomaly_score: Optional[float] = None
    anomaly_type: str
    diagnosis: DiagnosisOut
    solution: SolutionOut
    report_markdown: str = ""
    rag_hit_count: int = 0


class DiagnoseJobStatus(BaseModel):
    job_id: str
    event_id: str
    status: JobStatus
    progress: int = 0
    created_at: str
    updated_at: str
    error: Optional[str] = None
    result: Optional[DiagnoseResult] = None


def request_to_anomaly_event(req: DiagnoseJobRequest) -> AnomalyEvent:
    """对外请求 → 内核 AnomalyEvent（rul_hours → rul_predicted）。"""
    return AnomalyEvent(
        event_id=req.event_id,
        device_id=req.device_id,
        device_model=req.device_model or "CMAPSS-Turbofan",
        timestamp=req.timestamp,
        model_version=req.model_version,
        anomaly_score=req.anomaly_score,
        anomaly_type=req.anomaly_type,
        window_start=req.window_start,
        window_end=req.window_end,
        feature_attribution=[
            FeatureAttribution(
                feature=f.feature,
                contribution=f.contribution,
                direction=f.direction,
            )
            for f in req.feature_attribution
        ],
        rul_predicted=req.rul_hours,
        rul_series=req.rul_series,
        pseudo_attribution=[
            PseudoAttribution(
                feature=p.feature,
                direction=p.direction,
                deviation_strength=p.deviation_strength,
            )
            for p in req.pseudo_attribution
        ],
    )


def state_to_diagnose_result(
    state: DiagnosticFlowState,
    *,
    risk_level: Optional[RiskLevel] = None,
    rul_hours: Optional[float] = None,
) -> DiagnoseResult:
    """Flow 终态 → 对外 DiagnoseResult。"""
    event = state.event
    if event is None:
        raise ValueError("diagnostic state missing event")
    diagnosis = state.l2l3_diagnosis
    decision = state.decision
    top1 = None
    if state.l1_diagnosis and state.l1_diagnosis.candidate_causes:
        top1 = state.l1_diagnosis.candidate_causes[0]

    root = (diagnosis.l1 if diagnosis else None) or (top1.cause if top1 else "未知")
    evidence_level = None
    if state.rag_results:
        evidence_level = state.rag_results[0].get("evidence_level")

    return DiagnoseResult(
        event_id=event.event_id,
        device_id=event.device_id,
        device_model=event.device_model,
        rul_hours=rul_hours if rul_hours is not None else event.rul_predicted,
        risk_level=risk_level,
        anomaly_score=event.anomaly_score,
        anomaly_type=event.anomaly_type,
        diagnosis=DiagnosisOut(
            root_cause=root,
            l1=diagnosis.l1 if diagnosis else root,
            l2=diagnosis.l2 if diagnosis else None,
            l3=diagnosis.l3 if diagnosis else None,
            confidence=(diagnosis.confidence if diagnosis else None) or (top1.confidence if top1 else 0.0),
            need_human_review=state.need_human_review,
            logic_path=list((diagnosis.logic_path if diagnosis else None) or (top1.logic_path if top1 else []) or []),
            mechanism=(top1.mechanism if top1 else None),
            evidence=(
                (diagnosis.severity_basis if diagnosis else None)
                or (top1.evidence if top1 else None)
            ),
            evidence_level=evidence_level,
        ),
        solution=SolutionOut(
            urgency=decision.urgency if decision else "monitor",
            action_plan=list(decision.action_plan) if decision else [],
            matched_tickets=list(decision.matched_tickets) if decision else [],
        ),
        report_markdown=state.report.markdown if state.report else "",
        rag_hit_count=len(state.rag_results),
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
