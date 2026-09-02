from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app
from app.storage.db import save_case


def test_health():
    res = TestClient(app).get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_image_endpoint_only_serves_medray_images():
    settings = get_settings()
    image_dir = settings.cases_dir / "endpoint-test"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / "preview.png"
    Image.new("RGB", (4, 4), color="black").save(image_path)

    client = TestClient(app)
    allowed = client.get("/api/image", params={"path": str(image_path)})
    blocked = client.get("/api/image", params={"path": __file__})

    assert allowed.status_code == 200
    assert blocked.status_code == 404


def test_annotation_export_endpoint_falls_back_to_analysis_annotations():
    settings = get_settings()
    image_dir = settings.cases_dir / "endpoint-export-fallback"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / "image.png"
    Image.new("RGB", (20, 20), color="black").save(image_path)
    save_case(
        {
            "case_id": "endpoint-export-fallback",
            "title": "Export fallback",
            "image_path": str(image_path),
            "annotations": [],
            "analysis": {
                "annotations": [
                    {
                        "id": "ann-analysis",
                        "label": "analysis fallback box",
                        "confidence": 0.4,
                        "source": "model-returned coordinate",
                        "coordinate": {"type": "bbox", "x": 2, "y": 2, "width": 8, "height": 8},
                    }
                ]
            },
        }
    )

    response = TestClient(app).post("/api/annotations/endpoint-export-fallback/export")

    assert response.status_code == 200
    assert response.json()["path"].endswith("annotated_reviewed.png")


def test_save_case_requires_case_id():
    response = TestClient(app).post("/api/cases", json={"title": "No case id"})

    assert response.status_code == 400


def test_save_case_rejects_image_paths_outside_cases_directory():
    response = TestClient(app).post(
        "/api/cases",
        json={"case_id": "unsafe-path-case", "image_path": __file__},
    )

    assert response.status_code == 400
    assert "outside the local cases directory" in response.json()["detail"]


def test_upload_uses_manual_case_title_and_delete_endpoint():
    from io import BytesIO

    image_buffer = BytesIO()
    Image.new("RGB", (4, 4), color="black").save(image_buffer, format="PNG")
    image_buffer.seek(0)
    response = TestClient(app).post(
        "/api/upload",
        files={"file": ("patient-name.png", image_buffer, "image/png")},
        data={"case_title": "NPM-123 / Patient A"},
    )
    assert response.status_code == 200
    assert response.json()["case"]["title"] == "NPM-123 / Patient A"

    default_image = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(default_image, format="PNG")
    default_image.seek(0)
    default_response = TestClient(app).post(
        "/api/upload",
        files={"file": ("source-filename.png", default_image, "image/png")},
    )
    assert default_response.status_code == 200
    assert default_response.json()["case"]["title"] == "New X-ray case"


def test_case_delete_and_clear_endpoints():
    save_case({"case_id": "delete-endpoint-case", "title": "Delete endpoint"})
    client = TestClient(app)
    deleted = client.delete("/api/cases/delete-endpoint-case")
    assert deleted.status_code == 200
    assert client.get("/api/cases/delete-endpoint-case").status_code == 404

    save_case({"case_id": "clear-endpoint-case", "title": "Clear endpoint"})
    cleared = client.delete("/api/cases")
    assert cleared.status_code == 200
    assert cleared.json()["deleted_case_count"] >= 1


def test_chat_tolerates_malformed_history_and_empty_message():
    save_case(
        {
            "case_id": "chat-malformed-history",
            "title": "Chat malformed history",
            "chat_history": [{"content": "missing role"}, {"role": "assistant"}],
            "annotations": [{"id": "ann-1"}],
            "analysis": {"report": {}, "annotations": []},
        }
    )

    response = TestClient(app).post("/api/chat/chat-malformed-history", json={"message": None})

    assert response.status_code == 200
    assert response.json()["message"]["role"] == "assistant"


def test_chat_replaces_malformed_history_collection():
    save_case(
        {
            "case_id": "chat-malformed-history-collection",
            "title": "Chat malformed history collection",
            "chat_history": "legacy-corrupt-history",
            "analysis": {},
        }
    )

    response = TestClient(app).post(
        "/api/chat/chat-malformed-history-collection", json={"message": "Review this case"}
    )

    assert response.status_code == 200
    assert [item["role"] for item in response.json()["history"]] == ["user", "assistant"]
