"""维修历史查询工具，维修历史查询工具。

数据源：本地 `knowledge/tickets/*.json`（冷启动种子工单）。生产环境接入工单系统后，
把 `default_store.tickets()` 换成真实 DB 查询即可，工具签名不变。
"""
from __future__ import annotations

from datetime import datetime, timezone

from crewai.tools import tool

from indusmind.knowledge import default_store


def query_maintenance_history_impl(device_id: str, fault_category: str) -> dict:
    """查同类故障历史维修记录，纯函数版本。"""
    tickets = default_store.maintenance_history(device_id, fault_category)
    if not tickets:
        return {
            "last_maintenance": None,
            "recurrence_count": 0,
            "avg_interval_days": None,
            "recommended_next_action": "无历史工单记录，建议按常规巡检周期处理",
        }

    def _parse(ts: str) -> datetime | None:
        try:
            return datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            return None

    tickets_sorted = sorted(tickets, key=lambda t: t.get("ticket_id", ""))
    last = tickets_sorted[-1]
    last_case_date = None
    for case in default_store.cases():
        if case.get("case_id") == last.get("linked_case_id"):
            last_case_date = _parse(case.get("timestamp", ""))
            break

    days_since = None
    if last_case_date:
        days_since = (datetime.now(timezone.utc) - last_case_date.astimezone(timezone.utc)).days

    recurrence_count = len(tickets_sorted)
    return {
        "last_maintenance": {
            "date": last_case_date.isoformat() if last_case_date else None,
            "action": last["actions"][-1] if last.get("actions") else None,
            "outcome": last.get("outcome"),
        },
        "recurrence_count": recurrence_count,
        "avg_interval_days": None,
        "days_since_last": days_since,
        "recommended_next_action": (
            "已有历史同类工单，建议参考上次处置方案" if recurrence_count else "无历史工单记录"
        ),
    }


@tool("query_maintenance_history")
def query_maintenance_history(device_id: str, fault_category: str) -> dict:
    """查同类故障的历史维修工单记录（是否复发、上次处置方案与结果）。

    Args:
        device_id: 设备 ID，如 "engine-CMAPSS-001"。
        fault_category: 故障大类，如 "压气机退化"。
    """
    return query_maintenance_history_impl(device_id, fault_category)
