import pytest
from pydantic import ValidationError

from indusmind.schemas.events import AnomalyEvent, CandidateCause


def test_rul_history_accepts_documented_flat_shape():
    event = AnomalyEvent(
        event_id="evt-rul",
        device_id="engine-1",
        timestamp="2026-07-20T00:00:00+08:00",
        model_version="rul-v1",
        anomaly_type="rul_anomaly",
        rul_history_drift={
            "7d_ago": 180,
            "3d_ago": 165,
            "now": 120,
            "drift_rate": -8.57,
        },
    )
    assert event.rul_history_drift.values == {"7d_ago": 180, "3d_ago": 165, "now": 120}
    assert event.rul_history_drift.drift_rate == -8.57


def test_confidence_is_bounded():
    with pytest.raises(ValidationError):
        CandidateCause(cause="错误置信度", confidence=1.2)
