from app.model_registry.validation_evidence import hash_artifact_file
from app.vision.ultralytics_detector import _resolve_detector_artifact, normalize_xyxy_box


def test_normalize_xyxy_box_clamps_to_original_image():
    box = normalize_xyxy_box([-10, 5, 120, 80], 100, 60)

    assert box == {"x": 0.0, "y": 5.0, "width": 100.0, "height": 55.0}


def test_normalize_xyxy_box_rejects_invalid_geometry():
    assert normalize_xyxy_box([5, 5, 5, 10], 100, 100) is None
    assert normalize_xyxy_box([float("nan"), 0, 10, 10], 100, 100) is None


def test_detector_rechecks_reviewed_weights_hash(tmp_path, monkeypatch):
    import app.vision.ultralytics_detector as detector

    weights = tmp_path / "fracture.pt"
    weights.write_bytes(b"reviewed")
    artifact = {
        "id": "local:test",
        "runtime_eligible": True,
        "task": "MSK fracture localization",
        "artifact_path": str(tmp_path),
        "card": {"validation_evidence": {"weights_filename": "fracture.pt", "artifact_hash": hash_artifact_file(weights)}},
    }
    monkeypatch.setattr(detector, "list_local_model_artifacts", lambda: [artifact])

    selected, issue = _resolve_detector_artifact("local:test")
    assert selected == weights
    assert issue == ""

    weights.write_bytes(b"changed-after-review")
    selected, issue = _resolve_detector_artifact("local:test")
    assert selected is None
    assert "hash no longer matches" in issue
