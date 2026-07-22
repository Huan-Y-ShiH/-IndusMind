"""波形特征提取工具，波形特征提取工具（占位，available=false）。

现状：尚未接入原始时序存储（OBS）+ ruptures/statsmodels 突变点检测（P2 优先级）。
当前返回确定性占位数据，字段结构与最终实现保持一致。接入后把本模块内部实现换成
真实读取 `raw_data_ref` + 趋势/突变点/周期性分析即可，工具签名不变。
"""
from __future__ import annotations

from crewai.tools import tool

_PLACEHOLDER_NOTE = "占位数据：尚未接入原始时序分析（ruptures/statsmodels），接入后替换本函数实现"


def extract_waveform_features_impl(raw_data_ref: str, feature_list: list[str]) -> dict:
    return {
        feature: {
            "trend_slope": None,
            "change_points": [],
            "periodicity_score": None,
            "noise_level": None,
            "shape_class": "unknown",
        }
        for feature in feature_list
    } | {
        "available": False,
        "reason": "WAVEFORM_BACKEND_NOT_CONNECTED",
        "_raw_data_ref": raw_data_ref,
        "_note": _PLACEHOLDER_NOTE,
    }


@tool("extract_waveform_features")
def extract_waveform_features(raw_data_ref: str, feature_list: list[str]) -> dict:
    """从原始时序提取趋势/突变/周期特征（不返回原始数据），用于区分渐变退化 vs 突发故障。

    Args:
        raw_data_ref: 原始数据的 OBS 引用（obs://...）。
        feature_list: 需要分析的传感器编号列表，如 ["s4", "s12"]。
    """
    return extract_waveform_features_impl(raw_data_ref, feature_list)
