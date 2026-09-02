from __future__ import annotations

from typing import Any


PROMOTED_REVIEW_STATUSES = {"accepted", "uncertain", "needs_follow_up"}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def build_differential_assistance(
    result_cards: Any,
    report: Any = None,
) -> list[dict[str, Any]]:
    """Build tentative differential considerations from traceable result cards only."""
    report_data = report if isinstance(report, dict) else {}
    comparison = str(report_data.get("comparison") or "").strip().lower()
    comparison_missing = not comparison or comparison in {"-", "tidak tersedia.", "tidak tersedia", "unavailable"}
    candidates: list[dict[str, Any]] = []

    for card in _list_of_dicts(result_cards):
        status = str(card.get("status") or "uncertain")
        review_status = str(card.get("review_status") or "unreviewed")
        candidate = str(card.get("candidate_diagnosis") or "").strip()
        if status == "negative" or review_status == "rejected" or not candidate or "no ai candidate diagnosis" in candidate.lower():
            continue

        evidence_for: list[str] = []
        evidence_against: list[str] = []
        for evidence in _list_of_dicts(card.get("evidence")):
            text = str(evidence.get("text") or "").strip()
            if not text:
                continue
            if str(evidence.get("kind") or "") == "limitation":
                evidence_against.append(text)
            else:
                evidence_for.append(text)
        if not evidence_for:
            evidence_for.append(f"Structured research signal: {card.get('finding') or 'unspecified finding'}.")
        if not evidence_against:
            evidence_against.append("No case-specific counter-evidence has been established in the structured output.")

        missing_information = ["Clinical history and examination indication are needed for correlation."]
        if comparison_missing:
            missing_information.append("Prior comparison is unavailable.")
        if not _string_list(card.get("annotation_refs")):
            missing_information.append("No reviewed localization is linked to this consideration.")
        if str(card.get("validation_status") or "not_validated") != "local_agreement_checked":
            missing_information.append("Local protocol agreement evidence is absent or incomplete.")

        candidates.append(
            {
                "id": f"differential:{card.get('id') or len(candidates) + 1}",
                "kind": "tentative_candidate",
                "label": candidate,
                "finding": str(card.get("finding") or ""),
                "tentative": True,
                "review_status": review_status,
                "eligible_for_report_review": review_status in PROMOTED_REVIEW_STATUSES,
                "evidence_for": evidence_for[:6],
                "evidence_against": evidence_against[:6],
                "missing_information": missing_information,
                "uncertainty": str(card.get("uncertainty_reason") or "Requires qualified human review."),
                "next_safe_action": str(card.get("next_safe_action") or "Review by a qualified radiologist/physician."),
                "result_card_id": str(card.get("id") or ""),
                "annotation_refs": _string_list(card.get("annotation_refs")),
                "source_image_ids": _string_list(card.get("source_image_ids")),
                "source_series_ids": _string_list(card.get("source_series_ids")),
                "source_views": _string_list(card.get("source_views")),
                "safety_note": "Tentative diagnostic assistance only; not a confirmed diagnosis or triage decision.",
            }
        )
    return candidates


def report_differential_assistance(result_cards: Any, report: Any = None) -> list[dict[str, Any]]:
    """Return only reviewer-eligible candidates for report exports."""
    return [item for item in build_differential_assistance(result_cards, report) if item.get("eligible_for_report_review")]
