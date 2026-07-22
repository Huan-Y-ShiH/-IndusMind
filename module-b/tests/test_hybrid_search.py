import pytest

from indusmind.rag import HybridSearch


@pytest.fixture()
def search() -> HybridSearch:
    # 不配置 dataset_id，强制走本地 FMEA 兜底路径（不依赖网络/Dify 凭据）
    return HybridSearch(cases_dataset_id="", manuals_dataset_id="")


@pytest.mark.asyncio
async def test_hybrid_search_falls_back_to_local_fmea(search: HybridSearch):
    query = {
        "device_id": "engine-CMAPSS-001",
        "device_model": "CMAPSS-Turbofan",
        "anomaly_type": "trend_anomaly",
        "top_features": ["s3", "s4", "s12", "s9"],
        "symptoms": [
            {"feature": "s3", "direction": "high"},
            {"feature": "s4", "direction": "high"},
            {"feature": "s12", "direction": "high"},
            {"feature": "s9", "direction": "high"},
        ],
        "symptom_text": "s3(↑), s4(↑), s12(↑), s9(↑)",
        "natural_language": "设备 engine-CMAPSS-001 发生 trend_anomaly, 主要征兆: s3(↑), s4(↑), s12(↑), s9(↑)",
    }
    results = await search.hybrid_search(query)
    assert results
    assert {r["source"] for r in results} <= {"fmea", "local_case_library"}
    assert results[0]["score"] >= results[-1]["score"]


@pytest.mark.asyncio
async def test_hybrid_search_without_device_model_returns_empty(search: HybridSearch):
    query = {
        "device_id": "unknown-device",
        "device_model": None,
        "anomaly_type": "trend_anomaly",
        "top_features": ["s3"],
        "symptoms": [{"feature": "s3", "direction": "high"}],
        "symptom_text": "s3(↑)",
        "natural_language": "设备 unknown-device 发生 trend_anomaly",
    }
    results = await search.hybrid_search(query)
    assert results == []
