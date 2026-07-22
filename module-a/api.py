"""Production API entrypoint for IndusMind Monitor v2."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault(
    "CHECKPOINT_PATH", str(ROOT / "model/saved/best_model.pt")
)
os.environ.setdefault("PROCESSED_PATH", str(ROOT / "processed"))
os.environ.setdefault("MODEL_VERSION", "monitor-v2.0")

from v2.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    Attribution,
    AttributionMetadata,
    MonitorEvent,
    MonitorV2Service,
    OperatingSettings,
    SensorPoint,
    analyze,
    app,
    get_service,
    health,
)

RULService = MonitorV2Service

__all__ = [
    "app",
    "analyze",
    "health",
    "get_service",
    "RULService",
    "MonitorV2Service",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "MonitorEvent",
    "Attribution",
    "AttributionMetadata",
    "SensorPoint",
    "OperatingSettings",
]
