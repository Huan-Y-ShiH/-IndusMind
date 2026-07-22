import pytest

from indusmind.knowledge import default_store
from indusmind.knowledge.store import jaccard, parse_symptom_signature


def test_parse_symptom_signature():
    assert parse_symptom_signature("s3↑;s4↑;s12↑") == [
        ("s3", "high"),
        ("s4", "high"),
        ("s12", "high"),
    ]
    assert parse_symptom_signature("s10↓") == [("s10", "low")]


def test_jaccard():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a", "b"}, {"a", "c"}) == pytest.approx(1 / 3)
    assert jaccard(set(), {"a"}) == 0.0


def test_fmea_rows_loaded():
    rows = default_store.fmea_rows()
    assert len(rows) > 0
    assert {"device_model", "failure_mode", "symptom_signature"} <= rows[0].keys()


def test_match_fmea_by_symptoms_returns_ranked_candidates():
    symptoms = [
        {"feature": "s3", "direction": "high"},
        {"feature": "s4", "direction": "high"},
        {"feature": "s12", "direction": "high"},
        {"feature": "s9", "direction": "high"},
    ]
    matches = default_store.match_fmea_by_symptoms("CMAPSS-Turbofan", symptoms)
    assert matches
    assert matches[0]["match_score"] >= matches[-1]["match_score"]
    assert matches[0]["direction_aware"] is True


def test_match_fmea_force_best_returns_row_even_without_overlap():
    matches = default_store.match_fmea_by_symptoms(
        "CMAPSS-Turbofan",
        [{"feature": "s999", "direction": "high"}],
        force_best=True,
    )
    assert matches
    assert matches[0]["failure_mode"]
    assert matches[0]["forced_best"] is True


def test_match_fmea_penalizes_opposite_direction():
    high = default_store.match_fmea_by_symptoms(
        "CFM56-7B", [{"feature": "s10", "direction": "high"}], top_k=10
    )
    low = default_store.match_fmea_by_symptoms(
        "CFM56-7B", [{"feature": "s10", "direction": "low"}], top_k=10
    )
    assert not any(row["failure_mode"] == "压气机叶片结垢" for row in high)
    assert any(row["failure_mode"] == "压气机叶片结垢" for row in low)


def test_expand_fmea_known_failure_mode():
    result = default_store.expand_fmea("CMAPSS-Turbofan", "高压压气机叶片结垢")
    sub_modes = {m["sub_mode"] for m in result["sub_modes"]}
    assert "静子叶片结垢" in sub_modes


def test_expand_fmea_unknown_failure_mode_returns_empty():
    result = default_store.expand_fmea("CMAPSS-Turbofan", "不存在的失效模式")
    assert result["sub_modes"] == []


def test_expand_fmea_rejects_cross_model_expansion():
    result = default_store.expand_fmea("CFM56-7B", "高压压气机叶片结垢")
    assert result["sub_modes"] == []


def test_describe_feature():
    assert "总温" in default_store.describe_feature("s3") or "T30" in default_store.describe_feature("s3")
