import pytest

from app.medrax_adapter.interfaces import OutputNormalizer


def test_normalizer_requires_contract():
    with pytest.raises(ValueError):
        OutputNormalizer().normalize({"case_id": "x"})


def test_normalizer_sanitizes_warning_collection():
    payload = {
        "case_id": "case-1",
        "input": {},
        "image_quality": {},
        "findings": [],
        "annotations": [],
        "result_cards": [],
        "differential_diagnosis": [],
        "anatomy_route": {},
        "systematic_reading": {},
        "report": {},
        "model_trace": [],
        "warnings": ["check calibration", "check calibration", 42],
    }

    normalized = OutputNormalizer().normalize(payload)
    payload["warnings"] = "not-a-list"

    assert normalized["warnings"] == ["check calibration", "42"]
    assert OutputNormalizer().normalize(payload)["warnings"] == []
