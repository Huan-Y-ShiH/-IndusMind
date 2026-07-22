"""工况历史查询工具（占位，available=false）。

尚未接入 SCADA。当前返回确定性占位数据，字段结构与最终真实实现保持一致；
接入后只需替换本模块内部实现，工具签名不变。
"""
from __future__ import annotations

from crewai.tools import tool

_PLACEHOLDER_NOTE = "占位数据：尚未接入 SCADA，接入后替换本函数实现"


def query_operating_conditions_impl(device_id: str, time_window: str = "last_30d") -> dict:
    return {
        "available": False,
        "reason": "SCADA_NOT_CONNECTED",
        "device_id": device_id,
        "time_window": time_window,
        "start_stop_count": None,
        "high_load_ratio": None,
        "low_load_ratio": None,
        "avg_ambient_temp": None,
        "environment": "unknown",
        "notable_events": [],
        "note": _PLACEHOLDER_NOTE,
    }


@tool("query_operating_conditions")
def query_operating_conditions(device_id: str, time_window: str = "last_30d") -> dict:
    """查设备近期工况分布（启停次数/负荷比例/环境），用于判断触发工况维度。

    Args:
        device_id: 设备 ID。
        time_window: 时间窗口，如 "last_30d"。
    """
    return query_operating_conditions_impl(device_id, time_window)
