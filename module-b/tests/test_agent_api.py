"""本地 Agent HTTP API 单测（假 Flow，不打真实 LLM）。"""
from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from indusmind.api.app import create_app
from indusmind.api.jobs import JobManager
from indusmind.flows.state import DiagnosticFlowState
from indusmind.schemas.events import (
    AnomalyEvent,
    Decision,
    DiagnosticReport,
    FeatureAttribution,
    L1Diagnosis,
    L2L3Diagnosis,
    CandidateCause,
)


API_KEY = "test-api-key"


def _payload(event_id: str = "evt-api-1") -> dict:
    return {
        "event_id": event_id,
        "device_id": "engine-CMAPSS-001",
        "device_model": "CMAPSS-Turbofan",
        "timestamp": "2026-07-21T00:00:00+00:00",
        "model_version": "test-rul",
        "anomaly_type": "rul_anomaly",
        "anomaly_score": 0.9,
        "rul_hours": 80.0,
        "risk_level": "high",
        "feature_attribution": [
            {"feature": "s3", "contribution": 0.4, "direction": "high"},
            {"feature": "s4", "contribution": 0.3, "direction": "high"},
        ],
    }


async def _fake_flow(event: AnomalyEvent) -> DiagnosticFlowState:
    await asyncio.sleep(0.05)
    return DiagnosticFlowState(
        event=event,
        l1_diagnosis=L1Diagnosis(
            event_id=event.event_id,
            candidate_causes=[
                CandidateCause(
                    cause="高压压气机效率/流量退化",
                    confidence=0.88,
                    evidence="s3/s4 上升",
                    mechanism="HPC 退化",
                    logic_path=["观测", "匹配", "结论"],
                )
            ],
        ),
        l2l3_diagnosis=L2L3Diagnosis(
            event_id=event.event_id,
            diagnosis_level="L2",
            l1="高压压气机效率/流量退化",
            l2="HPC 效率主导退化",
            confidence=0.9,
            severity_basis="s3/s4 上升",
            logic_path=["观测", "匹配", "结论"],
        ),
        decision=Decision(
            event_id=event.event_id,
            action_plan=["性能恢复水洗"],
            matched_tickets=["WO-cmapss-hpc-wash-seed"],
            urgency="planned_within_7d",
        ),
        report=DiagnosticReport(
            event_id=event.event_id,
            markdown="# 报告\nHPC",
            need_human_review=False,
        ),
        rag_results=[{"evidence_level": "dataset_label", "score": 0.9}],
    )


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("API_KEY", API_KEY)
    manager = JobManager(flow_runner=_fake_flow, max_concurrent=1, max_active=3)
    return create_app(job_manager=manager)


@pytest.mark.asyncio
async def test_unauthorized(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/diagnose/jobs", json=_payload())
    assert r.status_code == 401
    assert r.json()["code"] == 401


@pytest.mark.asyncio
async def test_cors_preflight_allows_options(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.options(
            "/api/v1/diagnose/jobs",
            headers={
                "Origin": "https://frontend.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-api-key",
            },
        )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") in {"*", "https://frontend.example.com"}
    allow_headers = (r.headers.get("access-control-allow-headers") or "").lower()
    assert "x-api-key" in allow_headers or allow_headers == "*"


@pytest.mark.asyncio
async def test_submit_poll_success(app):
    transport = ASGITransport(app=app)
    headers = {"X-Api-Key": API_KEY}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/diagnose/jobs", json=_payload(), headers=headers)
        assert r.status_code == 202
        body = r.json()
        assert body["code"] == 0
        job_id = body["data"]["job_id"]
        assert body["data"]["event_id"] == "evt-api-1"

        result = None
        for _ in range(40):
            g = await client.get(f"/api/v1/diagnose/jobs/{job_id}", headers=headers)
            assert g.status_code == 200
            data = g.json()["data"]
            if data["status"] in {"succeeded", "failed"}:
                result = data
                break
            await asyncio.sleep(0.05)

    assert result is not None
    assert result["status"] == "succeeded"
    assert result["progress"] == 100
    assert result["result"]["diagnosis"]["root_cause"] == "高压压气机效率/流量退化"
    assert result["result"]["solution"]["action_plan"] == ["性能恢复水洗"]
    assert result["result"]["rul_hours"] == 80.0
    assert result["result"]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_idempotent_same_event_id(app):
    transport = ASGITransport(app=app)
    headers = {"X-Api-Key": API_KEY}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/v1/diagnose/jobs", json=_payload("evt-idem"), headers=headers)
        r2 = await client.post("/api/v1/diagnose/jobs", json=_payload("evt-idem"), headers=headers)
    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["data"]["job_id"] == r2.json()["data"]["job_id"]
    assert r2.json()["msg"] == "idempotent"


@pytest.mark.asyncio
async def test_job_not_found(app):
    transport = ASGITransport(app=app)
    headers = {"X-Api-Key": API_KEY}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/diagnose/jobs/job_missing", headers=headers)
    assert r.status_code == 404
    assert r.json()["code"] == 404


@pytest.mark.asyncio
async def test_busy_returns_429(monkeypatch):
    monkeypatch.setenv("API_KEY", API_KEY)

    async def slow_flow(event: AnomalyEvent) -> DiagnosticFlowState:
        await asyncio.sleep(2.0)
        return await _fake_flow(event)

    manager = JobManager(flow_runner=slow_flow, max_concurrent=1, max_active=1)
    app = create_app(job_manager=manager)
    transport = ASGITransport(app=app)
    headers = {"X-Api-Key": API_KEY}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/v1/diagnose/jobs", json=_payload("evt-busy-1"), headers=headers)
        r2 = await client.post("/api/v1/diagnose/jobs", json=_payload("evt-busy-2"), headers=headers)
    assert r1.status_code == 202
    assert r2.status_code == 429
    assert r2.json()["msg"] == "busy"


@pytest.mark.asyncio
async def test_request_to_anomaly_maps_rul_hours():
    from indusmind.schemas.api import DiagnoseJobRequest, request_to_anomaly_event

    req = DiagnoseJobRequest.model_validate(_payload())
    event = request_to_anomaly_event(req)
    assert event.rul_predicted == 80.0
    assert event.feature_attribution[0] == FeatureAttribution(
        feature="s3", contribution=0.4, direction="high"
    )
