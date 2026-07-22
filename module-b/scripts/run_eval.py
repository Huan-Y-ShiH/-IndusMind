#!/usr/bin/env python3
"""回放 `tests/fixtures/annotated_events.json` 标注事件，计算 Top-1/Top-3/MRR/幻觸率。

用法：
    python scripts/run_eval.py [--fixture path/to/annotated_events.json]

这是冷启动阶段的烟雾评估（种子数据只有 3 条），生产环境应扩充到
标注事件回放，并把 Recall@10/Recall@3
对齐到 10.2 的目标阈值。
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from indusmind.eval import evaluate_retrieval
from indusmind.flows.query import event_to_query
from indusmind.rag import default_hybrid_search
from indusmind.schemas.events import AnomalyEvent, FeatureAttribution

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "annotated_events.json"


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


async def run(fixture_path: Path) -> None:
    annotated_events = json.loads(fixture_path.read_text(encoding="utf-8"))

    results_by_event: dict[str, list[dict]] = {}
    for ann in annotated_events:
        event = _event_from_annotation(ann)
        query = event_to_query(event, top_k=len(ann["symptoms"]))
        results_by_event[ann["event_id"]] = await default_hybrid_search.hybrid_search(query.model_dump())

    report = evaluate_retrieval(annotated_events, results_by_event)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    if report.bad_cases:
        print("\nBad cases:")
        for bc in report.bad_cases:
            print(f"- {bc['event_id']}: {bc['reason']}")
            for r in bc["top_results"]:
                print(f"    候选: {r.get('root_cause')} (source={r.get('source')}, score={r.get('score')})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()
    asyncio.run(run(args.fixture))


if __name__ == "__main__":
    main()
