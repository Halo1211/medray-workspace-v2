from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.anatomy.router import anatomy_profiles, resolve_profile_model, route_study
from app.annotations.exporter import export_annotated_png, export_annotation_review_package
from app.audit.bundle import export_audit_bundle
from app.config import database_location_info, get_settings, set_database_folder
from app.dicom.safety import dicom_safety_report, export_deidentified_dicom, export_deidentified_metadata
from app.model_finder.providers import (
    clear_github_token,
    clear_huggingface_token,
    download_manager,
    github_login_status,
    huggingface_login_status,
    hardware_recommendations,
    import_local_model,
    list_local_model_artifacts,
    list_ollama_models,
    model_detail,
    runtime_hardware_plan,
    runtime_local_model_gate_issues,
    save_github_token,
    save_huggingface_token,
    save_local_model_card,
    search_all_sources,
    search_github,
    search_hugging_face,
)
from app.model_registry.cards import list_model_cards
from app.models.schemas import MAX_POLYGON_VERTICES, CaseRecord, ChatMessage, RuntimeConfig
from app.pipelines.analysis_pipeline import run_analysis
from app.reference_catalog import get_reference_catalog
from app.reports.generator import export_report
from app.runtime.adapters import chat_response
from app.services.image_service import image_to_data_url, ingest_upload
from app.storage.db import clear_case_database, delete_case, get_case, list_cases, load_runtime_config, save_case, save_runtime_config
from app.studies.images import active_study_image, normalize_case_images, study_image_from_ingest
from app.results.differential import build_differential_assistance
from app.validation.workbench import (
    delete_validation_label,
    export_validation_report,
    list_validation_labels,
    run_validation,
    save_validation_label,
    write_curated_sample_fixture,
)
from app.vision.registry import list_vision_adapters

router = APIRouter()

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _is_servable_image_path(path: Path) -> bool:
    settings = get_settings()
    resolved = path.expanduser().resolve()
    allowed_roots = [settings.cases_dir.resolve(), settings.exports_dir.resolve()]
    return (
        resolved.exists()
        and resolved.is_file()
        and resolved.suffix.lower() in IMAGE_SUFFIXES
        and any(resolved == root or resolved.is_relative_to(root) for root in allowed_roots)
    )


def _validate_case_file_paths(case: dict[str, Any]) -> None:
    """Keep persisted study files inside the application case root."""
    cases_root = get_settings().cases_dir.resolve()
    for index, image in enumerate(case.get("images") or []):
        if not isinstance(image, dict):
            continue
        for field in ("image_path", "preview_path", "source_path"):
            raw_path = image.get(field)
            if not raw_path:
                continue
            resolved = Path(str(raw_path)).expanduser().resolve()
            if not resolved.is_relative_to(cases_root):
                raise ValueError(f"Study image {index} has a {field} outside the local cases directory.")


def _validate_case_geometry(case: dict[str, Any]) -> None:
    """Reject oversized polygons before raw case JSON reaches the browser/exporters."""
    collections: list[Any] = [case.get("annotations")]
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    collections.append(analysis.get("annotations"))
    per_image = case.get("analyses_by_image") if isinstance(case.get("analyses_by_image"), dict) else {}
    collections.extend(item.get("annotations") for item in per_image.values() if isinstance(item, dict))
    for collection in collections:
        for annotation in collection if isinstance(collection, list) else []:
            if not isinstance(annotation, dict):
                continue
            coordinate = annotation.get("coordinate") if isinstance(annotation.get("coordinate"), dict) else {}
            points = coordinate.get("points") if isinstance(coordinate.get("points"), list) else []
            if str(coordinate.get("type") or "") == "polygon" and len(points) > MAX_POLYGON_VERTICES:
                raise ValueError(f"Polygon coordinates cannot contain more than {MAX_POLYGON_VERTICES} vertices.")


def _annotation_matches_image(annotation: dict[str, Any], image: dict[str, Any], first_image: bool = False, images: list[dict[str, Any]] | None = None) -> bool:
    source_id = str(annotation.get("source_image_id") or "")
    accepted_ids = {
        str(image.get("image_id") or ""),
        str(image.get("sop_instance_uid") or ""),
    }
    filename = str(image.get("filename") or "")
    if filename and sum(1 for item in (images or []) if str(item.get("filename") or "") == filename) == 1:
        accepted_ids.add(filename)
    if source_id in {"", "primary"}:
        return first_image
    return source_id in accepted_ids


def _dicom_source(case: dict[str, Any], image_id: str) -> tuple[dict[str, Any], Path]:
    normalized = normalize_case_images(case)
    image = next((item for item in normalized.get("images", []) if str(item.get("image_id")) == image_id), None)
    if not image:
        raise HTTPException(404, "Study image not found")
    source = Path(str(image.get("source_path") or "")).expanduser().resolve()
    cases_root = get_settings().cases_dir.resolve()
    if not source.exists() or not source.is_file() or source.suffix.lower() not in {".dcm", ".dicom"} or not source.is_relative_to(cases_root):
        raise HTTPException(404, "Original DICOM source not found")
    return image, source


@router.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {"ok": True, "app": settings.app_name, "version": settings.app_version, "data_dir": str(settings.data_dir)}


@router.get("/references")
def references() -> dict[str, Any]:
    return get_reference_catalog()


@router.get("/anatomy/profiles")
def anatomy_profile_list() -> list[dict[str, Any]]:
    return anatomy_profiles()


@router.post("/anatomy/route-preview")
def anatomy_route_preview(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    route = route_study(metadata, payload.get("filename"), payload.get("custom_prompt", ""), payload.get("profile_override", ""))
    runtime = RuntimeConfig(**load_runtime_config(RuntimeConfig().model_dump(mode="json"))).model_dump(mode="json")
    return resolve_profile_model(route, runtime)


@router.get("/validation/labels")
def validation_labels() -> list[dict[str, Any]]:
    return list_validation_labels()


@router.post("/validation/labels")
def validation_label_save(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return save_validation_label(payload)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/validation/labels/{case_id}")
def validation_label_delete(case_id: str) -> dict[str, Any]:
    return delete_validation_label(case_id)


@router.get("/validation/fixtures/curated-sample")
def validation_curated_sample_fixture() -> dict[str, Any]:
    return write_curated_sample_fixture()


@router.post("/validation/run")
def validation_run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    result = run_validation(payload.get("case_ids") or None)
    if payload.get("export"):
        exported = export_validation_report(result)
        result["export_path"] = exported["path"]
    return result


@router.post("/validation/export")
def validation_export() -> dict[str, Any]:
    return export_validation_report()


@router.post("/upload")
def upload(file: UploadFile = File(...), case_title: str = Form("")) -> dict[str, Any]:
    try:
        image = ingest_upload(file)
        study_image = study_image_from_ingest(image, image["case_id"], 0)
        case = CaseRecord(
            case_id=image["case_id"],
            # Do not expose the uploaded filename as the case identity. The
            # reviewer can enter an NPM/patient label in the Reading Room.
            title=case_title.strip() or "New X-ray case",
            image_path=image["stored_path"],
            image_preview=image["preview_path"],
            metadata=image["metadata"],
            file_hashes=image["hashes"],
            images=[study_image],
            active_image_id=study_image["image_id"],
        )
        save_case(case.model_dump(mode="json"))
        return {"case": case.model_dump(mode="json"), "image": image, "preview_data_url": image_to_data_url(image["preview_path"])}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/cases")
def clear_cases() -> dict[str, Any]:
    try:
        result = clear_case_database()
        deleted_labels = 0
        for label in list_validation_labels():
            if label.get("case_id") and delete_validation_label(str(label["case_id"])).get("deleted"):
                deleted_labels += 1
        return {**result, "deleted_validation_label_count": deleted_labels}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/cases/{case_id}")
def delete_case_record(case_id: str) -> dict[str, Any]:
    if not get_case(case_id):
        raise HTTPException(404, "Case not found")
    try:
        result = delete_case(case_id)
        label_result = delete_validation_label(case_id)
        return {**result, "validation_label_deleted": bool(label_result.get("deleted"))}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/cases/{case_id}/images")
def add_case_image(case_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    try:
        case = normalize_case_images(case)
        image = ingest_upload(file, case_id=case_id)
        study_image = study_image_from_ingest(image, case_id, len(case["images"]))
        case["images"].append(study_image)
        case = normalize_case_images(case)
        case["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_case(case)
        saved_image = case["images"][-1]
        return {"case": case, "image": saved_image}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/cases/{case_id}/active-image")
def set_active_case_image(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    case = normalize_case_images(case)
    image_id = str(payload.get("image_id") or "")
    if not any(str(image.get("image_id")) == image_id for image in case["images"]):
        raise HTTPException(404, "Study image not found")
    case["active_image_id"] = image_id
    case = normalize_case_images(case)
    case["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_case(case)
    return case


@router.get("/dicom/{case_id}/images/{image_id}/safety")
def dicom_image_safety(case_id: str, image_id: str) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    _image, source = _dicom_source(case, image_id)
    try:
        return dicom_safety_report(str(source))
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/dicom/{case_id}/images/{image_id}/export-metadata")
def dicom_metadata_export(case_id: str, image_id: str) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    image, source = _dicom_source(case, image_id)
    try:
        return export_deidentified_metadata(str(source), case_id, int(image.get("index") or 0))
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/dicom/{case_id}/images/{image_id}/export-deidentified")
def dicom_deidentified_export(case_id: str, image_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    image, source = _dicom_source(case, image_id)
    try:
        return export_deidentified_dicom(
            str(source),
            case_id,
            int(image.get("index") or 0),
            acknowledge_burned_in_risk=(payload or {}).get("acknowledge_burned_in_risk") is True,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/image")
def image(path: str) -> FileResponse:
    p = Path(path).expanduser().resolve()
    if not _is_servable_image_path(p):
        raise HTTPException(404, "Image not found")
    return FileResponse(p)


@router.post("/analysis/{case_id}")
async def analyze(case_id: str, custom_prompt: str = Form(""), language: str = Form("id"), anatomy_profile_override: str = Form("")) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    case = normalize_case_images(case)
    try:
        _validate_case_file_paths(case)
        _validate_case_geometry(case)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    active_image = active_study_image(case)
    if not active_image:
        raise HTTPException(404, "Case image not found")
    image = {
        "stored_path": active_image.get("image_path"),
        "preview_path": active_image.get("preview_path"),
        "metadata": active_image.get("metadata", {}),
        "filename": active_image.get("filename") or case.get("title"),
        "format": active_image.get("format"),
        "width": active_image.get("width"),
        "height": active_image.get("height"),
        "hashes": active_image.get("file_hashes", {}),
        "source_image_id": active_image.get("image_id"),
        "source_image_index": active_image.get("index", 0),
        "source_series_id": active_image.get("series_id", ""),
        "source_view": active_image.get("view", ""),
    }
    runtime = RuntimeConfig(**load_runtime_config(RuntimeConfig().model_dump(mode="json")))
    runtime_snapshot = runtime.model_dump(mode="json")
    report_language = "en" if language == "en" else "id"
    result = await run_analysis(case_id, image, custom_prompt=custom_prompt, backend=runtime.primary_backend.value, runtime_snapshot=runtime_snapshot, language=report_language, anatomy_profile_override=anatomy_profile_override)
    all_existing_annotations = _list_of_dicts(case.get("annotations"))
    first_image = bool(case.get("images") and case["images"][0].get("image_id") == active_image.get("image_id"))
    existing_manual = [
        annotation
        for annotation in all_existing_annotations
        if str(annotation.get("source", "")) == "manual user annotation" and _annotation_matches_image(annotation, active_image, first_image, case.get("images", []))
    ]
    other_image_annotations = [annotation for annotation in all_existing_annotations if not _annotation_matches_image(annotation, active_image, first_image, case.get("images", []))]
    result_annotations = _list_of_dicts(result.get("annotations"))
    generated_ids = {str(annotation.get("id", "")) for annotation in result_annotations}
    result_annotations.extend(annotation for annotation in existing_manual if str(annotation.get("id", "")) not in generated_ids)
    result["annotations"] = result_annotations
    analyses_by_image = case.get("analyses_by_image") if isinstance(case.get("analyses_by_image"), dict) else {}
    analyses_by_image[str(active_image["image_id"])] = result
    case["analyses_by_image"] = analyses_by_image
    case["analysis"] = result
    case["annotations"] = [*other_image_annotations, *result["annotations"]]
    case["report"] = result["report"]
    case["updated_at"] = datetime.now(timezone.utc).isoformat()
    case["runtime"] = runtime_snapshot
    save_case(case)
    return result


@router.get("/audit/{case_id}/export")
def audit_export(case_id: str) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    try:
        _validate_case_file_paths(normalize_case_images(case))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return export_audit_bundle(case)


@router.get("/model-cards")
def model_cards() -> list[dict[str, Any]]:
    return list_model_cards()


@router.post("/chat/{case_id}")
def chat(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    runtime = RuntimeConfig(**load_runtime_config(RuntimeConfig().model_dump(mode="json")))
    history = [
        {"role": str(m.get("role")), "content": str(m.get("content", ""))}
        for m in _list_of_dicts(case.get("chat_history"))
        if str(m.get("role")) in {"user", "assistant"}
    ]
    message = str(payload.get("message") or "")
    reply = chat_response(message, history, runtime, case)
    case["chat_history"] = _list_of_dicts(case.get("chat_history"))
    case["chat_history"].append(ChatMessage(role="user", content=message).model_dump(mode="json"))
    case["chat_history"].append(ChatMessage(role="assistant", content=reply["content"]).model_dump(mode="json"))
    case["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_case(case)
    return {"message": case["chat_history"][-1], "backend": reply["backend"], "fallback": reply["fallback"], "history": case["chat_history"]}


@router.get("/cases")
def cases(q: str = "") -> list[dict[str, Any]]:
    return [normalize_case_images(case) for case in list_cases(q)]


@router.get("/cases/{case_id}")
def case_detail(case_id: str) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return normalize_case_images(case)


@router.post("/cases")
def save_case_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("case_id"):
        raise HTTPException(400, "case_id is required")
    incoming_analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else None
    payload = normalize_case_images(payload)
    try:
        _validate_case_file_paths(payload)
        _validate_case_geometry(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    active_id = str(payload.get("active_image_id") or "")
    if active_id and incoming_analysis is not None:
        incoming_analysis["differential_diagnosis"] = build_differential_assistance(
            incoming_analysis.get("result_cards"), incoming_analysis.get("report")
        )
        analyses = payload.get("analyses_by_image") if isinstance(payload.get("analyses_by_image"), dict) else {}
        analyses[active_id] = incoming_analysis
        payload["analyses_by_image"] = analyses
        payload["analysis"] = incoming_analysis
        payload["report"] = incoming_analysis.get("report")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_case(payload)
    return payload


@router.post("/reports/{case_id}/export")
def export_case_report(case_id: str, payload: dict[str, str]) -> dict[str, str]:
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return export_report(case, payload.get("format", "markdown"), payload.get("language", "id"))


@router.post("/annotations/{case_id}/export")
def export_annotations(case_id: str) -> dict[str, str]:
    case = get_case(case_id)
    if not case or not case.get("image_path"):
        raise HTTPException(404, "Case image not found")
    case = normalize_case_images(case)
    try:
        _validate_case_file_paths(case)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    active_image = active_study_image(case)
    if not active_image:
        raise HTTPException(404, "Case image not found")
    analysis = case.get("analysis") if isinstance(case.get("analysis"), dict) else {}
    annotations = _list_of_dicts(case.get("annotations")) or _list_of_dicts(analysis.get("annotations"))
    first_image = bool(case.get("images") and case["images"][0].get("image_id") == active_image.get("image_id"))
    annotations = [annotation for annotation in annotations if _annotation_matches_image(annotation, active_image, first_image, case.get("images", []))]
    image_key = str(active_image.get("index", 0)) if len(case.get("images", [])) > 1 else ""
    path = export_annotated_png(case_id, str(active_image.get("image_path") or ""), annotations, image_key=image_key)
    return {"path": path}


@router.post("/annotations/{case_id}/export-review-package")
def export_annotation_package(case_id: str) -> dict[str, Any]:
    case = get_case(case_id)
    if not case or not case.get("image_path"):
        raise HTTPException(404, "Case image not found")
    try:
        _validate_case_file_paths(normalize_case_images(case))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return export_annotation_review_package(case)


@router.get("/runtime")
def get_runtime() -> dict[str, Any]:
    return RuntimeConfig(**load_runtime_config(RuntimeConfig().model_dump(mode="json"))).model_dump(mode="json")


@router.post("/runtime")
def set_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    config = RuntimeConfig(**payload)
    gate_issues = runtime_local_model_gate_issues(config.model_dump(mode="json"))
    if gate_issues:
        raise HTTPException(400, "Review required before runtime use: " + " ".join(gate_issues))
    save_runtime_config(config.model_dump(mode="json"))
    return config.model_dump(mode="json")


@router.get("/storage/database")
def get_database_location() -> dict[str, str | bool]:
    return database_location_info()


@router.post("/storage/database")
def configure_database_location(payload: dict[str, Any]) -> dict[str, str | bool]:
    try:
        return set_database_folder(str(payload.get("database_folder") or ""))
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/runtime/health")
def runtime_health() -> dict[str, Any]:
    return {"ollama": list_ollama_models(), "recommendations": hardware_recommendations()}


@router.get("/runtime/vision-adapters")
def runtime_vision_adapters() -> list[dict[str, Any]]:
    return list_vision_adapters()


@router.get("/runtime/huggingface")
def runtime_huggingface() -> dict[str, Any]:
    return huggingface_login_status()


@router.post("/runtime/huggingface-token")
def runtime_huggingface_token(payload: dict[str, str]) -> dict[str, Any]:
    try:
        return save_huggingface_token(payload.get("token", ""))
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/runtime/huggingface-token")
def runtime_huggingface_logout() -> dict[str, Any]:
    return clear_huggingface_token()


@router.get("/runtime/github")
def runtime_github() -> dict[str, Any]:
    return github_login_status()


@router.post("/runtime/github-token")
def runtime_github_token(payload: dict[str, str]) -> dict[str, Any]:
    try:
        return save_github_token(payload.get("token", ""))
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/runtime/github-token")
def runtime_github_logout() -> dict[str, Any]:
    return clear_github_token()


@router.get("/models/search")
def model_search(source: str = "hf", q: str = "xray radiology", limit: int = 20, page: int = 1) -> dict[str, Any]:
    try:
        if source == "all":
            payload = search_all_sources(q, limit, page)
            return payload
        if source == "github":
            results = search_github(q, limit, page)
            return {"source": "GitHub", "results": results, "fallback_used": not bool(results)}
        if source == "ollama":
            payload = list_ollama_models()
            return {"source": "Ollama", **payload, "fallback_used": not bool(payload.get("models"))}
        if source == "starter":
            return {"source": "MedRay shortlist removed", "results": [], "fallback_used": True}
        results = search_hugging_face(q, limit, page)
        return {"source": "Hugging Face", "results": results, "fallback_used": not bool(results)}
    except Exception as exc:
        return {"source": source, "results": [], "fallback_used": True, "error": str(exc)}

@router.get("/models/hardware-recommendations")
def model_hardware_recommendations() -> dict[str, Any]:
    return runtime_hardware_plan()


@router.get("/models/detail")
def model_finder_detail(source: str = "hf", id: str = "", url: str = "") -> dict[str, Any]:
    try:
        return model_detail(source, id, url)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/models/local")
def local_models() -> list[dict[str, Any]]:
    return list_local_model_artifacts()


@router.post("/models/model-card")
def local_model_card(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return save_local_model_card(payload)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/models/import")
def local_import(payload: dict[str, str]) -> dict[str, Any]:
    try:
        return import_local_model(payload.get("path", ""))
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/models/download")
def download(payload: dict[str, str]) -> dict[str, Any]:
    url = payload.get("url", "")
    if not url.startswith(("https://", "http://")):
        raise HTTPException(400, "Only http/https manual downloads are allowed.")
    try:
        return download_manager.start(url, payload.get("filename"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/models/downloads")
def downloads() -> list[dict[str, Any]]:
    return download_manager.list()


@router.post("/models/downloads/{job_id}/cancel")
def cancel_download(job_id: str) -> dict[str, Any]:
    return download_manager.cancel(job_id)


@router.post("/models/downloads/{job_id}/pause")
def pause_download(job_id: str) -> dict[str, Any]:
    return download_manager.pause(job_id)


@router.post("/models/downloads/{job_id}/resume")
def resume_download(job_id: str) -> dict[str, Any]:
    return download_manager.resume(job_id)


@router.post("/models/downloads/{job_id}/retry")
def retry_download(job_id: str) -> dict[str, Any]:
    return download_manager.retry(job_id)


@router.delete("/models/downloads/{job_id}")
def delete_download(job_id: str) -> dict[str, Any]:
    return download_manager.delete(job_id)
