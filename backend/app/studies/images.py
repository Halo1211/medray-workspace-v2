from __future__ import annotations

from copy import deepcopy
from typing import Any

REVIEW_METADATA_FIELDS = {"LocalRecordID", "PatientID", "AccessionNumber", "StudyDescription", "ClinicalIndication", "CaseNotes"}


def annotation_matches_image(annotation: dict[str, Any], image: dict[str, Any], first_image: bool = False, images: list[dict[str, Any]] | None = None) -> bool:
    source_id = str(annotation.get("source_image_id") or "")
    if source_id in {"", "primary"}:
        return first_image
    if source_id == str(image.get("image_id") or ""):
        return True
    # A canonical image ID takes priority over legacy aliases. Reimporting
    # the same DICOM must not attach the first image's annotations to a copy.
    if any(source_id == str(item.get("image_id") or "") for item in (images or [])):
        return False
    accepted: set[str] = set()
    sop_uid = str(image.get("sop_instance_uid") or "")
    if sop_uid and sum(str(item.get("sop_instance_uid") or "") == sop_uid for item in (images or [image])) == 1:
        accepted.add(sop_uid)
    filename = str(image.get("filename") or "")
    if filename and sum(str(item.get("filename") or "") == filename for item in (images or [])) == 1:
        accepted.add(filename)
    return source_id in accepted


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _image_id(metadata: dict[str, Any], case_id: str, index: int) -> str:
    return str(metadata.get("SOPInstanceUID") or f"{case_id}:{index}")


def study_image_from_ingest(image: dict[str, Any], case_id: str, index: int) -> dict[str, Any]:
    metadata = image.get("metadata") if isinstance(image.get("metadata"), dict) else {}
    return {
        "image_id": _image_id(metadata, case_id, index),
        "index": index,
        "filename": str(image.get("filename") or f"image-{index + 1}"),
        "image_path": image.get("stored_path"),
        "source_path": image.get("source_path"),
        "is_dicom": bool(image.get("is_dicom")),
        "preview_path": image.get("preview_path"),
        "format": image.get("format") or metadata.get("format"),
        "width": image.get("width") or metadata.get("width"),
        "height": image.get("height") or metadata.get("height"),
        "metadata": metadata,
        "file_hashes": image.get("hashes") if isinstance(image.get("hashes"), dict) else {},
        "study_id": str(metadata.get("StudyInstanceUID") or case_id),
        "series_id": str(metadata.get("SeriesInstanceUID") or ""),
        "sop_instance_uid": str(metadata.get("SOPInstanceUID") or ""),
        "view": str(metadata.get("ViewPosition") or ""),
        "laterality": str(metadata.get("Laterality") or ""),
    }


def normalize_case_images(case: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(case)
    case_id = str(normalized.get("case_id") or "case")
    # Older payloads occasionally contain an `images` key with a malformed
    # value. Treat it like a missing collection so the legacy top-level image
    # fields can still be migrated instead of silently producing an empty
    # study.
    images = _list_of_dicts(normalized.get("images"))
    if not images and normalized.get("image_path"):
        metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
        file_hashes = normalized.get("file_hashes") if isinstance(normalized.get("file_hashes"), dict) else {}
        input_hash = file_hashes.get("input") if isinstance(file_hashes.get("input"), dict) else {}
        images = [
            {
                "image_id": _image_id(metadata, case_id, 0),
                "index": 0,
                "filename": str(normalized.get("title") or "image-1"),
                "image_path": normalized.get("image_path"),
                "source_path": normalized.get("source_path") or input_hash.get("path"),
                "is_dicom": str(metadata.get("format") or "").upper() == "DICOM",
                "preview_path": normalized.get("image_preview"),
                "format": metadata.get("format"),
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "metadata": metadata,
                "file_hashes": file_hashes,
                "study_id": str(metadata.get("StudyInstanceUID") or case_id),
                "series_id": str(metadata.get("SeriesInstanceUID") or ""),
                "sop_instance_uid": str(metadata.get("SOPInstanceUID") or ""),
                "view": str(metadata.get("ViewPosition") or ""),
                "laterality": str(metadata.get("Laterality") or ""),
            }
        ]

    clean_images: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, image in enumerate(images):
        metadata = image.get("metadata") if isinstance(image.get("metadata"), dict) else {}
        image_id = str(image.get("image_id") or _image_id(metadata, case_id, index))
        if image_id in seen:
            image_id = f"{case_id}:{index}"
            suffix = 1
            while image_id in seen:
                image_id = f"{case_id}:{index}:{suffix}"
                suffix += 1
        seen.add(image_id)
        clean_images.append({**image, "image_id": image_id, "index": index, "metadata": metadata})

    active_id = str(normalized.get("active_image_id") or "")
    if active_id not in seen:
        active_id = clean_images[0]["image_id"] if clean_images else ""
    normalized["images"] = clean_images
    normalized["active_image_id"] = active_id
    raw_analyses = normalized.get("analyses_by_image") if isinstance(normalized.get("analyses_by_image"), dict) else {}
    # Keep only usable per-image analysis mappings. This prevents a corrupted
    # legacy value such as `null`, a string, or a list from leaking into the
    # frontend as if it were an AnalysisResult.
    analyses = {
        str(image_id): analysis
        for image_id, analysis in raw_analyses.items()
        if str(image_id) in seen and isinstance(analysis, dict)
    }
    # Migrate a legacy top-level analysis only when no usable per-image
    # mapping exists. Otherwise it may belong to the previously active image.
    legacy_analysis = normalized.get("analysis")
    if active_id and not analyses and isinstance(legacy_analysis, dict):
        analyses[active_id] = legacy_analysis
    normalized["analyses_by_image"] = analyses
    active = next((image for image in clean_images if image["image_id"] == active_id), None)
    if active:
        normalized["image_path"] = active.get("image_path")
        normalized["image_preview"] = active.get("preview_path")
        normalized["metadata"] = active.get("metadata") or {}
        reviewer_metadata = normalized.get("reviewer_metadata")
        if isinstance(reviewer_metadata, dict):
            normalized["metadata"] = {
                **{key: value for key, value in normalized["metadata"].items() if key not in REVIEW_METADATA_FIELDS},
                **{key: value for key, value in reviewer_metadata.items() if key in REVIEW_METADATA_FIELDS},
            }
        normalized["file_hashes"] = active.get("file_hashes") if isinstance(active.get("file_hashes"), dict) else {}
        if active_id in analyses:
            normalized["analysis"] = analyses[active_id]
            normalized["report"] = (analyses[active_id] or {}).get("report") if isinstance(analyses[active_id], dict) else None
        elif len(clean_images) > 1:
            normalized["analysis"] = None
            normalized["report"] = None
    return normalized


def active_study_image(case: dict[str, Any], image_id: str = "") -> dict[str, Any] | None:
    normalized = normalize_case_images(case)
    wanted = image_id or str(normalized.get("active_image_id") or "")
    return next((image for image in normalized.get("images", []) if image.get("image_id") == wanted), None)
