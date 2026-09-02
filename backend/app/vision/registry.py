from __future__ import annotations

import importlib.util
from typing import Any

from app.runtime.adapters import ollama_installed, ollama_tags


def _available_modules(modules: list[str]) -> tuple[bool, list[str]]:
    missing = [module for module in modules if importlib.util.find_spec(module) is None]
    return not missing, missing


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def list_vision_adapters() -> list[dict[str, Any]]:
    txrv_available, txrv_missing = _available_modules(["torch", "torchxrayvision"])
    ultralytics_available, ultralytics_missing = _available_modules(["torch", "ultralytics"])
    adapters = [
        {
            "id": "torchxrayvision:densenet121-res224-all",
            "name": "TorchXRayVision DenseNet-121",
            "task": "CXR multi-label classification",
            "status": "available" if txrv_available else "missing_optional_dependencies",
            "available": txrv_available,
            "missing_dependencies": txrv_missing,
            "runtime_field": "classification_model",
            "model_card_id": "torchxrayvision:densenet121-res224-all",
            "install_hint": "Install backend/requirements-optional.txt and use a PyTorch build appropriate for this machine.",
            "safety_note": "Research-only uncalibrated probabilities; not diagnosis, triage, or localization.",
        },
        {
            "id": "local:reviewed-ultralytics-detector",
            "name": "Reviewed local Ultralytics MSK detector",
            "task": "MSK fracture bounding-box localization",
            "status": "ready_for_local_artifact" if ultralytics_available else "missing_optional_dependencies",
            "available": False,
            "missing_dependencies": ultralytics_missing or ["reviewed local .pt artifact"],
            "runtime_field": "grounding_model",
            "model_card_id": "local-msk-fracture-detector",
            "install_hint": "Import a local .pt artifact, complete and human-review its model card, then select its local ID as grounding_model.",
            "safety_note": "Runs only on MSK-routed studies; boxes are research candidates and need box-level local validation.",
        },
    ]

    try:
        tags = ollama_tags()
        for model in _list_of_dicts(tags.get("models") if isinstance(tags, dict) else None):
            name = str(model.get("name") or "").strip()
            capabilities = [item.lower() for item in _string_list(model.get("capabilities"))]
            looks_like_vision = "vision" in capabilities or any(term in name.lower() for term in ["vision", "vl", "llava", "bakllava", "moondream"])
            if not name or not looks_like_vision:
                continue
            adapters.append(
                {
                    "id": name,
                    "name": f"Ollama VLM: {name}",
                    "task": "Local Ollama vision-language review",
                    "status": "available",
                    "available": True,
                    "missing_dependencies": [],
                    "runtime_field": "vision_language_model",
                    "runtime_backend": "ollama",
                    "model_card_id": "ollama-local-vlm",
                    "install_hint": "Already installed in Ollama. No Python model download required.",
                    "safety_note": "Uses the selected local Ollama VLM as unvalidated candidate observations; verify clinically.",
                }
            )
    except Exception:
        if ollama_installed():
            adapters.append(
                {
                    "id": "ollama-vlm-not-detected",
                    "name": "Ollama VLM not detected",
                    "task": "Ollama service/model check",
                    "status": "missing_runtime_model",
                    "available": False,
                    "missing_dependencies": ["ollama vision model"],
                    "runtime_field": "vision_language_model",
                    "runtime_backend": "ollama",
                    "model_card_id": "ollama-local-vlm",
                    "install_hint": "Start Ollama and pull a vision model such as llama3.2-vision or llava, then reload runtime.",
                    "safety_note": "Ollama itself is installed, but no running vision model was detected.",
                }
            )

    return adapters
