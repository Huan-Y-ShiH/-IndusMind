"""Qwen / DeepSeek 双通道 LLM 封装。

按任务类型选择主模型，主模型调用失败（超时/限流/5xx/网络错误）时自动降级到
备用模型。选型理由与路由表见 `.cursor/rules/tech-stack.mdc`。

用法：
    from indusmind.llm import default_router, TaskType

    text = await default_router.chat(
        TaskType.DEEP_REASONING,
        [{"role": "user", "content": "..."}],
    )
"""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from indusmind.config import env

logger = logging.getLogger(__name__)


class TaskType(str, enum.Enum):
    """诊断链路里的任务类型，决定用哪个模型通道。"""

    EXTRACTION = "extraction"          # 事件语义化 / 结构化抽取（event_to_query 等）
    FAST_RERANK = "fast_rerank"        # RAG 候选常规重排
    DEEP_REASONING = "deep_reasoning"  # L2/L3 因果推理、多假设验证综合
    REPORT = "report"                  # 报告生成


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str
    timeout: float = 60.0


class LLMError(RuntimeError):
    """主备通道均调用失败时抛出。"""


def qwen_config(model: str | None = None) -> ProviderConfig:
    return ProviderConfig(
        name="qwen",
        base_url=env("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1") or "",
        api_key=env("QWEN_API_KEY", "") or "",
        model=model or env("QWEN_MODEL", "qwen-plus") or "qwen-plus",
    )


def deepseek_config(model: str | None = None) -> ProviderConfig:
    return ProviderConfig(
        name="deepseek",
        base_url=env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1") or "",
        api_key=env("DEEPSEEK_API_KEY", "") or "",
        model=model or env("DEEPSEEK_MODEL", "deepseek-reasoner") or "deepseek-reasoner",
    )


# 任务类型 -> (主模型, 备用模型)。复杂推理主用 deepseek-reasoner，其余主用 qwen。
DEFAULT_ROUTING: dict[TaskType, tuple[ProviderConfig, ProviderConfig]] = {
    TaskType.EXTRACTION: (qwen_config("qwen-turbo"), deepseek_config("deepseek-chat")),
    TaskType.FAST_RERANK: (qwen_config("qwen-plus"), deepseek_config("deepseek-chat")),
    TaskType.DEEP_REASONING: (deepseek_config("deepseek-reasoner"), qwen_config("qwen-plus")),
    TaskType.REPORT: (qwen_config("qwen-plus"), deepseek_config("deepseek-chat")),
}


class LLMRouter:
    """按任务类型路由到 Qwen/DeepSeek，主模型失败自动降级。"""

    def __init__(
        self,
        routing: dict[TaskType, tuple[ProviderConfig, ProviderConfig]] | None = None,
    ) -> None:
        self._routing = routing or DEFAULT_ROUTING

    async def chat(
        self,
        task_type: TaskType,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        **extra: Any,
    ) -> str:
        primary, fallback = self._routing[task_type]
        try:
            return await self._call(primary, messages, temperature=temperature, max_tokens=max_tokens, **extra)
        except Exception as exc:  # noqa: BLE001 - 任何异常都应触发降级
            logger.warning(
                "LLM 主通道 %s 调用失败（task=%s），降级到 %s：%s",
                primary.name, task_type.value, fallback.name, exc,
            )
            try:
                return await self._call(fallback, messages, temperature=temperature, max_tokens=max_tokens, **extra)
            except Exception as exc2:  # noqa: BLE001
                raise LLMError(
                    f"主备通道均失败：{primary.name}({primary.model}) 和 "
                    f"{fallback.name}({fallback.model})，task={task_type.value}"
                ) from exc2

    async def _call(
        self,
        cfg: ProviderConfig,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        **extra: Any,
    ) -> str:
        if not cfg.api_key:
            raise LLMError(f"缺少 {cfg.name} 的 API Key，请设置 {cfg.name.upper()}_API_KEY 环境变量")
        async with httpx.AsyncClient(base_url=cfg.base_url, timeout=cfg.timeout) as client:
            resp = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                json={
                    "model": cfg.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **extra,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def crewai_llm(self, task_type: TaskType, *, use_fallback: bool = False):
        """构造 CrewAI Agent 可用的 `crewai.LLM` 实例（L2/L3 专家 Crew 用）。"""
        try:
            from crewai import LLM
        except ImportError as exc:  # pragma: no cover
            raise ImportError("crewai 未安装，运行 `pip install -e .`") from exc
        primary, fallback = self._routing[task_type]
        cfg = fallback if use_fallback else primary
        return LLM(model=f"openai/{cfg.model}", base_url=cfg.base_url, api_key=cfg.api_key)


default_router = LLMRouter()
