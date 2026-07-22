"""检索/诊断质量评估指标。

对齐 docs/knowledge-rag.md / eval 指标（Recall@k / MRR）与项目待办里的
"Top-1/Top-3/MRR/幻觉率"。用于回放标注事件（`tests/fixtures/annotated_events.json`）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _is_hit(result: dict, ground_truth_case_id: str | None, ground_truth_root_cause: str) -> bool:
    if ground_truth_case_id and result.get("case_id") == ground_truth_case_id:
        return True
    root_cause = result.get("root_cause")
    if not root_cause:
        return False
    return root_cause in ground_truth_root_cause or ground_truth_root_cause in root_cause


def rank_of_hit(
    results: list[dict], ground_truth_case_id: str | None, ground_truth_root_cause: str
) -> int | None:
    """真实根因在候选列表中的排名（1-based）；未命中返回 None。"""
    for idx, r in enumerate(results, start=1):
        if _is_hit(r, ground_truth_case_id, ground_truth_root_cause):
            return idx
    return None


@dataclass
class EvalReport:
    n: int = 0
    top1_hits: int = 0
    top3_hits: int = 0
    reciprocal_ranks: list[float] = field(default_factory=list)
    hallucinations: int = 0
    hallucination_checked: int = 0
    bad_cases: list[dict] = field(default_factory=list)

    @property
    def top1_accuracy(self) -> float:
        return self.top1_hits / self.n if self.n else 0.0

    @property
    def top3_accuracy(self) -> float:
        return self.top3_hits / self.n if self.n else 0.0

    @property
    def mrr(self) -> float:
        return sum(self.reciprocal_ranks) / self.n if self.n else 0.0

    @property
    def hallucination_rate(self) -> float | None:
        return (
            self.hallucinations / self.hallucination_checked
            if self.hallucination_checked
            else None
        )

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "top1_accuracy": round(self.top1_accuracy, 3),
            "top3_accuracy": round(self.top3_accuracy, 3),
            "mrr": round(self.mrr, 3),
            "hallucination_rate": (
                round(self.hallucination_rate, 3)
                if self.hallucination_rate is not None
                else None
            ),
        }


def evaluate_retrieval(
    annotated_events: list[dict],
    results_by_event: dict[str, list[dict]],
    *,
    predicted_causes_by_event: dict[str, list[str]] | None = None,
    known_causes: set[str] | None = None,
) -> EvalReport:
    """
    annotated_events: [{"event_id", "ground_truth_case_id"?, "ground_truth_root_cause"}]
    results_by_event: {event_id: hybrid_search() 返回的候选列表}
    """
    report = EvalReport()
    for ann in annotated_events:
        results = results_by_event.get(ann["event_id"], [])
        report.n += 1
        rank = rank_of_hit(results, ann.get("ground_truth_case_id"), ann["ground_truth_root_cause"])
        if rank == 1:
            report.top1_hits += 1
        if rank is not None and rank <= 3:
            report.top3_hits += 1
        report.reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        if rank is None:
            report.bad_cases.append(
                {"event_id": ann["event_id"], "reason": "未命中任何候选", "top_results": results[:3]}
            )
        if predicted_causes_by_event is not None and known_causes is not None:
            hallucinated, checked = check_hallucination(
                predicted_causes_by_event.get(ann["event_id"], []), known_causes
            )
            report.hallucinations += hallucinated
            report.hallucination_checked += checked
    return report


def check_hallucination(predicted_causes: list[str], known_causes: set[str]) -> tuple[int, int]:
    """检查候选根因（通常来自 LLM 重排/L2L3 Crew 输出）能否在本地知识库
    （FMEA failure_mode 集合 + 案例 root_cause 集合）里找到出处。

    返回 (幻觉数, 检查总数)；纯 FMEA/案例检索兜底路径天然为 0（结果本就来自知识库）。
    """
    checked = [c for c in predicted_causes if c]
    hallucinated = [c for c in checked if not any(c in k or k in c for k in known_causes)]
    return len(hallucinated), len(checked)
