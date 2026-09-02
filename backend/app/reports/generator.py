from __future__ import annotations

import json
from pathlib import Path
import textwrap
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.results.differential import report_differential_assistance
from app.storage.db import safe_path_component


DISCLAIMER_ID = "AI-assisted draft, not for standalone clinical diagnosis. Untuk riset/edukasi/prototyping; perlu verifikasi radiolog/dokter."
PROMOTED_REVIEW_STATUSES = {"accepted", "uncertain", "needs_follow_up"}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _result_card_text(result_cards: list[dict[str, Any]], language: str) -> str:
    if not result_cards:
        return "-"
    lines = []
    for card in result_cards:
        score = card.get("probability") if card.get("probability") is not None else card.get("confidence")
        score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else "n/a"
        action = card.get("next_safe_action") or "Review by a qualified radiologist/physician."
        if language == "en":
            lines.append(f"- {card.get('finding', '-')}: {card.get('candidate_diagnosis', '-')} ({card.get('status', '-')}, score {score_text}). Action: {action}")
        else:
            lines.append(f"- {card.get('finding', '-')}: {card.get('candidate_diagnosis', '-')} ({card.get('status', '-')}, skor {score_text}). Tindak lanjut aman: {action}")
    return "\n".join(lines)


def _score_text(card: dict[str, Any]) -> str:
    score = card.get("probability") if card.get("probability") is not None else card.get("confidence")
    return f"{float(score):.2f}" if isinstance(score, (int, float)) else "n/a"


def _all_annotations(case: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for annotation in [*_list_of_dicts(case.get("annotations")), *_list_of_dicts(analysis.get("annotations"))]:
        annotation_id = str(annotation.get("id") or "")
        if annotation_id and annotation_id in seen:
            continue
        if annotation_id:
            seen.add(annotation_id)
        annotations.append(annotation)
    return annotations


def _report_for_language(case: dict[str, Any], analysis: dict[str, Any], language: str) -> dict[str, Any]:
    report_value = case.get("report") or analysis.get("report")
    report = report_value if isinstance(report_value, dict) else {}
    wanted = "en" if language == "en" else "id"
    stored_language = str(report.get("language") or "id")
    if report and stored_language == wanted:
        return report

    quality = analysis.get("image_quality") if isinstance(analysis.get("image_quality"), dict) else {}
    reading = analysis.get("systematic_reading") if isinstance(analysis.get("systematic_reading"), dict) else {}
    cards = _list_of_dicts(analysis.get("result_cards"))
    exposure = str(quality.get("exposure") or "unknown")
    score = quality.get("score", "n/a")
    body_region = str(reading.get("body_region") or "unknown/general X-ray")
    card_text = _result_card_text(cards, wanted)
    if wanted == "en":
        return {
            "indication": "Not provided.",
            "technique": "Conventional radiograph; projection details follow available metadata and reviewer input.",
            "comparison": "Unavailable.",
            "findings": f"Estimated image quality: {exposure} (score {score}). Body-region template: {body_region}. Reviewable result cards:\n{card_text}",
            "impression": "AI-assisted non-diagnostic draft reconstructed from structured result cards; no finding is confirmed without qualified image review.",
            "recommendation": "Correlate clinically and verify by a qualified radiologist/physician.",
            "language": "en",
            "watermark": "AI-assisted draft, not for standalone clinical diagnosis.",
        }
    return {
        "indication": "Belum diisi.",
        "technique": "Radiografi konvensional; detail proyeksi mengikuti metadata dan masukan reviewer yang tersedia.",
        "comparison": "Tidak tersedia.",
        "findings": f"Kualitas gambar diperkirakan {exposure} (skor {score}). Template area: {body_region}. Result card yang dapat direview:\n{card_text}",
        "impression": "Draf non-diagnostik berbantuan AI yang disusun ulang dari result card terstruktur; tidak ada temuan yang dikonfirmasi tanpa review gambar oleh klinisi berkualifikasi.",
        "recommendation": "Korelasikan secara klinis dan verifikasi oleh radiolog/dokter.",
        "language": "id",
        "watermark": "AI-assisted draft, not for standalone clinical diagnosis.",
    }


def _wrapped_pdf_lines(text: str, width: int = 105) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        lines.extend(textwrap.wrap(raw_line, width=width, replace_whitespace=False, drop_whitespace=True) or [""])
    return lines


def _annotation_location(annotation: dict[str, Any], language: str) -> str:
    coordinate = annotation.get("coordinate") if isinstance(annotation.get("coordinate"), dict) else {}
    coordinate_type = coordinate.get("type") or "bbox"
    if coordinate_type == "point":
        try:
            return f"point x={float(coordinate.get('x', 0)):.0f}, y={float(coordinate.get('y', 0)):.0f}"
        except (TypeError, ValueError):
            return "point"
    if coordinate_type == "polygon":
        points = coordinate.get("points") if isinstance(coordinate.get("points"), list) else []
        return f"polygon ({len(points)} vertices)"
    if coordinate_type not in {"bbox", "grounding_box"}:
        return str(coordinate_type)
    try:
        x = float(coordinate.get("x", 0))
        y = float(coordinate.get("y", 0))
        width = float(coordinate.get("width", 0))
        height = float(coordinate.get("height", 0))
    except (TypeError, ValueError):
        return str(coordinate_type)
    label = "box" if language == "en" else "kotak"
    return f"{label} x={x:.0f}, y={y:.0f}, w={width:.0f}, h={height:.0f}"


def _linked_annotation_text(card: dict[str, Any], annotations_by_id: dict[str, dict[str, Any]], language: str) -> str:
    annotation_refs = [str(ref) for ref in card.get("annotation_refs") if ref] if isinstance(card.get("annotation_refs"), list) else []
    linked = [annotations_by_id[ref] for ref in annotation_refs if ref in annotations_by_id]
    reviewed = [annotation for annotation in linked if str(annotation.get("review_status") or "unreviewed") in PROMOTED_REVIEW_STATUSES]
    if not reviewed:
        return "no reviewed linked annotation" if language == "en" else "belum ada anotasi tertaut yang sudah direview"
    parts = []
    for annotation in reviewed:
        status = str(annotation.get("review_status") or "unreviewed").replace("_", " ")
        parts.append(f"{annotation.get('label', '-')}: {status}, {_annotation_location(annotation, language)}")
    return "; ".join(parts)


def build_grounded_review_statements(case: dict[str, Any], language: str = "id") -> list[dict[str, Any]]:
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    result_cards = _list_of_dicts(analysis.get("result_cards"))
    annotations = _all_annotations(case, analysis)
    annotations_by_id = {str(annotation.get("id")): annotation for annotation in annotations if annotation.get("id")}
    promoted_cards = [
        card
        for card in result_cards
        if str(card.get("review_status") or "unreviewed") in PROMOTED_REVIEW_STATUSES
    ]
    unpromoted_cards = [
        card
        for card in result_cards
        if str(card.get("review_status") or "unreviewed") not in PROMOTED_REVIEW_STATUSES
    ]
    standalone_annotations = [
        annotation
        for annotation in annotations
        if str(annotation.get("review_status") or "unreviewed") in PROMOTED_REVIEW_STATUSES
        and not annotation.get("linked_result_card_ids")
    ]

    statements: list[dict[str, Any]] = []
    for card in promoted_cards:
        review_status = str(card.get("review_status") or "unreviewed").replace("_", " ")
        finding = card.get("finding", "-")
        candidate = card.get("candidate_diagnosis") or ("AI candidate diagnosis" if language == "en" else "kandidat diagnosis AI")
        linked_text = _linked_annotation_text(card, annotations_by_id, language)
        reviewed_annotation_refs = [
            ref
            for ref in ([str(item) for item in card.get("annotation_refs") if item] if isinstance(card.get("annotation_refs"), list) else [])
            if ref in annotations_by_id
            and str(annotations_by_id[ref].get("review_status") or "unreviewed") in PROMOTED_REVIEW_STATUSES
        ]
        reviewer_note = str(card.get("reviewer_note") or "").strip()
        source_image_ids = sorted({str(annotations_by_id[ref].get("source_image_id") or "") for ref in reviewed_annotation_refs if annotations_by_id[ref].get("source_image_id")}) or [str(item) for item in card.get("source_image_ids", []) if item] if isinstance(card.get("source_image_ids"), list) else []
        source_series_ids = sorted({str(annotations_by_id[ref].get("source_series_id") or "") for ref in reviewed_annotation_refs if annotations_by_id[ref].get("source_series_id")}) or [str(item) for item in card.get("source_series_ids", []) if item] if isinstance(card.get("source_series_ids"), list) else []
        source_views = sorted({str(annotations_by_id[ref].get("source_view") or "") for ref in reviewed_annotation_refs if annotations_by_id[ref].get("source_view")}) or [str(item) for item in card.get("source_views", []) if item] if isinstance(card.get("source_views"), list) else []
        note_text = f" Reviewer note: {reviewer_note}" if language == "en" and reviewer_note else f" Catatan reviewer: {reviewer_note}" if reviewer_note else ""
        if language == "en":
            text = (
                f"Reviewed {review_status} candidate: {finding} -> {candidate} "
                f"(model status {card.get('status', '-')}, score {_score_text(card)}). Evidence: {linked_text}.{note_text}"
            )
        else:
            text = (
                f"Kandidat sudah direview ({review_status}): {finding} -> {candidate} "
                f"(status model {card.get('status', '-')}, skor {_score_text(card)}). Bukti: {linked_text}.{note_text}"
            )
        statements.append({
            "id": f"grounded:{card.get('id', finding)}",
            "kind": "reviewed_result_card",
            "promoted_to_report": True,
            "text": text,
            "result_card_id": card.get("id", ""),
            "annotation_refs": reviewed_annotation_refs,
            "review_status": card.get("review_status") or "unreviewed",
            "finding": finding,
            "candidate_diagnosis": candidate,
            "model_status": card.get("status", ""),
            "score": _score_text(card),
            "reviewer_note": reviewer_note,
            "source_image_ids": source_image_ids,
            "source_series_ids": source_series_ids,
            "source_views": source_views,
        })

    for annotation in standalone_annotations:
        review_status = str(annotation.get("review_status") or "unreviewed").replace("_", " ")
        reviewer_note = str(annotation.get("reviewer_note") or "").strip()
        note_text = f" Reviewer note: {reviewer_note}" if language == "en" and reviewer_note else f" Catatan reviewer: {reviewer_note}" if reviewer_note else ""
        if language == "en":
            text = f"Standalone reviewed annotation ({review_status}): {annotation.get('label', '-')} at {_annotation_location(annotation, language)}.{note_text}"
        else:
            text = f"Anotasi mandiri sudah direview ({review_status}): {annotation.get('label', '-')} pada {_annotation_location(annotation, language)}.{note_text}"
        statements.append({
            "id": f"grounded:{annotation.get('id', annotation.get('label', 'annotation'))}",
            "kind": "standalone_reviewed_annotation",
            "promoted_to_report": True,
            "text": text,
            "result_card_id": "",
            "annotation_refs": [annotation.get("id")] if annotation.get("id") else [],
            "review_status": annotation.get("review_status") or "unreviewed",
            "finding": annotation.get("label", ""),
            "candidate_diagnosis": "",
            "model_status": "",
            "score": _score_text(annotation),
            "reviewer_note": reviewer_note,
            "source_image_ids": [annotation.get("source_image_id")] if annotation.get("source_image_id") else [],
            "source_series_ids": [annotation.get("source_series_id")] if annotation.get("source_series_id") else [],
            "source_views": [annotation.get("source_view")] if annotation.get("source_view") else [],
        })

    rejected = [card for card in unpromoted_cards if str(card.get("review_status") or "unreviewed") == "rejected"]
    unreviewed = [card for card in unpromoted_cards if str(card.get("review_status") or "unreviewed") == "unreviewed"]
    if rejected or unreviewed:
        if language == "en":
            text = f"Not promoted into report findings: {len(rejected)} rejected and {len(unreviewed)} unreviewed result card(s)."
        else:
            text = f"Tidak dipromosikan menjadi temuan laporan: {len(rejected)} rejected dan {len(unreviewed)} result card belum direview."
        statements.append({
            "id": "grounded:not-promoted",
            "kind": "not_promoted_summary",
            "promoted_to_report": False,
            "text": text,
            "result_card_id": "",
            "annotation_refs": [],
            "review_status": "mixed",
            "rejected_result_card_count": len(rejected),
            "unreviewed_result_card_count": len(unreviewed),
        })
    if not statements:
        if language == "en":
            text = "No reviewed result card or standalone reviewed annotation has been promoted into a grounded report statement yet."
        else:
            text = "Belum ada result card atau anotasi mandiri yang sudah direview untuk dipromosikan menjadi statement laporan grounded."
        statements.append({
            "id": "grounded:none",
            "kind": "empty_state",
            "promoted_to_report": False,
            "text": text,
            "result_card_id": "",
            "annotation_refs": [],
            "review_status": "unreviewed",
        })
    return statements


def _grounded_review_statement_text(case: dict[str, Any], analysis: dict[str, Any], language: str) -> str:
    scoped_case = {**case, "analysis": analysis}
    return "\n".join(f"- {statement['text']}" for statement in build_grounded_review_statements(scoped_case, language))


def report_json_payload(case: dict[str, Any], language: str = "id") -> dict[str, Any]:
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    report_value = _report_for_language(case, analysis, language)
    return {
        "schema_version": "0.4.12",
        "case_id": case.get("case_id"),
        "title": case.get("title"),
        "active_image_id": case.get("active_image_id"),
        "study_images": _list_of_dicts(case.get("images")),
        "language": "en" if language == "en" else "id",
        "report": report_value if isinstance(report_value, dict) else {},
        "grounded_review_statements": build_grounded_review_statements(case, language),
        "differential_assistance": report_differential_assistance(analysis.get("result_cards"), report_value),
        "result_cards": _list_of_dicts(analysis.get("result_cards")),
        "annotations": _all_annotations(case, analysis),
        "markdown": report_markdown(case, language),
        "safety_note": DISCLAIMER_ID,
    }


def report_markdown(case: dict[str, Any], language: str = "id") -> str:
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    report_value = _report_for_language(case, analysis, language)
    report = report_value if isinstance(report_value, dict) else {}
    reading = analysis.get("systematic_reading") if isinstance(analysis.get("systematic_reading"), dict) else {}
    quality = analysis.get("image_quality") if isinstance(analysis.get("image_quality"), dict) else {}
    result_cards = _list_of_dicts(analysis.get("result_cards"))
    title = case.get("title") or case.get("case_id")
    if language == "en":
        heading = "MedRay v2 Radiology Draft"
        labels = ["Case Identity", "Indication", "Technique", "Image Quality", "Result Cards", "Grounded Review Statements", "Findings", "Impression", "Differential Diagnosis", "Recommendation", "AI Limitation"]
    else:
        heading = "Draf Laporan Radiologi MedRay v2"
        labels = ["Identitas Kasus", "Indikasi", "Teknik Pemeriksaan", "Kualitas Gambar", "Result Cards", "Statement Review Grounded", "Temuan", "Kesan", "Diagnosis Banding", "Rekomendasi", "Catatan Keterbatasan AI"]
    differential = report_differential_assistance(result_cards, report)
    ddx_lines = []
    for item in differential:
        evidence_for = "; ".join(_string for _string in item.get("evidence_for", []) if isinstance(_string, str)) or "-"
        evidence_against = "; ".join(_string for _string in item.get("evidence_against", []) if isinstance(_string, str)) or "-"
        missing = "; ".join(_string for _string in item.get("missing_information", []) if isinstance(_string, str)) or "-"
        if language == "en":
            ddx_lines.append(f"- Tentative: {item.get('label', '-')}. Evidence for: {evidence_for}. Evidence against/limitations: {evidence_against}. Missing information: {missing}.")
        else:
            ddx_lines.append(f"- Tentatif: {item.get('label', '-')}. Bukti mendukung: {evidence_for}. Bukti menentang/keterbatasan: {evidence_against}. Informasi belum tersedia: {missing}.")
    ddx = "\n".join(ddx_lines) or ("No structured differential candidate available." if language == "en" else "Belum ada kandidat diferensial terstruktur.")
    sections = [
        (labels[0], f"{title} ({case.get('case_id')})"),
        (labels[1], report.get("indication", "")),
        (labels[2], report.get("technique", "")),
        (labels[3], f"{quality.get('exposure', 'unknown')} / score {quality.get('score', 'n/a')}"),
        (labels[4], _result_card_text(result_cards, language)),
        (labels[5], _grounded_review_statement_text(case, analysis, language)),
        (labels[6], report.get("findings", "")),
        (labels[7], report.get("impression", "")),
        (labels[8], ddx),
        (labels[9], report.get("recommendation", "")),
        (labels[10], DISCLAIMER_ID),
    ]
    body = [f"# {heading}", ""]
    for label, value in sections:
        body.extend([f"## {label}", str(value or "-"), ""])
    return "\n".join(body)


def export_report(case: dict[str, Any], fmt: str = "markdown", language: str = "id") -> dict[str, str]:
    settings = get_settings()
    case_id = case.get("case_id", "case")
    out_dir = settings.exports_dir / safe_path_component(case_id, "case")
    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path = out_dir / "report.json"
        path.write_text(json.dumps(report_json_payload(case, language), indent=2, ensure_ascii=False), encoding="utf-8")
        return {"path": str(path), "content_type": "application/json"}
    if fmt == "pdf":
        path = out_dir / "report.pdf"
        text = report_markdown(case, language).replace("# ", "").replace("## ", "")
        c = canvas.Canvas(str(path), pagesize=A4)
        y = 800
        c.setFont("Helvetica", 9)
        for line in _wrapped_pdf_lines(text):
            if y < 50:
                c.showPage()
                c.setFont("Helvetica", 9)
                y = 800
            c.drawString(40, y, line)
            y -= 14
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(40, 28, "AI-assisted draft, not for standalone clinical diagnosis.")
        c.save()
        return {"path": str(path), "content_type": "application/pdf"}
    path = out_dir / "report.md"
    path.write_text(report_markdown(case, language), encoding="utf-8")
    return {"path": str(path), "content_type": "text/markdown"}
