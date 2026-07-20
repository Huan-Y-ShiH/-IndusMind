"""
Prediction API routes with degradation analysis.

v0.2.0: Added degradation_analysis output for Module B fault diagnosis.
         Mock mode generates realistic sensor anomaly patterns.
"""
import random
import time
from fastapi import APIRouter
from api.schemas import (
    RULRequest, RULResponseData, AnomalyRequest, AnomalyResponseData,
    APIResponse, SensorAnomaly, DegradationAnalysis
)

router = APIRouter(prefix="/api/v1/predict", tags=["prediction"])

USE_MOCK = True  # Toggle: True = mock, False = real model


# ==========================================
# Mock Data: Sensor metadata for realistic mock
# ==========================================

SENSOR_NAMES = {
    "sensor_2": "LPC出口温度",
    "sensor_3": "HPC出口温度",
    "sensor_4": "LPT出口温度",
    "sensor_7": "HPC出口压力",
    "sensor_8": "物理风扇转速",
    "sensor_9": "物理核心转速",
    "sensor_11": "HPC出口静压",
    "sensor_12": "燃油流量比",
    "sensor_13": "校正风扇转速",
    "sensor_14": "校正核心转速",
    "sensor_15": "旁通比",
    "sensor_17": "引气焓",
    "sensor_20": "HPT冷却气流",
    "sensor_21": "LPT冷却气流",
}

# Degradation pattern → typical abnormal sensors
DEGRADATION_PATTERNS = {
    "thermal_efficiency_loss": {
        "sensors": ["sensor_2", "sensor_3", "sensor_4", "sensor_7", "sensor_11"],
        "description": "热效率下降——压缩机和涡轮气路退化",
    },
    "mechanical_wear": {
        "sensors": ["sensor_8", "sensor_9", "sensor_13", "sensor_14"],
        "description": "机械磨损——轴承/转子系统退化",
    },
    "flow_path_degradation": {
        "sensors": ["sensor_7", "sensor_11", "sensor_12", "sensor_15"],
        "description": "气路退化——流道污染或叶片侵蚀",
    },
    "compressor_stall_risk": {
        "sensors": ["sensor_7", "sensor_8", "sensor_9", "sensor_11", "sensor_15"],
        "description": "喘振风险——压气机工作不稳定",
    },
}


def _generate_mock_sensor_anomalies(rul_hours: float, risk_level: str) -> DegradationAnalysis:
    """
    Generate realistic mock sensor anomalies based on RUL and risk level.
    
    In production, this will be replaced by:
    - Method 1: Attention weight analysis from LSTM+Transformer
    - Method 2: Sliding window residual analysis (Z-score vs baseline)
    """
    # Higher risk → more sensors abnormal, higher severity
    if risk_level == "critical":
        num_abnormal = random.randint(3, 5)
        base_severity = random.uniform(0.85, 0.98)
    elif risk_level == "high":
        num_abnormal = random.randint(2, 4)
        base_severity = random.uniform(0.70, 0.92)
    elif risk_level == "medium":
        num_abnormal = random.randint(1, 2)
        base_severity = random.uniform(0.45, 0.75)
    else:
        num_abnormal = 0
        base_severity = 0.0

    # Pick a degradation pattern based on RUL
    if rul_hours < 50:
        pattern = random.choice(["thermal_efficiency_loss", "mechanical_wear"])
    elif rul_hours < 100:
        pattern = random.choice(["thermal_efficiency_loss", "flow_path_degradation"])
    elif rul_hours < 200:
        pattern = "flow_path_degradation"
    else:
        pattern = "normal"

    # Pick sensors from the degradation pattern
    candidate_sensors = DEGRADATION_PATTERNS.get(
        pattern, DEGRADATION_PATTERNS["flow_path_degradation"]
    )["sensors"]
    selected = random.sample(candidate_sensors, min(num_abnormal, len(candidate_sensors)))

    # Generate sensor anomaly details
    anomalies = []
    for i, sensor in enumerate(selected):
        severity = min(1.0, base_severity + random.uniform(-0.1, 0.1))
        anomalies.append(SensorAnomaly(
            sensor=sensor,
            direction=random.choice(["rising", "falling", "fluctuating"]),
            severity=round(severity, 2),
            z_score=round(severity * random.uniform(2.0, 5.0), 1),
            description=f"{SENSOR_NAMES.get(sensor, sensor)}持续{'升高' if severity > 0.7 else '异常'}",
        ))

    # Feature importance (from mock attention weights)
    importance = {}
    for s in candidate_sensors[:5]:
        importance[s] = round(random.uniform(0.05, 0.35), 2)
    # Normalize
    total = sum(importance.values())
    importance = {k: round(v / total, 2) for k, v in importance.items()}

    return DegradationAnalysis(
        top_abnormal_sensors=anomalies,
        degradation_pattern=pattern,
        pattern_confidence=round(random.uniform(0.78, 0.96), 2),
        feature_importance=importance,
    )


def _mock_rul() -> dict:
    """Generate realistic mock RUL prediction with degradation analysis."""
    rul = round(random.uniform(10, 300), 1)
    if rul < 50:
        risk = "critical"
    elif rul < 100:
        risk = "high"
    elif rul < 200:
        risk = "medium"
    else:
        risk = "low"

    degradation = _generate_mock_sensor_anomalies(rul, risk)

    return {
        "rul_hours": rul,
        "confidence": round(random.uniform(0.75, 0.98), 2),
        "risk_level": risk,
        "trend": random.choice(["stable", "degrading", "accelerating"]),
        "degradation_analysis": degradation.model_dump(),
    }


def _mock_anomaly() -> dict:
    """Generate realistic mock anomaly detection."""
    score = round(random.uniform(0.0, 1.0), 3)
    is_anomaly = score > 0.7
    abnormal = []
    if is_anomaly:
        candidates = list(SENSOR_NAMES.keys())
        selected = random.sample(candidates, k=random.randint(1, 3))
        abnormal = [
            {
                "sensor": s,
                "direction": random.choice(["rising", "falling"]),
                "severity": round(random.uniform(0.6, 0.95), 2),
                "description": f"{SENSOR_NAMES[s]}异常",
            }
            for s in selected
        ]
    return {"anomaly_score": score, "is_anomaly": is_anomaly, "abnormal_sensors": abnormal}


# ==========================================
# API Endpoints
# ==========================================

@router.post("/rul")
async def predict_rul(req: RULRequest):
    """
    Predict Remaining Useful Life (RUL) with degradation analysis.

    Returns RUL + sensor anomaly details that Module B uses for fault diagnosis.
    The degradation_analysis field contains:
    - Top-N most abnormal sensors with direction, severity, Z-score
    - Classified degradation pattern (thermal/mechanical/flow_path/stall)
    - Sensor feature importance from attention weights
    """
    if USE_MOCK:
        time.sleep(0.15)  # Simulate inference latency
        result = _mock_rul()
    else:
        # TODO: Replace with real model inference
        # from model.lstm_transformer import predict_with_analysis
        # result = predict_with_analysis(req.sensor_data)
        raise NotImplementedError(
            "Real model not yet deployed. Set USE_MOCK=False after training."
        )

    return APIResponse(code=0, data={"device_id": req.device_id, **result})


@router.post("/anomaly")
async def detect_anomaly(req: AnomalyRequest):
    """
    Detect anomalies in a single sensor reading.
    """
    if USE_MOCK:
        result = _mock_anomaly()
    else:
        raise NotImplementedError("Real model not yet deployed.")

    return APIResponse(code=0, data={"device_id": req.device_id, **result})


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return APIResponse(
        code=0,
        data={
            "status": "healthy",
            "mock_mode": USE_MOCK,
            "model_loaded": False,
            "analysis_methods": ["attention_weights", "residual_analysis"],
        },
    )
