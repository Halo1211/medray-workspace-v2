from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.studies.images import normalize_case_images


def test_normalize_legacy_image_tolerates_malformed_file_hashes():
    case = normalize_case_images(
        {
            "case_id": "legacy-malformed-hashes",
            "image_path": "legacy.png",
            "metadata": "not-a-mapping",
            "file_hashes": "not-a-mapping",
        }
    )

    assert case["images"][0]["source_path"] is None
    assert case["images"][0]["metadata"] == {}
    assert case["file_hashes"] == {}


def _png_bytes(color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (12, 10), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_legacy_case_is_normalized_to_single_study_image():
    case = normalize_case_images(
        {
            "case_id": "legacy-study",
            "title": "legacy.png",
            "image_path": "legacy.png",
            "image_preview": "legacy.preview.png",
            "metadata": {"ViewPosition": "PA", "SeriesInstanceUID": "series-1"},
        }
    )

    assert len(case["images"]) == 1
    assert case["active_image_id"] == "legacy-study:0"
    assert case["images"][0]["view"] == "PA"
    assert case["images"][0]["series_id"] == "series-1"


def test_upload_add_and_switch_multi_image_study():
    client = TestClient(app)
    uploaded = client.post("/api/upload", files={"file": ("ap.png", _png_bytes("black"), "image/png")})
    assert uploaded.status_code == 200
    case = uploaded.json()["case"]
    first_id = case["active_image_id"]

    appended = client.post(
        f"/api/cases/{case['case_id']}/images",
        files={"file": ("lateral.png", _png_bytes("white"), "image/png")},
    )
    assert appended.status_code == 200
    multi_case = appended.json()["case"]
    assert len(multi_case["images"]) == 2
    assert multi_case["active_image_id"] == first_id

    second = multi_case["images"][1]
    switched = client.post(f"/api/cases/{case['case_id']}/active-image", json={"image_id": second["image_id"]})
    assert switched.status_code == 200
    switched_case = switched.json()
    assert switched_case["active_image_id"] == second["image_id"]
    assert switched_case["image_path"] == second["image_path"]
    assert switched_case["analysis"] is None


def test_active_image_switch_restores_per_image_analysis():
    case = normalize_case_images(
        {
            "case_id": "analysis-study",
            "images": [
                {"image_id": "image-a", "image_path": "a.png", "preview_path": "a.preview.png", "metadata": {}},
                {"image_id": "image-b", "image_path": "b.png", "preview_path": "b.preview.png", "metadata": {}},
            ],
            "active_image_id": "image-b",
            "analyses_by_image": {"image-a": {"case_id": "analysis-study", "report": {"findings": "A"}}, "image-b": {"case_id": "analysis-study", "report": {"findings": "B"}}},
        }
    )

    assert case["analysis"]["report"]["findings"] == "B"
    assert case["report"]["findings"] == "B"


def test_malformed_images_fall_back_to_legacy_top_level_image():
    case = normalize_case_images(
        {
            "case_id": "malformed-images",
            "images": ["not-an-image", None],
            "image_path": "legacy.png",
            "metadata": {"ViewPosition": "AP"},
            "analyses_by_image": {"malformed-images:0": "not-an-analysis"},
        }
    )

    assert len(case["images"]) == 1
    assert case["images"][0]["image_id"] == "malformed-images:0"
    assert case["images"][0]["view"] == "AP"
    assert case["analyses_by_image"] == {}


def test_legacy_active_analysis_survives_orphan_per_image_mapping():
    case = normalize_case_images(
        {
            "case_id": "orphan-analysis",
            "images": [
                {"image_id": "image-a", "image_path": "a.png", "metadata": {}},
                {"image_id": "image-b", "image_path": "b.png", "metadata": {}},
            ],
            "active_image_id": "deleted-image",
            "analysis": {"case_id": "orphan-analysis", "report": {"findings": "legacy active"}},
            "analyses_by_image": {
                "deleted-image": {"case_id": "orphan-analysis", "report": {"findings": "orphan"}},
                "": {"case_id": "orphan-analysis", "report": {"findings": "empty key"}},
            },
        }
    )

    assert case["active_image_id"] == "image-a"
    assert set(case["analyses_by_image"]) == {"image-a"}
    assert case["analysis"]["report"]["findings"] == "legacy active"
