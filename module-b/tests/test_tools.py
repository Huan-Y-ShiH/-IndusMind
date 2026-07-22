from indusmind.tools import (
    expand_fmea_impl,
    query_maintenance_history_impl,
    query_operating_conditions_impl,
    extract_waveform_features_impl,
    rag_refined_search_impl,
)


def test_expand_fmea_impl():
    result = expand_fmea_impl("CMAPSS-Turbofan", "高压压气机叶片结垢")
    assert result["sub_modes"]
    assert result["sub_modes"][0]["maintenance_action"]


def test_query_maintenance_history_impl_known_device():
    result = query_maintenance_history_impl("engine-CMAPSS-001", "压气机退化")
    assert result["recurrence_count"] >= 1
    assert result["last_maintenance"]["outcome"] == "resolved"


def test_query_maintenance_history_impl_unknown_device():
    result = query_maintenance_history_impl("no-such-device", "压气机退化")
    assert result["recurrence_count"] == 0


def test_query_operating_conditions_impl_is_placeholder():
    result = query_operating_conditions_impl("engine-CMAPSS-001")
    assert "note" in result


def test_extract_waveform_features_impl_is_placeholder():
    result = extract_waveform_features_impl("obs://x", ["s3", "s4"])
    assert set(result.keys()) >= {"s3", "s4"}


def test_rag_refined_search_impl_confirms_matching_case():
    result = rag_refined_search_impl(
        "CMAPSS-Turbofan", "HPC 效率主导退化", ["s3↑", "s4↑", "s12↑", "s9↑"]
    )
    assert result["matched_cases"]
    assert result["matched_cases"][0]["confirmed_hypothesis"] is True
