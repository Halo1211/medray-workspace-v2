from __future__ import annotations

import re
from typing import Any


ANATOMY_PROFILES: dict[str, dict[str, Any]] = {
    "chest": {
        "label": "Chest",
        "body_region": "Chest X-ray",
        "model_slot": "chest_xray_model",
        "terms": {"chest": "chest", "cxr": "chest", "thorax": "chest", "lung": "chest"},
        "finding_taxonomy": ["airspace opacity", "atelectasis", "pneumothorax", "pleural effusion", "pulmonary edema", "cardiomegaly", "nodule/mass", "mediastinal/hilar abnormality", "device position", "visible osseous abnormality"],
        "required_views": ["PA or AP", "lateral when available"],
        "supported_tasks": ["quality", "classification", "grounding", "report", "manual_annotation"],
    },
    "msk": {
        "label": "MSK / trauma",
        "body_region": "MSK/orthopedic X-ray",
        "model_slot": "msk_xray_model",
        "terms": {
            "pelvis": "pelvis", "hip": "hip", "shoulder": "shoulder", "clavicle": "clavicle", "elbow": "elbow",
            "humerus": "humerus", "forearm": "forearm", "radius": "forearm", "ulna": "forearm", "wrist": "wrist",
            "hand": "hand", "finger": "finger", "thumb": "thumb", "femur": "femur", "knee": "knee", "patella": "knee",
            "tibia": "lower leg", "fibula": "lower leg", "ankle": "ankle", "foot": "foot", "toe": "toe", "calcaneus": "foot",
            "rib": "ribs", "ribs": "ribs", "ac joint": "shoulder", "scapula": "shoulder",
        },
        "finding_taxonomy": ["fracture", "dislocation/subluxation", "alignment abnormality", "joint-space abnormality", "degenerative change", "lytic/sclerotic lesion", "periosteal reaction", "soft-tissue swelling", "effusion", "hardware complication"],
        "required_views": ["at least two orthogonal views when applicable"],
        "supported_tasks": ["quality", "classification", "localization", "grounding", "report", "manual_annotation"],
    },
    "abdomen": {
        "label": "Abdomen / KUB",
        "body_region": "Abdomen X-ray",
        "model_slot": "abdomen_xray_model",
        "terms": {"abdomen": "abdomen", "abdominal": "abdomen", "kub": "KUB", "kidney ureter bladder": "KUB"},
        "finding_taxonomy": ["bowel-gas pattern", "small-bowel dilatation", "large-bowel dilatation", "air-fluid levels", "free intraperitoneal air", "calcification/stone", "organ silhouette/mass effect", "device/foreign body", "visible osseous abnormality"],
        "required_views": ["supine", "upright or decubitus when free air/obstruction is queried"],
        "supported_tasks": ["quality", "classification", "grounding", "report", "manual_annotation"],
    },
    "spine": {
        "label": "Spine",
        "body_region": "Spine X-ray",
        "model_slot": "spine_xray_model",
        "terms": {"cervical spine": "cervical spine", "c-spine": "cervical spine", "thoracic spine": "thoracic spine", "t-spine": "thoracic spine", "lumbar spine": "lumbar spine", "l-spine": "lumbar spine", "lumbar": "lumbar spine", "sacrum": "sacrum", "coccyx": "coccyx", "scoliosis": "whole spine", "spine": "spine"},
        "finding_taxonomy": ["alignment abnormality", "vertebral height loss/fracture", "disc-space narrowing", "degenerative change", "spondylolisthesis", "destructive/sclerotic lesion", "curvature", "prevertebral/paraspinal soft tissue", "hardware complication"],
        "required_views": ["AP", "lateral", "additional views when clinically indicated"],
        "supported_tasks": ["quality", "classification", "localization", "grounding", "report", "manual_annotation"],
    },
    "skull_facial": {
        "label": "Skull / facial / sinus",
        "body_region": "Skull/facial X-ray",
        "model_slot": "skull_facial_xray_model",
        "terms": {"facial bones": "facial bones", "facial": "facial bones", "skull": "skull", "sinus": "paranasal sinuses", "mandible": "mandible", "nasal bone": "nasal bones", "orbit": "orbits", "mastoid": "mastoids"},
        "finding_taxonomy": ["fracture/alignment abnormality", "sinus opacity/fluid level", "focal bone lesion", "soft-tissue swelling", "foreign body", "dental/mandibular abnormality"],
        "required_views": ["region-specific orthogonal views"],
        "supported_tasks": ["quality", "classification", "grounding", "report", "manual_annotation"],
    },
    "general": {
        "label": "General X-ray",
        "body_region": "Unknown/general X-ray",
        "model_slot": "general_xray_model",
        "terms": {},
        "finding_taxonomy": ["image quality", "anatomic alignment", "bone abnormality", "joint abnormality", "soft-tissue abnormality", "device/foreign body", "other visible abnormality"],
        "required_views": ["confirm body part and projection before interpretation"],
        "supported_tasks": ["quality", "report", "manual_annotation"],
    },
}


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _term_match(text: str, term: str) -> bool:
    normalized_term = _normalized(term)
    return bool(normalized_term and re.search(rf"(?:^|\s){re.escape(normalized_term)}(?:$|\s)", text))


def _laterality(metadata: dict[str, Any], text: str) -> str:
    raw = _normalized(metadata.get("Laterality") or metadata.get("ImageLaterality"))
    if raw in {"l", "left"}:
        return "left"
    if raw in {"r", "right"}:
        return "right"
    if raw in {"b", "bilateral", "both"}:
        return "bilateral"
    if _term_match(text, "left"):
        return "left"
    if _term_match(text, "right"):
        return "right"
    if _term_match(text, "bilateral"):
        return "bilateral"
    return "unknown"


def _view(metadata: dict[str, Any], text: str) -> str:
    raw = str(metadata.get("ViewPosition") or metadata.get("view") or "").strip().upper()
    if raw:
        return raw
    view_terms = [("AP", [" ap ", "anteroposterior", "portable"]), ("PA", [" pa ", "posteroanterior"]), ("LATERAL", ["lateral", " lat "]), ("OBLIQUE", ["oblique"]), ("SUPINE", ["supine"]), ("UPRIGHT", ["upright", "erect"]), ("DECUBITUS", ["decubitus"])]
    padded = f" {text} "
    for label, terms in view_terms:
        if any(term in padded for term in terms):
            return label
    return "unknown"


def anatomy_profiles() -> list[dict[str, Any]]:
    return [{"id": profile_id, **{key: value for key, value in profile.items() if key != "terms"}} for profile_id, profile in ANATOMY_PROFILES.items()]


def route_study(metadata: dict[str, Any], filename: str | None = None, custom_prompt: str = "", profile_override: str = "") -> dict[str, Any]:
    sources = [
        ("dicom_body_part", metadata.get("BodyPartExamined"), 0.99),
        ("study_description", " ".join(str(metadata.get(key) or "") for key in ["StudyDescription", "SeriesDescription", "ProtocolName"]), 0.94),
        ("filename", filename, 0.82),
        ("user_context", custom_prompt, 0.65),
    ]
    all_text = _normalized(" ".join(str(value or "") for _, value, _ in sources))
    route_profile_id = "general"
    anatomy = "unknown"
    matched_term = ""
    route_source = "fallback"
    confidence = 0.2

    terms: list[tuple[int, str, str, str]] = []
    for profile_id, profile in ANATOMY_PROFILES.items():
        if profile_id == "general":
            continue
        for term, canonical in profile["terms"].items():
            terms.append((len(_normalized(term)), profile_id, term, canonical))
    terms.sort(reverse=True)

    if profile_override in ANATOMY_PROFILES:
        route_profile_id = profile_override
        anatomy = ANATOMY_PROFILES[profile_override]["label"].lower()
        matched_term = profile_override
        route_source = "reviewer_override"
        confidence = 1.0
    else:
        for source_name, source_value, source_confidence in sources:
            text = _normalized(source_value)
            if not text:
                continue
            match = next(((profile_id, term, canonical) for _, profile_id, term, canonical in terms if _term_match(text, term)), None)
            if match:
                route_profile_id, matched_term, anatomy = match
                route_source = source_name
                confidence = source_confidence
                break

    profile = ANATOMY_PROFILES[route_profile_id]
    warnings: list[str] = []
    if route_profile_id == "general":
        warnings.append("Body part is not confidently identified; anatomy-specific model inference is disabled until the study is routed or confirmed.")
    if _view(metadata, all_text) == "unknown":
        warnings.append("Projection/view is unknown; adequacy and view-dependent findings require reviewer confirmation.")
    return {
        "profile_id": route_profile_id,
        "profile_label": profile["label"],
        "body_region": profile["body_region"],
        "anatomy": anatomy,
        "laterality": _laterality(metadata, all_text),
        "view": _view(metadata, all_text),
        "confidence": confidence,
        "source": route_source,
        "matched_term": matched_term,
        "model_slot": profile["model_slot"],
        "selected_model": "disabled",
        "support_status": "fallback_only",
        "supported_tasks": list(profile["supported_tasks"]),
        "finding_taxonomy": list(profile["finding_taxonomy"]),
        "required_views": list(profile["required_views"]),
        "warnings": warnings,
    }


def resolve_profile_model(route: dict[str, Any], runtime_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    runtime = runtime_snapshot or {}
    configured = str(runtime.get(str(route["model_slot"])) or "inherit").strip()
    selected = str(runtime.get("vision_language_model") or "disabled").strip() if configured in {"", "inherit"} else configured
    raw_warnings = route.get("warnings")
    warnings = [str(item) for item in raw_warnings] if isinstance(raw_warnings, list) else []
    support_status = "fallback_only"
    if selected and selected not in {"disabled", "demo-vlm"}:
        if selected.startswith("torchxrayvision:"):
            support_status = "unsupported_model_task"
            warnings.append(f"{selected} is a classifier and cannot be used as the {route['profile_label']} vision-language model.")
            selected = "disabled"
        elif route["profile_id"] == "general":
            support_status = "routing_required"
            warnings.append("General/unknown anatomy is not sent to a configured anatomy model until the body part is confirmed.")
            selected = "disabled"
        else:
            support_status = "configured_unvalidated"
            warnings.append(f"Model {selected} is configured for {route['profile_label']} but has no profile-specific local validation record yet.")
    return {**route, "selected_model": selected or "disabled", "support_status": support_status, "warnings": warnings}
