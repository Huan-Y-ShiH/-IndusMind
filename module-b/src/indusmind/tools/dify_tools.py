"""Dify 语义检索工具：给 L1 解释兜底 / L2 Crew 按需查知识库。"""
from __future__ import annotations

import asyncio
import logging

from crewai.tools import tool

from indusmind.config import env
from indusmind.rag.dify_client import DifyClient, DifyClientError

logger = logging.getLogger(__name__)


async def dify_knowledge_search_async(query: str, top_k: int = 5) -> list[dict]:
    """对案例库/手册库做语义检索，返回精简命中列表。"""
    client = DifyClient()
    if not client.api_key:
        return []
    dataset_ids = []
    for key in ("DIFY_MANUALS_DATASET_ID", "DIFY_CASES_DATASET_ID"):
        value = env(key, "")
        if value and value not in dataset_ids:
            dataset_ids.append(value)
    if not dataset_ids:
        return []

    hits: list[dict] = []
    for dataset_id in dataset_ids:
        try:
            records = await client.retrieve(
                dataset_id,
                query,
                top_k=top_k,
                search_method="semantic_search",
                score_threshold=None,
            )
        except DifyClientError as exc:
            logger.warning("Dify 检索失败 dataset=%s: %s", dataset_id, exc)
            continue
        for rec in records:
            hits.append(
                {
                    "document_name": rec.document_name,
                    "score": round(float(rec.score or 0.0), 4),
                    "content": (rec.content or "")[:1200],
                    "dataset_id": dataset_id,
                }
            )
    hits.sort(key=lambda item: item["score"], reverse=True)
    # 跨库去重：同文档名保留高分
    seen: set[str] = set()
    unique: list[dict] = []
    for hit in hits:
        key = f"{hit['document_name']}:{hit['content'][:80]}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique[:top_k]


def dify_knowledge_search_impl(query: str, top_k: int = 5) -> list[dict]:
    """同步封装，供 CrewAI @tool 调用。"""
    try:
        return asyncio.run(dify_knowledge_search_async(query, top_k=top_k))
    except RuntimeError:
        # 已在事件循环内时用新循环跑
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(dify_knowledge_search_async(query, top_k=top_k))
        finally:
            loop.close()


@tool("dify_knowledge_search")
def dify_knowledge_search(query: str, top_k: int = 5) -> list[dict]:
    """在 Dify 知识库中语义检索手册/案例叙述，用于补全根因解释与逻辑路径。

    Args:
        query: 自然语言查询，建议包含故障征兆与候选根因。
        top_k: 返回条数上限，默认 5。
    """
    return dify_knowledge_search_impl(query, top_k=top_k)
