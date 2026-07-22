"""混合检索，对齐 docs/knowledge-rag.md 的 hybrid_search 契约。

策略：
1. 先用 Dify 语义检索案例库（案例叙述文本），从命中分段解析出 `case_id`，
   回到本地 `knowledge/cases/*.json` 取回结构化字段（symptoms/root_cause/mechanism）。
2. Dify 不可用（未配置 API Key / 网络错误）或召回不足时，本地 FMEA 表
   Jaccard 相似度兜底。
3. 附加 Dify 手册库检索结果作为机理佐证（source="manual"）。
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable

from indusmind.config import env
from indusmind.knowledge import default_store
from indusmind.knowledge.store import parse_symptom_signature
from indusmind.rag.dify_client import DifyClient, DifyClientError
from indusmind.schemas.events import DiagnosticQuery

logger = logging.getLogger(__name__)

_CASE_ID_RE = re.compile(r"^case_id:\s*(\S+)", re.MULTILINE)
_CHUNK_ID_RE = re.compile(r"^chunk_id:\s*(\S+)", re.MULTILINE)


class HybridSearch:
    """`hybrid_search(query) -> List[dict]` 的具体实现。"""

    def __init__(
        self,
        dify_client: DifyClient | None = None,
        cases_dataset_id: str | None = None,
        manuals_dataset_id: str | None = None,
    ) -> None:
        self._dify = dify_client or DifyClient()
        # None 表示读取环境变量；空字符串表示显式禁用，方便测试和离线运行。
        self._cases_dataset_id = env("DIFY_CASES_DATASET_ID") if cases_dataset_id is None else cases_dataset_id
        self._manuals_dataset_id = (
            env("DIFY_MANUALS_DATASET_ID") if manuals_dataset_id is None else manuals_dataset_id
        )
        self._dify_unavailable_until = 0.0

    async def hybrid_search(self, query: dict, top_k: int = 10) -> list[dict]:
        """
        输入 query: {device_id, device_model, anomaly_type, top_features,
                     symptom_text, natural_language}
        输出: [{case_id, root_cause, mechanism, symptoms, score,
                source: "case_library" | "fmea" | "manual"}]
        """
        validated = DiagnosticQuery.model_validate(query)
        query = validated.model_dump()
        dify_cases = await self._search_cases(query, top_k)
        local_cases = self._search_local_cases(query, top_k)
        fmea = self._fallback_fmea(query, top_k)
        manuals = await self._search_manuals(query, top_k=3)

        causes = _fuse_ranked_sources(
            (dify_cases, 1.0),
            (local_cases, 0.95),
            (fmea, 0.85),
        )
        causes = _dedupe(causes, key="root_cause")
        # 手册是佐证，不允许按原始向量分挤掉根因候选。
        supporting = _fuse_ranked_sources((manuals, 0.55))
        return causes[: max(top_k - 3, 1)] + supporting[:3]

    async def _search_cases(self, query: dict, top_k: int) -> list[dict]:
        if not self._cases_dataset_id or time.monotonic() < self._dify_unavailable_until:
            logger.info("未配置 DIFY_CASES_DATASET_ID，跳过案例库语义检索，直接走本地 FMEA 兜底")
            return []
        try:
            records = await self._dify.retrieve(self._cases_dataset_id, query["natural_language"], top_k=top_k)
        except DifyClientError as exc:
            self._dify_unavailable_until = time.monotonic() + 30
            logger.warning("Dify 案例库检索失败，走本地 FMEA 兜底：%s", exc)
            return []

        cases_by_id = {c["case_id"]: c for c in default_store.cases()}
        out = []
        for rec in records:
            m = _CASE_ID_RE.search(rec.content)
            case_id = m.group(1) if m else rec.document_name
            case = cases_by_id.get(case_id)
            if case:
                out.append(
                    {
                        "case_id": case["case_id"],
                        "root_cause": case.get("root_cause"),
                        "mechanism": case.get("mechanism"),
                        "symptoms": case.get("symptoms", []),
                        "score": rec.score,
                        "source": "case_library",
                    }
                )
            else:
                logger.warning("Dify 案例分段无法回查本地结构化案例，已忽略：document=%s", rec.document_name)
        return out

    def _search_local_cases(self, query: dict, top_k: int) -> list[dict]:
        rows = default_store.match_cases_by_symptoms(
            query.get("device_model") or "",
            query.get("anomaly_type") or "",
            query.get("symptoms", []),
            top_k=top_k,
        )
        return [
            {
                "case_id": case["case_id"],
                "root_cause": case.get("root_cause"),
                "mechanism": case.get("mechanism"),
                "symptoms": case.get("symptoms", []),
                "score": case["match_score"],
                "source": "local_case_library",
                "evidence_level": case.get("evidence_level", "unverified"),
                "synthetic": case.get("synthetic", False),
            }
            for case in rows
        ]

    async def _search_manuals(self, query: dict, top_k: int) -> list[dict]:
        if not self._manuals_dataset_id or time.monotonic() < self._dify_unavailable_until:
            return []
        try:
            records = await self._dify.retrieve(self._manuals_dataset_id, query["natural_language"], top_k=top_k)
        except DifyClientError as exc:
            self._dify_unavailable_until = time.monotonic() + 30
            logger.warning("Dify 手册库检索失败：%s", exc)
            return []
        chunks_by_id = {c["chunk_id"]: c for c in default_store.manual_chunks()}
        out = []
        for rec in records:
            m = _CHUNK_ID_RE.search(rec.content)
            chunk_id = m.group(1) if m else rec.document_name
            chunk = chunks_by_id.get(chunk_id, {})
            out.append(
                {
                    "case_id": None,
                    "root_cause": None,
                    "mechanism": chunk.get("content", rec.content),
                    "symptoms": [],
                    "score": rec.score,
                    "source": "manual",
                    "chunk_id": chunk_id,
                    "section": chunk.get("section"),
                    "page": chunk.get("page"),
                    "source_ref": chunk.get("source"),
                }
            )
        return out

    def _fallback_fmea(self, query: dict, top_k: int) -> list[dict]:
        device_model = query.get("device_model")
        if not device_model:
            return []
        symptoms = query.get("symptoms") or query.get("top_features", [])
        force_best = env("DIAGNOSTIC_ALWAYS_TOP1", "false").lower() in {"1", "true", "yes"}
        rows = default_store.match_fmea_by_symptoms(
            device_model, symptoms, top_k=top_k, force_best=force_best
        )
        return [
            {
                "case_id": None,
                "root_cause": row["failure_mode"],
                "mechanism": row.get("effect"),
                "symptoms": [
                    {"feature": f, "direction": d, "magnitude": None}
                    for f, d in parse_symptom_signature(row["symptom_signature"])
                ],
                "score": max(row["match_score"], 0.05 if force_best else 0.0),
                "source": "fmea",
                "evidence_level": row.get("evidence_level"),
                "source_ref": row.get("source"),
                "forced_best": row.get("forced_best", False),
            }
            for row in rows
        ]


def _fuse_ranked_sources(*sources: tuple[list[dict], float]) -> list[dict]:
    """分源归一化后融合，避免向量分和 Jaccard 原始量纲直接比较。"""
    fused: list[dict] = []
    for rows, source_weight in sources:
        for rank, row in enumerate(rows, start=1):
            raw = max(0.0, min(float(row.get("score", 0.0)), 1.0))
            rank_factor = 1.0 / (1.0 + 0.15 * (rank - 1))
            item = dict(row)
            item["raw_score"] = raw
            item["score"] = round(source_weight * (0.7 * raw + 0.3 * rank_factor), 4)
            fused.append(item)
    return sorted(fused, key=lambda item: item["score"], reverse=True)


def _dedupe(rows: Iterable[dict], key: str) -> list[dict]:
    seen: set[str] = set()
    out = []
    for row in rows:
        value = row.get(key) or f"{row.get('source')}:{row.get('case_id')}"
        if value in seen:
            continue
        seen.add(value)
        out.append(row)
    return out


default_hybrid_search = HybridSearch()
