from types import SimpleNamespace

import pydicom
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

from app.dicom import safety
from app.main import app
from app.services.image_service import _read_dicom
from app.storage.db import save_case


def _write_dicom(path, burned_in="YES"):
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientName = "Sensitive^Patient"
    ds.PatientID = "MRN-SECRET"
    ds.PatientBirthName = "Birth^Sensitive"
    ds.PatientComments = "Private patient comment"
    ds.PatientBirthDate = "19700101"
    ds.Modality = "DX"
    ds.BurnedInAnnotation = burned_in
    ds.Rows = 2
    ds.Columns = 2
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = bytes([0, 32, 128, 255])
    referenced_patient = Dataset()
    referenced_patient.PatientName = "Nested^Sensitive"
    referenced_patient.PatientID = "NESTED-SECRET"
    ds.ReferencedPatientSequence = [referenced_patient]
    ds.add_new((0x0011, 0x1010), "LO", "private-sensitive")
    pydicom.dcmwrite(str(path), ds, enforce_file_format=True)
    return ds


def test_dicom_safety_preview_and_safe_exports(tmp_path, monkeypatch):
    source = tmp_path / "source.dcm"
    _write_dicom(source, burned_in="YES")
    monkeypatch.setattr(safety, "get_settings", lambda: SimpleNamespace(exports_dir=tmp_path / "exports"))

    report = safety.dicom_safety_report(str(source))
    assert report["private_tag_count"] >= 1
    assert report["burned_in_annotation_risk"]["level"] == "high"
    assert any(item["keyword"] == "PatientName" and item["action"] == "replace" for item in report["tag_groups"]["patient"])
    assert any(item["keyword"] == "SOPInstanceUID" and item["action"] == "regenerate" for item in report["tag_groups"]["other"])
    assert report["pixel_data_summary"]["number_of_frames"] == 1

    metadata = safety.export_deidentified_metadata(str(source), "case-dicom", 0)
    metadata_text = open(metadata["path"], encoding="utf-8").read()
    assert "Sensitive^Patient" not in metadata_text
    assert "Birth^Sensitive" not in metadata_text
    assert "Private patient comment" not in metadata_text
    assert "private-sensitive" not in metadata_text
    assert metadata["payload"]["verification"]["passed"] is True

    with pytest.raises(ValueError, match="Burned-in annotation risk"):
        safety.export_deidentified_dicom(str(source), "case-dicom", 0)
    exported = safety.export_deidentified_dicom(str(source), "case-dicom", 0, acknowledge_burned_in_risk=True)
    clean = pydicom.dcmread(exported["path"])
    original = pydicom.dcmread(str(source))
    assert str(clean.PatientName) == "ANON"
    assert str(clean.PatientID).startswith("MR-case-dicom")
    assert all("Nested^Sensitive" not in str(element.value) and "NESTED-SECRET" not in str(element.value) for element in clean.iterall())
    assert "PatientBirthName" not in clean
    assert "PatientComments" not in clean
    assert not any(element.tag.is_private for element in clean.iterall())
    assert str(original.PatientName) == "Sensitive^Patient"
    assert exported["source_overwritten"] is False
    assert exported["pixel_data_unchanged"] is True
    assert exported["verification"]["passed"] is True
    exported_again = safety.export_deidentified_dicom(str(source), "case-dicom", 0, acknowledge_burned_in_risk=True)
    assert exported_again["path"] != exported["path"]
    assert open(exported["path"], "rb").read()


def test_dicom_safety_endpoint_reads_only_original_case_source(tmp_path):
    from app.config import get_settings

    case_id = "dicom-safety-endpoint"
    case_dir = get_settings().cases_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    source = case_dir / "source.dcm"
    _write_dicom(source, burned_in="YES")
    save_case({
        "case_id": case_id,
        "title": "DICOM safety endpoint",
        "images": [{
            "image_id": "dicom-image-1",
            "index": 0,
            "filename": "source.dcm",
            "source_path": str(source),
            "image_path": str(case_dir / "source.dicom.png"),
            "is_dicom": True,
            "metadata": {"format": "DICOM"},
        }],
        "active_image_id": "dicom-image-1",
    })

    response = TestClient(app).get(f"/api/dicom/{case_id}/images/dicom-image-1/safety")
    assert response.status_code == 200
    assert response.json()["burned_in_annotation_risk"]["level"] == "high"
    assert response.json()["dicomweb_status"] == "disabled_not_configured"
    rejected = TestClient(app).post(
        f"/api/dicom/{case_id}/images/dicom-image-1/export-deidentified",
        json={"acknowledge_burned_in_risk": "false"},
    )
    accepted = TestClient(app).post(
        f"/api/dicom/{case_id}/images/dicom-image-1/export-deidentified",
        json={"acknowledge_burned_in_risk": True},
    )
    assert rejected.status_code == 400
    assert accepted.status_code == 200


def test_dicom_preview_uses_first_frame_and_inverts_monochrome1(tmp_path):
    source = tmp_path / "multiframe.dcm"
    ds = _write_dicom(source, burned_in="NO")
    ds.NumberOfFrames = 2
    ds.PhotometricInterpretation = "MONOCHROME1"
    ds.PixelData = bytes([0, 64, 128, 255, 255, 128, 64, 0])
    pydicom.dcmwrite(str(source), ds, enforce_file_format=True)

    preview, metadata = _read_dicom(source)
    with Image.open(preview) as image:
        assert image.size == (2, 2)
        assert image.getpixel((0, 0)) > image.getpixel((1, 1))
    assert metadata["NumberOfFrames"] == 2
    assert metadata["PhotometricInterpretation"] == "MONOCHROME1"
