"""本地结构化知识库加载器：FMEA / FMEA-L2 / 案例 / 工单 / 特征元信息。

按 `.cursor/rules/tech-stack.mdc` 的分工：这些是结构化数据，直接本地读取做精确
匹配 / Jaccard 相似度，不上传 Dify 向量库（手册 chunk 和案例叙述文本才上 Dify，
见 [rag/dify_client.py](../rag/dify_client.py)）。
"""
from __future__ import annotations

import csv
import functools
import json
import re
from pathlib import Path
from typing import Any

from indusmind.config import resolve_path

_SYMPTOM_RE = re.compile(r"([a-zA-Z_]+\d*)\s*([↑↓])")


def parse_symptom_signature(signature: str) -> list[tuple[str, str]]:
    """把 `"s3↑;s4↑;s12↑"` 解析成 `[("s3", "high"), ("s4", "high"), ("s12", "high")]`。"""
    out = []
    for feature, arrow in _SYMPTOM_RE.findall(signature or ""):
        out.append((feature, "high" if arrow == "↑" else "low"))
    return out


def symptom_set(signature: str) -> set[str]:
    """转成 Jaccard 用的集合元素，如 `{"s3_high", "s4_high"}`。"""
    return {f"{feat}_{direction}" for feat, direction in parse_symptom_signature(signature)}


def symptoms_to_set(symptoms: list[dict[str, Any]] | list[tuple[str, str]]) -> set[str]:
    """把查询/案例征兆统一成 `feature_direction` 集合。"""
    out: set[str] = set()
    for item in symptoms:
        if isinstance(item, dict):
            feature, direction = item.get("feature"), item.get("direction")
        else:
            feature, direction = item
        if feature and direction in {"high", "low"}:
            out.add(f"{feature}_{direction}")
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class KnowledgeStore:
    """懒加载 + 缓存 `knowledge/` 下的结构化文件。"""

    def __init__(self) -> None:
        self._fmea_rows: list[dict[str, Any]] | None = None
        self._fmea_l2: dict[str, Any] | None = None
        self._cases: list[dict[str, Any]] | None = None
        self._manual_chunks: list[dict[str, Any]] | None = None
        self._feature_defs: dict[str, Any] | None = None
        self._tickets: list[dict[str, Any]] | None = None

    # ---- FMEA 表（兜底规则匹配） ----
    def fmea_rows(self) -> list[dict[str, Any]]:
        if self._fmea_rows is None:
            path = resolve_path("fmea_csv")
            with open(path, encoding="utf-8", newline="") as f:
                self._fmea_rows = list(csv.DictReader(f))
        return self._fmea_rows

    def fmea_for_model(self, device_model: str) -> list[dict[str, Any]]:
        return [r for r in self.fmea_rows() if r["device_model"] == device_model]

    def match_fmea_by_symptoms(
        self,
        device_model: str,
        symptoms: list[dict[str, Any]] | list[str],
        top_k: int = 3,
        *,
        force_best: bool = False,
    ) -> list[dict[str, Any]]:
        """按方向化征兆匹配 FMEA；旧调用只传特征名时保留兼容但降低可信度。

        force_best=True：即使 Jaccard 全为 0，也按「特征名软匹配 → 风险先验」
        强制返回至少一条最可能失效模式（演示/始终出结论模式用）。
        """
        directional = bool(symptoms and isinstance(symptoms[0], dict))
        query_set = symptoms_to_set(symptoms) if directional else set(symptoms)
        query_features = {
            (item.get("feature") if isinstance(item, dict) else item)
            for item in (symptoms or [])
            if (item.get("feature") if isinstance(item, dict) else item)
        }
        scored = []
        soft_scored = []
        for row in self.fmea_for_model(device_model):
            parsed = parse_symptom_signature(row["symptom_signature"])
            row_dir = symptom_set(row["symptom_signature"]) if directional else {feat for feat, _ in parsed}
            row_feats = {feat for feat, _ in parsed}
            base_score = jaccard(query_set, row_dir)
            evidence_level, evidence_weight = _evidence_grade(row.get("source", ""))
            score = base_score * evidence_weight
            if score > 0:
                scored.append((row, score, evidence_level, base_score))
            elif force_best:
                soft = jaccard(query_features, row_feats) * evidence_weight * 0.5
                prior = _risk_prior(row) * 0.05 * evidence_weight
                soft_scored.append((row, soft + prior, evidence_level, soft))
        scored.sort(key=lambda x: x[1], reverse=True)
        if scored:
            selected = scored[:top_k]
        elif force_best and soft_scored:
            soft_scored.sort(key=lambda x: x[1], reverse=True)
            selected = soft_scored[:top_k]
        elif force_best:
            # 型号下无任何重叠时，按风险先验兜底一条。
            priors = []
            for row in self.fmea_for_model(device_model):
                level, weight = _evidence_grade(row.get("source", ""))
                priors.append((row, _risk_prior(row) * 0.05 * weight, level, 0.0))
            priors.sort(key=lambda x: x[1], reverse=True)
            selected = priors[:top_k]
        else:
            selected = []
        return [
            {
                **row,
                "match_score": round(score, 3),
                "raw_match_score": round(base_score, 3),
                "evidence_level": level,
                "direction_aware": directional,
                "forced_best": force_best and base_score <= 0,
            }
            for row, score, level, base_score in selected
        ]

    def match_cases_by_symptoms(
        self,
        device_model: str,
        anomaly_type: str,
        symptoms: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Dify 不可用/漏召回时的本地案例结构化 fallback。"""
        query_set = symptoms_to_set(symptoms)
        scored = []
        for case in self.cases():
            if case.get("device_model") != device_model:
                continue
            if anomaly_type and case.get("anomaly_type") != anomaly_type:
                continue
            score = jaccard(query_set, symptoms_to_set(case.get("symptoms", [])))
            if score > 0:
                # 合成案例保留召回能力，但不能与真实历史案例同权。
                weight = 0.8 if case.get("synthetic", False) else 1.0
                scored.append((case, score * weight, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            {**case, "match_score": round(score, 3), "raw_match_score": round(raw, 3)}
            for case, score, raw in scored[:top_k]
        ]

    # ---- FMEA L2 展开 ----
    def fmea_l2(self) -> dict[str, Any]:
        if self._fmea_l2 is None:
            path = resolve_path("fmea_l2")
            with open(path, encoding="utf-8") as f:
                self._fmea_l2 = json.load(f)
        return self._fmea_l2

    def expand_fmea(self, device_model: str, failure_mode: str) -> dict[str, Any]:
        """expand_fmea 工具的核心逻辑（不带 @tool 装饰）。"""
        data = self.fmea_l2()
        if data.get("device_model") != device_model:
            return {"failure_mode": failure_mode, "sub_modes": [], "source": None}
        for expansion in data.get("expansions", []):
            if expansion["failure_mode"] == failure_mode:
                return {
                    "failure_mode": failure_mode,
                    "sub_modes": expansion["sub_modes"],
                    "source": expansion.get("source"),
                }
        return {"failure_mode": failure_mode, "sub_modes": [], "source": None}

    # ---- 历史案例库 ----
    def cases(self) -> list[dict[str, Any]]:
        if self._cases is None:
            case_dir = resolve_path("cases_dir")
            cases = []
            for path in sorted(Path(case_dir).glob("*.json")):
                with open(path, encoding="utf-8") as f:
                    cases.append(json.load(f))
            self._cases = cases
        return self._cases

    # ---- 设备手册 chunk（叙述文本，通常走 Dify，本地读取用于评估/离线） ----
    def manual_chunks(self) -> list[dict[str, Any]]:
        if self._manual_chunks is None:
            chunk_dir = resolve_path("manual_chunks_dir")
            chunks = []
            for path in sorted(Path(chunk_dir).glob("*.json")):
                with open(path, encoding="utf-8") as f:
                    chunks.append(json.load(f))
            self._manual_chunks = chunks
        return self._manual_chunks

    # ---- 特征元信息（传感器编号 -> 物理含义） ----
    def feature_definitions(self) -> dict[str, Any]:
        if self._feature_defs is None:
            path = resolve_path("feature_meta")
            with open(path, encoding="utf-8") as f:
                self._feature_defs = json.load(f)
        return self._feature_defs

    def describe_feature(self, feature: str) -> str:
        return self.feature_definitions().get("feature_definitions", {}).get(feature, feature)

    # ---- 维修工单库 ----
    def tickets(self) -> list[dict[str, Any]]:
        if self._tickets is None:
            ticket_dir = resolve_path("tickets_dir")
            tickets = []
            for path in sorted(Path(ticket_dir).glob("*.json")):
                with open(path, encoding="utf-8") as f:
                    tickets.append(json.load(f))
            self._tickets = tickets
        return self._tickets

    def maintenance_history(self, device_id: str, fault_category: str | None = None) -> list[dict[str, Any]]:
        results = [t for t in self.tickets() if t["device_id"] == device_id]
        if fault_category:
            results = [t for t in results if t.get("fault_category") == fault_category]
        return results

    @staticmethod
    def fault_category_for_failure_mode(failure_mode: str) -> str:
        """把 L1 失效模式映射成工单大类，避免拿全称做错误精确匹配。"""
        categories = (
            ("压气机", "压气机退化"),
            ("风扇", "风扇退化"),
            ("涡轮", "涡轮退化"),
            ("燃烧", "燃烧系统故障"),
            ("喷嘴", "燃烧系统故障"),
            ("轴承", "轴承故障"),
            ("轴系", "轴系故障"),
        )
        return next((category for keyword, category in categories if keyword in failure_mode), failure_mode)


def _risk_prior(row: dict[str, Any]) -> float:
    """把 FMEA 的 S/O/D 或 RPN 压到 0~1，作强制兜底排序先验。"""
    try:
        rpn = float(row.get("risk_priority") or 0)
    except (TypeError, ValueError):
        rpn = 0.0
    if rpn > 0:
        return min(rpn / 300.0, 1.0)
    try:
        s = float(row.get("severity") or 0)
        o = float(row.get("occurrence") or 0)
        return min((s * o) / 100.0, 1.0)
    except (TypeError, ValueError):
        return 0.0


def _evidence_grade(source: str) -> tuple[str, float]:
    source_lower = source.lower()
    if "docs_analogy" in source_lower or "gas_path_physics" in source_lower:
        return "inferred", 0.65
    if "seed" in source_lower:
        return "seed", 0.75
    if "nasa" in source_lower or "skf" in source_lower:
        return "literature", 1.0
    return "unverified", 0.7


@functools.lru_cache(maxsize=1)
def _cached_store() -> KnowledgeStore:
    return KnowledgeStore()


default_store: KnowledgeStore = _cached_store()
