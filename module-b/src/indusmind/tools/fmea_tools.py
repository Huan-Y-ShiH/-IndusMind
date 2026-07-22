"""FMEA 多级展开工具，FMEA 多级展开工具。"""
from __future__ import annotations

from crewai.tools import tool

from indusmind.knowledge import default_store


def expand_fmea_impl(device_model: str, failure_mode: str) -> dict:
    """从 FMEA 表展开 L1 → L2 子模式（纯函数版本，供测试/非 Agent 场景直接调用）。"""
    return default_store.expand_fmea(device_model, failure_mode)


@tool("expand_fmea")
def expand_fmea(device_model: str, failure_mode: str) -> dict:
    """从 FMEA 表展开 L1 失效模式为 L2 子模式（部位/典型征兆/严重度判据/维修动作）。

    Args:
        device_model: 设备型号，如 "CMAPSS-Turbofan"。
        failure_mode: 粗诊断给出的 L1 失效模式名称，如 "高压压气机叶片结垢"。
    """
    return expand_fmea_impl(device_model, failure_mode)
