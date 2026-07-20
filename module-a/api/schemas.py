"""
Pydantic schemas for Module A - Prediction Engine.

Updated v0.2.0: Added degradation_analysis to RUL response
for Module B's fault diagnosis agent.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# ==========================================
# Sensor Data Models
# ==========================================

class SensorReading(BaseModel):
    """Single sensor reading at one timestamp (21 channels)."""
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    sensor_1: Optional[float] = None   # Fan inlet temperature (°R)
    sensor_2: Optional[float] = None   # LPC outlet temperature (°R)
    sensor_3: Optional[float] = None   # HPC outlet temperature (°R)
    sensor_4: Optional[float] = None   # LPT outlet temperature (°R)
    sensor_5: Optional[float] = None   # Fan inlet Pressure (psia)
    sensor_6: Optional[float] = None   # Bypass duct pressure (psia)
    sensor_7: Optional[float] = None   # HPC outlet pressure (psia)
    sensor_8: Optional[float] = None   # Physical fan speed (rpm)
    sensor_9: Optional[float] = None   # Physical core speed (rpm)
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


# ==========================================
# Request Models
# ==========================================

class RULRequest(BaseModel):
    """RUL prediction request."""
    device_id: str = Field(..., description="Device/engine identifier")
    sensor_data: List[SensorReading] = Field(
        ..., min_length=1, description="Time-series sensor readings (sliding window)"
    )


class AnomalyRequest(BaseModel):
    """Anomaly detection request for single timestamp."""
    device_id: str
    sensor_data: SensorReading


# ==========================================
# Response Models
# ==========================================

class SensorAnomaly(BaseModel):
    """Single sensor anomaly detail for Module B's diagnosis."""
    sensor: str = Field(..., description="Sensor name, e.g. 'sensor_2'")
    direction: Literal["rising", "falling", "fluctuating"] = Field(
        ..., description="Trend direction"
    )
    severity: float = Field(
        ..., ge=0.0, le=1.0, description="How severe the deviation is (0=normal, 1=extreme)"
    )
    z_score: Optional[float] = Field(
        None, description="Number of standard deviations from baseline mean"
    )
    description: str = Field(..., description="Human-readable, e.g. 'LPC出口温度持续升高'")


class DegradationAnalysis(BaseModel):
    """
    Degradation analysis output for Module B's fault diagnosis.
    
    This is the KEY bridge between Module A and Module B.
    B uses these abnormal sensor patterns to query RAG knowledge base
    and determine the root cause of the degradation.
    """
    top_abnormal_sensors: List[SensorAnomaly] = Field(
        ..., description="Top-N most abnormal sensors, ranked by severity"
    )
    degradation_pattern: Literal[
        "normal", "thermal_efficiency_loss", "mechanical_wear",
        "flow_path_degradation", "compressor_stall_risk"
    ] = Field(..., description="Classified degradation pattern")
    pattern_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence of pattern classification"
    )
    feature_importance: dict = Field(
        ..., description="Sensor importance scores for RUL prediction (from attention weights)"
    )
    analysis_method: str = Field(
        default="attention_weights + residual_analysis",
        description="Methods used for degradation analysis"
    )


class RULResponseData(BaseModel):
    """RUL prediction response data."""
    device_id: str
    rul_hours: float = Field(..., description="Predicted remaining useful life (hours)")
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high", "critical"]
    trend: Literal["stable", "degrading", "accelerating"]
    degradation_analysis: Optional[DegradationAnalysis] = Field(
        None, description="Sensor anomaly details for Module B diagnosis"
    )


class AnomalyResponseData(BaseModel):
    """Anomaly detection response data."""
    device_id: str
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    is_anomaly: bool
    abnormal_sensors: List[SensorAnomaly] = []


class APIResponse(BaseModel):
    """Unified API response wrapper (Iron Rule #1)."""
    code: int = 0
    data: Optional[dict] = None
    msg: str = "success"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    mock_mode: bool = True
    model_loaded: bool = False
    analysis_methods: List[str] = ["attention_weights", "residual_analysis"]
