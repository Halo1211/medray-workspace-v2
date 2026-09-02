from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pydicom
from pydicom.dataset import Dataset
from pydicom.multival import MultiValue
from pydicom.uid import generate_uid

from app.config import get_settings
from app.storage.db import safe_path_component


PHI_REMOVE_KEYWORDS = {
    "PatientBirthDate", "PatientBirthTime", "PatientAddress", "PatientTelephoneNumbers",
    "PatientBirthName", "PatientMotherBirthName", "PatientComments", "CountryOfResidence",
    "RegionOfResidence",
    "OtherPatientIDs", "OtherPatientNames", "EthnicGroup", "Occupation", "AdditionalPatientHistory",
    "PatientReligiousPreference",
    "MilitaryRank", "BranchOfService", "ResponsiblePerson", "ResponsibleOrganization",
    "ReferringPhysicianName", "PerformingPhysicianName", "PhysiciansOfRecord", "OperatorsName",
    "InstitutionName", "InstitutionAddress", "StationName", "AccessionNumber", "StudyID",
    "RequestingPhysician", "RequestedProcedureDescription", "AdmissionID", "MedicalRecordLocator",
    "StudyDate", "StudyTime", "SeriesDate", "SeriesTime", "AcquisitionDate", "AcquisitionTime",
    "AcquisitionDateTime", "ContentDate", "ContentTime", "InstanceCreationDate", "InstanceCreationTime",
    "PatientSex", "PatientAge", "PatientSize", "PatientWeight", "StudyDescription", "SeriesDescription",
    "DeviceSerialNumber", "ProtocolName", "PerformedProcedureStepID", "PerformedProcedureStepDescription",
}
PHI_REPLACE_KEYWORDS = {"PatientName", "PatientID"}
INSTANCE_UID_KEYWORDS = {"StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "FrameOfReferenceUID"}
PRESERVED_UID_KEYWORDS = {"SOPClassUID", "MediaStorageSOPClassUID", "TransferSyntaxUID", "ImplementationClassUID"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _group(keyword: str, is_private: bool) -> str:
    if is_private:
        return "private"
    if keyword.startswith(("Patient", "OtherPatient", "ResponsiblePerson")):
        return "patient"
    if keyword.startswith("Study") or keyword in {"AccessionNumber", "ReferringPhysicianName", "RequestingPhysician"}:
        return "study"
    if keyword.startswith("Series") or keyword in {"Modality", "BodyPartExamined", "ViewPosition", "Laterality", "ImageLaterality", "ProtocolName"}:
        return "series"
    if keyword.startswith(("Acquisition", "Exposure", "Content")) or keyword in {"InstanceNumber", "Rows", "Columns", "PixelSpacing", "KVP", "XRayTubeCurrent"}:
        return "acquisition"
    return "other"


def _value(element: Any) -> Any:
    if element.VR == "SQ":
        return f"Sequence with {len(element.value or [])} item(s)"
    if element.VR in {"OB", "OD", "OF", "OL", "OV", "OW", "UN"}:
        value = element.value or b""
        return f"Binary value ({len(value) if hasattr(value, '__len__') else 'unknown'} bytes)"
    value = str(element.value or "")
    return value[:500] + ("…" if len(value) > 500 else "")


def grouped_tags(ds: Dataset, include_values: bool = True) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in ("patient", "study", "series", "acquisition", "private", "other")}
    elements = list(ds.iterall())
    if getattr(ds, "file_meta", None):
        elements.extend(list(ds.file_meta))
    for element in elements:
        if element.keyword == "PixelData":
            continue
        keyword = str(element.keyword or "")
        action = (
            "replace" if keyword in PHI_REPLACE_KEYWORDS
            else "remove" if keyword in PHI_REMOVE_KEYWORDS or element.tag.is_private
            else "regenerate" if element.VR == "UI" and keyword not in PRESERVED_UID_KEYWORDS
            else "retain_review"
        )
        item = {
            "tag": str(element.tag),
            "keyword": keyword or "private_or_unknown",
            "name": str(element.name),
            "vr": str(element.VR),
            "is_private": bool(element.tag.is_private),
            "action": action,
        }
        if include_values:
            item["value"] = _value(element)
        groups[_group(keyword, bool(element.tag.is_private))].append(item)
    return groups


def _burned_in_risk(ds: Dataset) -> dict[str, Any]:
    burned = str(getattr(ds, "BurnedInAnnotation", "") or "").upper()
    recognizable = str(getattr(ds, "RecognizableVisualFeatures", "") or "").upper()
    if burned == "YES" or recognizable == "YES":
        level = "high"
        reason = "DICOM declares burned-in annotation or recognizable visual features. Pixel data requires manual inspection."
    elif burned == "NO" and recognizable in {"", "NO"}:
        level = "low_declared"
        reason = "BurnedInAnnotation is declared NO; manual pixel review is still recommended."
    else:
        level = "unknown"
        reason = "BurnedInAnnotation is absent or unknown. Pixel data must be reviewed before sharing."
    return {"level": level, "burned_in_annotation": burned or "not_declared", "recognizable_visual_features": recognizable or "not_declared", "reason": reason}


def _transformations(ds: Dataset) -> list[dict[str, str]]:
    transformations = []
    for keyword in sorted(PHI_REPLACE_KEYWORDS):
        transformations.append({"keyword": keyword, "action": "replace", "replacement": "local pseudonym"})
    for keyword in sorted(PHI_REMOVE_KEYWORDS):
        if keyword in ds:
            transformations.append({"keyword": keyword, "action": "remove", "replacement": ""})
    transformations.extend([
        {"keyword": "private tags", "action": "remove_all", "replacement": ""},
        {"keyword": "instance UIDs", "action": "regenerate", "replacement": "new local UID values"},
        {"keyword": "PixelData", "action": "retain_unchanged", "replacement": "manual burned-in review required"},
    ])
    return transformations


def _dataset_tree(root: Dataset) -> list[Dataset]:
    datasets: list[Dataset] = []

    def collect(dataset: Dataset) -> None:
        datasets.append(dataset)
        for element in dataset:
            if element.VR == "SQ":
                for item in element.value or []:
                    if isinstance(item, Dataset):
                        collect(item)

    collect(root)
    return datasets


def _verification(ds: Dataset, pseudonym: str, source_pixel_hash: str = "") -> dict[str, Any]:
    datasets = _dataset_tree(ds)
    private_tags = [str(element.tag) for dataset in datasets for element in dataset if element.tag.is_private]
    forbidden = sorted({keyword for dataset in datasets for keyword in PHI_REMOVE_KEYWORDS if keyword in dataset})
    replacement_issues = []
    for dataset in datasets:
        if "PatientName" in dataset and str(dataset.PatientName) != "ANON":
            replacement_issues.append("PatientName")
        if "PatientID" in dataset and str(dataset.PatientID) != pseudonym:
            replacement_issues.append("PatientID")
    exported_pixel_hash = hashlib.sha256(bytes(ds.PixelData)).hexdigest() if "PixelData" in ds else ""
    pixel_data_unchanged = not source_pixel_hash or source_pixel_hash == exported_pixel_hash
    passed = not private_tags and not forbidden and not replacement_issues and str(getattr(ds, "PatientIdentityRemoved", "")) == "YES" and pixel_data_unchanged
    return {
        "passed": passed,
        "private_tags_remaining": private_tags,
        "forbidden_keywords_remaining": forbidden,
        "replacement_issues": sorted(set(replacement_issues)),
        "patient_identity_removed": str(getattr(ds, "PatientIdentityRemoved", "")),
        "pixel_data_unchanged": pixel_data_unchanged,
    }


def dicom_safety_report(path: str) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise ValueError("DICOM source file was not found.")
    ds = pydicom.dcmread(str(source), stop_before_pixels=True, force=True)
    tags = grouped_tags(ds)
    private_count = len(tags["private"])
    risk = _burned_in_risk(ds)
    transfer_syntax = str(getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", "") or "")
    transfer_uid = getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", None)
    compressed = bool(getattr(transfer_uid, "is_compressed", False))
    number_of_frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
    warnings = []
    if private_count:
        warnings.append(f"{private_count} private tag(s) detected; safe export removes them.")
    warnings.append(risk["reason"])
    if compressed:
        warnings.append("Compressed transfer syntax detected; pixel decoding requires the matching local codec. Safe export retains the original compressed pixel stream.")
    if number_of_frames > 1:
        warnings.append(f"Multi-frame DICOM detected ({number_of_frames} frames); the Reading Room preview currently displays the first frame only.")
    warnings.append("MedRay basic de-identification is a local prototype preview, not a certification of DICOM PS3.15 compliance.")
    return {
        "schema_version": "medray-dicom-safety-v1",
        "generated_at": _now_iso(),
        "source_path": str(source),
        "source_sha256": _file_hash(source),
        "tag_groups": tags,
        "tag_counts": {key: len(items) for key, items in tags.items()},
        "private_tag_count": private_count,
        "burned_in_annotation_risk": risk,
        "pixel_data_summary": {
            "declared_by_image_attributes": bool(getattr(ds, "Rows", 0) and getattr(ds, "Columns", 0)),
            "number_of_frames": number_of_frames,
            "transfer_syntax_uid": transfer_syntax,
            "compressed": compressed,
            "export_behavior": "pixel_data_retained_unchanged",
        },
        "deidentification_preview": _transformations(ds),
        "warnings": warnings,
        "dicomweb_status": "disabled_not_configured",
    }


def _deidentify(ds: Dataset, case_id: str) -> Dataset:
    output = copy.deepcopy(ds)
    output.remove_private_tags()
    datasets = _dataset_tree(output)
    pseudonym = f"MR-{case_id[:12]}"
    for dataset in datasets:
        for keyword in PHI_REMOVE_KEYWORDS:
            if keyword in dataset:
                del dataset[keyword]
        if "PatientName" in dataset:
            dataset.PatientName = "ANON"
        if "PatientID" in dataset:
            dataset.PatientID = pseudonym
    output.PatientName = "ANON"
    output.PatientID = pseudonym
    output.PatientIdentityRemoved = "YES"
    output.DeidentificationMethod = "MedRay v2 prototype de-id; manual verification required"
    uid_map: dict[str, str] = {}
    for element in output.iterall():
        if element.VR != "UI" or str(element.keyword or "") in PRESERVED_UID_KEYWORDS:
            continue
        is_multi = isinstance(element.value, (list, tuple, MultiValue))
        values = list(element.value) if is_multi else [element.value]
        replacements = []
        for value in values:
            old = str(value or "")
            if not old:
                replacements.append(value)
                continue
            uid_map.setdefault(old, generate_uid())
            replacements.append(uid_map[old])
        element.value = replacements if is_multi else replacements[0]
    if getattr(output, "file_meta", None) and "MediaStorageSOPInstanceUID" in output.file_meta:
        old = str(output.file_meta.MediaStorageSOPInstanceUID or "")
        output.file_meta.MediaStorageSOPInstanceUID = uid_map.get(old, generate_uid())
    return output


def _export_dir(case_id: str) -> Path:
    path = get_settings().exports_dir / safe_path_component(case_id, "case") / "dicom"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _unique_output(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 10000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("Could not allocate a unique DICOM export filename.")


def export_deidentified_metadata(path: str, case_id: str, image_index: int = 0) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    ds = pydicom.dcmread(str(source), stop_before_pixels=True, force=True)
    clean = _deidentify(ds, case_id)
    verification = _verification(clean, f"MR-{case_id[:12]}")
    if not verification["passed"]:
        raise ValueError("Metadata de-identification verification failed; export was not written.")
    payload = {
        "schema_version": "medray-deidentified-metadata-v1",
        "generated_at": _now_iso(),
        "case_id": case_id,
        "source_sha256": _file_hash(source),
        "pixel_data_included": False,
        "tag_groups": grouped_tags(clean, include_values=True),
        "verification": verification,
        "safety_note": "Metadata-only local research export; manual verification remains required.",
    }
    output = _unique_output(_export_dir(case_id) / f"image_{image_index}_deidentified_metadata.json")
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(output), "payload": payload}


def export_deidentified_dicom(path: str, case_id: str, image_index: int = 0, acknowledge_burned_in_risk: bool = False) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    report = dicom_safety_report(str(source))
    risk = report["burned_in_annotation_risk"]["level"]
    if risk in {"high", "unknown"} and not acknowledge_burned_in_risk:
        raise ValueError("Burned-in annotation risk must be acknowledged after manual pixel review before DICOM export.")
    ds = pydicom.dcmread(str(source), force=True)
    source_pixel_hash = hashlib.sha256(bytes(ds.PixelData)).hexdigest() if "PixelData" in ds else ""
    clean = _deidentify(ds, case_id)
    output = _unique_output(_export_dir(case_id) / f"image_{image_index}_deidentified.dcm")
    if output.resolve() == source:
        raise ValueError("Safe export cannot overwrite the source DICOM.")
    pydicom.dcmwrite(str(output), clean, enforce_file_format=True)
    readback = pydicom.dcmread(str(output), force=True)
    verification = _verification(readback, f"MR-{case_id[:12]}", source_pixel_hash)
    if not verification["passed"]:
        output.unlink(missing_ok=True)
        raise ValueError("DICOM de-identification readback verification failed; unsafe export was removed.")
    return {
        "path": str(output),
        "source_path": str(source),
        "source_overwritten": False,
        "source_sha256": report["source_sha256"],
        "export_sha256": _file_hash(output),
        "burned_in_annotation_risk": report["burned_in_annotation_risk"],
        "private_tags_removed": report["private_tag_count"],
        "pixel_data_unchanged": verification["pixel_data_unchanged"],
        "verification": verification,
        "safety_note": "Prototype de-identified DICOM; manual tag and pixel verification remains required before sharing.",
    }
