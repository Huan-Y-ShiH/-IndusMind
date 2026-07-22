"""Server酱旁路通知单测（不打真实网络）。"""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from indusmind.flows.state import DiagnosticFlowState
from indusmind.notify import serverchan as sc
from indusmind.schemas.events import (
    AnomalyEvent,
    Decision,
    DiagnosticReport,
    FeatureAttribution,
    L2L3Diagnosis,
)


def _state() -> DiagnosticFlowState:
    event = AnomalyEvent(
        event_id="evt-notify-1",
        device_id="engine-CMAPSS-001",
        device_model="CMAPSS-Turbofan",
        timestamp="2026-07-20T00:00:00+08:00",
        model_version="test",
        anomaly_type="trend_anomaly",
        feature_attribution=[
            FeatureAttribution(feature="s3", contribution=0.9, direction="high"),
        ],
    )
    return DiagnosticFlowState(
        event=event,
        l2l3_diagnosis=L2L3Diagnosis(
            event_id="evt-notify-1",
            diagnosis_level="L1",
            l1="高压压气机效率/流量退化",
            confidence=0.82,
            logic_path=["s3↑", "匹配 HPC 签名"],
        ),
        decision=Decision(
            event_id="evt-notify-1",
            action_plan=["性能恢复水洗"],
            urgency="planned_within_7d",
        ),
        report=DiagnosticReport(
            event_id="evt-notify-1",
            markdown="## 诊断报告\n根因：HPC",
            need_human_review=False,
        ),
    )


@pytest.fixture(autouse=True)
def _reset_dedup():
    sc._SENT_EVENT_IDS.clear()
    yield
    sc._SENT_EVENT_IDS.clear()


@pytest.mark.asyncio
async def test_notify_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("NOTIFY_ENABLED", "false")
    assert await sc.notify_diagnostic_complete(_state()) is False


@pytest.mark.asyncio
@respx.mock
async def test_notify_posts_to_serverchan(monkeypatch):
    monkeypatch.setenv("NOTIFY_ENABLED", "true")
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCT_TEST_KEY")
    route = respx.post("https://sctapi.ftqq.com/SCT_TEST_KEY.send").mock(
        return_value=Response(200, json={"code": 0, "message": "success"})
    )
    assert await sc.notify_diagnostic_complete(_state()) is True
    assert route.called
    # 同 event 去重
    assert await sc.notify_diagnostic_complete(_state()) is False
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_notify_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv("NOTIFY_ENABLED", "true")
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SCT_TEST_KEY")
    respx.post("https://sctapi.ftqq.com/SCT_TEST_KEY.send").mock(
        return_value=Response(500, text="boom")
    )
    assert await sc.notify_diagnostic_complete(_state()) is False
