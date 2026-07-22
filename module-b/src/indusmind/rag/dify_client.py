"""Dify Retrieval API 封装。

按 `.cursor/rules/tech-stack.mdc` 的分工：设备手册 chunk 与案例叙述文本存 Dify
知识库，用这里的 Retrieval API 做语义检索；FMEA / 工单 / 特征元信息仍走本地
结构化查询（见 [indusmind.knowledge.store](../knowledge/store.py)）。

Dify Retrieval API: `POST {base_url}/datasets/{dataset_id}/retrieve`
文档: https://docs.dify.ai/en/api-reference/knowledge-bases/retrieve-chunks-from-a-knowledge-base-test-retrieval
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from indusmind.config import env

SearchMethod = Literal["keyword_search", "semantic_search", "full_text_search", "hybrid_search"]


@dataclass
class DifyRecord:
    content: str
    score: float
    document_name: str
    document_id: str
    segment_id: str


class DifyClientError(RuntimeError):
    pass


class DifyClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url or env("DIFY_BASE_URL", "https://api.dify.ai/v1")
        self.api_key = api_key or env("DIFY_DATASET_API_KEY", "")
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise DifyClientError("缺少 Dify Dataset API Key，请设置环境变量 DIFY_DATASET_API_KEY")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def retrieve(
        self,
        dataset_id: str,
        query: str,
        *,
        top_k: int = 10,
        search_method: SearchMethod = "hybrid_search",
        score_threshold: float | None = 0.3,
    ) -> list[DifyRecord]:
        """调用 Dify Retrieval API，返回匹配到的知识库分段列表。"""
        retrieval_model: dict[str, Any] = {
            "search_method": search_method,
            "reranking_enable": False,
            "top_k": top_k,
            "score_threshold_enabled": score_threshold is not None,
        }
        if score_threshold is not None:
            retrieval_model["score_threshold"] = score_threshold

        data = await self._request(
            "POST",
            f"/datasets/{dataset_id}/retrieve",
            json={"query": query, "retrieval_model": retrieval_model},
        )

        records: list[DifyRecord] = []
        for rec in data.get("records", []):
            seg = rec.get("segment", {})
            doc = seg.get("document", {}) or {}
            records.append(
                DifyRecord(
                    content=seg.get("content", ""),
                    score=rec.get("score") or 0.0,
                    document_name=doc.get("name", ""),
                    document_id=seg.get("document_id", ""),
                    segment_id=seg.get("id", ""),
                )
            )
        return records

    async def create_document_by_text(
        self,
        dataset_id: str,
        name: str,
        text: str,
        *,
        indexing_technique: str = "high_quality",
    ) -> dict[str, Any]:
        """写入一篇知识库文档（供 scripts/sync_dify_kb.py 冷启动同步用）。"""
        return await self._request(
            "POST",
            f"/datasets/{dataset_id}/document/create-by-text",
            json=self._document_payload(name, text, indexing_technique),
        )

    async def upsert_document_by_text(
        self,
        dataset_id: str,
        name: str,
        text: str,
        *,
        indexing_technique: str = "high_quality",
    ) -> dict[str, Any]:
        """按文档名幂等写入：已存在则更新，不存在才创建。"""
        listing = await self._request(
            "GET",
            f"/datasets/{dataset_id}/documents",
            params={"keyword": name, "limit": 100},
        )
        exact = next((doc for doc in listing.get("data", []) if doc.get("name") == name), None)
        if not exact:
            return await self.create_document_by_text(
                dataset_id, name, text, indexing_technique=indexing_technique
            )
        return await self._request(
            "POST",
            f"/datasets/{dataset_id}/documents/{exact['id']}/update-by-text",
            json={
                "name": name,
                "text": text,
                "process_rule": {"mode": "automatic"},
            },
        )

    @staticmethod
    def _document_payload(name: str, text: str, indexing_technique: str) -> dict[str, Any]:
        return {
            "name": name,
            "text": text,
            "indexing_technique": indexing_technique,
            "process_rule": {"mode": "automatic"},
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """401/403 快速失败；429/5xx/网络抖动做有限指数退避。

        trust_env=False：避免 macOS/系统 HTTP 代理把 localhost 请求劫持成空 503。
        本地 Dify 请用 DIFY_BASE_URL=http://127.0.0.1/v1。
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url, timeout=self.timeout, trust_env=False
                ) as client:
                    resp = await client.request(method, path, headers=self._headers(), **kwargs)
                if resp.status_code in {401, 403}:
                    raise DifyClientError(f"Dify 鉴权失败（HTTP {resp.status_code}）")
                if resp.status_code == 429 or resp.status_code >= 500:
                    detail = (resp.text or "").strip()[:200]
                    raise DifyClientError(
                        f"Dify API 暂时不可用（HTTP {resp.status_code}）{': ' + detail if detail else ''}"
                    )
                resp.raise_for_status()
                return resp.json()
            except DifyClientError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(0.5 * (2**attempt))
        raise DifyClientError(f"Dify API 调用失败：{method} {path}") from last_error
