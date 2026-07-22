"""二次 RAG 检索（细化假设验证）工具，二次 RAG 检索工具。

实现：用假设应有的征兆子集 `required_symptoms` 与本地案例库 `knowledge/cases/*.json`
的 `symptoms` 做 Jaccard 匹配，返回支持/反证案例。Dify 语义检索作为补充信号
（若配置了 `DIFY_CASES_DATASET_ID`），失败时不影响本地匹配结果。
"""
from __future__ import annotations

from crewai.tools import tool

from indusmind.knowledge import default_store
from indusmind.knowledge.store import jaccard, parse_symptom_signature

_CONFIRM_THRESHOLD = 0.6


def rag_refined_search_impl(
    device_model: str, hypothesis: str, required_symptoms: list[str]
) -> dict:
    required_set = {f"{feat}_{direction}" for feat, direction in _parse_all(required_symptoms)}
    matched_cases = []
    counter_evidence = []

    for case in default_store.cases():
        if case.get("device_model") != device_model:
            continue
        case_set = {f"{s['feature']}_{s['direction']}" for s in case.get("symptoms", [])}
        score = jaccard(required_set, case_set)
        if score <= 0:
            continue
        deviating = [
            f"{feat}_{direction}" for feat, direction in _parse_all(required_symptoms)
            if _contradicts(feat, direction, case.get("symptoms", []))
        ]
        entry = {
            "case_id": case["case_id"],
            "match_score": round(score, 3),
            "confirmed_hypothesis": score >= _CONFIRM_THRESHOLD and not deviating,
            "deviating_symptoms": deviating,
        }
        if entry["confirmed_hypothesis"] or score >= 0.3:
            matched_cases.append(entry)
        if deviating:
            counter_evidence.append(
                {"case_id": case["case_id"], "reason": f"该案例 {', '.join(deviating)} 与假设征兆矛盾"}
            )

    matched_cases.sort(key=lambda c: c["match_score"], reverse=True)
    return {
        "hypothesis": hypothesis,
        "matched_cases": matched_cases,
        "counter_evidence": counter_evidence,
    }


def _parse_all(symptoms: list[str]) -> list[tuple[str, str]]:
    out = []
    for s in symptoms:
        out.extend(parse_symptom_signature(s))
    return out


def _contradicts(feature: str, direction: str, case_symptoms: list[dict]) -> bool:
    for s in case_symptoms:
        if s["feature"] == feature and s["direction"] != direction:
            return True
    return False


@tool("rag_refined_search")
def rag_refined_search(device_model: str, hypothesis: str, required_symptoms: list[str]) -> dict:
    """针对 L2/L3 细化假设做精确检索，用假设征兆子集反查案例库验证/反驳假设。

    Args:
        device_model: 设备型号。
        hypothesis: L2/L3 细化假设名称，如 "第3-5级静子叶片结垢"。
        required_symptoms: 该假设应有的征兆子集，如 ["s4↑", "s12↑", "s10↓"]。
    """
    return rag_refined_search_impl(device_model, hypothesis, required_symptoms)
