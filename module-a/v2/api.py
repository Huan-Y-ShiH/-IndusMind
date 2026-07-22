"""Backward-compatible v2 monitoring API with formal anomaly attribution."""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

try:
    from .attribution import calibrated_anomaly_score, explain_both
    from .model import create_v2_model
except ImportError:
    from attribution import calibrated_anomaly_score, explain_both
    from model import create_v2_model


V2_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = V2_ROOT.parent
CHECKPOINT_PATH = Path(
    os.getenv(
        "CHECKPOINT_PATH", str(V2_ROOT / "model/saved/best_model.pt")
    )
)
PROCESSED_PATH = Path(
    os.getenv("PROCESSED_PATH", str(PROJECT_ROOT / "processed"))
)
SEQUENCE_LENGTH = 30


class SensorPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    s1: float
    s2: float
    s3: float
    s4: float
    s5: float
    s6: float
    s7: float
    s8: float
    s9: float
    s10: float
    s11: float
    s12: float
    s13: float
    s14: float
    s15: float
    s16: float
    s17: float
    s18: float
    s19: float
    s20: float
    s21: float


class OperatingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op1: float
    op2: float
    op3: float


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=128)
    device_model: str = Field(min_length=1, max_length=128)
    sensor_data: List[SensorPoint] = Field(
        min_length=SEQUENCE_LENGTH, max_length=2048
    )
    operating_settings: Optional[OperatingSettings] = None
    dataset: Optional[
        Literal["FD001", "FD002", "FD003", "FD004", "PHM08"]
    ] = None
    raw_data_ref: Optional[str] = None


class Attribution(BaseModel):
    feature: str
    direction: Literal["high", "low", "stable"]
    contribution: float


class AttributionMetadata(BaseModel):
    method: str
    baseline: str
    steps: int
    rul_completeness_delta: float
    anomaly_completeness_delta: float


class MonitorEvent(BaseModel):
    event_id: str
    device_id: str
    device_model: str
    timestamp: datetime
    model_version: str
    anomaly_score: Optional[float]
    anomaly_type: Optional[str]
    rul_predicted: float
    rul_series: List[float]
    feature_attribution: Optional[List[Attribution]]
    pseudo_attribution: Optional[List[Attribution]]
    raw_data_ref: Optional[str]
    anomaly_attribution: Optional[List[Attribution]] = None
    attribution_metadata: Optional[AttributionMetadata] = None


class AnalyzeResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: MonitorEvent


class MonitorV2Service:
    def __init__(self, checkpoint_path: Path, processed_path: Path):
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        stats_path = processed_path / "normalization_stats.npz"
        if not stats_path.exists():
            raise FileNotFoundError(f"Normalization metadata missing: {stats_path}")
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        checkpoint = torch.load(
            checkpoint_path, map_location=self.device, weights_only=False
        )
        if checkpoint.get("schema_version") != 2:
            raise ValueError("v2 API requires a schema_version=2 checkpoint")
        if "anomaly_calibration" not in checkpoint:
            raise ValueError("Checkpoint is not anomaly-calibrated")
        self.model = create_v2_model(**checkpoint["model_kwargs"]).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
        self.model.max_rul = float(checkpoint["max_rul"])
        self.model_version = os.getenv(
            "MODEL_VERSION", checkpoint.get("model_version", "monitor-v2.0")
        )
        self.max_rul = self.model.max_rul
        self.feature_names = checkpoint["feature_names"]
        self.calibration = checkpoint["anomaly_calibration"]
        self.sequence_length = int(checkpoint["seq_length"])

        stats = np.load(stats_path)
        self.op_mean = stats["op_mean"]
        self.op_scale = stats["op_scale"]
        self.condition_centers = stats["condition_centers"]
        self.sensor_mean = stats["sensor_mean"]
        self.sensor_scale = stats["sensor_scale"]
        self.sensor_names = [str(value) for value in stats["sensor_names"]]
        self.dataset_names = [str(value) for value in stats["dataset_names"]]

    def _prepare(self, points, settings, dataset):
        op_raw = np.array(
            [settings.op1, settings.op2, settings.op3], dtype=np.float64
        )
        op_norm = (op_raw - self.op_mean) / self.op_scale
        condition_id = int(
            np.argmin(((self.condition_centers - op_norm) ** 2).sum(axis=1))
        )
        dataset_id = self.dataset_names.index(dataset)
        rows = []
        for point in sorted(points, key=lambda item: item.timestamp):
            raw = point.model_dump()
            feature_map: Dict[str, float] = {}
            sensor_values = np.array(
                [
                    raw[f"s{int(name.split('_')[1])}"]
                    for name in self.sensor_names
                ],
                dtype=np.float64,
            )
            sensor_norm = (
                sensor_values - self.sensor_mean[condition_id]
            ) / self.sensor_scale[condition_id]
            feature_map.update(dict(zip(self.sensor_names, sensor_norm)))
            feature_map.update({
                "op_setting_1": op_norm[0],
                "op_setting_2": op_norm[1],
                "op_setting_3": op_norm[2],
            })
            for index in range(len(self.dataset_names)):
                feature_map[f"dataset_{index}"] = float(index == dataset_id)
            for index in range(len(self.condition_centers)):
                feature_map[f"condition_{index}"] = float(index == condition_id)
            rows.append([feature_map[name] for name in self.feature_names])
        return np.asarray(rows, dtype=np.float32), condition_id

    @torch.no_grad()
    def _predict_windows(self, features, condition_id):
        windows = np.stack([
            features[index - self.sequence_length:index]
            for index in range(self.sequence_length, len(features) + 1)
        ])
        rul_predictions = []
        latest_distance = 0.0
        for start in range(0, len(windows), 512):
            batch = torch.as_tensor(
                windows[start:start + 512],
                dtype=torch.float32,
                device=self.device,
            )
            conditions = torch.full(
                (len(batch),), condition_id,
                dtype=torch.long, device=self.device,
            )
            output = self.model(batch, conditions)
            rul_predictions.extend(
                (
                    output["rul"].squeeze(-1) * self.max_rul
                ).cpu().numpy().tolist()
            )
            latest_distance = float(output["anomaly_distance"][-1].cpu())
        return (
            [round(max(0.0, value), 2) for value in rul_predictions],
            latest_distance,
        )

    @staticmethod
    def _convert_attribution(items):
        direction_map = {
            "positive": "high",
            "negative": "low",
            "neutral": "stable",
        }
        return [
            Attribution(
                feature=f"s{int(item['sensor'].split('_')[1])}",
                direction=direction_map[item["direction"]],
                contribution=item["importance"],
            )
            for item in items
        ]

    def analyze(self, request):
        if request.operating_settings is None or request.dataset is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "This model requires 'operating_settings' and 'dataset'."
                ),
            )
        points = sorted(request.sensor_data, key=lambda item: item.timestamp)
        features, condition_id = self._prepare(
            points, request.operating_settings, request.dataset
        )
        rul_series, distance = self._predict_windows(features, condition_id)
        anomaly_score = calibrated_anomaly_score(
            distance, condition_id, self.calibration
        )
        latest = torch.as_tensor(
            features[-self.sequence_length:][None],
            dtype=torch.float32,
            device=self.device,
        )
        explanation = explain_both(
            self.model,
            latest,
            condition_id,
            self.calibration,
            self.feature_names,
        )
        threshold = float(self.calibration.get("threshold", 0.95))
        timestamp = points[-1].timestamp
        event_stamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        return MonitorEvent(
            event_id=f"evt-{event_stamp}-{uuid.uuid4().hex[:8]}",
            device_id=request.device_id,
            device_model=request.device_model,
            timestamp=timestamp,
            model_version=self.model_version,
            anomaly_score=round(anomaly_score, 6),
            anomaly_type=(
                "condition_representation_deviation"
                if anomaly_score >= threshold else "normal"
            ),
            rul_predicted=rul_series[-1],
            rul_series=rul_series,
            feature_attribution=self._convert_attribution(
                explanation["feature_attribution"]
            ),
            pseudo_attribution=None,
            raw_data_ref=request.raw_data_ref,
            anomaly_attribution=self._convert_attribution(
                explanation["anomaly_attribution"]
            ),
            attribution_metadata=AttributionMetadata(
                method=explanation["method"],
                baseline=explanation["baseline"],
                steps=explanation["steps"],
                rul_completeness_delta=explanation["completeness_delta"]["rul"],
                anomaly_completeness_delta=explanation[
                    "completeness_delta"
                ]["anomaly"],
            ),
        )


app = FastAPI(title="IndusMind Monitor API", version="2.0.0")
origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
_service: Optional[MonitorV2Service] = None


def get_service():
    global _service
    if _service is None:
        _service = MonitorV2Service(CHECKPOINT_PATH, PROCESSED_PATH)
    return _service


@app.get("/health")
def health():
    service = get_service()
    return {
        "status": "ok",
        "model_version": service.model_version,
        "device": str(service.device),
        "anomaly_calibrated": True,
    }


@app.post("/api/v1/monitor/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    return AnalyzeResponse(data=get_service().analyze(request))
