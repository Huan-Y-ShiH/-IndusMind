"""Prediction API routes - Mock version for parallel development."""
import random
import time
from fastapi import APIRouter
from api.schemas import RULRequest, RULResponse, AnomalyRequest, AnomalyResponse, APIResponse

router = APIRouter(prefix="/api/v1/predict", tags=["prediction"])


# --- MOCK MODE ---
# When use_mock=True, returns randomized but realistic fake predictions.
# This lets Module B and Module C develop in parallel before the real model is ready.
# Set to False once real model is deployed.

USE_MOCK = True  # Toggle: True = mock, False = real model


def _mock_rul() -> dict:
    """Generate realistic mock RUL prediction."""
    rul = round(random.uniform(10, 300), 1)
    if rul < 50:
        risk = "critical"
    elif rul < 100:
        risk = "high"
    elif rul < 200:
        risk = "medium"
    else:
        risk = "low"
    return {
        "rul_hours": rul,
        "confidence": round(random.uniform(0.75, 0.98), 2),
        "risk_level": risk,
        "trend": random.choice(["stable", "degrading", "accelerating"]),
    }


def _mock_anomaly() -> dict:
    """Generate realistic mock anomaly detection."""
    score = round(random.uniform(0.0, 1.0), 3)
    is_anomaly = score > 0.7
    sensors = ["sensor_2", "sensor_3", "sensor_4", "sensor_7",
               "sensor_8", "sensor_9", "sensor_11", "sensor_12",
               "sensor_13", "sensor_14", "sensor_15", "sensor_17",
               "sensor_20", "sensor_21"]
    abnormal = random.sample(sensors, k=random.randint(0, 3)) if is_anomaly else []
    return {"anomaly_score": score, "is_anomaly": is_anomaly, "abnormal_sensors": abnormal}


@router.post("/rul")
async def predict_rul(req: RULRequest):
    """
    Predict Remaining Useful Life (RUL) for an engine.

    Input: device_id + time-series sensor readings (21 channels)
    Output: RUL in hours, confidence, risk level, trend
    """
    if USE_MOCK:
        import time
        time.sleep(0.1)  # Simulate inference latency
        result = _mock_rul()
    else:
        # TODO: Replace with real model inference
        # from model.lstm_transformer import predict
        # result = predict(req.sensor_data)
        raise NotImplementedError("Real model not yet deployed. Toggle USE_MOCK=False after training.")

    return APIResponse(code=0, data={"device_id": req.device_id, **result})


@router.post("/anomaly")
async def detect_anomaly(req: AnomalyRequest):
    """
    Detect anomalies in a single sensor reading.

    Input: device_id + one sensor reading
    Output: anomaly score, is_anomaly flag, list of abnormal sensors
    """
    if USE_MOCK:
        result = _mock_anomaly()
    else:
        raise NotImplementedError("Real model not yet deployed.")

    return APIResponse(code=0, data={"device_id": req.device_id, **result})


@router.get("/health")
async def health_check():
    """Health check endpoint for docker-compose monitoring."""
    return APIResponse(
        code=0,
        data={"status": "healthy", "mock_mode": USE_MOCK, "model_loaded": False},
    )
