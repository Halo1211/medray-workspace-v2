from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.config import get_settings
from app.studies.images import normalize_case_images
from app.storage.db import safe_path_component


COLORS = {
    "model-returned coordinate": "#2dd4bf",
    "segmentation mask": "#a78bfa",
    "fallback heuristic": "#f59e0b",
    "manual user annotation": "#ef4444",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _coordinate_scale(annotation: dict[str, Any], image_width: int, image_height: int) -> tuple[float, float]:
    transform = annotation.get("transform_metadata") if isinstance(annotation.get("transform_metadata"), dict) else {}
    source_width = _safe_float(transform.get("original_width"), image_width)
    source_height = _safe_float(transform.get("original_height"), image_height)
    scale_x = image_width / source_width if source_width > 0 else 1.0
    scale_y = image_height / source_height if source_height > 0 else 1.0
    return scale_x, scale_y


def original_ai_annotation(annotation: dict[str, Any]) -> dict[str, Any] | None:
    if annotation.get("source") == "manual user annotation":
        return None

    original = copy.deepcopy(annotation)
    state = annotation.get("original_state") if isinstance(annotation.get("original_state"), dict) else {}
    original["label"] = state.get("label", annotation.get("label", "finding"))
    original["confidence"] = state.get("confidence", annotation.get("confidence", 0))
    coordinate = state.get("coordinate") or annotation.get("original_coordinate") or annotation.get("coordinate")
    original["coordinate"] = copy.deepcopy(coordinate if isinstance(coordinate, dict) else {})
    original["explanation"] = state.get("explanation", annotation.get("explanation", ""))
    original["visible"] = state.get("visible", True)
    original["locked"] = False
    original["review_status"] = "unreviewed"
    original["reviewer_note"] = ""
    original["linked_result_card_ids"] = copy.deepcopy(state.get("linked_result_card_ids") or [])
    original["linked_report_statement_id"] = state.get("linked_report_statement_id", "")
    original["revision_history"] = []
    return original


def annotation_states(annotations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reviewed = copy.deepcopy(annotations)
    originals = [item for annotation in annotations if (item := original_ai_annotation(annotation)) is not None]
    return originals, reviewed


def export_annotated_png(
    case_id: str,
    image_path: str,
    annotations: list[dict[str, Any]],
    variant: str = "reviewed",
    image_key: str = "",
) -> str:
    settings = get_settings()
    out_dir = settings.exports_dir / safe_path_component(case_id, "case")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_variant = "ai_original" if variant == "ai_original" else "reviewed"
    safe_image_key = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in image_key)[:80]
    out_path = out_dir / (f"annotated_{safe_image_key}_{safe_variant}.png" if safe_image_key else f"annotated_{safe_variant}.png")
    with Image.open(image_path) as img:
        canvas = img.convert("RGB")
        draw = ImageDraw.Draw(canvas)
        for ann in _list_of_dicts(annotations):
            if not ann.get("visible", True):
                continue
            if str(ann.get("source") or "") == "fallback heuristic":
                continue
            coord = ann.get("coordinate") if isinstance(ann.get("coordinate"), dict) else {}
            scale_x, scale_y = _coordinate_scale(ann, canvas.width, canvas.height)
            color = COLORS.get(ann.get("source"), "#38bdf8")
            if coord.get("type", "bbox") in {"bbox", "grounding_box"}:
                x = _safe_float(coord.get("x")) * scale_x
                y = _safe_float(coord.get("y")) * scale_y
                w = _safe_float(coord.get("width")) * scale_x
                h = _safe_float(coord.get("height")) * scale_y
                if w <= 0 or h <= 0:
                    continue
                draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
                label = f"{ann.get('label', 'finding')} {_safe_float(ann.get('confidence')):.2f}"
                draw.rectangle([x, max(0, y - 18), x + min(420, len(label) * 8), y], fill=color)
                draw.text((x + 4, max(0, y - 16)), label, fill="black")
            elif coord.get("type") == "point":
                x = _safe_float(coord.get("x")) * scale_x
                y = _safe_float(coord.get("y")) * scale_y
                radius = 6
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=3)
                draw.line([x - 10, y, x + 10, y], fill=color, width=2)
                draw.line([x, y - 10, x, y + 10], fill=color, width=2)
                draw.text((x + 9, max(0, y - 16)), str(ann.get("label") or "point"), fill=color)
            elif coord.get("type") == "polygon":
                points = [
                    (_safe_float(item[0]) * scale_x, _safe_float(item[1]) * scale_y)
                    for item in coord.get("points", [])
                    if isinstance(item, (list, tuple)) and len(item) == 2
                ]
                if len(points) < 3:
                    continue
                draw.polygon(points, outline=color)
                draw.line([*points, points[0]], fill=color, width=3)
                draw.text((points[0][0] + 5, max(0, points[0][1] - 16)), str(ann.get("label") or "polygon"), fill=color)
        canvas.save(out_path)
    return str(out_path)


def build_annotation_review_bundle(case: dict[str, Any]) -> dict[str, Any]:
    case = normalize_case_images(case)
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    annotations = _list_of_dicts(case.get("annotations")) or _list_of_dicts(analysis.get("annotations"))
    originals, reviewed = annotation_states(annotations)
    review_status_counts = {
        status: sum(1 for annotation in reviewed if str(annotation.get("review_status") or "unreviewed") == status)
        for status in sorted({str(annotation.get("review_status") or "unreviewed") for annotation in reviewed})
    }
    return {
        "schema_version": "0.1.0",
        "generated_at": _now_iso(),
        "case_id": case.get("case_id"),
        "source_images": [
            {
                "source_image_id": image.get("image_id"),
                "source_image_index": image.get("index", index),
                "source_view": image.get("view", ""),
                "source_series_id": image.get("series_id", ""),
                "image_path": image.get("image_path"),
                "preview_path": image.get("preview_path"),
                "input_hash": image.get("file_hashes", {}).get("input") if isinstance(image.get("file_hashes"), dict) else None,
            }
            for index, image in enumerate(case.get("images", []))
        ],
        "ai_original_annotations": originals,
        "reviewed_annotations": reviewed,
        "review_summary": {
            "ai_original_count": len(originals),
            "reviewed_count": len(reviewed),
            "manual_count": sum(1 for annotation in reviewed if annotation.get("source") == "manual user annotation"),
            "changed_count": sum(1 for annotation in reviewed if annotation.get("revision_history")),
            "review_status_counts": review_status_counts,
        },
    }


def export_annotation_review_package(case: dict[str, Any]) -> dict[str, Any]:
    case = normalize_case_images(case)
    settings = get_settings()
    case_id = str(case.get("case_id") or "unknown")
    out_dir = settings.exports_dir / safe_path_component(case_id, "case")
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = build_annotation_review_bundle(case)
    comparison_path = out_dir / "annotation_review_comparison.json"
    comparison_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")

    reviewed_pngs: dict[str, str] = {}
    original_pngs: dict[str, str] = {}
    images = case.get("images", [])
    for index, image in enumerate(images):
        image_id = str(image.get("image_id") or f"{case_id}:{index}")
        def belongs(annotation: dict[str, Any]) -> bool:
            source_id = str(annotation.get("source_image_id") or "")
            accepted_ids = {image_id, str(image.get("sop_instance_uid") or ""), str(image.get("filename") or "")}
            return source_id in accepted_ids or (index == 0 and source_id in {"", "primary"})
        reviewed = [annotation for annotation in bundle["reviewed_annotations"] if belongs(annotation)]
        originals = [annotation for annotation in bundle["ai_original_annotations"] if belongs(annotation)]
        image_path = str(image.get("image_path") or "")
        image_key = str(index) if len(images) > 1 else ""
        reviewed_pngs[image_id] = export_annotated_png(case_id, image_path, reviewed, "reviewed", image_key)
        original_pngs[image_id] = export_annotated_png(case_id, image_path, originals, "ai_original", image_key)
    active_id = str(case.get("active_image_id") or "")
    reviewed_png = reviewed_pngs.get(active_id) or next(iter(reviewed_pngs.values()), "")
    original_png = original_pngs.get(active_id) or next(iter(original_pngs.values()), "")
    return {
        "reviewed_png": reviewed_png,
        "ai_original_png": original_png,
        "reviewed_pngs": reviewed_pngs,
        "ai_original_pngs": original_pngs,
        "comparison_json": str(comparison_path),
        "bundle": bundle,
    }
