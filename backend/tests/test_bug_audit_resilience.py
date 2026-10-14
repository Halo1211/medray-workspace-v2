import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.ai_setup import service
from app.ai_setup.catalog import TXRV_ID, classifier_recipe, weights_path
from app.config import get_settings
from app.main import app
from app.model_finder import providers
from app.model_registry.validation_evidence import normalize_validation_evidence
from app.storage.db import load_runtime_config, save_case, upsert_json
from app.validation import workbench
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize("reviewed", [False, True])
def test_valid_model_folder_import_is_accepted(reviewed):
    folder = get_settings().models_dir / "synthetic-folder"
    folder.mkdir()
    (folder / "config.json").write_text("{}", encoding="utf-8")
    if reviewed:
        providers.save_local_model_card({"artifact_path": str(folder), "human_reviewed": True,
            **{field: "synthetic fixture" for field in providers.REQUIRED_LOCAL_CARD_FIELDS}})
    result = client.post("/api/models/import", json={"path": str(folder)})
    assert result.status_code == 200
    assert result.json()["model"]["status"] == "installed"
    assert result.json()["validation"]["runtime_eligible"] is reviewed


@pytest.mark.parametrize("previous_weights", [None, b"corrupt old weights"])
def test_classifier_setup_reuses_completed_job_when_weights_missing_or_corrupt(monkeypatch, previous_weights):
    manager = providers.DownloadManager()
    monkeypatch.setattr(service, "download_manager", manager)
    monkeypatch.setattr(service, "dependencies", lambda: [])
    content = b"verified synthetic weights"
    recipe = {**classifier_recipe(TXRV_ID), "sha256": hashlib.sha256(content).hexdigest()}
    monkeypatch.setattr(service, "classifier_recipe", lambda _: recipe)
    target = weights_path()
    if previous_weights is not None:
        target.write_bytes(previous_weights)
    job = {"id": "previous-completed-job", "url": recipe["url"], "target_path": str(target),
        "partial_path": str(target.with_suffix(".pt.part")), "status": "completed", "bytes_read": 100, "percent": 100}
    manager.jobs[job["id"]] = job
    upsert_json("downloads", job["id"], job)
    downloads = []
    def complete(job_id):
        current = manager.jobs[job_id]
        downloads.append(current["target_path"])
        Path(current["target_path"]).write_bytes(content)
        current.update(status="completed", percent=100)
        manager._persist(current)
    monkeypatch.setattr(manager, "_start_worker", complete)
    service._setup("download")
    assert service.read_state()["status"] == "needs_setup"
    assert target.read_bytes() == content
    assert downloads == [str(target)]
    assert service.read_state()["download_id"] == job["id"]


def test_retry_completed_download_does_not_overwrite_existing_weights(monkeypatch):
    manager = providers.DownloadManager()
    target = get_settings().models_dir / "keep.onnx"
    target.write_bytes(b"existing weights")
    manager.jobs["completed"] = {"id": "completed", "status": "completed", "target_path": str(target)}
    calls = []
    monkeypatch.setattr(manager, "_start_worker", lambda _: calls.append(True))
    assert manager.retry("completed")["status"] == "completed"
    assert target.read_bytes() == b"existing weights"
    assert not calls


def test_download_only_rejects_corrupt_new_classifier_weights(monkeypatch):
    def download(*args, **kwargs):
        weights_path().write_bytes(b"corrupt newly downloaded weights")
        return {"id": "new-download", "status": "completed"}
    monkeypatch.setattr(service, "download_manager", SimpleNamespace(list=lambda: [], start=download))
    service._setup("download")
    state = service.read_state()
    assert state["status"] == "error"
    assert "integrity" in state["detail"].lower()
    assert not state["passed"]


def test_nonzero_node_process_exit_never_reports_ready(monkeypatch):
    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs:
        SimpleNamespace(returncode=1, stdout="v24.0.0", stderr="synthetic failure"))
    node = next(item for item in service.system_check()["checks"] if item["name"] == "Node")
    assert node["status"] != "ready"


@pytest.mark.parametrize("value", [[], {}, {"secret": "private_fixture"}])
def test_malformed_review_depth_is_rejected_without_server_failure(value):
    before = load_runtime_config({})
    result = client.post("/api/ai-setup/preferences", json={"review_depth": value})
    assert result.status_code == 400
    assert "private_fixture" not in result.text
    assert load_runtime_config({}) == before


@pytest.mark.parametrize("value", [True, 1.5, float("inf"), float("nan")])
def test_validation_evidence_counts_reject_noninteger_or_nonfinite_values(value):
    evidence = normalize_validation_evidence({"case_count": value, "label_count": value})
    assert evidence["case_count"] is None
    assert evidence["label_count"] is None


def test_polygon_with_corrupt_vertex_is_not_a_validation_hit():
    case = {"annotations": [{"label": "opacity", "coordinate": {
        "type": "polygon", "points": [[0, 0], [10, 0], [10, 10], ["corrupt", 5]],
    }}]}
    result = workbench._annotation_result({"expected_annotations": [{"label": "opacity", "coordinate_type": "polygon"}]}, case)[0]
    assert not result["matched"]
    assert result["valid_geometry_count"] == 0


def test_point_distance_overflow_does_not_break_validation_api():
    save_case({"case_id": "extreme-point", "analysis": {"findings": []}, "annotations": [{
        "label": "opacity", "coordinate": {"type": "point", "x": 1e308, "y": 0},
    }]})
    workbench.save_validation_label({"case_id": "extreme-point", "expected_annotations": [{
        "label": "opacity", "coordinate_type": "point", "points": [[-1e308, 0]],
    }]})
    result = client.post("/api/validation/run", json={"case_ids": ["extreme-point"], "export": True})
    assert result.status_code == 200
    check = result.json()["results"][0]["annotation_checks"][0]
    assert not check["matched"]
    assert check["best_point_distance"] is None
    exported = Path(result.json()["export_path"]).read_text(encoding="utf-8")
    def reject_nonfinite(value):
        raise ValueError(f"Nonstandard JSON number: {value}")
    json.loads(exported, parse_constant=reject_nonfinite)


def test_box_missing_origin_does_not_match_at_zero():
    case = {"annotations": [{"label": "opacity", "coordinate": {"type": "bbox", "width": 10, "height": 10}}]}
    result = workbench._annotation_result({"expected_annotations": [{"label": "opacity", "coordinate_type": "bbox",
        "coordinate": {"x": 0, "y": 0, "width": 10, "height": 10}}]}, case)[0]
    assert not result["matched"]
    assert result["valid_geometry_count"] == 0


@pytest.mark.parametrize("content", ["[]", "null", '"text"'])
def test_model_worker_nonobject_output_has_actionable_error(monkeypatch, content):
    monkeypatch.setattr(service, "_run_command", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=content))
    with pytest.raises(RuntimeError, match="valid output"):
        service.test_xray()


@pytest.mark.parametrize("value", [0, 12, 12.0, "12"])
def test_valid_validation_counts_remain_supported(value):
    assert normalize_validation_evidence({"case_count": value})["case_count"] == int(value)
