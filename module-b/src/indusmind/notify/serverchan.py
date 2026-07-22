"""Server酱 Turbo 旁路推送：诊断完成后通知手机，不调用 Module C。

API: POST https://sctapi.ftqq.com/{sendkey}.send
文档: https://sct.ftqq.com/
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from indusmind.config import env

if TYPE_CHECKING:
    from indusmind.flows.state import DiagnosticFlowState

logger = logging.getLogger(__name__)

_SENT_EVENT_IDS: set[str] = set()


def notify_enabled() -> bool:
    return (env("NOTIFY_ENABLED", "false") or "false").lower() in {"1", "true", "yes"}


def _sendkey() -> str:
    return (env("SERVERCHAN_SENDKEY", "") or "").strip()


async def push_serverchan(title: str, desp: str = "") -> bool:
    """向 Server酱发送一条消息。未配置或失败返回 False，不抛给调用方。"""
    key = _sendkey()
    if not key:
        logger.debug("SERVERCHAN_SENDKEY 未配置，跳过推送")
        return False
    url = f"https://sctapi.ftqq.com/{key}.send"
    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            resp = await client.post(url, data={"title": title[:100], "desp": desp[:8000]})
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Server酱推送失败：%s", exc)
        return False
    # 成功码一般为 0；兼容字段 errno / code
    code = payload.get("code", payload.get("errno", -1))
    if code not in (0, "0"):
        logger.warning("Server酱返回非成功：%s", payload)
        return False
    return True


def _format_status(state: DiagnosticFlowState) -> tuple[str, str]:
    event = state.event
    diagnosis = state.l2l3_diagnosis
    decision = state.decision
    root = (diagnosis.l1 if diagnosis else None) or "（尚无根因）"
    conf = diagnosis.confidence if diagnosis else None
    urgency = decision.urgency if decision else "monitor"
    review = "是" if state.need_human_review else "否"
    actions = list((decision.action_plan if decision else None) or [])[:4]
    logic = list((diagnosis.logic_path if diagnosis else None) or [])[:5]

    title = f"[IndusMind] {event.event_id} · {root[:40]}"
    lines = [
        f"**设备**: `{event.device_id}`",
        f"**型号**: {event.device_model or '-'}",
        f"**根因**: {root}",
        f"**置信度**: {conf if conf is not None else '-'}",
        f"**紧急度**: {urgency}",
        f"**人工复核**: {review}",
        "",
        "### 处置建议",
    ]
    lines.extend([f"- {a}" for a in actions] or ["- （无）"])
    if logic:
        lines.extend(["", "### 逻辑路径"])
        lines.extend([f"{i}. {step}" for i, step in enumerate(logic, 1)])
    if state.report and state.report.markdown:
        # 正文过长时截断，避免刷爆免费额度内容长度
        md = state.report.markdown.strip()
        if len(md) > 2500:
            md = md[:2500] + "\n\n…（已截断）"
        lines.extend(["", "### 报告摘要", md])
    return title, "\n".join(lines)


async def notify_diagnostic_complete(state: DiagnosticFlowState) -> bool:
    """诊断 Flow 结束后旁路推送；默认关、失败不影响主流程。"""
    if not notify_enabled():
        return False
    if not state.event:
        return False
    event_id = state.event.event_id
    if event_id in _SENT_EVENT_IDS:
        logger.info("event_id=%s 已推送过，跳过去重", event_id)
        return False
    title, desp = _format_status(state)
    ok = await push_serverchan(title, desp)
    if ok:
        _SENT_EVENT_IDS.add(event_id)
        logger.info("Server酱已推送 event_id=%s", event_id)
    return ok
