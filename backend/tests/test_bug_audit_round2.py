import io
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.annotations.exporter import export_annotated_png
from app.audit.bundle import build_audit_bundle
from app.main import app
from app.models.schemas import Coordinate
from app.services.image_service import ingest_upload
from app.storage.db import get_case


client = TestClient(app, raise_server_exceptions=False)


def png():
    stream = io.BytesIO()
    Image.new("RGB", (32, 32), "black").save(stream, format="PNG")
    return stream.getvalue()


def case():
    return client.post("/api/upload", files={"file": ("synthetic.png", png(), "image/png")}).json()["case"]


@pytest.mark.parametrize("coordinate", [
    {"type": "bbox", "x": "NaN", "y": 1, "width": 10, "height": 10},
    {"type": "grounding_box", "x": 1, "y": 1, "width": "Infinity", "height": 10},
    {"type": "bbox", "x": 1, "y": 1, "width": -1, "height": 10},
    {"type": "polygon", "points": [[0, 0], [1e308, 0], [0, 1e308]]},
])
def test_coordinate_rejects_invalid_boxes_and_overflow_area(coordinate):
    with pytest.raises(ValidationError):
        Coordinate(**coordinate)


@pytest.mark.parametrize("coordinate", [
    {"type": "point", "x": "NaN", "y": 1},
    {"type": "polygon", "points": None},
    {"type": "bbox", "x": 1, "y": 1, "width": -1, "height": 10},
])
@pytest.mark.parametrize("collection", ["annotations", "analysis", "analyses_by_image"])
def test_case_api_rejects_invalid_geometry_without_replacing_saved_case(coordinate, collection):
    original = case()
    annotation = {"id": "invalid", "label": "synthetic", "confidence": 1, "source": "manual user annotation", "explanation": "test", "coordinate": coordinate}
    payload = {**original}
    if collection == "annotations":
        payload[collection] = [annotation]
    elif collection == "analysis":
        payload[collection] = {"annotations": [annotation]}
    else:
        payload[collection] = {original["active_image_id"]: {"annotations": [annotation]}}
    result = client.post("/api/cases", json=payload, headers={"If-Match": str(original["revision"])})
    assert result.status_code == 400
    assert get_case(original["case_id"]) == original


@pytest.mark.parametrize("field,value", [("case_id", []), ("case_id", 123), ("title", None), ("title", {})])
def test_case_api_rejects_invalid_identity_and_title(field, value):
    original = case()
    result = client.post("/api/cases", json={**original, field: value})
    assert result.status_code == 400
    assert get_case(original["case_id"]) == original


def test_same_filename_concurrent_ingest_never_overwrites_source(monkeypatch):
    from app.config import get_settings

    target = get_settings().cases_dir / "concurrent" / "same.png"
    barrier = threading.Barrier(2)
    local = threading.local()
    exists = Path.exists

    def synchronized_exists(path):
        result = exists(path)
        if path == target and not getattr(local, "checked", False):
            local.checked = True
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(Path, "exists", synchronized_exists)
    def upload(_):
        return ingest_upload(SimpleNamespace(filename="same.png", file=io.BytesIO(png())), case_id="concurrent")
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(upload, range(2)))
    assert len({item["source_path"] for item in results}) == 2
    assert len({item["preview_path"] for item in results}) == 2
    assert all(Path(item["source_path"]).read_bytes() == png() for item in results)


def test_concurrent_upload_cannot_take_another_images_pending_preview(monkeypatch):
    from app.services import image_service

    preview_started = threading.Event()
    second_finished = threading.Event()
    preview = image_service._image_preview
    def delayed_preview(path, *args, **kwargs):
        if path.name == "image.png":
            preview_started.set()
            assert second_finished.wait(timeout=5)
        return preview(path, *args, **kwargs)
    monkeypatch.setattr(image_service, "_image_preview", delayed_preview)
    white = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(white, format="PNG")
    with ThreadPoolExecutor(max_workers=1) as workers:
        first = workers.submit(ingest_upload, SimpleNamespace(filename="image.png", file=io.BytesIO(png())), "preview-race")
        assert preview_started.wait(timeout=5)
        try:
            second = ingest_upload(SimpleNamespace(filename="image.png.preview.png", file=io.BytesIO(white.getvalue())), "preview-race")
        finally:
            second_finished.set()
        first_image = first.result(timeout=5)
    assert first_image["preview_path"] != second["source_path"]
    assert Path(second["source_path"]).read_bytes() == white.getvalue()


def test_export_box_above_image_does_not_crash(tmp_path):
    source = tmp_path / "image.png"
    source.write_bytes(png())
    annotation = {"label": "edge", "source": "manual user annotation", "coordinate": {"type": "bbox", "x": 2, "y": -5, "width": 10, "height": 15}}
    output = export_annotated_png("edge", str(source), [annotation])
    assert Path(output).is_file()


@pytest.mark.parametrize("url", [None, 123, [], {}])
def test_download_api_rejects_invalid_url_without_server_error(url):
    result = client.post("/api/models/download", json={"url": url})
    assert result.status_code == 400


@pytest.mark.parametrize("coordinate", [
    {"type": "point", "x": "NaN", "y": 1},
    {"type": "polygon", "points": None},
])
def test_export_ignores_damaged_legacy_geometry(tmp_path, coordinate):
    source = tmp_path / "image.png"
    source.write_bytes(png())
    output = export_annotated_png("legacy", str(source), [{"label": "invalid", "source": "manual user annotation", "coordinate": coordinate}])
    with Image.open(output) as rendered:
        assert rendered.getbbox() is None


def test_audit_counts_use_unambiguous_image_identities():
    images = [
        {"image_id": "uid", "sop_instance_uid": "uid", "filename": "same.dcm"},
        {"image_id": "copy", "sop_instance_uid": "uid", "filename": "same.dcm"},
    ]
    bundle = build_audit_bundle({"case_id": "duplicate", "images": images, "annotations": [
        {"id": "canonical", "source_image_id": "uid"},
        {"id": "ambiguous", "source_image_id": "same.dcm"},
    ]})
    assert bundle["output_summary"]["annotations_by_image"] == {"uid": 1, "copy": 0}


@pytest.mark.parametrize("delete_all", [False, True])
def test_deleting_cases_removes_generated_audit_export(delete_all):
    original = case()
    exported = client.get(f"/api/audit/{original['case_id']}/export")
    assert exported.status_code == 200
    output = Path(exported.json()["path"])
    assert output.is_file()
    deleted = client.delete("/api/cases" if delete_all else f"/api/cases/{original['case_id']}")
    assert deleted.status_code == 200
    assert not output.exists()


@pytest.mark.parametrize("delete_all", [False, True])
def test_delete_cleans_legacy_audit_but_keeps_other_case_exports(delete_all):
    from app.config import get_settings
    from app.storage.db import safe_path_component

    original = case()
    root = get_settings().exports_dir
    legacy = root / f"{safe_path_component(original['case_id'])}_audit_bundle.json"
    other = root / "other_audit_bundle.json"
    legacy.write_text("{}")
    other.write_text("{}")
    client.delete("/api/cases" if delete_all else f"/api/cases/{original['case_id']}")
    assert not legacy.exists()
    assert other.exists() is (not delete_all)


def test_valid_geometry_and_original_ai_state_still_save():
    original = case()
    annotation = {"id": "valid", "label": "synthetic", "confidence": 0.5, "source": "model-returned coordinate", "explanation": "test",
                  "coordinate": {"type": "bbox", "x": 0, "y": 0, "width": 10, "height": 10},
                  "original_coordinate": {"type": "point", "x": 1, "y": 1},
                  "original_state": {"coordinate": {"type": "polygon", "points": [[0, 0], [10, 0], [0, 10]]}}}
    result = client.post("/api/cases", json={**original, "annotations": [annotation]}, headers={"If-Match": str(original["revision"])})
    assert result.status_code == 200
    assert get_case(original["case_id"])["annotations"] == [annotation]


@pytest.mark.parametrize("field", ["original_coordinate", "original_state"])
def test_invalid_original_ai_geometry_is_not_persisted(field):
    original = case()
    invalid = {"type": "point", "x": "NaN", "y": 1}
    annotation = {"coordinate": {"type": "point", "x": 1, "y": 1}, field: {"coordinate": invalid} if field == "original_state" else invalid}
    result = client.post("/api/cases", json={**original, "annotations": [annotation]})
    assert result.status_code == 400
    assert get_case(original["case_id"]) == original
