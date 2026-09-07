from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from app.dicom.viewer import dicom_viewer_profile, render_dicom_frame
from app.main import app
from app.storage.db import save_case
from test_dicom_safety import _write_dicom


def test_profile_and_frame_render_support_multiframe_windowing(tmp_path):
    source = tmp_path / "viewer.dcm"
    ds = _write_dicom(source, burned_in="NO")
    ds.NumberOfFrames = 2
    ds.PixelSpacing = [0.5, 0.25]
    ds.WindowCenter = 100
    ds.WindowWidth = 200
    ds.PixelData = bytes([0, 20, 80, 120, 40, 100, 180, 255])
    ds.save_as(source)

    profile = dicom_viewer_profile(source)
    assert profile["number_of_frames"] == 2
    assert profile["pixel_spacing"] == {"row_mm": 0.5, "column_mm": 0.25}
    assert profile["window_presets"][0]["center"] == 100
    assert profile["window_presets"][0]["width"] == 200

    first = Image.open(BytesIO(render_dicom_frame(source, frame=0, window_center=100, window_width=200)))
    second = Image.open(BytesIO(render_dicom_frame(source, frame=1, window_center=100, window_width=200)))
    assert first.size == (2, 2)
    assert list(first.get_flattened_data()) != list(second.get_flattened_data())


def test_dicom_viewer_endpoint_is_bound_to_case_source(tmp_path, monkeypatch):
    source = tmp_path / "source.dcm"
    _write_dicom(source, burned_in="NO")
    case_id = "dicom-viewer-endpoint"
    monkeypatch.setattr("app.api.routes.get_settings", lambda: SimpleNamespace(cases_dir=tmp_path, exports_dir=tmp_path))
    save_case({
        "case_id": case_id,
        "title": "DICOM viewer",
        "images": [{"image_id": "image-1", "index": 0, "source_path": str(source), "image_path": str(tmp_path / "preview.png"), "is_dicom": True}],
        "active_image_id": "image-1",
    })

    client = TestClient(app)
    profile = client.get(f"/api/dicom/{case_id}/images/image-1/viewer-profile")
    rendered = client.get(f"/api/dicom/{case_id}/images/image-1/preview?frame=0&window_center=127&window_width=255")
    invalid = client.get(f"/api/dicom/{case_id}/images/image-1/preview?frame=99")
    assert profile.status_code == 200
    assert rendered.status_code == 200 and rendered.headers["content-type"] == "image/png"
    assert invalid.status_code == 400
