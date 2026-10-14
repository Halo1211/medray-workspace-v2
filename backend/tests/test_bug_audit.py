"""Regression checks for case isolation, image rendering and provider failures."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.annotations import exporter
from app.dicom.viewer import render_dicom_frame
from app.main import app
from app.reports.generator import build_grounded_review_statements
from app.runtime import adapters
from app.services.image_service import _read_dicom
from test_dicom_safety import _write_dicom


def png(color="black"):
    output = BytesIO()
    Image.new("RGB", (32, 32), color).save(output, format="PNG")
    return output.getvalue()


def upload(client, filename="first.png", color="black"):
    response = client.post("/api/upload", files={"file": (filename, png(color), "image/png")})
    assert response.status_code == 200
    return response.json()["case"]


def test_switch_to_unanalyzed_image_does_not_copy_previous_analysis():
    client = TestClient(app)
    case = upload(client)
    first_id = case["active_image_id"]
    assert client.post(f"/api/analysis/{case['case_id']}").status_code == 200
    case = client.post(f"/api/cases/{case['case_id']}/images", files={"file": ("second.png", png("white"), "image/png")}).json()["case"]
    second_id = case["images"][1]["image_id"]
    switched = client.post(f"/api/cases/{case['case_id']}/active-image", json={"image_id": second_id}).json()
    assert switched["analysis"] is None
    assert switched["report"] is None
    assert set(switched["analyses_by_image"]) == {first_id}


def test_metadata_edit_survives_save_reload_and_image_switch():
    client = TestClient(app)
    case = upload(client)
    case["metadata"].update(LocalRecordID="synthetic-NPM", ClinicalIndication="synthetic indication")
    case = client.post("/api/cases", json=case).json()
    assert case["metadata"]["LocalRecordID"] == "synthetic-NPM"
    case = client.post(f"/api/cases/{case['case_id']}/images", files={"file": ("second.png", png(), "image/png")}).json()["case"]
    case = client.post(f"/api/cases/{case['case_id']}/active-image", json={"image_id": case["images"][1]["image_id"]}).json()
    assert case["metadata"]["LocalRecordID"] == "synthetic-NPM"
    case["metadata"].pop("LocalRecordID")
    client.post("/api/cases", json=case)
    case = client.post(f"/api/cases/{case['case_id']}/active-image", json={"image_id": case["images"][0]["image_id"]}).json()
    assert "LocalRecordID" not in case["metadata"]


@pytest.mark.parametrize("filename", ["first.preview.png", "first.jpg"])
def test_upload_does_not_overwrite_existing_preview(filename):
    client = TestClient(app)
    case = upload(client)
    original_path = Path(case["image_preview"])
    original = original_path.read_bytes()
    result = client.post(f"/api/cases/{case['case_id']}/images", files={"file": (filename, png("white"), "image/png")})
    assert result.status_code == 200
    assert original_path.read_bytes() == original
    assert result.json()["image"]["preview_path"] != str(original_path)


def test_unsupported_upload_extension_is_rejected_without_orphan_files():
    client = TestClient(app)
    result = client.post("/api/upload", files={"file": ("image.txt", png(), "image/png")})
    assert result.status_code == 400
    from app.config import get_settings
    assert not list(get_settings().cases_dir.rglob("*.txt"))


def test_explicit_dicom_window_maps_to_fixed_display_range(tmp_path):
    source = tmp_path / "window.dcm"
    ds = _write_dicom(source, burned_in="NO")
    ds.PixelData = bytes([40, 60, 80, 100])
    ds.save_as(source)
    image = Image.open(BytesIO(render_dicom_frame(source, window_center=100, window_width=200)))
    assert list(image.get_flattened_data()) == [51, 76, 102, 128]


def test_dicom_width_one_is_a_threshold(tmp_path):
    source = tmp_path / "threshold.dcm"
    _write_dicom(source, burned_in="NO")
    image = Image.open(BytesIO(render_dicom_frame(source, window_center=100, window_width=1)))
    assert list(image.get_flattened_data()) == [0, 0, 255, 255]


def test_dicom_color_is_preserved_in_viewer_and_ingestion(tmp_path):
    source = tmp_path / "rgb.dcm"
    ds = _write_dicom(source, burned_in="NO")
    ds.SamplesPerPixel = 3
    ds.PlanarConfiguration = 0
    ds.PhotometricInterpretation = "RGB"
    pixels = np.array([[[255, 0, 0], [0, 255, 0]], [[0, 0, 255], [80, 100, 120]]], dtype=np.uint8)
    ds.PixelData = pixels.tobytes()
    ds.save_as(source)
    rendered = Image.open(BytesIO(render_dicom_frame(source)))
    stored, _ = _read_dicom(source)
    assert rendered.mode == "RGB"
    assert np.array_equal(np.asarray(rendered), pixels)
    assert np.array_equal(np.asarray(Image.open(stored)), pixels)


def test_dicom_ingestion_matches_viewer_with_rescale_and_window(tmp_path):
    source = tmp_path / "rescale.dcm"
    ds = _write_dicom(source, burned_in="NO")
    ds.RescaleSlope = 2
    ds.RescaleIntercept = -100
    ds.WindowCenter = 100
    ds.WindowWidth = 200
    ds.save_as(source)
    stored, _ = _read_dicom(source)
    assert np.array_equal(np.asarray(Image.open(stored)), np.asarray(Image.open(BytesIO(render_dicom_frame(source)))))


def test_export_package_does_not_apply_unbound_or_ambiguous_annotations_to_second_image(tmp_path, monkeypatch):
    paths = [tmp_path / "a.png", tmp_path / "b.png"]
    for path in paths:
        Image.new("RGB", (32, 32), "black").save(path)
    monkeypatch.setattr(exporter, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))
    case = {
        "case_id": "synthetic",
        "images": [{"image_id": name, "filename": "same.png", "image_path": str(path)} for name, path in zip(["a", "b"], paths)],
        "annotations": [{"id": "unbound", "source_image_id": "", "source": "manual user annotation", "coordinate": {"type": "point", "x": 15, "y": 15}},
                        {"id": "ambiguous", "source_image_id": "same.png", "source": "manual user annotation", "coordinate": {"type": "point", "x": 15, "y": 15}}],
    }
    package = exporter.export_annotation_review_package(case)
    assert np.array_equal(np.asarray(Image.open(package["reviewed_pngs"]["b"])), np.asarray(Image.open(paths[1])))


def test_png_export_does_not_draw_annotations_from_another_frame(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 32), "black").save(source)
    monkeypatch.setattr(exporter, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))
    output = exporter.export_annotated_png("frames", str(source), [{"source": "manual user annotation", "source_frame_number": 1, "coordinate": {"type": "point", "x": 15, "y": 15}}])
    assert np.array_equal(np.asarray(Image.open(output)), np.asarray(Image.open(source)))


def test_report_provenance_comes_from_linked_annotation_when_card_has_no_provenance():
    case = {
        "analysis": {"result_cards": [{"id": "card", "finding": "synthetic", "review_status": "accepted", "annotation_refs": ["ann"]}]},
        "annotations": [{"id": "ann", "review_status": "accepted", "source_image_id": "image-a", "source_series_id": "series-a", "source_view": "PA", "coordinate": {"type": "point", "x": 0, "y": 0}}],
    }
    statement = build_grounded_review_statements(case, "en")[0]
    assert statement["source_image_ids"] == ["image-a"]
    assert statement["source_series_ids"] == ["series-a"]
    assert statement["source_views"] == ["PA"]


@pytest.mark.parametrize("provider", ["ollama", "compatible"])
def test_permanent_provider_http_error_is_not_retried(monkeypatch, provider):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError("http://127.0.0.1", 401, "denied", {}, None)
    monkeypatch.setattr(adapters.urllib.request, "build_opener", lambda *args: SimpleNamespace(open=fail))
    monkeypatch.setattr(adapters.time, "sleep", lambda seconds: None)
    with pytest.raises(urllib.error.HTTPError):
        if provider == "ollama":
            adapters.ollama_chat([], "test", max_retries=3)
        else:
            adapters.openai_compatible_chat([], "test", "http://127.0.0.1/v1", "dummy", max_retries=3)
    assert len(calls) == 1


def test_analysis_preserves_edits_made_while_model_is_running(monkeypatch):
    from app.api import routes
    from app.storage.db import get_case, save_case
    client = TestClient(app)
    case = upload(client)
    original_run = routes.run_analysis
    async def edit_during_analysis(*args, **kwargs):
        result = await original_run(*args, **kwargs)
        current = get_case(case["case_id"])
        current["title"] = "Edited while model was running"
        save_case(current)
        return result
    monkeypatch.setattr(routes, "run_analysis", edit_during_analysis)
    assert client.post(f"/api/analysis/{case['case_id']}").status_code == 200
    assert client.get(f"/api/cases/{case['case_id']}").json()["title"] == "Edited while model was running"


def test_analysis_does_not_resurrect_a_deleted_case(monkeypatch):
    from app.api import routes
    from app.storage.db import delete_case
    client = TestClient(app)
    case = upload(client)
    original_run = routes.run_analysis
    async def delete_during_analysis(*args, **kwargs):
        result = await original_run(*args, **kwargs)
        delete_case(case["case_id"])
        return result
    monkeypatch.setattr(routes, "run_analysis", delete_during_analysis)
    assert client.post(f"/api/analysis/{case['case_id']}").status_code == 404
    assert client.get(f"/api/cases/{case['case_id']}").status_code == 404


def test_vision_provider_does_not_block_event_loop(tmp_path, monkeypatch):
    import asyncio
    import threading
    from app.pipelines import analysis_pipeline as pipeline
    source = tmp_path / "chest.png"
    Image.new("L", (16, 16), 128).save(source)
    provider_entered = threading.Event()
    heartbeat_ran = threading.Event()
    observed = []
    def provider(*args, **kwargs):
        provider_entered.set()
        observed.append(heartbeat_ran.wait(timeout=1))
        return "Unvalidated synthetic observation."
    monkeypatch.setattr(pipeline, "ollama_vision", provider)
    async def exercise():
        async def heartbeat():
            while not provider_entered.is_set():
                await asyncio.sleep(0)
            heartbeat_ran.set()
        monitor = asyncio.create_task(heartbeat())
        await pipeline.run_analysis("synthetic", {"stored_path": str(source), "filename": "chest.png", "width": 16, "height": 16, "metadata": {"BodyPartExamined": "CHEST"}}, backend="ollama", runtime_snapshot={"primary_backend": "ollama", "vision_language_model": "synthetic-model", "chest_xray_model": "synthetic-model", "ollama_base_url": "http://127.0.0.1:11434"})
        await asyncio.wait_for(monitor, timeout=1)
    asyncio.run(exercise())
    assert observed == [True]


def test_active_image_report_excludes_other_image_standalone_annotations():
    case = {
        "active_image_id": "b", "images": [{"image_id": "a"}, {"image_id": "b"}],
        "annotations": [{"id": "other", "label": "other image", "source_image_id": "a", "review_status": "accepted", "coordinate": {"type": "point"}}],
    }
    assert not any(item["promoted_to_report"] for item in build_grounded_review_statements(case, "en"))


def test_canonical_image_identity_wins_over_duplicate_dicom_uid_alias():
    from app.api.routes import _annotation_matches_image
    images = [{"image_id": "sop-uid", "sop_instance_uid": "sop-uid"}, {"image_id": "case:1", "sop_instance_uid": "sop-uid"}]
    annotation = {"source_image_id": "sop-uid"}
    assert _annotation_matches_image(annotation, images[0], True, images)
    assert not _annotation_matches_image(annotation, images[1], False, images)


def test_normalization_allocates_unique_ids_even_when_fallback_is_taken():
    from app.studies.images import normalize_case_images
    case = normalize_case_images({"case_id": "case", "images": [{"image_id": "case:2"}, {"image_id": "duplicate"}, {"image_id": "duplicate"}]})
    ids = [image["image_id"] for image in case["images"]]
    assert len(set(ids)) == len(ids)
