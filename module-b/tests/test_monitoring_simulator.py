import pytest

from indusmind.monitoring import SimulatedMonitoringModel, normalize_monitoring_response


@pytest.mark.asyncio
async def test_simulated_monitor_response_normalizes_to_event():
    response = await SimulatedMonitoringModel().predict("engine-1", "CMAPSS-Turbofan")
    event = normalize_monitoring_response(
        response,
        event_id="evt-1",
        device_id="engine-1",
        device_model="CMAPSS-Turbofan",
    )
    assert event.anomaly_score == 0.91
    assert event.model_version == "simulated-monitor-fd001-v1"
    assert [item.feature for item in event.top_features()] == ["s3", "s4", "s12", "s9"]
