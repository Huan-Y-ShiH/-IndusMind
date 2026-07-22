#!/usr/bin/env python3
"""监测模型模拟响应 → 事件标准化 → Dify/RAG → LLM → 决策/人工门控 → 报告。"""
from __future__ import annotations

import asyncio
import json

from indusmind.flows import run_diagnostic_flow
from indusmind.monitoring import SimulatedMonitoringModel, normalize_monitoring_response


async def main_async() -> dict:
    device_id = "engine-CMAPSS-001"
    device_model = "CMAPSS-Turbofan"
    response = await SimulatedMonitoringModel().predict(device_id, device_model)
    event = normalize_monitoring_response(
        response,
        event_id="e2e-simulated-monitor-001",
        device_id=device_id,
        device_model=device_model,
    )
    state = await run_diagnostic_flow(event)
    top = state.l1_diagnosis.candidate_causes[0] if state.l1_diagnosis.candidate_causes else None
    return {
        "monitor_model_version": response.model_version,
        "event_normalized": state.event is not None,
        "rag_count": len(state.rag_results),
        "rag_sources": sorted({item["source"] for item in state.rag_results}),
        "l1_top": top.cause if top else None,
        "l1_confidence": top.confidence if top else 0.0,
        "need_human_review": state.need_human_review,
        "decision_created": state.decision is not None,
        "report_created": state.report is not None,
    }


def main() -> None:
    print(json.dumps(asyncio.run(main_async()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
