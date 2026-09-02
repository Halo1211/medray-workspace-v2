from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


VALIDATION_EVIDENCE_FIELDS = [
    "protocol_id",
    "dataset_name",
    "held_out_split",
    "case_count",
    "label_count",
    "metric_summary",
    "false_alert_burden",
    "known_failures",
    "subgroup_coverage",
    "reviewer",
    "review_date",
    "artifact_hash",
    "weights_filename",
]

WEIGHT_SUFFIXES = {".pt", ".pth", ".bin", ".safetensors", ".onnx", ".gguf"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("\r", "").split("\n") if item.strip()]
    return []


def _count(value: Any) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def _summary(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items() if _text(item)}
    text = _text(value)
    return {"summary": text} if text else {}


def _coverage(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    return {
        "anatomy": _string_list(raw.get("anatomy")),
        "views": _string_list(raw.get("views")),
        "age_groups": _string_list(raw.get("age_groups")),
        "notes": _text(raw.get("notes") if raw else value),
    }


def normalize_validation_evidence(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    return {
        "protocol_id": _text(raw.get("protocol_id")),
        "dataset_name": _text(raw.get("dataset_name")),
        "held_out_split": _text(raw.get("held_out_split")),
        "case_count": _count(raw.get("case_count")),
        "label_count": _count(raw.get("label_count")),
        "metric_summary": _summary(raw.get("metric_summary")),
        "false_alert_burden": _summary(raw.get("false_alert_burden")),
        "missed_reference_summary": _summary(raw.get("missed_reference_summary")),
        "known_failures": _string_list(raw.get("known_failures")),
        "subgroup_coverage": _coverage(raw.get("subgroup_coverage")),
        "reviewer": _text(raw.get("reviewer")),
        "review_date": _text(raw.get("review_date")),
        "artifact_hash": _text(raw.get("artifact_hash")).lower(),
        "artifact_hash_algorithm": _text(raw.get("artifact_hash_algorithm")) or "sha256",
        "weights_filename": _text(raw.get("weights_filename")),
        "report_reference": _text(raw.get("report_reference")),
        "evidence_scope": "local_research_prototype_only",
    }


def validation_evidence_assessment(value: Any) -> dict[str, Any]:
    evidence = normalize_validation_evidence(value)
    missing: list[str] = []
    for field in VALIDATION_EVIDENCE_FIELDS:
        item = evidence.get(field)
        if field in {"case_count", "label_count"}:
            if item is None or item <= 0:
                missing.append(field)
        elif field in {"metric_summary", "false_alert_burden"}:
            if not isinstance(item, dict) or not item:
                missing.append(field)
        elif field == "known_failures":
            if not item:
                missing.append(field)
        elif field == "subgroup_coverage":
            coverage = item if isinstance(item, dict) else {}
            if not any(coverage.get(key) for key in ("anatomy", "views", "age_groups", "notes")):
                missing.append(field)
        elif not _text(item):
            missing.append(field)
    artifact_hash = evidence.get("artifact_hash", "")
    if artifact_hash and (len(artifact_hash) != 64 or any(ch not in "0123456789abcdef" for ch in artifact_hash)):
        missing.append("artifact_hash_valid_sha256")
    complete = not missing
    return {
        "status": "locally_validated_for_protocol" if complete else "structured_evidence_incomplete",
        "complete": complete,
        "missing_fields": missing,
        "confidence_posture": "protocol_bounded_research_evidence" if complete else "conservative_unvalidated",
        "safety_note": "Local research/prototype evidence only; this does not establish clinical performance.",
    }


def hash_artifact_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bind_artifact_identity(value: Any, artifact_path: Path) -> dict[str, Any]:
    evidence = normalize_validation_evidence(value)
    candidates = [artifact_path] if artifact_path.is_file() else [item for item in artifact_path.rglob("*") if item.is_file() and item.suffix.lower() in WEIGHT_SUFFIXES]
    filename = evidence.get("weights_filename", "")
    selected: Path | None = None
    if filename:
        candidate = (artifact_path / filename).resolve() if artifact_path.is_dir() else artifact_path.resolve()
        root = artifact_path.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("Validation evidence weights_filename must stay inside the local artifact.")
        if not candidate.exists() or not candidate.is_file():
            raise ValueError("Validation evidence weights_filename was not found in the local artifact.")
        selected = candidate
    elif len(candidates) == 1:
        selected = candidates[0]

    if selected:
        relative = selected.name if artifact_path.is_file() else selected.relative_to(artifact_path).as_posix()
        computed = hash_artifact_file(selected)
        supplied = evidence.get("artifact_hash", "")
        if supplied and supplied != computed:
            raise ValueError("Validation evidence artifact_hash does not match the selected weights file.")
        evidence["weights_filename"] = relative
        evidence["artifact_hash"] = computed
        evidence["artifact_hash_algorithm"] = "sha256"
    return evidence
