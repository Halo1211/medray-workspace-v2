import json
from pathlib import Path

import pytest
from app.config import get_settings
from app.main import app
from app.model_finder import providers
from app.model_registry.validation_evidence import normalize_validation_evidence
from app.storage.db import save_case, save_runtime_config
from app.validation import workbench
from fastapi.testclient import TestClient

client = TestClient(app)


def local_artifact():
    path = get_settings().models_dir / "audit-model.onnx"
    path.write_bytes(b"synthetic weights")
    item = next(item for item in providers.list_local_model_artifacts() if Path(item["artifact_path"]) == path)
    return path, item["id"]


@pytest.mark.parametrize("task", ["vision", "chat", "report"])
def test_task_connection_cannot_bypass_local_review(task):
    _, model_id = local_artifact()
    result = client.post("/api/runtime", json={"task_connections": {task: {
        "backend": "openai-compatible", "base_url": "http://127.0.0.1:1234/v1", "model": model_id,
    }}})
    assert result.status_code == 400
    assert "human-reviewed" in result.text


@pytest.mark.parametrize("reference", ["task_id", "task_path", "slot_path"])
def test_cannot_remove_model_referenced_by_runtime(reference):
    path, model_id = local_artifact()
    if reference == "slot_path":
        config = {"classification_model": str(path)}
    else:
        config = {"task_connections": {"vision": {
            "backend": "openai-compatible", "base_url": "http://127.0.0.1:1234/v1",
            "model": model_id if reference == "task_id" else str(path),
        }}}
    save_runtime_config(config)
    result = client.post("/api/ai-setup/local/remove", json={"model_id": model_id})
    assert result.status_code == 409
    assert path.exists()


@pytest.mark.parametrize("reviewed", ["false", "true", 1, None])
def test_model_review_requires_explicit_boolean(reviewed):
    path, _ = local_artifact()
    result = client.post("/api/models/model-card", json={
        "artifact_path": str(path), "human_reviewed": reviewed,
        **{field: "synthetic fixture" for field in providers.REQUIRED_LOCAL_CARD_FIELDS},
    })
    assert result.status_code == 400
    assert not providers.list_local_model_artifacts()[0]["runtime_eligible"]


def test_malformed_stored_review_flag_does_not_enable_model():
    _, model_id = local_artifact()
    providers._local_card_path(model_id).write_text(json.dumps({
        "human_reviewed": "false",
        **{field: "synthetic fixture" for field in providers.REQUIRED_LOCAL_CARD_FIELDS},
    }), encoding="utf-8")
    assert not providers.list_local_model_artifacts()[0]["runtime_eligible"]
    assert providers.runtime_local_model_gate_issues({"classification_model": model_id})


def test_partial_download_segments_are_not_model_artifacts():
    path, _ = local_artifact()
    path.with_name(path.name + ".part.segment-0").write_bytes(b"partial")
    path.with_name(path.name + ".part.segment-1").write_bytes(b"partial")
    assert [item["name"] for item in providers.list_local_model_artifacts()] == [path.name]


def test_zero_validation_metrics_survive_normalization():
    result = normalize_validation_evidence({
        "metric_summary": {"agreement_rate": 0.0, "false_alert_count": 0},
        "false_alert_burden": {"false_alerts_per_case": 0.0},
        "missed_reference_summary": {"missed_reference_count": 0},
    })
    assert result["metric_summary"] == {"agreement_rate": 0.0, "false_alert_count": 0}
    assert result["false_alert_burden"] == {"false_alerts_per_case": 0.0}
    assert result["missed_reference_summary"] == {"missed_reference_count": 0}


def study_case():
    case = {
        "case_id": "validation-study", "active_image_id": "a",
        "images": [
            {"image_id": "a", "filename": "front.png", "sop_instance_uid": "uid-a"},
            {"image_id": "b", "filename": "side.png", "sop_instance_uid": "uid-b"},
        ],
        "analysis": {"findings": [{"label": "opacity", "status": "negative"}]},
        "analyses_by_image": {
            "a": {"findings": [{"label": "opacity", "status": "negative"}]},
            "b": {"findings": [{"label": "opacity", "status": "positive"}]},
        },
        "annotations": [{"id": "box-b", "source_image_id": "b", "label": "opacity",
                         "coordinate": {"type": "bbox", "x": 10, "y": 10, "width": 20, "height": 20}}],
    }
    save_case(case)
    return case


def test_validation_default_image_excludes_other_image_annotations():
    case = study_case()
    label = {"case_id": case["case_id"], "expected_annotations": [{"label": "opacity", "coordinate_type": "bbox"}]}
    result = workbench._case_result(label)
    assert result["annotation_checks"][0]["candidate_count"] == 0
    assert not result["annotation_checks"][0]["matched"]


@pytest.mark.parametrize("selector", [{"source_image_index": 1}, {"source_image_id": "side.png"}, {"source_image_id": "uid-b"}])
def test_validation_resolves_image_index_and_unique_alias(selector):
    case = study_case()
    result = workbench._case_result({"case_id": case["case_id"], **selector,
        "expected_findings": [{"label": "opacity", "status": "positive"}],
        "expected_annotations": [{"label": "opacity", "coordinate_type": "bbox"}],
    })
    assert result["status"] == "evaluated"
    assert result["source_image_id"] == "b"
    assert result["matches"][0]["matched"]
    assert result["annotation_checks"][0]["matched"]


@pytest.mark.parametrize("expectation", [
    {"coordinate": {"x": "NaN", "y": 0, "width": 10, "height": 10}},
    {"coordinate": {"x": 0, "y": 0, "width": "Infinity", "height": 10}},
    {"points": [["Infinity", 0]]},
    {"max_point_distance": "Infinity"},
])
def test_validation_rejects_nonfinite_reference_geometry(expectation):
    with pytest.raises(ValueError):
        workbench.save_validation_label({"case_id": "nonfinite", "expected_annotations": [{"label": "opacity", **expectation}]})
    assert not workbench.label_path("nonfinite").exists()


@pytest.mark.parametrize("coordinate", [
    {"type": "bbox", "x": "corrupt", "y": 10, "width": 20, "height": 20},
    {"type": "bbox", "x": 10, "y": 10, "width": 0, "height": 20},
    {"type": "bbox", "x": float("inf"), "y": 10, "width": 20, "height": 20},
])
def test_invalid_legacy_geometry_cannot_crash_or_match_validation(coordinate):
    case = {"annotations": [{"label": "opacity", "coordinate": coordinate}]}
    result = workbench._annotation_result({"expected_annotations": [{
        "label": "opacity", "coordinate_type": "bbox", "min_iou": 0,
        "coordinate": {"x": 10, "y": 10, "width": 20, "height": 20},
    }]}, case)[0]
    assert not result["matched"]
    assert result["valid_geometry_count"] == 0
    assert result["best_iou"] == 0


@pytest.mark.parametrize("content", ["broken JSON", "[]", "null"])
def test_valid_label_can_replace_corrupt_stored_label(content):
    path = workbench.label_path("repair-label")
    path.write_text(content, encoding="utf-8")
    result = workbench.save_validation_label({"case_id": "repair-label", "reviewer": "test reviewer"})
    assert result["label"]["reviewer"] == "test reviewer"
    assert not workbench.list_validation_labels()[0].get("invalid")


def reviewed_artifact():
    path, model_id = local_artifact()
    providers.save_local_model_card({"artifact_path": str(path), "human_reviewed": True,
        **{field: "synthetic fixture" for field in providers.REQUIRED_LOCAL_CARD_FIELDS}})
    return path, model_id


@pytest.mark.parametrize("reference", ["id", "path", "windows_case"])
def test_reviewed_model_task_connection_is_allowed(reference):
    path, model_id = reviewed_artifact()
    value = model_id if reference == "id" else str(path)
    if reference == "windows_case":
        import os
        if os.name != "nt":
            pytest.skip("Case-insensitive model paths are specific to Windows")
        value = str(path).upper()
    assert providers.runtime_local_model_gate_issues({"task_connections": {"vision": {"model": value}}}) == []


def test_inactive_model_can_still_be_archived():
    path, model_id = local_artifact()
    result = client.post("/api/ai-setup/local/remove", json={"model_id": model_id})
    assert result.status_code == 200
    assert not path.exists()
    assert len(list((get_settings().models_dir / ".removed").iterdir())) == 1


def test_invalid_reference_cannot_replace_existing_label():
    original = workbench.save_validation_label({"case_id": "keep-label", "reviewer": "original"})
    path = Path(original["path"])
    previous = path.read_bytes()
    result = client.post("/api/validation/labels", json={"case_id": "keep-label",
        "expected_annotations": [{"label": "opacity", "points": [["NaN", 10]]}]})
    assert result.status_code == 400
    assert path.read_bytes() == previous


def test_validation_does_not_guess_ambiguous_filename_alias():
    case = study_case()
    case["images"][0]["filename"] = "side.png"
    save_case(case)
    result = workbench._case_result({"case_id": case["case_id"], "source_image_id": "side.png"})
    assert result["status"] == "skipped_no_analysis"


def test_validation_canonical_identity_wins_over_alias():
    case = study_case()
    case["images"][1]["sop_instance_uid"] = "a"
    case["annotations"][0]["source_image_id"] = "a"
    save_case(case)
    result = workbench._case_result({"case_id": case["case_id"], "source_image_id": "b",
        "expected_annotations": [{"label": "opacity", "coordinate_type": "bbox"}]})
    assert result["annotation_checks"][0]["candidate_count"] == 0


def test_validation_matches_unique_legacy_annotation_alias():
    case = study_case()
    case["annotations"][0]["source_image_id"] = "side.png"
    save_case(case)
    result = workbench._case_result({"case_id": case["case_id"], "source_image_id": "b",
        "expected_annotations": [{"label": "opacity", "coordinate_type": "bbox"}]})
    assert result["annotation_checks"][0]["matched"]


def test_legacy_single_image_analysis_remains_evaluable():
    save_case({"case_id": "legacy-single", "images": [{"image_id": "single"}],
        "analysis": {"findings": [{"label": "opacity", "status": "negative"}]}})
    result = workbench._case_result({"case_id": "legacy-single",
        "expected_findings": [{"label": "opacity", "status": "negative"}]})
    assert result["status"] == "evaluated"
    assert result["source_image_id"] == "single"
    assert result["matches"][0]["matched"]


def test_model_listing_skips_paths_resolving_outside_model_root(monkeypatch, tmp_path):
    path, _ = local_artifact()
    resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda self, *args, **kwargs:
        tmp_path / "outside.onnx" if self == path else resolve(self, *args, **kwargs))
    assert providers.list_local_model_artifacts() == []


def test_automatic_weights_selection_checks_resolved_boundary(monkeypatch, tmp_path):
    from app.model_registry import validation_evidence
    root = get_settings().models_dir / "folder-model"
    root.mkdir()
    weights = root / "model.onnx"
    weights.write_bytes(b"fixture")
    resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda self, *args, **kwargs:
        tmp_path / "outside.onnx" if self == weights else resolve(self, *args, **kwargs))
    calls = []
    monkeypatch.setattr(validation_evidence, "hash_artifact_file", lambda selected: calls.append(selected) or "0" * 64)
    with pytest.raises(ValueError, match="inside"):
        validation_evidence.bind_artifact_identity({}, root)
    assert not calls
