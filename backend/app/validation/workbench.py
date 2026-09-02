from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.storage.db import get_case, safe_path_component


VALIDATION_SCHEMA_VERSION = "0.4.0"


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ValidationFindingLabel(BaseModel):
    label: str
    status: str = "uncertain"
    note: str = ""


class ValidationImageQualityLabel(BaseModel):
    diagnostic_quality: str = "unknown"
    limitations: list[str] = []
    note: str = ""


class ValidationBox(BaseModel):
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ValidationAnnotationExpectation(BaseModel):
    label: str
    coordinate_type: str = "bbox"
    required: bool = False
    coordinate: ValidationBox | None = None
    min_iou: float = Field(default=0.3, ge=0, le=1)
    note: str = ""
    source_image_id: str = ""
    points: list[tuple[float, float]] = []
    max_point_distance: float = Field(default=10, ge=0)
    min_vertex_count: int = Field(default=3, ge=3)


class ValidationCaseLabel(BaseModel):
    case_id: str
    title: str = ""
    protocol_id: str = "local-research-protocol"
    dataset_name: str = "local validation set"
    split: str = "local"
    anatomy: str = ""
    view: str = ""
    age_group: str = ""
    subgroup_notes: str = ""
    source_image_id: str = ""
    source_image_index: int | None = Field(default=None, ge=0)
    source_series_id: str = ""
    source_view: str = ""
    expected_body_region: str = ""
    expected_image_quality: ValidationImageQualityLabel = Field(default_factory=ValidationImageQualityLabel)
    expected_findings: list[ValidationFindingLabel] = []
    expected_annotations: list[ValidationAnnotationExpectation] = []
    reference_standard: str = "local research label"
    reviewer: str = ""
    protocol_notes: str = ""
    skip_reason: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


def validation_dir() -> Path:
    path = get_settings().data_dir / "validation"
    path.mkdir(parents=True, exist_ok=True)
    (path / "labels").mkdir(parents=True, exist_ok=True)
    return path


def label_path(case_id: str) -> Path:
    safe_id = safe_path_component(case_id, "case", 120)
    return validation_dir() / "labels" / f"{safe_id}.json"


def fixtures_dir() -> Path:
    path = validation_dir() / "fixtures"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_validation_labels() -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    for path in sorted((validation_dir() / "labels").glob("*.json")):
        try:
            labels.append(ValidationCaseLabel(**json.loads(path.read_text(encoding="utf-8"))).model_dump(mode="json"))
        except Exception as exc:
            labels.append({"case_id": path.stem, "invalid": True, "error": str(exc)})
    return labels


def save_validation_label(payload: dict[str, Any]) -> dict[str, Any]:
    existing = {}
    if payload.get("case_id") and label_path(str(payload["case_id"])).exists():
        existing = json.loads(label_path(str(payload["case_id"])).read_text(encoding="utf-8"))
    merged = {**existing, **payload, "updated_at": now_iso()}
    label = ValidationCaseLabel(**merged)
    path = label_path(label.case_id)
    path.write_text(json.dumps(label.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "label": label.model_dump(mode="json")}


def delete_validation_label(case_id: str) -> dict[str, Any]:
    path = label_path(case_id)
    if path.exists():
        path.unlink()
        return {"deleted": True, "case_id": case_id, "path": str(path)}
    return {"deleted": False, "case_id": case_id, "path": str(path)}


def curated_sample_fixture() -> dict[str, Any]:
    fixture = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "name": "curated_sample_research_labels",
        "purpose": "Offline fixture for exercising the Validation Workbench without network access or clinical claims.",
        "labels": [
            ValidationCaseLabel(
                case_id="fixture-cxr-normal-001",
                title="Fixture CXR normal control",
                dataset_name="MedRay sample validation fixture",
                split="fixture",
                expected_body_region="Chest X-ray",
                expected_image_quality=ValidationImageQualityLabel(diagnostic_quality="adequate", limitations=[]),
                expected_findings=[ValidationFindingLabel(label="fallback_no_confirmed_abnormality", status="uncertain", note="Demo pipeline fixture label.")],
                reference_standard="synthetic fixture label for software testing only",
                reviewer="MedRay fixture",
                protocol_notes="Use to verify workbench plumbing; do not use for model performance.",
            ),
            ValidationCaseLabel(
                case_id="fixture-cxr-unsupported-001",
                title="Fixture unsupported case",
                dataset_name="MedRay sample validation fixture",
                split="fixture",
                expected_body_region="Chest X-ray",
                expected_image_quality=ValidationImageQualityLabel(diagnostic_quality="limited", limitations=["unsupported_fixture"]),
                expected_findings=[],
                reference_standard="synthetic fixture label for software testing only",
                reviewer="MedRay fixture",
                protocol_notes="Demonstrates skip/unsupported accounting.",
                skip_reason="Fixture intentionally has no local case image or analysis.",
            ),
        ],
    }
    return {
        **fixture,
        "labels": [label.model_dump(mode="json") for label in fixture["labels"]],
    }


def write_curated_sample_fixture() -> dict[str, Any]:
    fixture = curated_sample_fixture()
    path = fixtures_dir() / "curated_sample_labels.json"
    path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "fixture": fixture}


def _finding_lookup(case: dict[str, Any], analysis: dict[str, Any] | None = None) -> dict[str, str]:
    selected = analysis if isinstance(analysis, dict) else (case.get("analysis") if isinstance(case.get("analysis"), dict) else {})
    findings = _list_of_dicts(selected.get("findings"))
    return {str(item.get("label", "")).lower(): str(item.get("status", "uncertain")) for item in findings}


def _result_card_lookup(case: dict[str, Any], analysis: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    selected = analysis if isinstance(analysis, dict) else (case.get("analysis") if isinstance(case.get("analysis"), dict) else {})
    cards = _list_of_dicts(selected.get("result_cards"))
    return {str(item.get("finding", "")).lower(): item for item in cards}


def _quality_result(label: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    expected = label.get("expected_image_quality") if isinstance(label.get("expected_image_quality"), dict) else {}
    expected_quality = str(expected.get("diagnostic_quality") or "unknown")
    predicted = analysis.get("image_quality") if isinstance(analysis.get("image_quality"), dict) else {}
    predicted_limitations = [item.lower() for item in _string_list(predicted.get("limitations"))]
    expected_limitations = [item.lower() for item in _string_list(expected.get("limitations"))]
    limitation_matches = [item for item in expected_limitations if item in predicted_limitations]
    try:
        predicted_score = float(predicted.get("score"))
    except (TypeError, ValueError):
        predicted_score = None
    if predicted_score is None or not math.isfinite(predicted_score):
        predicted_quality = "unknown"
    elif predicted_score < 0.3:
        predicted_quality = "non_diagnostic"
    elif predicted_score < 0.6 or predicted_limitations:
        predicted_quality = "limited"
    else:
        predicted_quality = "adequate"
    return {
        "expected": expected_quality,
        "predicted": predicted_quality,
        "predicted_score": predicted.get("score"),
        "predicted_limitations": _string_list(predicted.get("limitations")),
        "expected_limitations": _string_list(expected.get("limitations")),
        "limitation_agreements": limitation_matches,
        "matched": None if expected_quality == "unknown" or predicted_quality == "unknown" else predicted_quality == expected_quality,
    }


def _bbox_iou(first: dict[str, Any], second: dict[str, Any]) -> float:
    ax1, ay1 = float(first.get("x", 0)), float(first.get("y", 0))
    ax2, ay2 = ax1 + float(first.get("width", 0)), ay1 + float(first.get("height", 0))
    bx1, by1 = float(second.get("x", 0)), float(second.get("y", 0))
    bx2, by2 = bx1 + float(second.get("width", 0)), by1 + float(second.get("height", 0))
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = max(0.0, (ax2 - ax1) * (ay2 - ay1)) + max(0.0, (bx2 - bx1) * (by2 - by1)) - intersection
    return intersection / union if union > 0 else 0.0


def _coordinate_points(coordinate: dict[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in coordinate.get("points", []) if isinstance(coordinate.get("points"), list) else []:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            x, y = float(item[0]), float(item[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            points.append((x, y))
    return points


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0
    return abs(sum(points[index][0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * points[index][1] for index in range(len(points))) / 2)


def _geometry_valid(coordinate: dict[str, Any], min_vertex_count: int = 3) -> bool:
    coordinate_type = str(coordinate.get("type") or "")
    if coordinate_type == "point":
        try:
            return math.isfinite(float(coordinate.get("x"))) and math.isfinite(float(coordinate.get("y")))
        except (TypeError, ValueError):
            return False
    if coordinate_type == "polygon":
        points = _coordinate_points(coordinate)
        return len(points) >= min_vertex_count and _polygon_area(points) > 0
    if coordinate_type in {"bbox", "grounding_box"}:
        try:
            return float(coordinate.get("width", 0)) > 0 and float(coordinate.get("height", 0)) > 0
        except (TypeError, ValueError):
            return False
    return bool(coordinate_type)


def _case_annotations(case: dict[str, Any], analysis: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    case_analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    selected_analysis = analysis if isinstance(analysis, dict) else case_analysis
    annotations: list[dict[str, Any]] = []
    seen: set[str] = set()
    # The case-level collection is the reviewed canonical copy. A selected
    # per-image analysis is a fallback for legacy/migrated cases that have not
    # copied its annotations to the case-level collection yet.
    sources = [
        _list_of_dicts(case.get("annotations")),
        _list_of_dicts(selected_analysis.get("annotations")),
    ]
    if selected_analysis is not case_analysis:
        sources.append(_list_of_dicts(case_analysis.get("annotations")))
    for annotation in [item for source in sources for item in source]:
        annotation_id = str(annotation.get("id") or "")
        if annotation_id and annotation_id in seen:
            continue
        if annotation_id:
            seen.add(annotation_id)
        annotations.append(annotation)
    return annotations


def _annotation_result(label: dict[str, Any], case: dict[str, Any], analysis: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    annotations = _case_annotations(case, analysis)
    results = []
    for expected in _list_of_dicts(label.get("expected_annotations")):
        expected_image_id = str(expected.get("source_image_id") or label.get("source_image_id") or "")
        key = (str(expected.get("label", "")).lower(), str(expected.get("coordinate_type", "")))
        candidates = [
            item for item in annotations
            if (str(item.get("label", "")).lower(), str(item.get("coordinate", {}).get("type", "")) if isinstance(item.get("coordinate"), dict) else "") == key
            and (not expected_image_id or str(item.get("source_image_id") or "") == expected_image_id)
        ]
        reference_box = expected.get("coordinate") if isinstance(expected.get("coordinate"), dict) else None
        expected_points = _coordinate_points({"points": expected.get("points")})
        box_spatial = bool(reference_box and key[1] in {"bbox", "grounding_box"})
        point_spatial = bool(expected_points and key[1] == "point")
        polygon_spatial = key[1] == "polygon"
        spatial_evaluated = box_spatial or point_spatial or polygon_spatial
        best_iou = max((_bbox_iou(reference_box, item.get("coordinate") if isinstance(item.get("coordinate"), dict) else {}) for item in candidates), default=0.0) if box_spatial else None
        best_point_distance = None
        if point_spatial:
            reference_point = expected_points[0]
            distances = []
            for item in candidates:
                coordinate = item.get("coordinate") if isinstance(item.get("coordinate"), dict) else {}
                try:
                    distances.append(math.dist(reference_point, (float(coordinate.get("x")), float(coordinate.get("y")))))
                except (TypeError, ValueError):
                    continue
            best_point_distance = min(distances, default=None)
        min_iou = float(expected.get("min_iou", 0.3))
        max_point_distance = float(expected.get("max_point_distance", 10))
        min_vertex_count = int(expected.get("min_vertex_count", 3))
        valid_geometry_count = sum(1 for item in candidates if _geometry_valid(item.get("coordinate") if isinstance(item.get("coordinate"), dict) else {}, min_vertex_count))
        matched = bool(candidates)
        if box_spatial:
            matched = matched and bool(best_iou is not None and best_iou >= min_iou)
        elif point_spatial:
            matched = matched and bool(best_point_distance is not None and best_point_distance <= max_point_distance)
        elif polygon_spatial:
            matched = valid_geometry_count > 0
        results.append(
            {
                "label": expected.get("label", ""),
                "coordinate_type": expected.get("coordinate_type", ""),
                "required": bool(expected.get("required", False)),
                "matched": matched,
                "candidate_count": len(candidates),
                "spatial_evaluated": spatial_evaluated,
                "best_iou": round(best_iou, 4) if best_iou is not None else None,
                "min_iou": min_iou if box_spatial else None,
                "best_point_distance": round(best_point_distance, 3) if best_point_distance is not None else None,
                "max_point_distance": max_point_distance if point_spatial else None,
                "min_vertex_count": min_vertex_count if polygon_spatial else None,
                "valid_geometry_count": valid_geometry_count,
                "localization_hit": matched if spatial_evaluated else None,
                "note": expected.get("note", ""),
                "source_image_id": expected_image_id,
            }
        )
    return results


def _result_card_matches(label: dict[str, Any], case: dict[str, Any], analysis: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    predicted_cards = _result_card_lookup(case, analysis)
    matches = []
    for expected in label.get("expected_findings") or []:
        label_name = str(expected.get("label", ""))
        card = predicted_cards.get(label_name.lower())
        predicted_status = str((card or {}).get("status", "not_predicted"))
        matches.append(
            {
                "label": label_name,
                "result_card_id": (card or {}).get("id", ""),
                "expected_status": expected.get("status", "uncertain"),
                "predicted_status": predicted_status,
                "matched": predicted_status == expected.get("status", "uncertain"),
                "review_status": (card or {}).get("review_status", "not_reviewed"),
                "annotation_refs": (card or {}).get("annotation_refs") or [],
                "validation_status": "local_agreement_checked" if card else "not_predicted",
            }
        )
    return matches


def _case_result(label: dict[str, Any]) -> dict[str, Any]:
    if label.get("skip_reason"):
        return {
            "case_id": label["case_id"],
            "title": label.get("title", ""),
            "status": "skipped_by_label",
            "matches": [],
            "notes": [label["skip_reason"]],
        }
    case = get_case(label["case_id"])
    if not case:
        return {"case_id": label["case_id"], "title": label.get("title", ""), "status": "skipped_missing_case", "matches": [], "notes": ["Case is not in local library."]}
    source_image_id = str(label.get("source_image_id") or "")
    analyses_by_image = case.get("analyses_by_image") if isinstance(case.get("analyses_by_image"), dict) else {}
    analysis_value = analyses_by_image.get(source_image_id) if source_image_id else case.get("analysis")
    analysis = analysis_value if isinstance(analysis_value, dict) else {}
    if not analysis:
        return {"case_id": label["case_id"], "title": case.get("title") or label.get("title", ""), "status": "skipped_no_analysis", "matches": [], "notes": ["Case has no analysis result yet."]}

    reading = analysis.get("systematic_reading") if isinstance(analysis.get("systematic_reading"), dict) else {}
    predicted_body_region = str(reading.get("body_region", ""))
    expected_body_region = str(label.get("expected_body_region") or "")
    body_region_match = bool(expected_body_region) and expected_body_region.lower() in predicted_body_region.lower()
    predicted_findings = _finding_lookup(case, analysis)
    matches = []
    for expected in label.get("expected_findings") or []:
        label_name = str(expected.get("label", ""))
        predicted_status = predicted_findings.get(label_name.lower(), "not_predicted")
        matches.append(
            {
                "label": label_name,
                "expected_status": expected.get("status", "uncertain"),
                "predicted_status": predicted_status,
                "matched": predicted_status == expected.get("status", "uncertain"),
                "note": expected.get("note", ""),
            }
        )
    model_trace = _list_of_dicts(analysis.get("model_trace"))
    return {
        "case_id": label["case_id"],
        "title": case.get("title") or label.get("title", ""),
        "dataset_name": label.get("dataset_name", "local validation set"),
        "split": label.get("split", "local"),
        "source_image_id": source_image_id or str(case.get("active_image_id") or ""),
        "source_image_index": label.get("source_image_index"),
        "source_series_id": label.get("source_series_id", ""),
        "source_view": label.get("source_view", ""),
        "status": "evaluated",
        "body_region": {
            "expected": expected_body_region,
            "predicted": predicted_body_region,
            "matched": body_region_match if expected_body_region else None,
        },
        "image_quality": _quality_result(label, analysis),
        "matches": matches,
        "result_card_matches": _result_card_matches(label, case, analysis),
        "annotation_checks": _annotation_result(label, case, analysis),
        "warnings": _string_list(analysis.get("warnings")),
        "trace_count": len(model_trace),
        "runtime_snapshot": analysis.get("runtime_snapshot") if isinstance(analysis.get("runtime_snapshot"), dict) else (case.get("runtime") if isinstance(case.get("runtime"), dict) else {}),
        "model_refs": sorted({str(item.get("model", "")) for item in model_trace if item.get("model")}),
        "protocol_notes": label.get("protocol_notes", ""),
    }


def _dataset_summary(labels: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    datasets = sorted({str(label.get("dataset_name") or "local validation set") for label in labels})
    splits = sorted({str(label.get("split") or "local") for label in labels})
    return {
        "protocol_ids": sorted({str(label.get("protocol_id") or "local-research-protocol") for label in labels}),
        "dataset_names": datasets,
        "splits": splits,
        "anatomy_coverage": sorted({str(label.get("anatomy") or label.get("expected_body_region") or "") for label in labels if label.get("anatomy") or label.get("expected_body_region")}),
        "view_coverage": sorted({str(label.get("view") or "") for label in labels if label.get("view")}),
        "age_group_coverage": sorted({str(label.get("age_group") or "") for label in labels if label.get("age_group")}),
        "subgroup_notes": sorted({str(label.get("subgroup_notes") or "") for label in labels if label.get("subgroup_notes")}),
        "reviewers": sorted({str(label.get("reviewer") or "") for label in labels if label.get("reviewer")}),
        "label_count": len(labels),
        "result_count": len(results),
        "case_status_counts": {status: sum(1 for item in results if item.get("status") == status) for status in sorted({str(item.get("status")) for item in results})},
    }


def _runtime_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [item for item in results if item.get("status") == "evaluated"]
    snapshots = [item.get("runtime_snapshot") for item in evaluated if isinstance(item.get("runtime_snapshot"), dict)]
    backends = sorted({str(item.get("primary_backend")) for item in snapshots if item.get("primary_backend")})
    model_refs = sorted({model for item in evaluated for model in _string_list(item.get("model_refs"))})
    return {"backends": backends, "model_refs": model_refs}


def run_validation(case_ids: list[str] | None = None) -> dict[str, Any]:
    labels = list_validation_labels()
    valid_labels = [label for label in labels if not label.get("invalid")]
    if case_ids:
        wanted = set(case_ids)
        valid_labels = [label for label in valid_labels if label["case_id"] in wanted]
    results = [_case_result(label) for label in valid_labels]

    evaluated = [result for result in results if result["status"] == "evaluated"]
    finding_matches = [match for result in evaluated for match in _list_of_dicts(result.get("matches"))]
    result_card_matches = [match for result in evaluated for match in _list_of_dicts(result.get("result_card_matches"))]
    body_checks = [result["body_region"] for result in evaluated if result.get("body_region", {}).get("matched") is not None]
    annotation_checks = [check for result in evaluated for check in _list_of_dicts(result.get("annotation_checks"))]
    required_annotation_checks = [check for check in annotation_checks if check.get("required")]
    spatial_box_checks = [check for check in annotation_checks if check.get("spatial_evaluated")]
    spatial_box_checks = [check for check in spatial_box_checks if check.get("coordinate_type") in {"bbox", "grounding_box"}]
    spatial_point_checks = [check for check in annotation_checks if check.get("coordinate_type") == "point" and check.get("spatial_evaluated")]
    spatial_polygon_checks = [check for check in annotation_checks if check.get("coordinate_type") == "polygon" and check.get("spatial_evaluated")]
    positive_mismatch_flags = [match for match in finding_matches if match.get("expected_status") == "positive" and not match.get("matched")]
    negative_mismatch_flags = [match for match in finding_matches if match.get("expected_status") == "negative" and match.get("predicted_status") == "positive"]
    metrics = {
        "label_count": len(valid_labels),
        "evaluated_cases": len(evaluated),
        "skipped_by_label": sum(1 for result in results if result["status"] == "skipped_by_label"),
        "skipped_missing_case": sum(1 for result in results if result["status"] == "skipped_missing_case"),
        "skipped_no_analysis": sum(1 for result in results if result["status"] == "skipped_no_analysis"),
        "finding_labels": len(finding_matches),
        "finding_agreements": sum(1 for match in finding_matches if match["matched"]),
        "result_card_labels": len(result_card_matches),
        "result_card_agreements": sum(1 for match in result_card_matches if match["matched"]),
        "positive_mismatch_flags": len(positive_mismatch_flags),
        "negative_to_positive_mismatch_flags": len(negative_mismatch_flags),
        "body_region_checks": len(body_checks),
        "body_region_agreements": sum(1 for item in body_checks if item["matched"]),
        "annotation_checks": len(annotation_checks),
        "required_annotation_agreements": sum(1 for check in required_annotation_checks if check["matched"]),
        "spatial_box_checks": len(spatial_box_checks),
        "spatial_point_checks": len(spatial_point_checks),
        "spatial_polygon_checks": len(spatial_polygon_checks),
        "localization_hits": sum(1 for check in spatial_box_checks if check.get("localization_hit")),
        "point_hits": sum(1 for check in spatial_point_checks if check.get("localization_hit")),
        "polygon_geometry_hits": sum(1 for check in spatial_polygon_checks if check.get("localization_hit")),
    }
    metrics["finding_agreement_rate"] = round(metrics["finding_agreements"] / metrics["finding_labels"], 3) if metrics["finding_labels"] else None
    metrics["result_card_agreement_rate"] = round(metrics["result_card_agreements"] / metrics["result_card_labels"], 3) if metrics["result_card_labels"] else None
    metrics["body_region_agreement_rate"] = round(metrics["body_region_agreements"] / metrics["body_region_checks"], 3) if metrics["body_region_checks"] else None
    metrics["required_annotation_agreement_rate"] = round(metrics["required_annotation_agreements"] / len(required_annotation_checks), 3) if required_annotation_checks else None
    metrics["box_hit_rate"] = round(metrics["localization_hits"] / len(spatial_box_checks), 3) if spatial_box_checks else None
    metrics["mean_best_iou"] = round(sum(float(check.get("best_iou") or 0) for check in spatial_box_checks) / len(spatial_box_checks), 3) if spatial_box_checks else None
    metrics["point_hit_rate"] = round(metrics["point_hits"] / len(spatial_point_checks), 3) if spatial_point_checks else None
    metrics["polygon_geometry_hit_rate"] = round(metrics["polygon_geometry_hits"] / len(spatial_polygon_checks), 3) if spatial_polygon_checks else None

    false_alert_burden = {
        "false_alert_count": len(negative_mismatch_flags),
        "evaluated_cases": len(evaluated),
        "false_alerts_per_case": round(len(negative_mismatch_flags) / len(evaluated), 3) if evaluated else None,
        "definition": "Reference-negative finding labels predicted positive; local research review only.",
    }
    missed_reference_summary = {
        "missed_reference_count": len(positive_mismatch_flags),
        "positive_reference_labels": sum(1 for match in finding_matches if match.get("expected_status") == "positive"),
        "definition": "Reference-positive finding labels without agreement; local research review only.",
    }
    known_failures = [
        f"{result.get('case_id')}: {result.get('status')}"
        for result in results
        if result.get("status") != "evaluated"
    ]
    for result in evaluated:
        for match in _list_of_dicts(result.get("matches")):
            if not match.get("matched"):
                known_failures.append(
                    f"{result.get('case_id')}: {match.get('label')} expected {match.get('expected_status')} but got {match.get('predicted_status')}"
                )
        for check in _list_of_dicts(result.get("annotation_checks")):
            if check.get("required") and not check.get("matched"):
                known_failures.append(f"{result.get('case_id')}: missed required localization {check.get('label')}")

    dataset_summary = _dataset_summary(valid_labels, results)
    validation_evidence_draft = {
        "protocol_id": ", ".join(dataset_summary["protocol_ids"]),
        "dataset_name": ", ".join(dataset_summary["dataset_names"]),
        "held_out_split": ", ".join(dataset_summary["splits"]),
        "case_count": len(evaluated),
        "label_count": len(finding_matches) + len(annotation_checks),
        "metric_summary": {key: value for key, value in metrics.items() if value is not None},
        "false_alert_burden": false_alert_burden,
        "missed_reference_summary": missed_reference_summary,
        "known_failures": known_failures or ["No failures observed in this bounded run; broader failure discovery remains required."],
        "subgroup_coverage": {
            "anatomy": dataset_summary["anatomy_coverage"],
            "views": dataset_summary["view_coverage"],
            "age_groups": dataset_summary["age_group_coverage"],
            "notes": "; ".join(dataset_summary["subgroup_notes"]),
        },
        "reviewer": ", ".join(dataset_summary["reviewers"]),
        "review_date": now_iso()[:10],
        "artifact_hash": "",
        "artifact_hash_algorithm": "sha256",
        "weights_filename": "",
        "report_reference": "",
        "evidence_scope": "local_research_prototype_only",
    }

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "evaluation_status": "research_only_not_clinical_performance",
        "dataset_summary": dataset_summary,
        "protocol_notes": sorted({str(label.get("protocol_notes")) for label in valid_labels if label.get("protocol_notes")}),
        "runtime_snapshot_summary": _runtime_summary(results),
        "model_card_refs": _runtime_summary(results)["model_refs"],
        "failure_cases": [result for result in results if result.get("status") != "evaluated"],
        "metrics": metrics,
        "false_alert_burden": false_alert_burden,
        "missed_reference_summary": missed_reference_summary,
        "model_card_evidence_draft": validation_evidence_draft,
        "results": results,
        "limitations": [
            "Agreement metrics are for local research review only.",
            "This workbench does not establish clinical sensitivity, specificity, or diagnostic performance.",
            "Labels need documented source, reviewer, and reference standard before meaningful evaluation.",
        ],
    }


def export_validation_report(result: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = get_settings()
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    report = result or run_validation()
    path = settings.exports_dir / f"validation_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}.json"
    evidence = report.get("model_card_evidence_draft")
    if isinstance(evidence, dict):
        evidence["report_reference"] = str(path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "report": report}
