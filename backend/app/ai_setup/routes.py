import hashlib
import json
import threading
import time
import urllib.request
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from app.ai_setup import service
from app.ai_setup.catalog import compatibility
from app.model_finder.providers import load_github_token, load_huggingface_token, model_detail, runtime_local_model_gate_issues
from app.models.schemas import RuntimeConfig, RuntimeBackend, RuntimeTaskConnection
from app.runtime import adapters
from app.runtime.secrets import provider_key, save_provider_key, safe_error
from app.storage.db import load_runtime_config, save_runtime_config

router = APIRouter(prefix="/ai-setup")
_tests = {}
_test_lock = threading.RLock()


@router.post("/connection/models")
def connection_models(payload: dict):
    try:
        endpoint = str(payload.get("base_url") or "").strip().rstrip("/")
        adapters.require_allowed_endpoint(endpoint, payload.get("allow_cloud") is True)
        if payload.get("backend") == "ollama":
            return service.ollama_status(endpoint)
        request = urllib.request.Request(endpoint + "/models", headers={"Authorization": f"Bearer {provider_key(endpoint) or 'local'}"})
        with urllib.request.build_opener(adapters.NoRedirect()).open(request, timeout=3) as response:
            data = json.loads(response.read(1024 * 1024))
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError("Invalid model list")
        models = [{"name": item["id"]} for item in data["data"] if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()]
        return {"models": models, "detail": "Models detected from this server. Test the selected model before use."}
    except Exception as exc:
        raise HTTPException(400, safe_error(exc)) from None


@router.get("")
def overview():
    stored = load_runtime_config(RuntimeConfig().model_dump(mode="json"))
    return {"models": service.library(), "runtime": RuntimeConfig(**stored).model_dump(mode="json"), "provider_key_configured": bool(provider_key())}


@router.get("/system")
def system():
    return service.system_check()


@router.get("/classifiers")
def classifiers():
    return [item for item in service.library() if item.get("runtime") == "TorchXRayVision"]


@router.post("/xray/{action}")
def xray(action: str, payload: dict | None = None):
    try:
        model_id = str((payload or {}).get("model_id") or "").strip() or service.TXRV_ID
        if action == "activate":
            return service.activate_xray(model_id)
        return service.start_xray(action, model_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/demo")
def demo():
    config = RuntimeConfig().model_dump(mode="json")
    save_runtime_config(config)
    return config


@router.get("/ollama")
def ollama(base_url: str = "http://127.0.0.1:11434"):
    return service.ollama_status(base_url)


@router.post("/hf/test")
def hf_test(payload: dict):
    token = str(payload.get("token") or load_huggingface_token()).strip()
    if not token:
        return {"ok": False, "detail": "Not signed in. Sign-in is optional for public models."}
    try:
        request = urllib.request.Request("https://huggingface.co/api/whoami-v2", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.build_opener(adapters.NoRedirect()).open(request, timeout=3) as response:
            data = json.loads(response.read(1024 * 1024))
        if not isinstance(data, dict) or not data.get("name"):
            raise ValueError("Invalid account response")
        return {"ok": True, "detail": "Sign-in verified. Access to gated models also requires the model owner's approval."}
    except Exception as exc:
        return {"ok": False, "detail": safe_error(exc)}


@router.post("/github/test")
def github_test(payload: dict):
    token = str(payload.get("token") or load_github_token()).strip()
    if not token:
        return {"ok": False, "detail": "Not signed in. A token is optional, but raises GitHub API limits."}
    try:
        request = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "MedRay-v2"},
        )
        with urllib.request.build_opener(adapters.NoRedirect()).open(request, timeout=3) as response:
            data = json.loads(response.read(1024 * 1024))
        if not isinstance(data, dict) or not data.get("login"):
            raise ValueError("Invalid account response")
        return {"ok": True, "detail": "GitHub sign-in verified for model metadata and search."}
    except Exception as exc:
        return {"ok": False, "detail": safe_error(exc)}


@router.post("/provider-key")
def key_save(payload: dict):
    endpoint = str(payload.get("base_url") or "").strip()
    if endpoint:
        try:
            adapters.require_allowed_endpoint(endpoint, True)
        except Exception:
            raise HTTPException(400, "Enter the provider's valid server URL before saving its key.") from None
    save_provider_key(str(payload.get("key") or ""), endpoint)
    return {"configured": bool(provider_key())}


@router.get("/compatibility")
def model_compatibility(source: str, id: str):
    try:
        detail = model_detail(source, id)
        return {**detail, "compatibility": compatibility(detail)}
    except Exception as exc:
        raise HTTPException(400, safe_error(exc)) from None


def _connection(payload):
    backend = str(payload.get("backend", ""))
    if backend not in {"ollama", "openai-compatible"}:
        raise ValueError("Choose Ollama or an OpenAI-compatible service.")
    task = str(payload.get("task", "chat"))
    if task not in {"chat", "vision", "report"}:
        raise ValueError("This service has no implemented MedRay adapter for the selected task.")
    endpoint = str(payload.get("base_url", "")).strip().rstrip("/")
    allow_cloud = payload.get("allow_cloud") is True
    adapters.require_allowed_endpoint(endpoint, allow_cloud)
    if backend == "ollama" and not adapters.endpoint_is_local(endpoint):
        raise ValueError("Local Ollama setup requires an address on this computer.")
    model = str(payload.get("model", "")).strip()
    if not model or len(model) > 300:
        raise ValueError("Select a model first.")
    language = "id" if payload.get("language") == "id" else "en"
    provider = " ".join(str(payload.get("provider") or "").split())[:80]
    return {"backend": backend, "task": task, "base_url": endpoint, "allow_cloud": allow_cloud, "model": model, "provider": provider, "language": language}


def _signature(config):
    connection_config = {key: value for key, value in config.items() if key != "language" and not (key == "provider" and not value)}
    return hashlib.sha256((json.dumps(connection_config, sort_keys=True) + (provider_key(config["base_url"]) if config["backend"] == "openai-compatible" else "")).encode()).hexdigest()


def _test_connection(test_id, config):
    try:
        is_ollama = config["backend"] == "ollama"
        if is_ollama:
            tags = adapters.ollama_tags(config["base_url"])
            if config["model"] not in [item.get("name") for item in tags.get("models", []) if isinstance(item, dict)]:
                raise ValueError("Selected model is no longer installed.")
        def chat(prompt):
            messages = [{"role": "user", "content": prompt}]
            return adapters.ollama_chat(messages, config["model"], config["base_url"]) if is_ollama else adapters.openai_compatible_chat(messages, config["model"], config["base_url"], provider_key(config["base_url"]))
        if config["task"] == "vision":
            import tempfile
            from pathlib import Path
            from PIL import Image
            with tempfile.TemporaryDirectory(dir=service.get_settings().cache_dir) as folder:
                path = Path(folder) / "synthetic.png"
                Image.new("L", (224, 224), 127).save(path)
                prompt = "Describe this synthetic gray test image in one sentence."
                output = adapters.ollama_vision(str(path), prompt, config["model"], config["base_url"]) if is_ollama else adapters.openai_compatible_vision(str(path), prompt, config["model"], config["base_url"], provider_key(config["base_url"]))
        elif config["task"] == "report":
            language_instruction = "Write entirely in Indonesian." if config.get("language") == "id" else "Write entirely in English."
            output = chat(f"This is a synthetic setup test without patient data. Return JSON with nonempty string fields findings, impression, recommendation. {language_instruction} State that this test image has no clinical interpretation and needs physician verification.")
            from app.pipelines.analysis_pipeline import _json_object_from_text
            report = _json_object_from_text(output)
            if not all(isinstance(report.get(field), str) and report[field].strip() for field in ("findings", "impression", "recommendation")):
                raise ValueError("Report model returned invalid structured output.")
        else:
            output = chat("Reply with a short greeting. This is a connection test without patient data.")
        if not isinstance(output, str) or not output.strip():
            raise ValueError("Invalid response")
        with _test_lock:
            _tests[test_id].update(status="ready", detail="Selected model and task responded successfully. Research use still requires human verification.")
    except Exception as exc:
        with _test_lock:
            _tests[test_id].update(status="connection_failed", detail=safe_error(exc))


@router.post("/connection/test")
def connection_test(payload: dict):
    try:
        config = _connection(payload)
    except Exception as exc:
        raise HTTPException(400, safe_error(exc)) from None
    with _test_lock:
        for key in list(_tests):
            if time.time() - _tests[key]["created_at"] > 600:
                _tests.pop(key)
        if sum(test["status"] == "testing" for test in _tests.values()) >= 2:
            raise HTTPException(409, "A connection test is already running. Wait for it to finish.")
        test_id = uuid4().hex
        _tests[test_id] = {"id": test_id, "status": "testing", "detail": "Testing the selected model. No patient data is used.", "signature": _signature(config), "created_at": time.time()}
        threading.Thread(target=_test_connection, args=(test_id, config), daemon=True).start()
        return {key: value for key, value in _tests[test_id].items() if key != "signature"}


@router.get("/connection/test/{test_id}")
def connection_result(test_id: str):
    with _test_lock:
        if test_id not in _tests:
            raise HTTPException(404, "Test expired. Test the connection again.")
        return {key: value for key, value in _tests[test_id].items() if key != "signature"}


@router.post("/connection/activate")
def connection_activate(payload: dict):
    try:
        config = _connection(payload)
        with _test_lock:
            test = _tests.get(str(payload.get("test_id")), {})
            if test.get("status") != "ready" or test.get("signature") != _signature(config) or time.time() - test.get("created_at", 0) > 600:
                raise ValueError("Test the current settings before activation.")
        runtime = RuntimeConfig(**load_runtime_config(RuntimeConfig().model_dump(mode="json")))
        runtime.primary_backend = RuntimeBackend(config["backend"])
        runtime.allow_cloud = config["allow_cloud"]
        if config["backend"] == "ollama":
            runtime.ollama_base_url = config["base_url"]
        else:
            runtime.openai_base_url = config["base_url"]
        if config["task"] == "vision":
            runtime.vision_language_model = config["model"]
        elif config["task"] == "report":
            runtime.report_model = config["model"]
        else:
            runtime.chat_model = config["model"]
        runtime.task_connections[config["task"]] = RuntimeTaskConnection(
            backend=RuntimeBackend(config["backend"]),
            base_url=config["base_url"],
            model=config["model"],
            allow_cloud=config["allow_cloud"],
            provider=config["provider"],
        )
        issues = runtime_local_model_gate_issues(runtime.model_dump(mode="json"))
        if issues:
            raise ValueError("Local model review is required before activation.")
        save_runtime_config(runtime.model_dump(mode="json"))
        return runtime.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/preferences")
def preferences(payload: dict):
    area_fields = {"chest_xray_model", "msk_xray_model", "abdomen_xray_model", "spine_xray_model", "skull_facial_xray_model", "general_xray_model"}
    preference_fields = area_fields | {
        "cpu_only", "localization_confidence_threshold", "annotation_auto_accept_threshold", "review_depth",
        "temperature", "top_p", "seed", "max_output_tokens", "request_timeout_seconds", "max_retries", "download_connections",
    }
    if set(payload) - preference_fields:
        raise HTTPException(400, "Use Local AI or Online AI to change connections and model assignments.")
    if "localization_confidence_threshold" in payload:
        threshold = payload["localization_confidence_threshold"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            raise HTTPException(400, "Localization confidence threshold must be between 0 and 1.")
    if "review_depth" in payload and payload["review_depth"] not in {"focused", "balanced", "thorough"}:
        raise HTTPException(400, "Review depth must be focused, balanced, or thorough.")
    current = load_runtime_config(RuntimeConfig().model_dump(mode="json"))
    for field in area_fields & set(payload):
        if not isinstance(payload[field], str) or payload[field] not in {"inherit", "disabled", current.get(field), current.get("vision_language_model")}:
            raise HTTPException(400, "Test and select this image-review model in its connection settings first.")
    try:
        runtime = RuntimeConfig(**{**current, **payload})
    except ValidationError as exc:
        raise HTTPException(422, "One or more advanced preference values are outside the supported range.") from exc
    issues = runtime_local_model_gate_issues(runtime.model_dump(mode="json"))
    if issues:
        raise HTTPException(400, "Review the local model card before changing its use.")
    save_runtime_config(runtime.model_dump(mode="json"))
    return runtime.model_dump(mode="json")
