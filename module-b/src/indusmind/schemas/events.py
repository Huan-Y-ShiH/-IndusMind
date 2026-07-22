"""标准化事件 / 诊断结果 Pydantic 模型。

对齐 docs/architecture.md 与 schemas：异常事件 / L2L3 诊断输出。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

Direction = Literal["high", "low"]


class FeatureAttribution(BaseModel):
    feature: str
    contribution: float
    direction: Direction


class PseudoAttribution(BaseModel):
    feature: str
    direction: Direction
    deviation_strength: float


class RulHistoryDrift(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, float] = Field(default_factory=dict)
    drift_rate: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def accept_flat_history(cls, data):
        """兼容文档中的扁平格式：7d_ago/3d_ago/now 与 drift_rate 同级。"""
        if not isinstance(data, dict) or "values" in data:
            return data
        return {
            "values": {k: v for k, v in data.items() if k != "drift_rate"},
            "drift_rate": data.get("drift_rate"),
        }


class SymptomSignal(BaseModel):
    """用于检索的方向化征兆，避免只传特征名丢失 ↑/↓ 信息。"""

    feature: str
    direction: Direction
    strength: Optional[float] = None


class AnomalyEvent(BaseModel):
    """标准化异常事件对象（见 docs/architecture.md）。"""

    event_id: str
    device_id: str
    device_model: Optional[str] = None
    timestamp: str
    model_version: str
    anomaly_score: Optional[float] = None
    anomaly_type: str
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    feature_attribution: list[FeatureAttribution] = Field(default_factory=list)
    rul_predicted: Optional[float] = None
    raw_data_ref: Optional[str] = None

    # 仅有 RUL 时的补充字段
    rul_series: Optional[list[float]] = None
    rul_shape: Optional[str] = None
    rul_curvature: Optional[float] = None
    rul_residual: Optional[float] = None
    rul_residual_zscore: Optional[float] = None
    rul_history_drift: Optional[RulHistoryDrift] = None
    pseudo_attribution: list[PseudoAttribution] = Field(default_factory=list)

    def top_features(self, k: int = 4) -> list[FeatureAttribution]:
        if self.feature_attribution:
            return sorted(self.feature_attribution, key=lambda f: f.contribution, reverse=True)[:k]
        pseudo = sorted(self.pseudo_attribution, key=lambda f: f.deviation_strength, reverse=True)[:k]
        return [FeatureAttribution(feature=p.feature, contribution=p.deviation_strength, direction=p.direction) for p in pseudo]


class DiagnosticQuery(BaseModel):
    """event_to_query() 输出；hybrid_search 输入契约见 docs/knowledge-rag.md。"""

    device_id: str
    device_model: Optional[str] = None
    anomaly_type: str
    top_features: list[str]
    symptoms: list[SymptomSignal] = Field(default_factory=list)
    symptom_text: str
    natural_language: str


class CandidateCause(BaseModel):
    cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    matched_cases: list[str] = Field(default_factory=list)
    evidence: Optional[str] = None
    mechanism: Optional[str] = None
    logic_path: list[str] = Field(
        default_factory=list,
        description="从征兆到根因的推理步骤（可含 LLM 生成叙述）",
    )


class L1Diagnosis(BaseModel):
    event_id: str
    candidate_causes: list[CandidateCause] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    need_human_review: bool = False


class EvidenceItem(BaseModel):
    evidence_id: str
    type: str
    content: str
    supports: Optional[str] = None
    refutes: Optional[str] = None
    adds: Optional[str] = None


class MaintenanceRecommendation(BaseModel):
    action: str
    location: Optional[str] = None
    urgency: Literal["immediate", "planned_within_7d", "monitor"] = "monitor"
    estimated_downtime: Optional[str] = None
    follow_up: Optional[str] = None


class L2L3Diagnosis(BaseModel):
    """L2/L3 细化诊断输出（见 docs/architecture.md）。"""

    event_id: str
    diagnosis_level: Literal["L1", "L2", "L3"] = "L2"
    l1: str
    l2: Optional[str] = None
    l3: Optional[str] = None
    location: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    severity: Optional[str] = None
    severity_basis: Optional[str] = None
    evidence_chain: list[EvidenceItem] = Field(default_factory=list)
    logic_path: list[str] = Field(default_factory=list)
    maintenance_recommendation: Optional[MaintenanceRecommendation] = None
    counter_evidence: list[dict] = Field(default_factory=list)


class Decision(BaseModel):
    event_id: str
    action_plan: list[str] = Field(default_factory=list)
    matched_tickets: list[str] = Field(default_factory=list)
    urgency: Literal["immediate", "planned_within_7d", "monitor"] = "monitor"


class DiagnosticReport(BaseModel):
    event_id: str
    markdown: str
    need_human_review: bool = False
