"""Synthetic regression cases for the cross-module audit on 2026-10-14."""
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.annotations.exporter import export_annotated_png, export_annotation_review_package
from app.audit.bundle import export_audit_bundle
from app.config import get_settings
from app.dicom.viewer import dicom_viewer_profile, render_dicom_frame
from app.main import app
from app.models.schemas import RuntimeConfig
from app.reports.generator import export_report
from app.runtime.adapters import chat_response
from app.storage.db import save_case
from test_dicom_safety import _write_dicom


def synthetic_case():
    settings = get_settings()
    source = settings.cases_dir / "synthetic.png"
    Image.new("RGB", (24, 24), "black").save(source)
    return {"case_id": "audit-oct14", "title": "Synthetic", "image_path": str(source), "annotations": []}


def test_palette_dicom_uses_rgb_lookup_table(tmp_path):
    source = tmp_path / "palette.dcm"
    ds = _write_dicom(source)
    ds.PhotometricInterpretation = "PALETTE COLOR"
    ds.PixelData = bytes([0, 1, 2, 3])
    for channel, data in [("Red", [255, 0, 0, 255]), ("Green", [0, 255, 0, 255]), ("Blue", [0, 0, 255, 255])]:
        setattr(ds, channel + "PaletteColorLookupTableDescriptor", [4, 0, 8])
        setattr(ds, channel + "PaletteColorLookupTableData", bytes(data))
    ds.save_as(source)
    image = Image.open(BytesIO(render_dicom_frame(source)))
    assert image.mode == "RGB"
    assert list(image.get_flattened_data()) == [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
    inverted = Image.open(BytesIO(render_dicom_frame(source, invert=True)))
    assert inverted.getpixel((0, 0)) == (0, 255, 255)


@pytest.mark.parametrize("spacing", [[float("nan"), .25, .5], [.25, .5, .75], [.25]])
def test_invalid_spacing_cannot_become_a_valid_calibration(tmp_path, spacing):
    source = tmp_path / "spacing.dcm"
    ds = _write_dicom(source)
    ds.PixelSpacing = spacing
    ds.save_as(source)
    assert dicom_viewer_profile(source)["pixel_spacing"] is None


def test_dicom_presets_keep_center_width_and_name_paired(tmp_path):
    source = tmp_path / "presets.dcm"
    ds = _write_dicom(source)
    ds.WindowCenter = [float("nan"), 100]
    ds.WindowWidth = [10, 200]
    ds.WindowCenterWidthExplanation = ["invalid", "valid"]
    ds.save_as(source)
    assert dicom_viewer_profile(source)["window_presets"] == [{"name": "valid", "center": 100.0, "width": 200.0}]


@pytest.mark.parametrize("backend", ["demo", "ollama"])
def test_chat_only_uses_active_image_annotations(backend, monkeypatch):
    captured = []
    monkeypatch.setattr("app.runtime.adapters.ollama_chat", lambda messages, *_: captured.extend(messages) or "ok")
    context = {"case_id": "study", "active_image_id": "second", "images": [{"image_id": "first"}, {"image_id": "second"}],
               "annotations": [{"id": "a", "source_image_id": "first"}, {"id": "b", "source_image_id": "second"}],
               "analysis": {"findings": []}}
    reply = chat_response("annotations?", [], RuntimeConfig(primary_backend=backend, chat_model="model"), context, "en")
    if backend == "demo":
        assert "There are 1 annotations" in reply["content"]
    else:
        focused = json.loads(captured[-1]["content"].split("Structured case context: ")[1].split("\n\nAdditional metadata")[0])
        assert [annotation["id"] for annotation in focused["annotations"]] == ["b"]
        assert focused["active_image_id"] == "second"


def test_analyzed_chat_keeps_conversation_history(monkeypatch):
    captured = []
    monkeypatch.setattr("app.runtime.adapters.ollama_chat", lambda messages, *_: captured.extend(messages) or "ok")
    history = [{"role": "user", "content": "Discuss the second finding"}, {"role": "assistant", "content": "Earlier answer"}]
    chat_response("Explain that further", history, RuntimeConfig(primary_backend="ollama", chat_model="model"), {"analysis": {"findings": []}}, "en")
    assert captured[:-1] == history


@pytest.mark.parametrize("artifact", ["markdown", "json", "audit", "comparison"])
def test_failed_text_export_preserves_previous_document(artifact, monkeypatch):
    case = synthetic_case()
    folder = get_settings().exports_dir / case["case_id"]
    folder.mkdir()
    name = {"markdown": "report.md", "json": "report.json", "audit": "audit_bundle.json", "comparison": "annotation_review_comparison.json"}[artifact]
    previous = folder / name
    previous.write_text("previous complete export")
    real_write = Path.write_text

    def interrupted_write(path, *args, **kwargs):
        real_write(path, "partial")
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr(Path, "write_text", interrupted_write)
    action = {"audit": export_audit_bundle, "comparison": export_annotation_review_package}.get(artifact)
    with pytest.raises(OSError, match="Synthetic"):
        action(case) if action else export_report(case, artifact)
    assert previous.read_text() == "previous complete export"
    assert sorted(path.name for path in folder.iterdir()) == [name]


def test_failed_png_export_preserves_previous_image(monkeypatch):
    case = synthetic_case()
    folder = get_settings().exports_dir / case["case_id"]
    folder.mkdir()
    previous = folder / "annotated_reviewed.png"
    previous.write_bytes(b"previous complete PNG")

    def interrupted_save(_image, path, *args, **kwargs):
        Path(path).write_bytes(b"partial PNG")
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr(Image.Image, "save", interrupted_save)
    with pytest.raises(OSError):
        export_annotated_png(case["case_id"], case["image_path"], [])
    assert previous.read_bytes() == b"previous complete PNG"
    assert sorted(path.name for path in folder.iterdir()) == [previous.name]


@pytest.mark.parametrize("payload", [{"format": "xml", "language": "en"}, {"format": "json", "language": "unknown"}])
def test_report_export_rejects_unsupported_options(payload):
    save_case(synthetic_case())
    response = TestClient(app).post("/api/reports/audit-oct14/export", json=payload)
    assert response.status_code == 400
    assert not (get_settings().exports_dir / "audit-oct14").exists()


@pytest.mark.parametrize("field", ["metadata", "analysis"])
def test_nonfinite_case_payload_is_rejected_before_storage(field):
    client = TestClient(app, raise_server_exceptions=False)
    payload = {"case_id": "nonfinite", "title": "Synthetic", field: {"score": float("nan")}}
    response = client.post("/api/cases", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert client.get("/api/cases/nonfinite").status_code == 404


def test_color_dicom_never_suggests_monochrome_windowing(tmp_path):
    source = tmp_path / "color-window.dcm"
    ds = _write_dicom(source)
    ds.SamplesPerPixel = 3
    ds.PlanarConfiguration = 0
    ds.PhotometricInterpretation = "RGB"
    ds.WindowCenter = 100
    ds.WindowWidth = 200
    ds.PixelData = bytes(range(12))
    ds.save_as(source)
    profile = dicom_viewer_profile(source)
    assert profile["default_window"] is None
    assert profile["window_presets"] == []
    assert not profile["supports_window_level"]


@pytest.mark.parametrize("pixels", [[[0, 1000], [2000, 65535]], [[0, 0], [0, 0]]])
def test_16bit_png_preview_preserves_intensity_range(pixels):
    buffer = BytesIO()
    Image.fromarray(np.asarray(pixels, dtype=np.uint16)).save(buffer, format="PNG")
    original_bytes = buffer.getvalue()
    response = TestClient(app).post("/api/upload", files={"file": ("synthetic16.png", original_bytes, "image/png")})
    assert response.status_code == 200
    uploaded = response.json()["image"]
    assert Path(uploaded["source_path"]).read_bytes() == original_bytes
    with Image.open(uploaded["preview_path"]) as preview:
        values = [pixel[0] for pixel in preview.get_flattened_data()]
    expected = [0, 4, 8, 255] if pixels[1][1] else [0, 0, 0, 0]
    assert values == expected
    with Image.open(uploaded["stored_path"]) as image:
        assert image.mode == "L"
        assert list(image.get_flattened_data()) == expected


def test_failed_pdf_export_preserves_previous_document(monkeypatch):
    case = synthetic_case()
    folder = get_settings().exports_dir / case["case_id"]
    folder.mkdir()
    previous = folder / "report.pdf"
    previous.write_bytes(b"previous complete PDF")

    def interrupted_save(canvas):
        Path(canvas._filename).write_bytes(b"partial PDF")
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr("app.reports.generator.canvas.Canvas.save", interrupted_save)
    with pytest.raises(OSError):
        export_report(case, "pdf")
    assert previous.read_bytes() == b"previous complete PDF"
    assert sorted(path.name for path in folder.iterdir()) == [previous.name]


def test_failed_model_card_write_preserves_review(monkeypatch):
    from app.model_finder import providers
    artifact = get_settings().models_dir / "synthetic.pt"
    artifact.write_bytes(b"synthetic")
    card = providers.save_local_model_card({"artifact_path": str(artifact), "human_reviewed": True})
    path = Path(card["card_path"])
    previous = path.read_bytes()
    real_write = Path.write_text

    def interrupted_write(path, *args, **kwargs):
        real_write(path, "partial")
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr(Path, "write_text", interrupted_write)
    with pytest.raises(OSError):
        providers.save_local_model_card({"artifact_id": card["artifact_id"], "human_reviewed": True, "limitations": "updated"})
    assert path.read_bytes() == previous
    assert not list(path.parent.glob("*.tmp"))


def test_duplicate_download_cannot_discard_requested_checksum(monkeypatch):
    from app.model_finder import providers
    manager = providers.DownloadManager()
    monkeypatch.setattr(providers, "_validate_manual_download_url", lambda *_: None)
    monkeypatch.setattr(manager, "_start_worker", lambda *_: None)
    original = manager.start("https://models.example/synthetic.pt")
    with pytest.raises(ValueError, match="checksum"):
        manager.start(original["url"], checksum_sha256="a" * 64)
    assert len(manager.jobs) == 1
    assert original["checksum_sha256"] == ""


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -.1, 1.1])
def test_detector_rejects_invalid_confidence_instead_of_promoting_it(score, monkeypatch):
    from app.vision import ultralytics_detector as detector
    source = synthetic_case()["image_path"]
    tensor = lambda values: SimpleNamespace(cpu=lambda: SimpleNamespace(tolist=lambda: values))
    result = SimpleNamespace(names={0: "fracture"}, boxes=SimpleNamespace(
        xyxy=tensor([[1, 1, 15, 15], [2, 2, 20, 20]]), conf=tensor([score, .8]), cls=tensor([0, 0])))
    monkeypatch.setattr(detector, "_resolve_detector_artifact", lambda _: (Path("synthetic.pt"), ""))
    monkeypatch.setattr(detector.importlib.util, "find_spec", lambda _: True)
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda _: SimpleNamespace(predict=lambda **_: [result])))
    response = detector.run_msk_fracture_detector(source, "local:synthetic")
    assert response["status"] == "ok"
    assert [detection["confidence"] for detection in response["detections"]] == [.8]
    assert any("Rejected 1" in warning for warning in response["warnings"])


def test_failed_database_relocation_cleans_partial_configuration(tmp_path, monkeypatch):
    from app import config
    current = config.get_settings().db_path
    previous = json.dumps({"database_path": str(current)})
    config.DATABASE_LOCATION_CONFIG.write_text(previous)
    real_write = Path.write_text

    def interrupted_write(path, *args, **kwargs):
        real_write(path, "partial")
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr(Path, "write_text", interrupted_write)
    with pytest.raises(OSError):
        config.set_database_folder(str(tmp_path / "destination"))
    assert config.DATABASE_LOCATION_CONFIG.read_text() == previous
    assert not (tmp_path / "destination" / config.DATABASE_FILENAME).exists()
    assert not list(config.DATABASE_LOCATION_CONFIG.parent.glob("*.tmp"))
