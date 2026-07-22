"""事件语义化：`event_to_query()`（见 docs/architecture.md）。

把监测事件的特征归因（或 RUL-only 伪归因）压缩成诊断 / RAG 可用的语义查询。
"""
from __future__ import annotations

from indusmind.knowledge import default_store
from indusmind.schemas.events import AnomalyEvent, DiagnosticQuery, SymptomSignal


def event_to_query(event: AnomalyEvent, top_k: int = 4) -> DiagnosticQuery:
    top_features = event.top_features(top_k)
    symptom_text = ", ".join(
        f"{f.feature}({'↑' if f.direction == 'high' else '↓'})" for f in top_features
    )
    device_desc = f"设备 {event.device_id}"
    if event.device_model:
        device_desc += f"（{event.device_model}）"
    natural_language = f"{device_desc} 发生 {event.anomaly_type}, 主要征兆: {symptom_text}"
    return DiagnosticQuery(
        device_id=event.device_id,
        device_model=event.device_model,
        anomaly_type=event.anomaly_type,
        top_features=[f.feature for f in top_features],
        symptoms=[
            SymptomSignal(feature=f.feature, direction=f.direction, strength=f.contribution)
            for f in top_features
        ],
        symptom_text=symptom_text,
        natural_language=natural_language,
    )


def describe_symptom_text(event: AnomalyEvent, top_k: int = 4) -> str:
    """把 `symptom_text` 里的传感器编号翻译成物理含义，用于报告/prompt 展示。"""
    top_features = event.top_features(top_k)
    parts = []
    for f in top_features:
        desc = default_store.describe_feature(f.feature)
        arrow = "↑" if f.direction == "high" else "↓"
        parts.append(f"{f.feature}({desc}){arrow}")
    return ", ".join(parts)
