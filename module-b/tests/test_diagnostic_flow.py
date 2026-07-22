import json

import pytest

from indusmind.crews import l2l3_crew
from indusmind.flows import diagnostic_flow as flow_module
from indusmind.llm import default_router
from indusmind.rag import default_hybrid_search
from indusmind.schemas.events import (
    AnomalyEvent,
    FeatureAttribution,
    L2L3Diagnosis,
    MaintenanceRecommendation,
)


@pytest.fixture(autouse=True)
def _disable_serverchan_notify(monkeypatch):
    """单测不打真实 Server酱，也不消耗免费额度。"""
    monkeypatch.setenv("NOTIFY_ENABLED", "false")


def _event() -> AnomalyEvent:
    return AnomalyEvent(
        event_id="evt-flow",
        device_id="engine-CMAPSS-001",
        device_model="CMAPSS-Turbofan",
        timestamp="2026-07-20T00:00:00+08:00",
        model_version="test",
        anomaly_type="trend_anomaly",
        feature_attribution=[
            FeatureAttribution(feature="s3", contribution=0.9, direction="high"),
            FeatureAttribution(feature="s4", contribution=0.8, direction="high"),
        ],
    )


def _rag(score: float) -> list[dict]:
    return [
        {
            "case_id": "case-cmapss-fd001-hpc-seed",
            "root_cause": "高压压气机效率/流量退化",
            "mechanism": "HPC 效率下降",
            "symptoms": [{"feature": "s3", "direction": "high"}],
            "score": score,
            "source": "local_case_library",
            "evidence_level": "dataset_label",
        }
    ]


@pytest.mark.asyncio
async def test_low_confidence_branch_still_returns_human_review_report(monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_ALWAYS_TOP1", "false")
    monkeypatch.setattr(flow_module, "always_top1", lambda: False)

    async def search(_query):
        return _rag(0.65)

    async def malformed(*_args, **_kwargs):
        return "这不是 JSON"

    monkeypatch.setattr(default_hybrid_search, "hybrid_search", search)
    monkeypatch.setattr(default_router, "chat", malformed)

    state = await flow_module.run_diagnostic_flow(_event())
    assert state.need_human_review is True
    assert state.report is not None
    assert state.report.need_human_review is True
    assert "禁止依据当前候选自动维修" in state.report.markdown


@pytest.mark.asyncio
async def test_high_confidence_branch_reaches_decision_and_report(monkeypatch):
    async def search(_query):
        return _rag(0.95)

    async def rerank(*_args, **_kwargs):
        return json.dumps(
            {
                "candidate_causes": [
                    {
                        "cause": "高压压气机效率/流量退化",
                        "confidence": 0.9,
                        "matched_cases": ["case-cmapss-fd001-hpc-seed"],
                    }
                ],
                "need_human_review": False,
            },
            ensure_ascii=False,
        )

    async def refined(_event, _diagnosis):
        return L2L3Diagnosis(
            event_id="evt-flow",
            diagnosis_level="L2",
            l1="高压压气机效率/流量退化",
            l2="HPC 效率主导退化",
            confidence=0.88,
            maintenance_recommendation=MaintenanceRecommendation(
                action="性能恢复水洗", urgency="planned_within_7d"
            ),
        )

    monkeypatch.setattr(default_hybrid_search, "hybrid_search", search)
    monkeypatch.setattr(default_router, "chat", rerank)
    monkeypatch.setattr(l2l3_crew, "run_l2l3_crew", refined)

    state = await flow_module.run_diagnostic_flow(_event())
    assert state.need_human_review is False
    assert state.decision.action_plan == ["性能恢复水洗"]
    assert state.report is not None


@pytest.mark.asyncio
async def test_always_top1_skips_human_review_and_keeps_logic_path(monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_ALWAYS_TOP1", "true")
    monkeypatch.setattr(flow_module, "always_top1", lambda: True)

    async def search(_query):
        return _rag(0.2)

    async def rerank(*_args, **_kwargs):
        return json.dumps(
            {
                "candidate_causes": [
                    {
                        "cause": "高压压气机效率/流量退化",
                        "confidence": 0.35,
                        "matched_cases": ["case-cmapss-fd001-hpc-seed"],
                        "evidence": "s3/s4 上升与 HPC 退化一致",
                        "mechanism": "HPC 效率下降导致热端与燃油补偿",
                        "logic_path": [
                            "观测到 s3↑ s4↑",
                            "与 HPC 退化签名最接近",
                            "判定为高压压气机效率/流量退化",
                        ],
                    }
                ],
                "recommended_actions": ["孔探评估 HPC"],
                "need_human_review": False,
            },
            ensure_ascii=False,
        )

    async def refined(_event, diagnosis):
        top = diagnosis.candidate_causes[0]
        return L2L3Diagnosis(
            event_id="evt-flow",
            diagnosis_level="L1",
            l1=top.cause,
            confidence=top.confidence,
            logic_path=list(top.logic_path),
            maintenance_recommendation=MaintenanceRecommendation(
                action="孔探评估 HPC", urgency="monitor"
            ),
        )

    monkeypatch.setattr(default_hybrid_search, "hybrid_search", search)
    monkeypatch.setattr(default_router, "chat", rerank)
    monkeypatch.setattr(l2l3_crew, "run_l2l3_crew", refined)

    state = await flow_module.run_diagnostic_flow(_event())
    assert state.need_human_review is False
    assert state.l1_diagnosis.candidate_causes[0].cause == "高压压气机效率/流量退化"
    assert "逻辑路径" in state.report.markdown
    assert "观测到 s3↑ s4↑" in state.report.markdown


@pytest.mark.asyncio
async def test_weak_match_fetches_dify_for_llm_explain(monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_ALWAYS_TOP1", "true")
    monkeypatch.setattr(flow_module, "always_top1", lambda: True)

    async def search(_query):
        return [
            {
                "case_id": None,
                "root_cause": "高压压气机效率/流量退化",
                "mechanism": "弱匹配先验",
                "symptoms": [],
                "score": 0.05,
                "source": "fmea",
                "forced_best": True,
            }
        ]

    async def fake_dify(query: str, top_k: int = 5):
        assert "s3" in query or "HPC" in query or "压气机" in query or "候选根因" in query
        return [
            {
                "document_name": "CMAPSS_fault_sensor_signature_map.md",
                "score": 0.71,
                "content": "HPC Degradation：T30/T50/phi 上升",
                "dataset_id": "demo",
            }
        ]

    async def rerank(*_args, **_kwargs):
        return json.dumps(
            {
                "candidate_causes": [
                    {
                        "cause": "高压压气机效率/流量退化",
                        "confidence": 0.4,
                        "evidence": "Dify 显示 T30/T50/phi 上升",
                        "mechanism": "HPC 退化导致热端升温",
                        "logic_path": ["弱匹配", "查 Dify", "给出解释"],
                    }
                ],
                "need_human_review": False,
            },
            ensure_ascii=False,
        )

    async def refined(_event, diagnosis):
        top = diagnosis.candidate_causes[0]
        return L2L3Diagnosis(
            event_id="evt-flow",
            diagnosis_level="L1",
            l1=top.cause,
            confidence=top.confidence,
            logic_path=list(top.logic_path),
        )

    monkeypatch.setattr(default_hybrid_search, "hybrid_search", search)
    monkeypatch.setattr(flow_module, "dify_knowledge_search_async", fake_dify)
    monkeypatch.setattr(default_router, "chat", rerank)
    monkeypatch.setattr(l2l3_crew, "run_l2l3_crew", refined)

    state = await flow_module.run_diagnostic_flow(_event())
    assert state.dify_explain_hits
    assert "Dify 解释依据" in state.report.markdown
    assert "CMAPSS_fault_sensor_signature_map.md" in state.report.markdown
