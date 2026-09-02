from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from app.models.schemas import (
    Annotation,
    AnnotationOriginalState,
    AnnotationSource,
    AnnotationTransformMetadata,
    Coordinate,
)


LOCATE_ANYTHING_COORDINATE_SCALE = 1000
MAX_LOCATE_ANYTHING_OUTPUT_CHARS = 200_000
MAX_LOCATE_ANYTHING_GROUNDINGS = 100
MAX_LOCATE_ANYTHING_LABEL_CHARS = 160
MAX_IMAGE_DIMENSION = 100_000
MAX_IMAGE_PIXELS = 1_000_000_000


_GROUNDING_TOKEN = re.compile(
    rf"""
    (?:
        <ref>(?P<label>[^<>]{{1,{MAX_LOCATE_ANYTHING_LABEL_CHARS}}})</ref>\s*
    )?
    <box>\s*
    (?:
        (?P<none>none)
        |
        <(?P<a>\d{{1,4}})>\s*<(?P<b>\d{{1,4}})>
        (?:\s*<(?P<c>\d{{1,4}})>\s*<(?P<d>\d{{1,4}})>)?
    )
    \s*</box>
    """,
    re.VERBOSE,
)


def _clean_label(value: str, fallback: str) -> str:
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        cleaned = " ".join(str(fallback or "").split())
    return cleaned[:MAX_LOCATE_ANYTHING_LABEL_CHARS] or "unlabeled grounding"


def _valid_image_dimensions(width: Any, height: Any) -> bool:
    if isinstance(width, bool) or isinstance(height, bool):
        return False
    if not isinstance(width, int) or not isinstance(height, int):
        return False
    if width <= 0 or height <= 0 or width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        return False
    return width * height <= MAX_IMAGE_PIXELS


def _pixel(value: int, extent: int) -> float:
    return value / LOCATE_ANYTHING_COORDINATE_SCALE * extent


def _same_grounding(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("type") != right.get("type") or str(left.get("label") or "").casefold() != str(right.get("label") or "").casefold():
        return False
    left_coord = left.get("normalized_coordinate") if isinstance(left.get("normalized_coordinate"), dict) else {}
    right_coord = right.get("normalized_coordinate") if isinstance(right.get("normalized_coordinate"), dict) else {}
    if left.get("type") == "point":
        return left_coord.get("x") == right_coord.get("x") and left_coord.get("y") == right_coord.get("y")
    required = ("x1", "y1", "x2", "y2")
    if not all(isinstance(left_coord.get(key), int) and isinstance(right_coord.get(key), int) for key in required):
        return False
    intersection_width = max(0, min(left_coord["x2"], right_coord["x2"]) - max(left_coord["x1"], right_coord["x1"]))
    intersection_height = max(0, min(left_coord["y2"], right_coord["y2"]) - max(left_coord["y1"], right_coord["y1"]))
    intersection = intersection_width * intersection_height
    left_area = (left_coord["x2"] - left_coord["x1"]) * (left_coord["y2"] - left_coord["y1"])
    right_area = (right_coord["x2"] - right_coord["x1"]) * (right_coord["y2"] - right_coord["y1"])
    union = left_area + right_area - intersection
    return union > 0 and intersection / union >= 0.95


def _validated_annotation_coordinate(value: dict[str, Any], width: int, height: int) -> Coordinate:
    coordinate_type = value.get("type")
    if coordinate_type not in {"grounding_box", "point"}:
        raise ValueError("LocateAnything annotations support only grounding boxes and points.")

    def finite_number(name: str) -> float:
        item = value.get(name)
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            raise ValueError(f"LocateAnything coordinate '{name}' must be finite.")
        return float(item)

    x = finite_number("x")
    y = finite_number("y")
    if coordinate_type == "point":
        if not (0 <= x <= width and 0 <= y <= height):
            raise ValueError("LocateAnything point falls outside the original image.")
        return Coordinate(
            type="point",
            x=x,
            y=y,
            width=0,
            height=0,
            points=[(x, y)],
            coordinate_space="original_image",
        )

    box_width = finite_number("width")
    box_height = finite_number("height")
    if x < 0 or y < 0 or box_width <= 0 or box_height <= 0 or x + box_width > width or y + box_height > height:
        raise ValueError("LocateAnything box is invalid or falls outside the original image.")
    return Coordinate(
        type="grounding_box",
        x=x,
        y=y,
        width=box_width,
        height=box_height,
        points=[],
        coordinate_space="original_image",
    )


def parse_locate_anything_output(
    answer: str,
    image_width: int,
    image_height: int,
    *,
    query: str = "",
    max_items: int = MAX_LOCATE_ANYTHING_GROUNDINGS,
) -> dict[str, Any]:
    """Parse official LocateAnything box/point tokens without invoking a model.

    Coordinates are accepted only in the documented inclusive range [0, 1000].
    Invalid geometry is rejected rather than reordered or clamped. The raw answer is
    represented by a SHA-256 digest so downstream trace records can bind to the exact
    parser input without copying arbitrary model text into every annotation.
    """

    if not isinstance(answer, str):
        raise TypeError("LocateAnything answer must be a string.")
    if not _valid_image_dimensions(image_width, image_height):
        raise ValueError("Original image dimensions are invalid or exceed the parser budget.")
    if isinstance(max_items, bool) or not isinstance(max_items, int) or not 1 <= max_items <= MAX_LOCATE_ANYTHING_GROUNDINGS:
        raise ValueError(f"max_items must be between 1 and {MAX_LOCATE_ANYTHING_GROUNDINGS}.")
    if len(answer) > MAX_LOCATE_ANYTHING_OUTPUT_CHARS:
        raise ValueError("LocateAnything output exceeds the parser character budget.")

    raw_output_hash = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    box_marker_count = answer.count("<box>")
    ref_marker_count = answer.count("<ref>")
    closing_ref_count = answer.count("</ref>")
    base = {
        "format": "locateanything-pbd-v1",
        "query": _clean_label(query, ""),
        "raw_output_hash": raw_output_hash,
        "original_width": image_width,
        "original_height": image_height,
        "groundings": [],
        "none_count": 0,
        "rejected_count": 0,
        "deduplicated_count": 0,
        "warnings": [],
    }

    if box_marker_count > max_items:
        return {
            **base,
            "status": "rejected",
            "rejected_count": box_marker_count,
            "warnings": [f"Rejected output containing {box_marker_count} grounding tokens; limit is {max_items}."],
        }
    if ref_marker_count != closing_ref_count:
        return {
            **base,
            "status": "rejected",
            "rejected_count": max(1, box_marker_count),
            "warnings": ["Rejected output with unbalanced <ref> label tags."],
        }

    matches = list(_GROUNDING_TOKEN.finditer(answer))
    matched_label_count = sum(1 for match in matches if match.group("label") is not None)
    if ref_marker_count != matched_label_count:
        return {
            **base,
            "status": "rejected",
            "rejected_count": max(1, box_marker_count),
            "warnings": ["Rejected output with a label that is not bound to exactly one grounding token."],
        }

    groundings: list[dict[str, Any]] = []
    none_count = 0
    invalid_count = max(0, box_marker_count - len(matches))

    for match in matches:
        if match.group("none") is not None:
            none_count += 1
            continue
        values = [int(match.group(name)) for name in ("a", "b")]
        if match.group("c") is not None and match.group("d") is not None:
            values.extend([int(match.group("c")), int(match.group("d"))])
        if any(value < 0 or value > LOCATE_ANYTHING_COORDINATE_SCALE for value in values):
            invalid_count += 1
            continue

        label = _clean_label(match.group("label") or "", query)
        if len(values) == 2:
            x, y = values
            groundings.append({
                "type": "point",
                "label": label,
                "normalized_coordinate": {"x": x, "y": y, "scale": LOCATE_ANYTHING_COORDINATE_SCALE},
                "coordinate": {
                    "type": "point",
                    "x": _pixel(x, image_width),
                    "y": _pixel(y, image_height),
                    "width": 0.0,
                    "height": 0.0,
                    "points": [(_pixel(x, image_width), _pixel(y, image_height))],
                    "coordinate_space": "original_image",
                },
            })
            continue

        x1, y1, x2, y2 = values
        if x2 <= x1 or y2 <= y1:
            invalid_count += 1
            continue
        pixel_x1 = _pixel(x1, image_width)
        pixel_y1 = _pixel(y1, image_height)
        pixel_x2 = _pixel(x2, image_width)
        pixel_y2 = _pixel(y2, image_height)
        groundings.append({
            "type": "grounding_box",
            "label": label,
            "normalized_coordinate": {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "scale": LOCATE_ANYTHING_COORDINATE_SCALE,
            },
            "coordinate": {
                "type": "grounding_box",
                "x": pixel_x1,
                "y": pixel_y1,
                "width": pixel_x2 - pixel_x1,
                "height": pixel_y2 - pixel_y1,
                "points": [],
                "coordinate_space": "original_image",
            },
        })

    deduplicated: list[dict[str, Any]] = []
    duplicate_count = 0
    for grounding in groundings:
        if any(_same_grounding(grounding, existing) for existing in deduplicated):
            duplicate_count += 1
        else:
            deduplicated.append(grounding)

    warnings: list[str] = []
    if invalid_count:
        warnings.append(f"Rejected {invalid_count} malformed or invalid grounding token(s).")
    if duplicate_count:
        warnings.append(f"Removed {duplicate_count} duplicate or near-identical grounding token(s) for the same label.")
    if none_count and groundings:
        warnings.append("Output mixed explicit 'none' and coordinate groundings; coordinates require manual review.")
    if deduplicated:
        status = "ok"
    elif none_count and not invalid_count:
        status = "none"
    else:
        status = "rejected"
        if not warnings:
            warnings.append("No valid LocateAnything grounding token was found.")

    return {
        **base,
        "status": status,
        "groundings": deduplicated,
        "none_count": none_count,
        "rejected_count": invalid_count,
        "deduplicated_count": duplicate_count,
        "warnings": warnings,
    }


def locate_anything_annotations(
    parsed: dict[str, Any],
    *,
    source_model: str = "nvidia/LocateAnything-3B",
    source_model_version: str = "",
    source_image_id: str = "primary",
    source_image_index: int = 0,
    source_view: str = "",
    source_series_id: str = "",
) -> list[Annotation]:
    """Convert a successful parser result into unreviewed MedRay annotations."""

    if not isinstance(parsed, dict) or parsed.get("status") != "ok":
        return []
    groundings = parsed.get("groundings")
    if not isinstance(groundings, list) or len(groundings) > MAX_LOCATE_ANYTHING_GROUNDINGS:
        raise ValueError("Parsed grounding collection is invalid or exceeds the annotation budget.")
    width = parsed.get("original_width")
    height = parsed.get("original_height")
    if not _valid_image_dimensions(width, height):
        raise ValueError("Parsed result has invalid original image dimensions.")

    query = _clean_label(str(parsed.get("query") or ""), "")
    raw_output_hash = str(parsed.get("raw_output_hash") or "")
    annotations: list[Annotation] = []
    for grounding in groundings:
        if not isinstance(grounding, dict) or not isinstance(grounding.get("coordinate"), dict):
            raise ValueError("Parsed grounding is missing a coordinate object.")
        coordinate = _validated_annotation_coordinate(grounding["coordinate"], width, height)
        label = _clean_label(str(grounding.get("label") or ""), query)
        explanation = (
            f"Experimental unvalidated visual grounding for query '{query}'. "
            "Coordinate output only; no calibrated pathology confidence. Qualified human review is required."
        )
        annotations.append(Annotation(
            label=label,
            confidence=0.0,
            source=AnnotationSource.MODEL_COORDINATE,
            source_model=_clean_label(source_model, "nvidia/LocateAnything-3B"),
            source_model_version=" ".join(str(source_model_version or "").split())[:MAX_LOCATE_ANYTHING_LABEL_CHARS],
            coordinate=coordinate,
            original_coordinate=coordinate.model_copy(deep=True),
            original_state=AnnotationOriginalState(
                label=label,
                confidence=0.0,
                coordinate=coordinate.model_copy(deep=True),
                explanation=explanation,
            ),
            explanation=explanation,
            source_image_id=str(source_image_id or "primary"),
            source_image_index=source_image_index,
            source_view=str(source_view or ""),
            source_series_id=str(source_series_id or ""),
            transform_metadata=AnnotationTransformMetadata(
                source_space="original_image",
                display_space="original_image",
                original_width=width,
                original_height=height,
                note=(
                    "LocateAnything normalized coordinates were strictly validated and restored to original-image pixels; "
                    f"raw output SHA-256={raw_output_hash or 'unavailable'}."
                ),
            ),
        ))
    return annotations
