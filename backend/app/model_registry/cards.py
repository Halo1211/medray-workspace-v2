from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.model_registry.validation_evidence import validation_evidence_assessment


DEMO_MODEL_CARDS: dict[str, dict[str, Any]] = {
    "demo-safe-radiology-assistant": {
        "id": "demo-safe-radiology-assistant",
        "name": "Demo Safe Radiology Assistant",
        "version": "0.2-demo",
        "source": "MedRay local demo",
        "task": "case-aware chat",
        "clinical_status": "non-diagnostic demo",
        "intended_use": "Education, prototyping, and UX testing only.",
        "limitations": [
            "Does not perform validated diagnosis.",
            "May summarize fallback outputs that contain no real pathology localization.",
        ],
        "requires_opt_in_cloud": False,
    },
    "demo-vlm": {
        "id": "demo-vlm",
        "name": "Demo Vision-Language Placeholder",
        "version": "0.2-demo",
        "source": "MedRay local demo",
        "task": "vision-language reasoning placeholder",
        "clinical_status": "placeholder",
        "intended_use": "Preserve pipeline shape before a validated local VLM is connected.",
        "limitations": ["No real image-language inference is performed."],
        "requires_opt_in_cloud": False,
    },
    "demo-classifier": {
        "id": "demo-classifier",
        "name": "Demo Classifier Placeholder",
        "version": "0.2-demo",
        "source": "MedRay local demo",
        "task": "classification placeholder",
        "clinical_status": "placeholder",
        "intended_use": "Expose classifier slots for future local CXR models.",
        "limitations": ["Does not emit calibrated pathology probabilities."],
        "requires_opt_in_cloud": False,
    },
    "torchxrayvision:densenet121-res224-all": {
        "id": "torchxrayvision:densenet121-res224-all",
        "name": "TorchXRayVision DenseNet-121 All-Datasets Classifier",
        "version": "optional-local-adapter",
        "source": "TorchXRayVision pretrained model weights",
        "task": "chest X-ray multi-label classification",
        "clinical_status": "research-only, not locally validated",
        "intended_use": "Local research experiments that need structured CXR classifier probabilities before report drafting.",
        "limitations": [
            "Not calibrated for the user's local dataset, scanner, acquisition protocol, or population.",
            "Outputs are pathology probabilities only and do not provide lesion localization.",
            "Requires optional PyTorch/TorchXRayVision dependencies and local model weights.",
            "Must not be interpreted as diagnostic advice or clinical triage.",
        ],
        "requires_opt_in_cloud": "only if pretrained weights need to be downloaded",
        "references": [
            "https://mlmed.org/torchxrayvision/models.html",
            "https://arxiv.org/abs/2111.00595",
        ],
    },
    "local-msk-fracture-detector": {
        "id": "local-msk-fracture-detector",
        "name": "Reviewed Local MSK Fracture Detector Adapter",
        "version": "ultralytics-local-adapter-v1",
        "source": "Human-reviewed local artifact",
        "task": "MSK fracture bounding-box localization",
        "clinical_status": "research-only; model-specific validation required",
        "intended_use": "Pilot candidate-fracture localization on MSK radiographs routed by MedRay.",
        "limitations": [
            "No model weights are bundled or enabled automatically.",
            "Only fracture-labeled detector classes are imported as annotations.",
            "Anatomy, views, age groups, dataset shift, thresholds, and box-level performance depend on the selected local artifact.",
            "Boxes are candidate review cues, not confirmed fracture boundaries or triage decisions.",
        ],
        "requires_opt_in_cloud": False,
        "references": ["https://docs.ultralytics.com/tasks/detect/"],
    },
    "demo-report-generator": {
        "id": "demo-report-generator",
        "name": "Demo Report Generator",
        "version": "0.2-demo",
        "source": "MedRay local demo",
        "task": "report drafting",
        "clinical_status": "non-diagnostic draft helper",
        "intended_use": "Generate watermarked draft text from fallback/template output.",
        "limitations": ["Draft text requires qualified clinician verification."],
        "requires_opt_in_cloud": False,
    },
    "pipeline": {
        "id": "pipeline",
        "name": "MedRay Pipeline Controller",
        "version": "0.2",
        "source": "MedRay local",
        "task": "workflow orchestration",
        "clinical_status": "software trace component",
        "intended_use": "Record user prompt handling and pipeline stage status.",
        "limitations": ["Not a model and not a clinical inference component."],
        "requires_opt_in_cloud": False,
    },
}


def _placeholder_card(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "name": model_id,
        "version": "external-or-local",
        "source": "runtime configuration",
        "task": "configured model/tool",
        "clinical_status": "unverified in MedRay registry",
        "intended_use": "Configured by the user or runtime adapter.",
        "limitations": ["No MedRay model card has been registered yet."],
        "requires_opt_in_cloud": "unknown",
    }


def _local_model_card(model_id: str) -> dict[str, Any] | None:
    if not model_id.startswith("local:"):
        return None
    safe_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in model_id)
    path = get_settings().models_dir / "_registry" / f"{safe_id}.model-card.json"
    if not path.exists():
        return None
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(card, dict):
        return None
    assessment = validation_evidence_assessment(card.get("validation_evidence"))
    return {
        **card,
        "id": model_id,
        "name": str(card.get("name") or Path(str(card.get("artifact_path") or "")).name or model_id),
        "source": "Human-reviewed local artifact",
        "clinical_status": "research-only; protocol-bounded evidence" if assessment["complete"] else "research-only; structured validation evidence incomplete",
        "validation_evidence_status": assessment["status"],
        "validation_evidence_assessment": assessment,
    }
def get_model_card(model_id: str) -> dict[str, Any]:
    return DEMO_MODEL_CARDS.get(model_id) or _local_model_card(model_id) or _placeholder_card(model_id)


def list_model_cards() -> list[dict[str, Any]]:
    cards = list(DEMO_MODEL_CARDS.values())
    registry_dir = get_settings().models_dir / "_registry"
    if not registry_dir.exists():
        return cards
    for path in sorted(registry_dir.glob("*.model-card.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        model_id = str(payload.get("artifact_id") or "").strip()
        card = _local_model_card(model_id) if model_id else None
        if card:
            cards.append(card)
    return cards


def cards_for_trace(model_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    cards: list[dict[str, Any]] = []
    for item in model_trace:
        model_id = str(item.get("model") or "").strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        cards.append(get_model_card(model_id))
    return cards
