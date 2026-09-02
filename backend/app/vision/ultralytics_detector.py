from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Any

from PIL import Image

from app.model_finder.providers import list_local_model_artifacts
from app.model_registry.validation_evidence import hash_artifact_file


FRACTURE_LABEL_TERMS = ("fracture", "fractured", "break")


def normalize_xyxy_box(xyxy: list[float] | tuple[float, ...], width: int, height: int) -> dict[str, float] | None:
    if len(xyxy) != 4 or width <= 0 or height <= 0:
        return None
    values = [float(value) for value in xyxy]
    if not all(math.isfinite(value) for value in values):
        return None
    x1, y1, x2, y2 = values
    x1, x2 = sorted((max(0.0, min(float(width), x1)), max(0.0, min(float(width), x2))))
    y1, y2 = sorted((max(0.0, min(float(height), y1)), max(0.0, min(float(height), y2))))
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def _resolve_detector_artifact(model_id: str) -> tuple[Path | None, str]:
    artifact = next((item for item in list_local_model_artifacts() if item.get("id") == model_id), None)
    if not artifact:
        return None, "Local detector artifact is not registered."
    if not artifact.get("runtime_eligible"):
        return None, "Local detector requires a complete human-reviewed model card."
    task = str(artifact.get("task") or "").lower()
    if not any(term in task for term in ("detect", "localization", "ground")):
        return None, f"Local artifact task '{task or 'unknown'}' is not an object-detection/localization task."
    root = Path(str(artifact.get("artifact_path") or ""))
    weights = sorted(root.rglob("*.pt")) if root.is_dir() else ([root] if root.suffix.lower() == ".pt" else [])
    if not weights:
        return None, "Ultralytics detector requires a reviewed .pt weights file in the artifact folder."
    card = artifact.get("card") if isinstance(artifact.get("card"), dict) else {}
    evidence = card.get("validation_evidence") if isinstance(card.get("validation_evidence"), dict) else {}
    reviewed_filename = str(evidence.get("weights_filename") or "").strip()
    if reviewed_filename:
        selected = (root / reviewed_filename).resolve() if root.is_dir() else root.resolve()
        if selected not in [item.resolve() for item in weights]:
            return None, "Reviewed validation evidence weights file is missing or is not a .pt detector artifact."
        reviewed_hash = str(evidence.get("artifact_hash") or "").strip().lower()
        if reviewed_hash and hash_artifact_file(selected) != reviewed_hash:
            return None, "Reviewed detector weights hash no longer matches the local artifact; review is required again."
        return selected, ""
    if len(weights) > 1:
        return None, "Multiple .pt files were found; select an exact weights filename in structured validation evidence."
    return weights[0], ""


def run_msk_fracture_detector(image_path: str | None, model_id: str, cpu_only: bool = True, threshold: float = 0.25) -> dict[str, Any]:
    if not image_path or not Path(image_path).exists():
        return {"status": "skipped", "model": model_id, "detail": "No source image is available for localization.", "detections": [], "warnings": []}
    weights, issue = _resolve_detector_artifact(model_id)
    if issue:
        return {"status": "skipped", "model": model_id, "detail": issue, "detections": [], "warnings": [issue]}
    if importlib.util.find_spec("ultralytics") is None:
        detail = "Optional dependency 'ultralytics' is not installed."
        return {"status": "skipped", "model": model_id, "detail": detail, "detections": [], "warnings": [detail]}

    try:
        from ultralytics import YOLO

        with Image.open(image_path) as image:
            original_width, original_height = image.size
        model = YOLO(str(weights))
        result = model.predict(source=image_path, conf=threshold, device="cpu" if cpu_only else None, verbose=False)[0]
        boxes = result.boxes
        names = result.names
        detections = []
        rejected = 0
        for xyxy, confidence, class_id in zip(boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(), boxes.cls.cpu().tolist()):
            label = str(names.get(int(class_id), f"class_{int(class_id)}")) if isinstance(names, dict) else str(names[int(class_id)])
            if not any(term in label.lower() for term in FRACTURE_LABEL_TERMS):
                continue
            coordinate = normalize_xyxy_box(xyxy, original_width, original_height)
            if coordinate is None:
                rejected += 1
                continue
            detections.append({
                "label": "candidate fracture",
                "model_label": label,
                "confidence": max(0.0, min(1.0, float(confidence))),
                "coordinate": coordinate,
            })
            if len(detections) >= 20:
                break
        warnings = [
            "MSK fracture boxes are unvalidated research localizations and require radiologist/physician review."
        ]
        if rejected:
            warnings.append(f"Rejected {rejected} invalid detector box(es) after original-image coordinate validation.")
        return {
            "status": "ok",
            "model": model_id,
            "weights": str(weights),
            "detail": f"Produced {len(detections)} candidate fracture box(es) in original-image coordinates.",
            "detections": detections,
            "original_width": original_width,
            "original_height": original_height,
            "model_input_width": None,
            "model_input_height": None,
            "warnings": warnings,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "model": model_id,
            "detail": str(exc),
            "detections": [],
            "warnings": [f"MSK localization failed: {exc}"],
        }
