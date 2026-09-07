from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from app.ai_setup.catalog import TXRV_ID, CLASSIFIER_RECIPES, classifier_recipe, weights_path
from app.config import PROJECT_ROOT, get_settings
from app.model_finder.providers import detect_hardware_profile, download_manager, list_local_model_artifacts
from app.models.schemas import RuntimeConfig
from app.runtime import adapters
from app.runtime.secrets import private_json, safe_error
from app.storage.db import connect, load_runtime_config, save_runtime_config

_lock = threading.RLock()
_workers: dict[str, threading.Thread] = {}
_boot = uuid4().hex
_install_lock = threading.RLock()
MODULES = {"torch": "PyTorch", "torchvision": "TorchVision", "torchxrayvision": "TorchXRayVision", "skimage": "Image processing"}


class ModelTestError(RuntimeError):
    """Sanitized diagnostic from MedRay's isolated model adapter."""


def dependencies() -> list[dict]:
    result = []
    for module, name in MODULES.items():
        try:
            present = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            present = False
        result.append({"name": name, "module": module, "status": "installed" if present else "missing"})
    return result


def fingerprint(model_id: str = TXRV_ID) -> str:
    recipe = classifier_recipe(model_id)
    path = weights_path(model_id)
    versions = []
    for package in ("torch", "torchvision", "torchxrayvision", "scikit-image", "numpy"):
        try:
            versions.append(importlib.metadata.version(package))
        except importlib.metadata.PackageNotFoundError:
            versions.append("missing")
    stat = path.stat() if path.is_file() else None
    return hashlib.sha256(repr((str(path), stat.st_size if stat else 0, stat.st_mtime_ns if stat else 0, versions, sys.executable, "preprocess-v3", recipe["sha256"])).encode()).hexdigest()


def state_path(model_id: str = TXRV_ID) -> Path:
    suffix = classifier_recipe(model_id)["weights"].replace("/", "-")
    return get_settings().cache_dir / f"xray_setup-{suffix}.json"


def read_state(model_id: str = TXRV_ID) -> dict:
    with _lock:
        try:
            state = json.loads(state_path(model_id).read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return {}
        except (OSError, ValueError):
            return {}
        if state.get("status") in {"installing", "downloading", "testing"} and state.get("boot") != _boot:
            state.update(status="error", detail="Setup was interrupted. Continue setup to recover.")
        return state


def write_state(model_id: str = TXRV_ID, **values) -> dict:
    with _lock:
        state = {**read_state(model_id), **values, "boot": _boot, "updated_at": time.time()}
        private_json(state_path(model_id), state)
        return state


def cpu_install_supported() -> bool:
    return (platform.system() in {"Windows", "Linux"} and platform.machine().lower() in {"amd64", "x86_64"}
            and (3, 10) <= sys.version_info[:2] <= (3, 12) and sys.prefix != sys.base_prefix)


def xray_readiness(model_id: str = TXRV_ID) -> dict:
    recipe = classifier_recipe(model_id)
    deps = dependencies()
    missing = [item["name"] for item in deps if item["status"] == "missing"]
    state = read_state(model_id)
    artifact = weights_path(model_id).is_file() and weights_path(model_id).stat().st_size > 0
    tested = bool(state.get("passed") and state.get("fingerprint") == fingerprint(model_id) and not missing and artifact)
    status, reason, action = "ready", "Technical test passed. Clinical validation is still required.", "Use as classifier"
    if not tested:
        status, reason, action = "needs_setup", "Run the model test before using this classifier.", "Test model"
    if not artifact:
        status, reason, action = "needs_setup", "Model weights have not been downloaded.", "Continue setup"
    if missing:
        status, reason, action = "dependency_missing", "Missing: " + ", ".join(missing) + ".", "Continue setup"
    if state.get("status") in {"installing", "downloading", "testing", "error"}:
        status, reason = state["status"], state.get("detail", "Setup is running.")
        tested = False
        action = "Retry setup" if status == "error" else "Setup in progress"
    config = load_runtime_config(RuntimeConfig().model_dump(mode="json"))
    return {"model_id": model_id, "display_name": recipe["display_name"], "source": "Official TorchXRayVision release (GitHub)",
            "task": "Chest X-ray classification", "runtime": "TorchXRayVision", "adapter": model_id,
            "status": status, "artifact_status": "downloaded" if artifact else "not_downloaded", "dependencies": deps,
            "dependency_status": "missing" if missing else "installed", "hardware_status": "likely_compatible" if cpu_install_supported() else "unknown",
            "connection_status": "not_required", "model_card_status": "research_card", "validation_status": "needs_validation",
            "ready_for_inference": tested, "blocking_reasons": [] if tested else [reason], "detail": reason,
            "recommended_action": action, "active": config.get("classification_model") == model_id,
            "automatic_cpu_setup": cpu_install_supported(), "test_passed": tested, "job": state,
            "automatic_setup": True, "dataset": recipe["dataset"], "scope": recipe["scope"], "resolution": recipe["resolution"],
            "checks": [{"name": "MedRay adapter", "status": "passed"}, {"name": "CPU setup", "status": "likely compatible" if cpu_install_supported() else "guided setup required"},
                       *deps, {"name": "Model weights", "status": "downloaded" if artifact else "not downloaded"},
                       {"name": "Model load and test inference", "status": "passed" if tested else "not tested"}]}


def _run_command(args: list[str], timeout=1200) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if not key.startswith("PIP_")}
    env["PYTHONPATH"] = str(PROJECT_ROOT / "backend")
    # Keep the child in the same storage context; no patient data is used.
    env["MEDRAY_DATA_DIR"] = str(get_settings().data_dir)
    return subprocess.run(args, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def install_torch() -> None:
    if not cpu_install_supported():
        raise RuntimeError("Guided setup required for this Python, OS or architecture.")
    if any(item["status"] == "missing" for item in dependencies() if item["module"] in {"torch", "torchvision"}):
        result = _run_command([sys.executable, "-m", "pip", "--isolated", "install", "--only-binary=:all:", "--index-url", "https://download.pytorch.org/whl/cpu", "torch==2.7.1", "torchvision==0.22.1"])
        if result.returncode:
            raise RuntimeError("CPU dependency installation failed.")

def install_dependencies() -> None:
    with _install_lock:
        install_torch()
        result = _run_command([sys.executable, "-m", "pip", "--isolated", "install", "--only-binary=:all:", "--index-url", "https://pypi.org/simple", "-r", str(PROJECT_ROOT / "backend/requirements-xray.txt")])
        if result.returncode:
            raise RuntimeError("X-ray dependency installation failed.")
        importlib.invalidate_caches()


def test_xray(model_id: str = TXRV_ID) -> dict:
    result = _run_command([sys.executable, "-m", "app.ai_setup.worker", "--classifier", model_id], timeout=180)
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError("Model test did not return valid output.") from None
    if result.returncode or payload.get("status") != "ok":
        raise ModelTestError(str(payload.get("detail") or "Model load or test inference failed.")[:600])
    return payload


def _setup(action: str, model_id: str = TXRV_ID) -> None:
    recipe = classifier_recipe(model_id)
    model_weights_path = weights_path(model_id)
    try:
        if action in {"setup", "download"} and model_weights_path.is_file():
            from app.model_registry.validation_evidence import hash_artifact_file
            if hash_artifact_file(model_weights_path) != recipe["sha256"]:
                archive = get_settings().models_dir / ".removed"
                archive.mkdir(exist_ok=True)
                if archive.is_symlink():
                    raise ValueError("Invalid model archive directory.")
                model_weights_path.rename(archive / (uuid4().hex + "-" + recipe["weights_name"]))
        if action == "setup" and any(item["status"] == "missing" for item in dependencies()):
            write_state(model_id, status="installing", detail="Installing MedRay's official CPU dependencies. This can take several minutes.", passed=False)
            if shutil.disk_usage(get_settings().data_dir).free < 3 * 1024**3:
                raise OSError(28, "Insufficient disk space")
            install_dependencies()
        if action in {"setup", "download"} and not model_weights_path.is_file():
            write_state(model_id, status="downloading", detail="Downloading official model weights. Progress is shown below.", passed=False)
            jobs = [job for job in download_manager.list() if job.get("url") == recipe["url"] and job.get("target_path") == str(model_weights_path)]
            job = jobs[0] if jobs and jobs[0]["status"] != "completed" else download_manager.start(recipe["url"], recipe["weights_name"])
            if job["status"] in {"paused", "failed"}:
                job = download_manager.resume(job["id"])
            elif job["status"] == "cancelled":
                job = download_manager.retry(job["id"])
            write_state(model_id, download_id=job["id"])
            deadline = time.monotonic() + 1800
            while job["status"] in {"queued", "downloading", "pausing", "cancelling"}:
                if time.monotonic() > deadline:
                    download_manager.pause(job["id"])
                    raise TimeoutError()
                time.sleep(0.3)
            if job["status"] != "completed" or not model_weights_path.is_file():
                raise RuntimeError("Download interrupted")
        if action != "download":
            write_state(model_id, status="testing", detail="Loading weights and running a synthetic image through the classifier. No patient data is used.", passed=False)
            test_xray(model_id)
            write_state(model_id, status="ready", detail="Model loaded. Test inference and output checks passed.", passed=True, fingerprint=fingerprint(model_id), error_type=None)
        else:
            write_state(model_id, status="needs_setup", detail="Weights downloaded. Test the model next.", passed=False)
    except Exception as exc:
        message = safe_error(exc)
        if isinstance(exc, ModelTestError):
            message = str(exc)
        if isinstance(exc, RuntimeError) and str(exc) in {"CPU dependency installation failed.", "X-ray dependency installation failed.", "Model load or test inference failed."}:
            message = str(exc) + " Check disk space, internet and System Check, then retry. GPU setups may need the guided installation."
        write_state(model_id, status="error", passed=False, detail=message, error_type=type(exc).__name__)


def start_xray(action: str, model_id: str = TXRV_ID) -> dict:
    classifier_recipe(model_id)
    if action not in {"setup", "test", "download"}:
        raise ValueError("Unknown setup action.")
    with _lock:
        key = str(state_path(model_id))
        if _workers.get(key) and _workers[key].is_alive():
            return read_state(model_id)
        if action == "setup" and any(item["status"] == "missing" for item in dependencies()) and not cpu_install_supported():
            raise ValueError("MedRay cannot safely choose a build here. Open guided PyTorch setup, then retry.")
        write_state(model_id, status="testing" if action == "test" else "installing", detail="Checking setup requirements…", passed=False, download_id=None)
        worker = threading.Thread(target=_setup, args=(action, model_id), daemon=True)
        _workers[key] = worker
        worker.start()
        return read_state(model_id)


def activate_xray(model_id: str = TXRV_ID) -> dict:
    classifier_recipe(model_id)
    if not xray_readiness(model_id)["ready_for_inference"]:
        raise ValueError("Test this model successfully before using it as classifier.")
    config = RuntimeConfig(**load_runtime_config(RuntimeConfig().model_dump(mode="json")))
    config.classification_model = model_id
    save_runtime_config(config.model_dump(mode="json"))
    return config.model_dump(mode="json")


def ollama_status(base_url: str) -> dict:
    try:
        adapters.require_allowed_endpoint(base_url, False)
        tags = adapters.ollama_tags(base_url)
        models = [{"name": item["name"], "status": "needs_setup", "detail": "Installed. Test the selected task before use."}
                  for item in tags.get("models", []) if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]]
        return {"installed": adapters.ollama_installed(), "running": True, "models": models, "detail": "Service connected."}
    except Exception as exc:
        return {"installed": adapters.ollama_installed(), "running": False, "models": [], "detail": safe_error(exc)}


def library() -> list[dict]:
    items = [{"model_id": "demo", "display_name": "Built-in Demo", "source": "MedRay", "runtime": "Built-in Demo", "task": "Workflow demonstration", "status": "ready", "ready_for_inference": True, "detail": "Deterministic examples; no clinical inference.", "recommended_action": "Use Demo"}, *[xray_readiness(model_id) for model_id in CLASSIFIER_RECIPES]]
    for item in list_local_model_artifacts():
        if item.get("name") in {recipe["weights_name"] for recipe in CLASSIFIER_RECIPES.values()}:
            continue
        items.append({"model_id": item["id"], "display_name": item["name"], "source": "Local file/folder", "task": item.get("task"),
                      "runtime": "External runtime required", "status": "configuration_required" if item.get("runtime_eligible") else "needs_review", "ready_for_inference": False,
                      "artifact_status": "downloaded", "model_card_status": item.get("model_card_status"), "validation_status": item.get("validation_evidence_status"),
                      "detail": "Load this file in a runtime that supports its architecture, then select and test that runtime model in Local AI.", "recommended_action": "Connect runtime"})
    return items


def system_check() -> dict:
    checks = [{"name": "Python", "status": "ready", "detail": platform.python_version()}, {"name": "Backend", "status": "ready", "detail": "Responding"}]
    try:
        with connect() as connection:
            connection.execute("SELECT count(*) FROM cases").fetchone()
        checks.append({"name": "Database", "status": "ready", "detail": "Readable"})
    except Exception as exc:
        checks.append({"name": "Database", "status": "error", "detail": safe_error(exc)})
    try:
        import tempfile
        with tempfile.TemporaryFile(dir=get_settings().cache_dir) as stream:
            stream.write(b"check")
        disk_gb = round(shutil.disk_usage(get_settings().data_dir).free / 1024**3, 1)
        checks.append({"name": "Storage", "status": "ready", "detail": f"{disk_gb} GB free"})
    except Exception as exc:
        disk_gb = None
        checks.append({"name": "Storage", "status": "error", "detail": safe_error(exc)})
    try:
        node = subprocess.run([shutil.which("node") or "node", "--version"], capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        version = node.stdout.strip().lstrip("v").split(".")
        supported = (int(version[0]) == 22 and int(version[1]) >= 12) or int(version[0]) >= 24
        checks.append({"name": "Node", "status": "ready" if supported else "needs_setup", "detail": node.stdout.strip() + ("" if supported else ": install Node 22.12+ or 24 LTS")})
    except Exception:
        checks.append({"name": "Node", "status": "unknown", "detail": "Node could not be detected."})
    return {"checks": checks, "hardware": {**detect_hardware_profile(), "disk_free_gb": disk_gb, "architecture": platform.machine(), "cuda": "Not tested; CPU wizard does not require CUDA", "apple_silicon": platform.system() == "Darwin" and platform.machine() == "arm64"},
            "overall": "core_ready" if all(item["status"] == "ready" for item in checks if item["name"] != "Node") else "needs_setup"}
