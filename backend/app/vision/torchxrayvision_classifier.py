from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from app.models.schemas import Finding


MODEL_PREFIX = "torchxrayvision:"
DEFAULT_WEIGHTS = "densenet121-res224-all"


def is_torchxrayvision_model(model_id: str | None) -> bool:
    return bool(model_id and str(model_id).startswith(MODEL_PREFIX))


def parse_weights(model_id: str | None) -> str:
    if not model_id:
        return DEFAULT_WEIGHTS
    if model_id.startswith(MODEL_PREFIX):
        return model_id.removeprefix(MODEL_PREFIX) or DEFAULT_WEIGHTS
    return model_id


def _status_from_probability(probability: float) -> str:
    if probability >= 0.65:
        return "positive"
    if probability <= 0.35:
        return "negative"
    return "uncertain"


def run_torchxrayvision_classifier(image_path: str | None, model_id: str | None, top_k: int = 5) -> dict[str, Any]:
    weights = parse_weights(model_id)
    if not image_path or not Path(image_path).exists():
        return {
            "status": "skipped",
            "model": f"{MODEL_PREFIX}{weights}",
            "findings": [],
            "warnings": ["TorchXRayVision classifier skipped: image path is missing."],
            "detail": "No local image file was available for classifier inference.",
        }

    try:
        import torch
        import torchxrayvision as xrv
    except Exception as exc:
        return {
            "status": "skipped",
            "model": f"{MODEL_PREFIX}{weights}",
            "findings": [],
            "warnings": [
                "TorchXRayVision classifier is configured but optional dependencies are not installed.",
                "Install optional PyTorch/TorchXRayVision dependencies before enabling real local CXR classification.",
            ],
            "detail": f"Optional dependency import failed: {exc}",
        }

    try:
        image = xrv.utils.load_image(image_path)
        image = xrv.datasets.normalize(image, 255)
        transform = xrv.datasets.XRayResizer(224)
        image = transform(image)
        tensor = torch.from_numpy(image).unsqueeze(0)
        model = xrv.models.DenseNet(weights=weights, apply_sigmoid=True)
        model.eval()
        with torch.no_grad():
            preds = model(tensor)[0].detach().cpu().tolist()
    except Exception as exc:
        return {
            "status": "failed",
            "model": f"{MODEL_PREFIX}{weights}",
            "findings": [],
            "warnings": [
                "TorchXRayVision classifier failed and MedRay kept the conservative fallback output.",
                "Do not interpret missing classifier output as absence of disease.",
            ],
            "detail": str(exc),
        }

    valid_scores = [
        (label, float(probability))
        for label, probability in zip(model.targets, preds)
        if math.isfinite(float(probability)) and 0 <= float(probability) <= 1
    ]
    scored = sorted(valid_scores, key=lambda item: item[1], reverse=True)[:top_k]
    invalid_score_count = len(preds) - len(valid_scores)
    if not scored:
        return {
            "status": "failed",
            "model": f"{MODEL_PREFIX}{weights}",
            "findings": [],
            "warnings": ["TorchXRayVision returned no finite probabilities in the expected 0..1 range."],
            "detail": "Classifier output was rejected as invalid.",
        }
    findings = [
        Finding(
            label=f"txrv_{label.lower().replace(' ', '_')}",
            description=f"Research classifier signal for {label}. This is not a diagnosis.",
            confidence=round(float(probability), 3),
            probability=round(float(probability), 3),
            evidence=[f"TorchXRayVision weights={weights}", "Uncalibrated local classifier probability."],
            status=_status_from_probability(float(probability)),
        ).model_dump(mode="json")
        for label, probability in scored
    ]
    return {
        "status": "ok",
        "model": f"{MODEL_PREFIX}{weights}",
        "findings": findings,
        "warnings": [
            "TorchXRayVision classifier output is a research signal only, not a clinical diagnosis.",
            "Probabilities are not calibrated for this local dataset or acquisition protocol.",
            *( [f"Rejected {invalid_score_count} invalid classifier probability value(s)."] if invalid_score_count else [] ),
        ],
        "detail": f"Returned top {len(findings)} TorchXRayVision pathology scores.",
        "raw_targets": list(model.targets),
    }
