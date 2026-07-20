"""Pydantic schemas for Module A - Prediction Engine."""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class SensorReading(BaseModel):
    """Single sensor reading at one timestamp."""
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    sensor_1: Optional[float] = None  # Fan inlet temperature (°R)
    sensor_2: Optional[float] = None  # LPC outlet temperature (°R)
    sensor_3: Optional[float] = None  # HPC outlet temperature (°R)
    sensor_4: Optional[float] = None  # LPT outlet temperature (°R)
    sensor_5: Optional[float] = None  # Fan inlet Pressure (psia)
    sensor_6: Optional[float] = None  # Bypass duct pressure (psia)
    sensor_7: Optional[float] = None  # HPC outlet pressure (psia)
    sensor_8: Optional[float] = None  # Physical fan speed (rpm)
    sensor_9: Optional[float] = None  # Physical core speed (rpm)
    sensor_10: Optional[float] = None  # Engine pressure ratio
    sensor_11: Optional[float] = None  # HPC outlet Static pressure (psia)
    sensor_12: Optional[float] = None  # Ratio of fuel flow to Ps30 (pps/psi)
    sensor_13: Optional[float] = None  # Corrected fan speed (rpm)
    sensor_14: Optional[float] = None  # Corrected core speed (rpm)
    sensor_15: Optional[float] = None  # Bypass ratio
    sensor_16: Optional[float] = None  # Burner fuel-air ratio
    sensor_17: Optional[float] = None  # Bleed enthalpy
    sensor_18: Optional[float] = None  # Demanded fan speed (rpm)
    sensor_19: Optional[float] = None  # Demanded corrected fan speed (rpm)
    sensor_20: Optional[float] = None  # HPT coolant bleed (lbm/s)
    sensor_21: Optional[float] = None  # LPT coolant bleed (lbm/s)


class RULRequest(BaseModel):
    """RUL prediction request."""
    device_id: str = Field(..., description="Device/engine identifier")
    sensor_data: List[SensorReading] = Field(
        ..., min_length=1, description="Time-series sensor readings"
    )


class RULResponse(BaseModel):
    """RUL prediction response."""
    device_id: str
    rul_hours: float = Field(..., description="Predicted remaining useful life (hours)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")
    risk_level: Literal["low", "medium", "high", "critical"]
    trend: Literal["stable", "degrading", "accelerating"]


class AnomalyRequest(BaseModel):
    """Anomaly detection request."""
    device_id: str
    sensor_data: SensorReading


class AnomalyResponse(BaseModel):
    """Anomaly detection response."""
    device_id: str
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    is_anomaly: bool
    abnormal_sensors: List[str] = []


class APIResponse(BaseModel):
    """Unified API response wrapper (Iron Rule #1)."""
    code: int = 0
    data: Optional[dict] = None
    msg: str = "success"
