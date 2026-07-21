"""Unified monitoring API for the IndusMind RUL model."""
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

from lstm_transformer import create_simple_lstm


ROOT = Path(__file__).resolve().parent
MODEL_VERSION = os.getenv("MODEL_VERSION", "monitor-v1.0")
CHECKPOINT_PATH = Path(
    os.getenv("CHECKPOINT_PATH", str(ROOT / "model/saved/best_model.pt"))
)
PROCESSED_PATH = Path(os.getenv("PROCESSED_PATH", str(ROOT / "processed")))
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
    sensor_data: List[SensorPoint] = Field(min_length=SEQUENCE_LENGTH, max_length=2048)
    # The integrated model was trained with these fields. They cannot be
    # reconstructed reliably from the 21 sensor measurements.
    operating_settings: Optional[OperatingSettings] = None
    dataset: Optional[Literal["FD001", "FD002", "FD003", "FD004", "PHM08"]] = None
    raw_data_ref: Optional[str] = None


class Attribution(BaseModel):
    feature: str
    direction: Literal["high", "low", "stable"]
    contribution: float


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


class AnalyzeResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: MonitorEvent


class RULService:
    def __init__(self, checkpoint_path: Path, processed_path: Path):
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        stats_path = processed_path / "normalization_stats.npz"
        feature_path = processed_path / "feature_names.txt"
        if not stats_path.exists() or not feature_path.exists():
            raise FileNotFoundError(
                "normalization_stats.npz and feature_names.txt are required"
            )

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        model_args = checkpoint.get("args", {})
        self.max_rul = float(checkpoint["max_rul"])
        self.model = create_simple_lstm(
            n_features=int(checkpoint["n_features"]),
            hidden=int(model_args.get("lstm_hidden", 128)),
            num_layers=int(model_args.get("lstm_layers", 2)),
            dropout=float(model_args.get("dropout", 0.3)),
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        stats = np.load(stats_path)
        self.op_mean = stats["op_mean"]
        self.op_scale = stats["op_scale"]
        self.condition_centers = stats["condition_centers"]
        self.sensor_mean = stats["sensor_mean"]
        self.sensor_scale = stats["sensor_scale"]
        self.sensor_names = [str(x) for x in stats["sensor_names"]]
        self.dataset_names = [str(x) for x in stats["dataset_names"]]
        self.feature_names = [
            line.strip() for line in feature_path.read_text().splitlines() if line.strip()
        ]
        if len(self.feature_names) != int(checkpoint["n_features"]):
            raise ValueError("Feature metadata does not match model input dimension")

    def _prepare(
        self,
        points: List[SensorPoint],
        settings: OperatingSettings,
        dataset: str,
    ) -> np.ndarray:
        op_raw = np.array([settings.op1, settings.op2, settings.op3], dtype=np.float64)
        op_norm = (op_raw - self.op_mean) / self.op_scale
        distances = ((self.condition_centers - op_norm) ** 2).sum(axis=1)
        condition_id = int(np.argmin(distances))
        dataset_id = self.dataset_names.index(dataset)

        rows = []
        for point in sorted(points, key=lambda item: item.timestamp):
            raw = point.model_dump()
            feature_map: Dict[str, float] = {}
            sensor_values = np.array(
                [raw[f"s{int(name.split('_')[1])}"] for name in self.sensor_names],
                dtype=np.float64,
            )
            sensor_norm = (
                sensor_values - self.sensor_mean[condition_id]
            ) / self.sensor_scale[condition_id]
            feature_map.update(dict(zip(self.sensor_names, sensor_norm)))
            feature_map.update(
                {
                    "op_setting_1": op_norm[0],
                    "op_setting_2": op_norm[1],
                    "op_setting_3": op_norm[2],
                }
            )
            for index in range(len(self.dataset_names)):
                feature_map[f"dataset_{index}"] = float(index == dataset_id)
            for index in range(len(self.condition_centers)):
                feature_map[f"condition_{index}"] = float(index == condition_id)
            rows.append([feature_map[name] for name in self.feature_names])
        return np.asarray(rows, dtype=np.float32)

    @torch.no_grad()
    def _predict_windows(self, features: np.ndarray) -> List[float]:
        windows = np.stack(
            [
                features[index - SEQUENCE_LENGTH : index]
                for index in range(SEQUENCE_LENGTH, len(features) + 1)
            ]
        )
        predictions = []
        for start in range(0, len(windows), 512):
            batch = torch.as_tensor(
                windows[start : start + 512], dtype=torch.float32, device=self.device
            )
            pred_norm, _ = self.model(batch)
            predictions.extend(
                (pred_norm.squeeze(-1) * self.max_rul).cpu().numpy().tolist()
            )
        return [round(max(0.0, float(value)), 2) for value in predictions]

    def _pseudo_attribution(self, latest_window: np.ndarray) -> List[Attribution]:
        x = torch.tensor(
            latest_window[None, ...],
            dtype=torch.float32,
            device=self.device,
            requires_grad=True,
        )
        # cuDNN RNN backward is unavailable in eval mode. Disable cuDNN only
        # for this single explanation pass; regular inference remains on cuDNN.
        with torch.backends.cudnn.flags(enabled=False):
            pred_norm, _ = self.model(x)
            pred_norm.backward()
        scores = (x.grad * x).abs().mean(dim=1).squeeze(0).detach().cpu().numpy()

        sensor_indices = [
            index
            for index, name in enumerate(self.feature_names)
            if name.startswith("sensor_")
        ]
        sensor_scores = scores[sensor_indices]
        total = float(sensor_scores.sum())
        if total <= 0:
            return []
        ranked = sorted(
            zip(sensor_indices, sensor_scores / total),
            key=lambda pair: pair[1],
            reverse=True,
        )[:5]
        result = []
        for index, contribution in ranked:
            name = self.feature_names[index]
            sensor_number = int(name.split("_")[1])
            latest_value = float(latest_window[-1, index])
            direction = "high" if latest_value > 0.1 else "low" if latest_value < -0.1 else "stable"
            result.append(
                Attribution(
                    feature=f"s{sensor_number}",
                    direction=direction,
                    contribution=round(float(contribution), 4),
                )
            )
        return result

    def analyze(self, request: AnalyzeRequest) -> MonitorEvent:
        if request.operating_settings is None or request.dataset is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "This RUL model requires 'operating_settings' and 'dataset'. "
                    "They are not inferable from sensor_data and will not be fabricated."
                ),
            )
        points = sorted(request.sensor_data, key=lambda item: item.timestamp)
        features = self._prepare(
            points, request.operating_settings, request.dataset
        )
        rul_series = self._predict_windows(features)
        attribution = self._pseudo_attribution(features[-SEQUENCE_LENGTH:])
        timestamp = points[-1].timestamp
        event_stamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        return MonitorEvent(
            event_id=f"evt-{event_stamp}-{uuid.uuid4().hex[:8]}",
            device_id=request.device_id,
            device_model=request.device_model,
            timestamp=timestamp,
            model_version=MODEL_VERSION,
            anomaly_score=None,
            anomaly_type=None,
            rul_predicted=rul_series[-1],
            rul_series=rul_series,
            feature_attribution=None,
            pseudo_attribution=attribution,
            raw_data_ref=request.raw_data_ref,
        )


app = FastAPI(title="IndusMind Monitor API", version="1.0.0")

# Allow browser clients on other hosts. Prefer same-origin reverse proxy in production.
_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_service: Optional[RULService] = None


def get_service() -> RULService:
    global _service
    if _service is None:
        _service = RULService(CHECKPOINT_PATH, PROCESSED_PATH)
    return _service


@app.get("/health")
def health():
    service = get_service()
    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "device": str(service.device),
    }


@app.post("/api/v1/monitor/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    event = get_service().analyze(request)
    return AnalyzeResponse(data=event)
