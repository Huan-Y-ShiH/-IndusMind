"""训练期间使用的监测模型模拟器。

只负责模拟“模型响应”，随后仍走真实的事件标准化、Dify、LLM、决策和报告链路。
监测模型上线后，用真实客户端替换 `SimulatedMonitoringModel.predict()` 即可。
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from indusmind.schemas import AnomalyEvent, FeatureAttribution


class MonitoringModelResponse(BaseModel):
    model_version: str
    anomaly_score: float = Field(ge=0.0, le=1.0)
    anomaly_type: str
    feature_attribution: list[FeatureAttribution]
    rul_predicted: float | None = None
    rul_series: list[float] | None = None


class SimulatedMonitoringModel:
    """返回一组符合 CMAPSS FD001 退化模式的可重复模拟数据。"""

    async def predict(self, device_id: str, device_model: str) -> MonitoringModelResponse:
        return MonitoringModelResponse(
            model_version="simulated-monitor-fd001-v1",
            anomaly_score=0.91,
            anomaly_type="trend_anomaly",
            rul_predicted=82.0,
            rul_series=[100.0, 96.0, 91.0, 85.0, 78.0, 70.0],
            feature_attribution=[
                FeatureAttribution(feature="s3", contribution=0.35, direction="high"),
                FeatureAttribution(feature="s4", contribution=0.30, direction="high"),
                FeatureAttribution(feature="s12", contribution=0.22, direction="high"),
                FeatureAttribution(feature="s9", contribution=0.13, direction="high"),
            ],
        )


def normalize_monitoring_response(
    response: MonitoringModelResponse,
    *,
    event_id: str,
    device_id: str,
    device_model: str,
) -> AnomalyEvent:
    """把监测模型响应转换成诊断 Flow 的标准事件契约。"""
    return AnomalyEvent(
        event_id=event_id,
        device_id=device_id,
        device_model=device_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
        model_version=response.model_version,
        anomaly_score=response.anomaly_score,
        anomaly_type=response.anomaly_type,
        feature_attribution=response.feature_attribution,
        rul_predicted=response.rul_predicted,
        rul_series=response.rul_series,
    )
