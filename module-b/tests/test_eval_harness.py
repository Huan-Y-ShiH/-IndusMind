"""回放标注事件，计算 Top-1/Top-3/MRR/幻觸率（对齐 docs/knowledge-rag.md / eval 指标）。

冷启动种子数据只有 3 条标注事件，阈值刻意放宽；扩充到 100 条标注对后应把
断言收紧到 docs 10.2 的目标（Recall@3 ≥ 85%、MRR ≥ 0.6）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from indusmind.eval import evaluate_retrieval
from indusmind.flows.query import event_to_query
from indusmind.rag import HybridSearch
from indusmind.schemas.events import AnomalyEvent, FeatureAttribution

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "annotated_events.json"


@pytest.fixture()
def annotated_events() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _event_from_annotation(ann: dict) -> AnomalyEvent:
    return AnomalyEvent(
        event_id=ann["event_id"],
        device_id=ann["device_id"],
        device_model=ann.get("device_model"),
        timestamp="2026-01-01T00:00:00+08:00",
        model_version="eval-harness",
        anomaly_type=ann["anomaly_type"],
        feature_attribution=[
            FeatureAttribution(feature=s["feature"], contribution=1.0, direction=s["direction"])
            for s in ann["symptoms"]
        ],
    )


@pytest.mark.asyncio
async def test_hybrid_search_eval_report(annotated_events: list[dict]) -> None:
    search = HybridSearch(cases_dataset_id="", manuals_dataset_id="")
    results_by_event = {}
    for ann in annotated_events:
        event = _event_from_annotation(ann)
        query = event_to_query(event, top_k=len(ann["symptoms"]))
        results_by_event[ann["event_id"]] = await search.hybrid_search(query.model_dump())

    report = evaluate_retrieval(annotated_events, results_by_event)

    assert report.n == len(annotated_events)
    # 冷启动烟雾阈值：只有本地 FMEA 兜底（未接 Dify 案例库）时也应至少命中一半
    assert report.top3_accuracy >= 0.5, f"top3_accuracy 太低: {report.as_dict()}, bad_cases={report.bad_cases}"
    assert report.mrr > 0
    assert report.hallucination_rate is None  # 未执行 LLM 诊断时不得伪报 0%


def test_hallucination_rate_is_actually_computed():
    annotations = [{"event_id": "e1", "ground_truth_root_cause": "压气机退化"}]
    report = evaluate_retrieval(
        annotations,
        {"e1": [{"root_cause": "压气机退化", "case_id": None}]},
        predicted_causes_by_event={"e1": ["压气机退化", "外星材料失效"]},
        known_causes={"压气机退化"},
    )
    assert report.hallucination_rate == 0.5
