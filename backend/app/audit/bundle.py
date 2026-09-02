from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.annotations.exporter import build_annotation_review_bundle
from app.config import get_settings
from app.dicom.safety import dicom_safety_report
from app.model_registry.cards import cards_for_trace
from app.reports.generator import build_grounded_review_statements
from app.results.differential import build_differential_assistance
from app.studies.images import normalize_case_images
from app.storage.db import safe_path_component


AUDIT_SCHEMA_VERSION = "0.4.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def hash_file(path: str | None, algorithm: str = "sha256") -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {"path": str(path), "algorithm": algorithm, "status": "missing"}

    digest = hashlib.new(algorithm)
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(p),
        "algorithm": algorithm,
        "digest": digest.hexdigest(),
        "bytes": p.stat().st_size,
        "status": "ok",
    }


def case_hashes(case: dict[str, Any]) -> dict[str, Any]:
    existing = case.get("file_hashes") if isinstance(case.get("file_hashes"), dict) else {}
    input_hash = existing.get("input") or hash_file(case.get("image_path"))
    preview_hash = existing.get("preview") or hash_file(case.get("image_preview"))
    return {"input": input_hash, "preview": preview_hash}


def _dicom_safety_summaries(case: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = []
    for image in _list_of_dicts(case.get("images")):
        source = str(image.get("source_path") or "")
        if not source or not bool(image.get("is_dicom")):
            continue
        try:
            report = dicom_safety_report(source)
            summaries.append({
                "source_image_id": image.get("image_id"),
                "source_image_index": image.get("index"),
                "source_sha256": report.get("source_sha256"),
                "private_tag_count": report.get("private_tag_count"),
                "burned_in_annotation_risk": report.get("burned_in_annotation_risk"),
                "dicomweb_status": report.get("dicomweb_status"),
                "warnings": report.get("warnings") or [],
            })
        except Exception as exc:
            summaries.append({"source_image_id": image.get("image_id"), "status": "safety_scan_failed", "error": str(exc)})
    return summaries


def build_audit_bundle(case: dict[str, Any]) -> dict[str, Any]:
    case = normalize_case_images(case)
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    model_trace = _list_of_dicts(analysis.get("model_trace"))
    runtime_snapshot = analysis.get("runtime_snapshot") if isinstance(analysis.get("runtime_snapshot"), dict) else (
        case.get("runtime") if isinstance(case.get("runtime"), dict) else {}
    )
    hashes = analysis.get("input_hashes") if isinstance(analysis.get("input_hashes"), dict) else case_hashes(case)
    annotations = _list_of_dicts(case.get("annotations")) or _list_of_dicts(analysis.get("annotations"))
    report_value = case.get("report") or analysis.get("report")
    report = report_value if isinstance(report_value, dict) else {}
    result_cards = _list_of_dicts(analysis.get("result_cards"))
    findings = _list_of_dicts(analysis.get("findings"))
    warnings = [str(item) for item in analysis.get("warnings")] if isinstance(analysis.get("warnings"), list) else []
    grounded_review_statements = build_grounded_review_statements(case, "id")
    differential_assistance = build_differential_assistance(result_cards, report)
    review_counts = {
        status: sum(1 for card in result_cards if card.get("review_status") == status)
        for status in sorted({str(card.get("review_status") or "unreviewed") for card in result_cards})
    }
    annotation_review_summary = build_annotation_review_bundle(case)["review_summary"]
    model_cards = cards_for_trace(model_trace)
    validation_evidence_used = [
        {
            "model_id": card.get("id"),
            "human_reviewed": bool(card.get("human_reviewed")),
            "validation_evidence_status": card.get("validation_evidence_status", "not_applicable_or_missing"),
            "confidence_posture": card.get("confidence_posture", "conservative_unvalidated"),
            "validation_evidence": card.get("validation_evidence") or {},
        }
        for card in model_cards
        if str(card.get("id") or "").startswith("local:")
    ]

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "case": {
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "created_at": case.get("created_at"),
            "updated_at": case.get("updated_at"),
            "metadata": case.get("metadata") or {},
            "active_image_id": case.get("active_image_id"),
            "study_images": case.get("images") or [],
        },
        "input_hashes": hashes,
        "runtime_snapshot": runtime_snapshot,
        "immutable_model_trace": model_trace,
        "model_cards": model_cards,
        "validation_evidence_used": validation_evidence_used,
        "dicom_safety": _dicom_safety_summaries(case),
        "output_summary": {
            "warnings": warnings,
            "findings_count": len(findings),
            "result_cards_count": len(result_cards),
            "result_card_review_status_counts": review_counts,
            "grounded_review_statement_count": sum(1 for item in grounded_review_statements if item.get("promoted_to_report")),
            "grounded_review_statements": grounded_review_statements,
            "differential_assistance_count": len(differential_assistance),
            "differential_assistance": differential_assistance,
            "anatomy_route": analysis.get("anatomy_route") or {},
            "annotations_count": len(annotations),
            "annotations_by_image": {
                str(image.get("image_id")): sum(
                1
                for annotation in annotations
                    if (
                        str(annotation.get("source_image_id") or "")
                        in {str(image.get("image_id") or ""), str(image.get("sop_instance_uid") or ""), str(image.get("filename") or "")}
                        or (
                            int(image.get("index") or 0) == 0
                            and str(annotation.get("source_image_id") or "") in {"", "primary"}
                        )
                    )
                )
                for image in case.get("images", [])
            },
            "annotation_review_summary": annotation_review_summary,
            "report_watermark": report.get("watermark"),
        },
        "why_this_output_exists": {
            "image": "Input and preview hashes identify the local files used for this case.",
            "runtime": "The runtime snapshot records backend and model settings active when analysis was run.",
            "trace": "The immutable model trace lists each pipeline stage, backend, selected model/tool, status, and timestamp.",
            "result_cards": "Result cards link candidate findings, evidence, uncertainty, annotation references, and human review status.",
            "grounded_review_statements": "Grounded review statements are promoted only from reviewed result cards or standalone reviewed annotations; rejected and unreviewed signals remain provenance, not report findings.",
            "differential_assistance": "Tentative differential considerations are organized from structured result-card evidence, counter-evidence, and missing information; they are not confirmed diagnoses or triage decisions.",
            "annotations": "Annotation review summary separates original AI output, reviewed state, manual marks, and recorded changes.",
            "anatomy_route": "The anatomy route records the selected X-ray profile, source evidence, confidence, view/laterality, model slot, and support boundary.",
            "cards": "Model cards describe whether each model is demo, placeholder, or externally configured.",
            "validation_evidence": "For active local artifacts, structured evidence records the bounded local research protocol, coverage, metrics, failure burden, reviewer, and exact weights hash used. Missing evidence keeps confidence conservative.",
            "safety": "Demo/fallback outputs are non-diagnostic and must not be treated as clinical findings.",
        },
    }


def export_audit_bundle(case: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    bundle = build_audit_bundle(case)
    case_id = str(case.get("case_id") or "unknown")
    path = settings.exports_dir / f"{safe_path_component(case_id, 'case')}_audit_bundle.json"
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "bundle": bundle}
