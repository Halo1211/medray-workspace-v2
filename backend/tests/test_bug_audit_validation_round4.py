"""Validation and audit regressions with isolated, synthetic case data."""
import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.audit.bundle import build_audit_bundle
from app.main import app
from app.storage.db import save_case
from app.validation import workbench


client = TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("scale", [1e200, 1e-200])
@pytest.mark.parametrize("offset, expected", [(0, 1), (0.5, 1 / 7)])
def test_box_iou_is_stable_for_large_and_small_finite_boxes(scale, offset, expected):
    first = {"x": 0, "y": 0, "width": scale, "height": scale}
    second = {**first, "x": offset * scale, "y": offset * scale}
    actual = workbench._bbox_iou(first, second)
    assert math.isfinite(actual)
    assert actual == pytest.approx(expected)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf"), "nan", "not-a-score"])
def test_invalid_legacy_quality_scores_do_not_break_validation_json(score):
    save_case({"case_id": "quality", "analysis": {"image_quality": {"score": score}}})
    workbench.save_validation_label({"case_id": "quality"})
    response = client.post("/api/validation/run", json={"export": True})
    assert response.status_code == 200
    quality = response.json()["results"][0]["image_quality"]
    assert quality["predicted"] == "unknown"
    assert quality["predicted_score"] is None
    json.loads(Path(response.json()["export_path"]).read_text(), parse_constant=lambda value: pytest.fail(f"Nonstandard JSON number {value}"))


@pytest.mark.parametrize("case_ids", ["case", 42, {}, [None], [True], [[]]])
def test_run_rejects_invalid_case_selection(case_ids):
    response = client.post("/api/validation/run", json={"case_ids": case_ids})
    assert response.status_code == 400


@pytest.mark.parametrize("export", ["false", 1, {}, []])
def test_run_export_flag_must_be_boolean(export):
    response = client.post("/api/validation/run", json={"export": export})
    assert response.status_code == 400


def test_explicit_empty_selection_does_not_evaluate_all_labels():
    workbench.save_validation_label({"case_id": "unselected"})
    response = client.post("/api/validation/run", json={"case_ids": []})
    assert response.status_code == 200
    assert response.json()["metrics"]["label_count"] == 0
    assert workbench.run_validation([])["metrics"]["label_count"] == 0


@pytest.mark.parametrize("case_id", ["", "  "])
def test_empty_reference_case_identity_is_rejected(case_id):
    response = client.post("/api/validation/labels", json={"case_id": case_id})
    assert response.status_code == 400
    assert workbench.list_validation_labels() == []


def test_reference_box_cannot_overflow_its_endpoint():
    response = client.post("/api/validation/labels", json={"case_id": "overflow", "expected_annotations": [{
        "label": "synthetic", "coordinate_type": "bbox", "coordinate": {"x": 1e308, "y": 0, "width": 1e308, "height": 1},
    }]})
    assert response.status_code == 400


def test_failed_label_write_preserves_the_previous_reference(monkeypatch):
    workbench.save_validation_label({"case_id": "reference", "title": "Previous reference"})
    original_write = Path.write_text
    def fail_write(path, text, *args, **kwargs):
        original_write(path, text[:12], *args, **kwargs)
        raise OSError("Synthetic interrupted write")
    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError):
        workbench.save_validation_label({"case_id": "reference", "title": "Replacement"})
    stored = json.loads(workbench.label_path("reference").read_text())
    assert stored["title"] == "Previous reference"
    assert len(list(workbench.label_path("reference").parent.iterdir())) == 1


@pytest.mark.parametrize("kind", ["card", "body", "quality"])
def test_evaluated_mismatches_are_listed_as_failures(kind):
    analysis = {
        "findings": [{"label": "synthetic", "status": "positive"}],
        "result_cards": [{"finding": "synthetic", "status": "negative" if kind == "card" else "positive"}],
        "systematic_reading": {"body_region": "Wrong region" if kind == "body" else "Chest X-ray"},
        "image_quality": {"score": 0.1 if kind == "quality" else 0.8},
    }
    save_case({"case_id": kind, "analysis": analysis})
    workbench.save_validation_label({"case_id": kind, "expected_body_region": "Chest X-ray",
        "expected_findings": [{"label": "synthetic", "status": "positive"}],
        "expected_image_quality": {"diagnostic_quality": "adequate"},
    })
    result = workbench.run_validation()
    assert [item["case_id"] for item in result["failure_cases"]] == [kind]
    assert not any("No failures observed" in message for message in result["model_card_evidence_draft"]["known_failures"])


def test_audit_counts_every_result_card_under_its_normalized_review_status():
    cards = [{"id": str(index), "finding": "synthetic", **values} for index, values in enumerate([
        {}, {"review_status": None}, {"review_status": ""}, {"review_status": "unreviewed"}, {"review_status": "accepted"},
    ])]
    counts = build_audit_bundle({"case_id": "counts", "analysis": {"result_cards": cards}})["output_summary"]["result_card_review_status_counts"]
    assert counts == {"accepted": 1, "unreviewed": 4}
    assert sum(counts.values()) == len(cards)


def test_agreeing_case_is_not_reported_as_a_failure():
    save_case({"case_id": "agreement", "analysis": {"systematic_reading": {"body_region": "Chest X-ray"}, "image_quality": {"score": 0.8}}})
    workbench.save_validation_label({"case_id": "agreement", "expected_body_region": "Chest X-ray", "expected_image_quality": {"diagnostic_quality": "adequate"}})
    result = workbench.run_validation()
    assert result["metrics"]["evaluated_cases"] == 1
    assert result["failure_cases"] == []
    assert any("No failures observed" in message for message in result["model_card_evidence_draft"]["known_failures"])
