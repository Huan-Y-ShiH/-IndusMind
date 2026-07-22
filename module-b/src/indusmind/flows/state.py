"""诊断 Flow 的状态模型，见 docs/architecture.md。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from indusmind.schemas.events import (
    AnomalyEvent,
    Decision,
    DiagnosticQuery,
    DiagnosticReport,
    L1Diagnosis,
    L2L3Diagnosis,
)


class DiagnosticFlowState(BaseModel):
    event: Optional[AnomalyEvent] = None
    query: Optional[DiagnosticQuery] = None
    rag_results: list[dict] = Field(default_factory=list)
    dify_explain_hits: list[dict] = Field(default_factory=list)
    l1_diagnosis: Optional[L1Diagnosis] = None
    l2l3_diagnosis: Optional[L2L3Diagnosis] = None
    decision: Optional[Decision] = None
    report: Optional[DiagnosticReport] = None
    need_human_review: bool = False
    retry_count: int = 0
