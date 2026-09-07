from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app


def test_ai_sourced_annotation_can_be_reviewed_persisted_and_exported():
    case_id = "synthetic-ai-annotation-e2e"
    case_dir = get_settings().cases_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    image_path = case_dir / "synthetic-xray.png"
    Image.new("L", (256, 256), color=42).save(image_path)
    annotation = {
        "id": "ai-reviewed-1",
        "label": "AI candidate right lower-zone opacity",
        "confidence": 0.82,
        "source": "model-returned coordinate",
        "source_model": "codex-synthetic-annotation-fixture",
        "source_model_version": "2026-09-06",
        "coordinate": {"type": "bbox", "x": 140, "y": 140, "width": 70, "height": 60, "coordinate_space": "original_image"},
        "original_coordinate": {"type": "bbox", "x": 138, "y": 138, "width": 72, "height": 62, "coordinate_space": "original_image"},
        "explanation": "Synthetic AI-origin localization used only to exercise the complete annotation review path.",
        "visible": True,
        "review_status": "accepted",
        "reviewer_note": "Geometry checked on a synthetic image; no clinical claim.",
        "source_image_id": "synthetic-image-1",
        "source_image_index": 0,
        "source_frame_number": 0,
        "revision_history": [{"action": "reviewed", "actor": "test reviewer", "note": "Accepted synthetic localization."}],
    }
    case = {
        "case_id": case_id,
        "title": "Synthetic annotation validation",
        "image_path": str(image_path),
        "image_preview": str(image_path),
        "metadata": {"width": 256, "height": 256, "format": "PNG"},
        "images": [{"image_id": "synthetic-image-1", "index": 0, "image_path": str(image_path), "preview_path": str(image_path), "width": 256, "height": 256, "metadata": {}}],
        "active_image_id": "synthetic-image-1",
        "annotations": [annotation],
    }
    client = TestClient(app)
    saved = client.post("/api/cases", json=case)
    exported = client.post(f"/api/annotations/{case_id}/export-review-package")

    assert saved.status_code == 200
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["bundle"]["review_summary"] == {
        "ai_original_count": 1,
        "reviewed_count": 1,
        "manual_count": 0,
        "changed_count": 1,
        "review_status_counts": {"accepted": 1},
    }
    output = Path(payload["reviewed_png"])
    assert output.exists()
    with Image.open(output) as image:
        assert image.getpixel((140, 140)) != (42, 42, 42)
