from __future__ import annotations

import re

from app.models.schemas import Annotation, AnnotationSource, Finding, ImageQuality, ModelTrace, ResultCard, ResultEvidence


def _safe_id(label: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:70]
    return f"result-{index + 1}-{slug or 'card'}"


def _candidate_label(label: str) -> str:
    cleaned = label.replace("txrv_", "").replace("_", " ").strip()
    if not cleaned or cleaned == "fallback no confirmed abnormality":
        return "No AI candidate diagnosis from fallback output"
    return f"AI candidate diagnosis: {cleaned}"


def _source_for_finding(finding: Finding) -> str:
    if finding.label.startswith("txrv_") or any("TorchXRayVision" in item for item in finding.evidence):
        return "torchxrayvision:densenet121-res224-all classifier research signal"
    if finding.label.startswith("fallback_"):
        return "demo/fallback structured reading"
    if finding.label == "candidate_fracture_localization":
        return "reviewed local MSK detector research signal"
    return "analysis pipeline"


def _uncertainty_reason(finding: Finding, quality: ImageQuality) -> str:
    reasons = []
    if finding.status in {"uncertain", "not_assessed"}:
        reasons.append("Result is not a confirmed diagnosis.")
    if finding.probability is not None:
        reasons.append("Classifier probabilities are not locally calibrated for clinical performance.")
    if quality.limitations:
        reasons.append("Image quality limitations may affect the research signal.")
    if not reasons:
        reasons.append("Requires qualified human review before use.")
    return " ".join(reasons)


def _next_action(finding: Finding, quality: ImageQuality) -> str:
    if quality.limitations:
        return "Review image quality and consider repeat image or prior comparison if clinically appropriate."
    if finding.status == "positive":
        return "Review by a qualified radiologist/physician and correlate clinically."
    if finding.status == "negative":
        return "Use as a review cue only; verify against the image and clinical context."
    return "Review by a qualified radiologist/physician."


def _matching_annotation_refs(finding: Finding, annotations: list[Annotation]) -> list[str]:
    finding_tokens = set(finding.label.lower().replace("txrv_", "").replace("_", " ").split())
    refs: list[str] = []
    for annotation in annotations:
        if annotation.source == AnnotationSource.FALLBACK_HEURISTIC:
            continue
        annotation_tokens = set(annotation.label.lower().replace("_", " ").split())
        if finding_tokens & annotation_tokens:
            refs.append(annotation.id)
    return refs


def _trace_refs(finding: Finding, trace: list[ModelTrace]) -> list[str]:
    if finding.label.startswith("txrv_"):
        return [item.model for item in trace if item.stage == "anatomy_classification" and item.model]
    if finding.label.startswith("fallback_"):
        return [item.model for item in trace if item.status in {"fallback", "skipped"} and item.model][:3]
    if finding.label == "candidate_fracture_localization":
        return [item.model for item in trace if item.stage == "msk_fracture_localization" and item.model]
    return [item.model for item in trace if item.status == "ok" and item.model][:3]


def compose_result_cards(
    findings: list[Finding],
    annotations: list[Annotation],
    model_trace: list[ModelTrace],
    image_quality: ImageQuality,
) -> list[ResultCard]:
    cards: list[ResultCard] = []
    for index, finding in enumerate(findings):
        annotation_refs = _matching_annotation_refs(finding, annotations)
        evidence = [
            ResultEvidence(kind="finding", text=finding.description, ref=finding.label),
            ResultEvidence(kind="image_quality", text=f"Estimated image quality: {image_quality.exposure} ({image_quality.score:.2f}).", ref="image_quality"),
        ]
        for item in finding.evidence:
            evidence.append(ResultEvidence(kind="limitation", text=item, ref=finding.label))
        for ref in annotation_refs:
            evidence.append(ResultEvidence(kind="annotation", text="Linked model-generated localization evidence.", ref=ref))

        cards.append(
            ResultCard(
                id=_safe_id(finding.label, index),
                finding=finding.label,
                status=finding.status,
                candidate_diagnosis=_candidate_label(finding.label),
                probability=finding.probability,
                confidence=finding.confidence,
                evidence=evidence,
                annotation_refs=annotation_refs,
                source=_source_for_finding(finding),
                uncertainty_reason=_uncertainty_reason(finding, image_quality),
                next_safe_action=_next_action(finding, image_quality),
                model_trace_refs=_trace_refs(finding, model_trace),
            )
        )
    return cards
