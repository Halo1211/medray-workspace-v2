from __future__ import annotations

import json
import hashlib
import ipaddress
import os
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.models.schemas import ModelMetadata
from app.model_registry.validation_evidence import (
    bind_artifact_identity,
    normalize_validation_evidence,
    validation_evidence_assessment,
)
from app.runtime.adapters import ollama_installed, ollama_tags
from app.storage.db import list_json, upsert_json


MEDICAL_HINTS = ["xray", "x-ray", "radiograph", "radiography", "cxr", "chest", "dicom", "chexpert", "mimic-cxr", "nih chest"]
MODEL_CARD_REQUIREMENTS = [
    ("license", "License declared"),
    ("task", "Task or pipeline declared"),
    ("dataset", "Dataset or provenance note present"),
    ("medical_fit", "Medical/radiology relevance visible"),
    ("card_text", "Model-card/readme available"),
    ("safety", "Safety, limitations, or evaluation evidence visible"),
]
MODEL_FILE_HINTS = {
    "config.json": "transformers config",
    "model.safetensors": "safetensors weights",
    "pytorch_model.bin": "pytorch weights",
    "tokenizer.json": "tokenizer",
    "tokenizer.model": "tokenizer",
    "generation_config.json": "generation config",
    "README.md": "model card/readme",
    "LICENSE": "license",
    "Modelfile": "ollama modelfile",
}
MAX_MANUAL_DOWNLOAD_BYTES = 16 * 1024 * 1024 * 1024


def _validate_manual_download_url(url: str) -> None:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Manual model downloads require an HTTP(S) URL with a hostname.")
    host = parsed.hostname.rstrip(".").lower()
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except (OSError, ValueError) as exc:
        raise ValueError("Manual download host could not be resolved safely.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
            raise ValueError("Manual downloads cannot target loopback, private, link-local, reserved, or multicast addresses.")


class _SafeDownloadRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_manual_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
REQUIRED_LOCAL_CARD_FIELDS = [
    "intended_use",
    "task",
    "license",
    "dataset_provenance",
    "limitations",
]
RUNTIME_MODEL_FIELDS = [
    "chat_model",
    "vision_language_model",
    "classification_model",
    "segmentation_model",
    "grounding_model",
    "chest_xray_model",
    "msk_xray_model",
    "abdomen_xray_model",
    "spine_xray_model",
    "skull_facial_xray_model",
    "general_xray_model",
    "report_model",
]

RUNTIME_TASK_RECOMMENDATIONS = [
    {
        "slot": "classification_model",
        "label": "X-ray analysis",
        "task": "X-ray classifier + vision-language review",
        "starter_id": "starter:torchxrayvision",
        "query": "chest xray cxr radiograph model",
        "source": "all",
        "includes": ["Classifier", "Vision-language"],
        "cpu": "Start with TorchXRayVision-style classifier or demo VLM; local CPU VLM will be slow.",
        "low": "Prioritize compact classifier first; add tiny/quantized VLM only as draft explanation.",
        "mid": "Use classifier plus compact 4B-ish VLM, with calibration and model-card review.",
        "high": "Classifier and MedGemma/LLaVA-style VLM can run as separate evidence tools after review.",
    },
    {
        "slot": "segmentation_model",
        "label": "X-ray localization",
        "task": "X-ray detection/segmentation overlays",
        "query": "xray detection segmentation",
        "source": "all",
        "includes": ["Segmentation", "Grounding"],
        "cpu": "Keep localization disabled; use manual annotations or visibly marked demo regions.",
        "low": "Usually disabled on low VRAM unless a tiny task-specific model is reviewed locally.",
        "mid": "Use small detector/segmentation add-on only after coordinate and mask validation.",
        "high": "Reviewed grounding/segmentation can be enabled selectively with traceable coordinates.",
    },
    {
        "slot": "report_model",
        "label": "X-ray report & chat",
        "task": "X-ray draft report + offline assistant",
        "starter_id": "starter:local-report-chat",
        "query": "xray report generation llm",
        "source": "all",
        "includes": ["Report", "Chat"],
        "cpu": "Quantized 1B-3B text model via Ollama, or demo report/chat for safest default.",
        "low": "Quantized 3B-4B text model for report wording grounded in result cards.",
        "mid": "Quantized 7B-8B text/chat model is reasonable; keep watermark and review requirement.",
        "high": "8B+ report/chat assistant is useful if constrained to case context and trace.",
    },
]


COOKBOOKS = [
    {
        "id": "cxr-classifier-local-first",
        "title": "First local CXR classifier",
        "best_for": "v0.4 first real vision model",
        "query": "chest xray chexpert classification pytorch",
        "sources": ["Hugging Face", "GitHub"],
        "hardware": "CPU/GPU acceptable for many DenseNet/EfficientNet-style classifiers.",
        "steps": [
            "Prefer a model with clear training dataset and label definitions.",
            "Add a model card before enabling it in analysis.",
            "Run local validation before displaying disease probabilities.",
            "Show calibration warnings until thresholds are validated locally.",
        ],
        "safety": "Classifier output must be framed as research signal, not diagnosis.",
    },
    {
        "id": "report-chat-local",
        "title": "Local report/chat assistant",
        "best_for": "offline drafting and explanation",
        "query": "radiology report generation llm qwen ollama",
        "sources": ["Ollama", "Hugging Face"],
        "hardware": "4GB-12GB VRAM with quantized 3B-8B text models; CPU is possible but slower.",
        "steps": [
            "Use only case metadata, findings, and user-approved context.",
            "Keep the report watermark visible.",
            "Do not allow cloud endpoints unless Runtime Settings opt-in is explicit.",
        ],
        "safety": "Generated reports remain draft text requiring clinician verification.",
    },
    {
        "id": "grounding-segmentation-research",
        "title": "X-ray localization add-on",
        "best_for": "future X-ray annotation/overlay work",
        "query": "chest xray detection segmentation localization",
        "sources": ["Hugging Face", "GitHub"],
        "hardware": "8GB-16GB+ VRAM recommended depending on architecture.",
        "steps": [
            "Keep fallback boxes visually distinct from model-returned coordinates.",
            "Store mask/coordinate provenance in model trace.",
            "Validate localization metrics before treating boxes as pathology locations.",
        ],
        "safety": "Unvalidated boxes or masks must not be presented as confirmed lesion location.",
    },
]


STARTER_MODELS = [
    {
        "id": "starter:torchxrayvision",
        "name": "TorchXRayVision DenseNet CXR classifier",
        "source": "GitHub",
        "task_type": "classification",
        "license": "BSD-2-Clause / model-specific weights",
        "size": "small",
        "quantization": "none",
        "vram_estimate": "4GB-6GB",
        "supports_cpu": True,
        "supports_gpu": True,
        "medical_tags": ["xray", "cxr", "chexpert"],
        "url": "https://github.com/mlmed/torchxrayvision",
        "status": "available",
        "reason": "Already supported by the optional local adapter; safest first real CXR signal.",
        "fit_summary": "Best current starter for local-first CXR classifier experiments.",
        "cookbook_tags": ["cxr-classifier-local-first"],
        "safety_notes": [
            "Research signal only; not a diagnosis.",
            "Probabilities need local validation and calibration warnings.",
        ],
    },
    {
        "id": "starter:local-report-chat",
        "name": "Qwen/Gemma local report and chat assistant",
        "source": "Ollama",
        "task_type": "report generation",
        "license": "model-dependent",
        "size": "3B-8B quantized",
        "quantization": "q4/q5 recommended",
        "vram_estimate": "4GB-12GB",
        "supports_cpu": True,
        "supports_gpu": True,
        "medical_tags": ["report", "radiology"],
        "url": "https://ollama.com/search",
        "status": "available",
        "reason": "Good offline drafting layer once result cards exist.",
        "fit_summary": "Use only for draft report/chat grounded in case data and result cards.",
        "cookbook_tags": ["report-chat-local"],
        "safety_notes": [
            "Generated reports remain draft text requiring clinician verification.",
            "Cloud endpoints stay disabled unless explicitly allowed.",
        ],
    },
]


def starter_models(query: str = "", limit: int = 20) -> list[dict[str, Any]]:
    text = query.lower().strip()
    if not text:
        return STARTER_MODELS[:limit]
    tokens = [token for token in text.replace("-", " ").split() if len(token) > 2]
    ranked = []
    for model in STARTER_MODELS:
        haystack = " ".join(
            [
                model["name"],
                model["task_type"],
                model.get("reason", ""),
                model.get("fit_summary", ""),
                " ".join(model.get("medical_tags", [])),
                " ".join(model.get("cookbook_tags", [])),
            ]
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score or not tokens:
            ranked.append((score, model))
    return [dict(model, maturity_score=80 if score else 60) for score, model in sorted(ranked, key=lambda item: item[0], reverse=True)[:limit]]


def infer_task(text: str) -> str:
    t = text.lower()
    if "segment" in t or "sam" in t:
        return "segmentation"
    if "detect" in t or "ground" in t or "maira" in t:
        return "grounding"
    if "classif" in t or "chex" in t or "densenet" in t:
        return "classification"
    if "report" in t:
        return "report generation"
    if "vlm" in t or "vision" in t or "llava" in t or "medgemma" in t:
        return "vision-language"
    if "embed" in t:
        return "embedding"
    return "LLM" if any(x in t for x in ["qwen", "llama", "mistral", "gemma"]) else "unknown"


def estimate_vram(name: str) -> str:
    t = name.lower()
    if any(x in t for x in ["0.5b", "1b", "2b", "3b", "4b", "q4", "int4"]):
        return "4GB-6GB"
    if any(x in t for x in ["7b", "8b", "q5", "8bit", "int8"]):
        return "8GB-12GB"
    if any(x in t for x in ["13b", "14b", "27b", "34b", "70b"]):
        return "16GB+"
    return "unknown"


def _vram_need_gb(vram: str) -> float | None:
    text = vram.lower()
    if "16gb+" in text:
        return 16
    numbers = [float(item) for item in re.findall(r"(\d+(?:\.\d+)?)\s*gb", text)]
    return max(numbers) if numbers else None


def _search_hardware_profile() -> dict[str, Any]:
    if not hasattr(_search_hardware_profile, "_cached"):
        setattr(_search_hardware_profile, "_cached", detect_hardware_profile())
    return getattr(_search_hardware_profile, "_cached")


def _hardware_fit_percent(payload: dict[str, Any]) -> tuple[int, str]:
    profile = _search_hardware_profile()
    tier = str(profile.get("tier") or "cpu")
    max_vram = float(profile.get("max_vram_gb") or 0)
    task = str(payload.get("task_type") or "").lower()
    required = _vram_need_gb(str(payload.get("vram_estimate") or ""))
    if required is None:
        if tier == "cpu" and task in {"vision-language", "segmentation", "grounding"}:
            return 35, "VRAM unknown; visual model likely heavy for CPU-only."
        return 55, "VRAM unknown; needs manual hardware check."
    if max_vram <= 0:
        if required <= 6 and task in {"classification", "report generation", "llm"}:
            return 65, "Likely runnable slowly on CPU/small model path."
        return 25, "No GPU VRAM detected for this likely visual workload."
    if required <= max_vram:
        return 95, f"Estimated need {required:g}GB fits detected {max_vram:g}GB VRAM."
    if required <= max_vram + 4:
        return 65, f"Close fit: estimated {required:g}GB vs detected {max_vram:g}GB VRAM."
    return 30, f"Likely too heavy: estimated {required:g}GB vs detected {max_vram:g}GB VRAM."


def _medray_fit(payload: dict[str, Any], text: str, license_name: str, maturity: int) -> tuple[int, list[dict[str, Any]]]:
    hardware_score, hardware_reason = _hardware_fit_percent(payload)
    t = text.lower()
    task_ok = infer_task(t) != "unknown"
    medical_ok = any(hint in t for hint in MEDICAL_HINTS)
    license_ok = bool(license_name and license_name.lower() not in {"unknown", "other", "none"})
    provenance_ok = any(term in t for term in ["chexpert", "mimic", "nih", "padchest", "rsna", "dataset", "model card", "paper", "arxiv"])
    safety_ok = any(term in t for term in ["validated", "benchmark", "evaluation", "limitation", "safety", "metric"])
    criteria = [
        {"label": "Hardware MedRay/Odysseus", "score": hardware_score, "reason": hardware_reason},
        {"label": "Medical/radiology fit", "score": 100 if medical_ok else 40, "reason": "Radiology/CXR terms found." if medical_ok else "Medical context is weak."},
        {"label": "Task match", "score": 100 if task_ok else 45, "reason": f"Task inferred as {payload.get('task_type', 'unknown')}."},
        {"label": "License", "score": 100 if license_ok else 35, "reason": license_name if license_ok else "License not declared."},
        {"label": "Provenance", "score": 90 if provenance_ok else 35, "reason": "Dataset/paper/model-card signal found." if provenance_ok else "Dataset/provenance signal is thin."},
        {"label": "Safety maturity", "score": max(20, maturity), "reason": "Higher is better for review readiness."},
    ]
    weighted = round(
        hardware_score * 0.35
        + (100 if medical_ok else 40) * 0.18
        + (100 if task_ok else 45) * 0.14
        + (100 if license_ok else 35) * 0.10
        + (90 if provenance_ok else 35) * 0.13
        + (90 if safety_ok else maturity) * 0.10
    )
    if any(term in t for term in ["chest", "cxr", "chexpert", "mimic-cxr", "nih chest", "pneumonia"]):
        weighted += 10
    if any(term in t for term in ["tooth", "dental", "shoulder", "wrist", "hand", "knee", "bone age"]):
        weighted -= 12
    return max(0, min(100, weighted)), criteria


def maturity_score(text: str, license_name: str = "unknown") -> int:
    t = text.lower()
    score = 10
    if any(hint in t for hint in MEDICAL_HINTS):
        score += 20
    if any(term in t for term in ["chexpert", "mimic", "nih", "padchest", "rsna"]):
        score += 15
    if infer_task(t) != "unknown":
        score += 15
    if license_name and license_name.lower() not in {"unknown", "other"}:
        score += 10
    if any(term in t for term in ["model card", "validated", "benchmark", "paper", "arxiv"]):
        score += 10
    if any(term in t for term in ["demo", "toy", "example"]):
        score -= 10
    return max(0, min(100, score))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def _card_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("cardData") or payload.get("card_data") or {}
    return data if isinstance(data, dict) else {}


def _declared_license(tags: list[str], card_data: dict[str, Any], fallback: str = "unknown") -> str:
    card_license = card_data.get("license")
    if isinstance(card_license, list) and card_license:
        return str(card_license[0])
    if isinstance(card_license, str) and card_license.strip():
        return card_license
    return next((tag.replace("license:", "") for tag in tags if tag.startswith("license:")), fallback)


def _declared_datasets(tags: list[str], card_data: dict[str, Any]) -> list[str]:
    datasets = [str(item) for item in _as_list(card_data.get("datasets")) if str(item).strip()]
    tagged = [tag.replace("dataset:", "") for tag in tags if tag.startswith("dataset:")]
    return sorted({*datasets, *tagged})


def model_card_readiness(payload: dict[str, Any], card_text: str = "") -> dict[str, Any]:
    tags = _string_list(payload.get("tags"))
    card_data = _card_data(payload)
    license_name = str(payload.get("license") or _declared_license(tags, card_data))
    task = str(payload.get("task_type") or payload.get("pipeline_tag") or card_data.get("pipeline_tag") or "")
    datasets = _declared_datasets(tags, card_data)
    haystack = " ".join(
        [
            str(payload.get("name") or payload.get("modelId") or ""),
            str(payload.get("reason") or payload.get("fit_summary") or ""),
            " ".join(tags),
            " ".join(str(item) for item in datasets),
            json.dumps(card_data, default=str),
            card_text[:4000],
        ]
    ).lower()
    checks = {
        "license": bool(license_name and license_name.lower() not in {"unknown", "other", "none"}),
        "task": bool(task and task.lower() != "unknown"),
        "dataset": bool(datasets or any(term in haystack for term in ["dataset", "trained on", "training data", "mimic", "chexpert", "nih", "padchest", "rsna"])),
        "medical_fit": bool(any(hint in haystack for hint in MEDICAL_HINTS)),
        "card_text": bool(card_text.strip() or card_data),
        "safety": bool(any(term in haystack for term in ["limitation", "safety", "bias", "evaluation", "metric", "benchmark", "validated", "paper", "arxiv"])),
    }
    passed = sum(1 for key, _label in MODEL_CARD_REQUIREMENTS if checks[key])
    total = len(MODEL_CARD_REQUIREMENTS)
    score = round((passed / total) * 100)
    if score >= 84:
        status = "ready for local review"
    elif score >= 50:
        status = "needs model-card work"
    else:
        status = "not ready for runtime use"
    return {
        "score": score,
        "status": status,
        "checks": [{"id": key, "label": label, "ok": checks[key]} for key, label in MODEL_CARD_REQUIREMENTS],
        "missing": [label for key, label in MODEL_CARD_REQUIREMENTS if not checks[key]],
        "license": license_name or "unknown",
        "datasets": datasets,
        "pipeline_tag": task or "unknown",
        "action_required": "Add/review a local MedRay model card before enabling this model for analysis.",
    }


def fit_summary(task_type: str, score: int, vram: str) -> str:
    if score >= 65:
        maturity = "strong candidate"
    elif score >= 40:
        maturity = "needs review"
    else:
        maturity = "exploratory only"
    return f"{maturity}; task={task_type}; estimated VRAM={vram}"


def safety_notes(task_type: str) -> list[str]:
    notes = ["Register a model card before using this in analysis.", "Validate locally before clinical-style display."]
    if task_type in {"classification", "grounding", "segmentation"}:
        notes.append("Show calibration/provenance warnings for visual or probabilistic outputs.")
    if task_type == "report generation":
        notes.append("Keep AI-assisted report watermark visible.")
    return notes


def cookbook_tags(text: str) -> list[str]:
    t = text.lower()
    tags = []
    for item in COOKBOOKS:
        if any(word in t for word in item["query"].lower().split()):
            tags.append(item["id"])
    return tags[:3]


def enrich_model(payload: dict[str, Any], text: str, license_name: str = "unknown") -> dict[str, Any]:
    score = maturity_score(text, license_name)
    task_type = payload.get("task_type", "unknown")
    medray_score, criteria = _medray_fit(payload, text, license_name, score)
    payload["maturity_score"] = score
    payload["fit_percent"] = medray_score
    payload["hardware_fit_percent"] = criteria[0]["score"]
    payload["fit_criteria"] = criteria
    payload["fit_summary"] = fit_summary(task_type, score, payload.get("vram_estimate", "unknown"))
    payload["cookbook_tags"] = cookbook_tags(text)
    payload["safety_notes"] = safety_notes(task_type)
    payload["card_readiness"] = model_card_readiness({**payload, "tags": text.split(), "license": license_name})
    return payload


def hardware_recommendations() -> list[dict[str, str]]:
    return [
        {"tier": "CPU only", "recommendation": "Demo mode, Ollama small text model, or quantized 1B-3B for report drafting only."},
        {"tier": "Low VRAM 4GB-6GB", "recommendation": "Qwen2.5/3 3B-4B quantized via Ollama; vision tasks should stay lightweight or remote/local VLM off."},
        {"tier": "Mid VRAM 8GB-12GB", "recommendation": "MedGemma 4B multimodal or compact LLaVA-style VLM; use 4-bit/8-bit quantization."},
        {"tier": "High VRAM 16GB+", "recommendation": "MedRAX-style selective tools: classifier + report generator + grounding/VLM where licensed."},
    ]


def _system_ram_gb() -> float | None:
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round((pages * page_size) / 1024**3, 1)
        except Exception:
            pass
    if platform.system().lower() == "windows":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullTotalPhys / 1024**3, 1)
        except Exception:
            return None
    return None


def _nvidia_gpus() -> list[dict[str, Any]]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=4,
        )
    except Exception:
        return []
    gpus = []
    for line in output.splitlines():
        if not line.strip() or "," not in line:
            continue
        name, memory_mb = [part.strip() for part in line.split(",", 1)]
        try:
            vram_gb = round(float(memory_mb) / 1024, 1)
        except ValueError:
            vram_gb = None
        gpus.append({"name": name, "vram_gb": vram_gb, "vendor": "NVIDIA"})
    return gpus


def detect_hardware_profile() -> dict[str, Any]:
    gpus = _nvidia_gpus()
    max_vram = max([gpu.get("vram_gb") or 0 for gpu in gpus], default=0)
    ram_gb = _system_ram_gb()
    if max_vram >= 16:
        tier = "high"
        tier_label = "High VRAM 16GB+"
    elif max_vram >= 8:
        tier = "mid"
        tier_label = "Mid VRAM 8GB-12GB"
    elif max_vram >= 4:
        tier = "low"
        tier_label = "Low VRAM 4GB-6GB"
    else:
        tier = "cpu"
        tier_label = "CPU only / GPU VRAM not detected"
    return {
        "detected_at": now_iso(),
        "os": f"{platform.system()} {platform.release()}".strip(),
        "cpu": platform.processor() or platform.machine() or "unknown CPU",
        "cpu_count": os.cpu_count(),
        "ram_gb": ram_gb,
        "gpus": gpus,
        "max_vram_gb": max_vram or None,
        "tier": tier,
        "tier_label": tier_label,
        "detection_notes": [
            "GPU VRAM detection uses nvidia-smi when available.",
            "Non-NVIDIA GPU support may show as not detected; use recommendations conservatively.",
        ],
    }


def _slot_recommendation_text(item: dict[str, Any], tier: str) -> str:
    return str(item.get(tier) or item.get("cpu") or "Use demo mode until this slot has a reviewed local model.")


def runtime_hardware_plan() -> dict[str, Any]:
    profile = detect_hardware_profile()
    tier = str(profile["tier"])
    recommendations = []
    starter_by_id = {model["id"]: model for model in STARTER_MODELS}
    for item in RUNTIME_TASK_RECOMMENDATIONS:
        starter = starter_by_id.get(str(item.get("starter_id")), {})
        recommendations.append(
            {
                "slot": item["slot"],
                "label": item["label"],
                "task": item["task"],
                "recommended_model": starter.get("name", "Demo / reviewed local model"),
                "starter_id": item.get("starter_id"),
                "source": item["source"],
                "includes": item.get("includes", []),
                "query": item["query"],
                "recommendation": _slot_recommendation_text(item, tier),
                "vram_estimate": starter.get("vram_estimate", "depends on selected model"),
                "safety_note": "Downloaded artifacts stay inactive until model-card review and local validation are complete.",
            }
        )
    return {
        "profile": profile,
        "runtime_slots": recommendations,
        "download_help": {
            "queue": "Download queues a file into data/models and tracks progress.",
            "not_runtime": "A downloaded file is not automatically enabled for analysis.",
            "next_step": "Review metadata, add a MedRay model card, validate locally, then select it in Runtime Settings.",
        },
    }


def get_model_cookbook() -> dict[str, Any]:
    return {
        "version": "0.2",
        "principles": [
            "Local-first by default; cloud requires explicit Runtime Settings opt-in.",
            "Prefer models with clear labels, license, dataset provenance, and model cards.",
            "Keep demo/fallback output visually and textually distinct from real inference.",
            "Do not show disease probabilities without validation and calibration warnings.",
        ],
        "hardware_recommendations": hardware_recommendations(),
        "cookbooks": [],
        "starter_models": [],
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_registry_dir() -> Path:
    path = get_settings().models_dir / "_registry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_local_model_path(path: str) -> Path:
    models_dir = get_settings().models_dir.resolve()
    p = Path(path).expanduser().resolve()
    if models_dir not in p.parents and p != models_dir:
        raise ValueError("Local model artifacts must stay inside data/models.")
    return p


def _local_artifact_id(path: Path) -> str:
    models_dir = get_settings().models_dir.resolve()
    rel = path.resolve().relative_to(models_dir).as_posix()
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
    return f"local:{digest}"


def _local_card_path(artifact_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in artifact_id)
    return _local_registry_dir() / f"{safe_id}.model-card.json"


def _read_local_card(artifact_id: str) -> dict[str, Any] | None:
    path = _local_card_path(artifact_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _scan_model_files(path: Path) -> dict[str, Any]:
    if path.is_file():
        relative_files = [path.name]
    else:
        relative_files = []
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    relative_files.append(item.relative_to(path).as_posix())
                except ValueError:
                    relative_files.append(item.name)
    files = [Path(name).name for name in relative_files]
    hints = []
    warnings = []
    for name in files:
        hint = MODEL_FILE_HINTS.get(name) or MODEL_FILE_HINTS.get(name.lower())
        if hint:
            hints.append(hint)
        elif name.endswith(".safetensors"):
            hints.append("safetensors weights")
        elif name.endswith((".bin", ".pt", ".pth", ".gguf", ".onnx")):
            hints.append("model weights")
    lower_files = {name.lower() for name in files}
    likely_model = bool(hints) or any(name.endswith((".safetensors", ".bin", ".pt", ".pth", ".gguf", ".onnx")) for name in lower_files)
    if "config.json" not in lower_files and not any(name.endswith((".gguf", ".onnx")) for name in lower_files):
        warnings.append("Missing config.json or a recognizable standalone model file.")
    if "readme.md" not in lower_files and "model_card.md" not in lower_files:
        warnings.append("Missing README/model card beside the artifact.")
    if "license" not in lower_files and "license.md" not in lower_files and "license.txt" not in lower_files:
        warnings.append("Missing local license file.")
    if not likely_model:
        warnings.append("No likely model weights/config files were detected.")
    return {
        "files": relative_files[:40],
        "file_count": len(relative_files),
        "detected_format_hints": sorted(set(hints)),
        "likely_model": likely_model,
        "missing_required_files": {
            "config": "config.json" not in lower_files and not any(name.endswith((".gguf", ".onnx")) for name in lower_files),
            "readme": "readme.md" not in lower_files and "model_card.md" not in lower_files,
            "license": "license" not in lower_files and "license.md" not in lower_files and "license.txt" not in lower_files,
        },
        "warnings": warnings,
    }


def _detect_model_files(path: Path) -> tuple[list[str], list[str], list[str]]:
    scan = _scan_model_files(path)
    return scan["detected_format_hints"], scan["warnings"], scan["files"]


def _task_slot(task: str) -> str:
    value = task.lower()
    if "segment" in value:
        return "segmentation_model"
    if "ground" in value or "localization" in value:
        return "grounding_model"
    if "report" in value:
        return "report_model"
    if "vision-language" in value or "vqa" in value or "vlm" in value:
        return "vision_language_model"
    if "chat" in value or "language" in value:
        return "chat_model"
    return "classification_model"


def validate_local_model_import(path: str) -> dict[str, Any]:
    p = _safe_local_model_path(path)
    if not p.exists() or not p.is_dir():
        raise ValueError("Import folder must exist inside data/models.")
    if p.parent != get_settings().models_dir.resolve() or p.name == "_registry" or p.name.startswith("."):
        raise ValueError("Import folder must be a top-level artifact folder inside data/models.")
    artifact_id = _local_artifact_id(p)
    card = _read_local_card(artifact_id)
    scan = _scan_model_files(p)
    missing_fields = [field for field in REQUIRED_LOCAL_CARD_FIELDS if not str((card or {}).get(field) or "").strip()]
    task = str((card or {}).get("task") or infer_task(" ".join([p.name, *scan["files"]])))
    runtime_eligible = bool(card and card.get("human_reviewed") and not missing_fields)
    evidence_assessment = validation_evidence_assessment((card or {}).get("validation_evidence"))
    readiness = "ready_for_model_card_review" if scan["likely_model"] else "blocked_missing_model_files"
    if runtime_eligible:
        readiness = "runtime_eligible"
    return {
        "id": artifact_id,
        "name": p.name,
        "artifact_path": str(p),
        "safe_path": True,
        "artifact_type": "folder",
        "task": task,
        "task_slot": _task_slot(task),
        "readiness": readiness,
        "runtime_eligible": runtime_eligible,
        "model_card_status": "reviewed" if runtime_eligible else ("incomplete" if card else "missing"),
        "missing_card_fields": missing_fields,
        "human_review_status": "human_reviewed" if card and card.get("human_reviewed") else "human_review_required",
        "validation_evidence_status": evidence_assessment["status"],
        "validation_evidence_assessment": evidence_assessment,
        "card_path": str(_local_card_path(artifact_id)) if card else "",
        **scan,
    }


def _download_state_by_path() -> dict[str, str]:
    states = {}
    for job in list_json("downloads"):
        target = str(job.get("target_path") or "")
        if target:
            states[str(Path(target).resolve())] = str(job.get("status") or "downloaded")
    return states


def list_local_model_artifacts() -> list[dict[str, Any]]:
    models_dir = get_settings().models_dir.resolve()
    models_dir.mkdir(parents=True, exist_ok=True)
    download_states = _download_state_by_path()
    items = []
    for path in sorted(models_dir.iterdir(), key=lambda item: item.name.lower()):
        if path.name == "_registry" or path.name.startswith(".") or path.name.endswith(".part"):
            continue
        artifact_id = _local_artifact_id(path)
        card = _read_local_card(artifact_id)
        scan = _scan_model_files(path)
        hints = scan["detected_format_hints"]
        warnings = scan["warnings"]
        files = scan["files"]
        human_reviewed = bool(card and card.get("human_reviewed"))
        missing_fields = [field for field in REQUIRED_LOCAL_CARD_FIELDS if not str((card or {}).get(field) or "").strip()]
        evidence_assessment = validation_evidence_assessment((card or {}).get("validation_evidence"))
        task = str((card or {}).get("task") or infer_task(" ".join([path.name, *files])))
        target_key = str(path.resolve())
        raw_state = download_states.get(target_key, "downloaded")
        state = "reviewed" if human_reviewed and not missing_fields else ("review_needed" if raw_state in {"completed", "installed", "downloaded"} else raw_state)
        card_path = _local_card_path(artifact_id)
        items.append(
            {
                "id": artifact_id,
                "name": path.name,
                "source": "local",
                "artifact_path": str(path),
                "artifact_type": "folder" if path.is_dir() else "file",
                "state": state,
                "runtime_eligible": human_reviewed and not missing_fields,
                "model_card_status": "reviewed" if human_reviewed and not missing_fields else "missing_or_incomplete",
                "missing_card_fields": missing_fields,
                "human_review_status": "human_reviewed" if human_reviewed else "human_review_required",
                "validation_evidence_status": evidence_assessment["status"],
                "validation_evidence_assessment": evidence_assessment,
                "task": task,
                "task_slot": _task_slot(task),
                "readiness": "runtime_eligible" if human_reviewed and not missing_fields else ("ready_for_model_card_review" if scan["likely_model"] else "blocked_missing_model_files"),
                "detected_format_hints": hints,
                "files": files,
                "file_count": scan["file_count"],
                "likely_model": scan["likely_model"],
                "missing_required_files": scan["missing_required_files"],
                "warnings": warnings,
                "card": card,
                "card_path": str(card_path) if card_path.exists() else "",
                "safety_note": (
                    "Review required before runtime use."
                    if not human_reviewed
                    else (
                        "Human-reviewed card and protocol-bounded local research evidence present."
                        if evidence_assessment["complete"]
                        else "Human-reviewed card present; structured validation evidence is incomplete, so confidence remains conservative."
                    )
                ),
            }
        )
    return items


def save_local_model_card(payload: dict[str, Any]) -> dict[str, Any]:
    artifact_id = str(payload.get("artifact_id") or payload.get("id") or "").strip()
    artifact_path = str(payload.get("artifact_path") or "").strip()
    path: Path | None = None
    if artifact_path:
        path = _safe_local_model_path(artifact_path)
        if not path.exists():
            raise ValueError("Local artifact path does not exist.")
        artifact_id = _local_artifact_id(path)
    if not artifact_id:
        raise ValueError("artifact_id or artifact_path is required.")
    existing = _read_local_card(artifact_id) or {}
    now = now_iso()
    raw_evidence = payload.get("validation_evidence", existing.get("validation_evidence"))
    validation_evidence = normalize_validation_evidence(raw_evidence)
    if path is None:
        stored_path = str(existing.get("artifact_path") or "").strip()
        if stored_path:
            path = _safe_local_model_path(stored_path)
    if path is not None:
        validation_evidence = bind_artifact_identity(validation_evidence, path)
    evidence_assessment = validation_evidence_assessment(validation_evidence)
    card = {
        **existing,
        **{key: value for key, value in payload.items() if key not in {"id"}},
        "artifact_id": artifact_id,
        "schema_version": "medray-local-model-card-v2",
        "human_reviewed": bool(payload.get("human_reviewed")),
        "validation_evidence": validation_evidence,
        "validation_evidence_status": evidence_assessment["status"],
        "validation_evidence_assessment": evidence_assessment,
        "confidence_posture": evidence_assessment["confidence_posture"],
        "updated_at": now,
        "created_at": existing.get("created_at") or now,
    }
    missing = [field for field in REQUIRED_LOCAL_CARD_FIELDS if not str(card.get(field) or "").strip()]
    card["runtime_eligible"] = bool(card["human_reviewed"] and not missing)
    card["missing_fields"] = missing
    card_path = _local_card_path(artifact_id)
    card["card_path"] = str(card_path)
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def runtime_local_model_gate_issues(payload: dict[str, Any]) -> list[str]:
    local_items = list_local_model_artifacts()
    eligible_ids = {item["id"] for item in local_items if item.get("runtime_eligible")}
    eligible_paths = {str(Path(item["artifact_path"]).resolve()) for item in local_items if item.get("runtime_eligible")}
    models_dir = get_settings().models_dir.resolve()
    issues = []
    for field in RUNTIME_MODEL_FIELDS:
        value = str(payload.get(field) or "").strip()
        if not value or value == "disabled" or value.startswith("demo"):
            continue
        if value.startswith("local:") and value not in eligible_ids:
            issues.append(f"{field}: local model requires a complete, human-reviewed model card before runtime use.")
            continue
        try:
            candidate = Path(value).expanduser().resolve()
        except Exception:
            continue
        if (models_dir in candidate.parents or candidate == models_dir) and str(candidate) not in eligible_paths:
            issues.append(f"{field}: data/models artifact is review-required and cannot be enabled yet.")
    return issues


def _huggingface_token_path() -> Path:
    return get_settings().cache_dir / "huggingface_token.json"


def _github_token_path() -> Path:
    return get_settings().cache_dir / "github_token.json"


def load_huggingface_token() -> str:
    path = _huggingface_token_path()
    if not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("token") or "").strip()
    except Exception:
        return ""


def load_github_token() -> str:
    path = _github_token_path()
    if not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("token") or "").strip()
    except Exception:
        return ""


def huggingface_login_status() -> dict[str, Any]:
    token = load_huggingface_token()
    return {
        "configured": bool(token),
        "storage": "local-only",
        "exported": False,
        "usage": "Used only for Hugging Face metadata/download requests when configured.",
    }


def save_huggingface_token(token: str) -> dict[str, Any]:
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("Hugging Face token is empty.")
    path = _huggingface_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"token": cleaned, "updated_at": now_iso()}), encoding="utf-8")
    return huggingface_login_status()


def clear_huggingface_token() -> dict[str, Any]:
    path = _huggingface_token_path()
    if path.exists():
        path.unlink()
    return huggingface_login_status()


def github_login_status() -> dict[str, Any]:
    token = load_github_token()
    return {
        "configured": bool(token),
        "storage": "local-only",
        "exported": False,
        "usage": "Used only for GitHub metadata/search requests when configured.",
    }


def save_github_token(token: str) -> dict[str, Any]:
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("GitHub token is empty.")
    path = _github_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"token": cleaned, "updated_at": now_iso()}), encoding="utf-8")
    return github_login_status()


def clear_github_token() -> dict[str, Any]:
    path = _github_token_path()
    if path.exists():
        path.unlink()
    return github_login_status()


def request_headers(url: str = "") -> dict[str, str]:
    headers = {"User-Agent": "MedRay-v2"}
    hostname = str(urllib.parse.urlparse(url).hostname or "").rstrip(".").lower()

    def official_domain(domain: str) -> bool:
        return hostname == domain or hostname.endswith(f".{domain}")

    hf_token = load_huggingface_token()
    if hf_token and official_domain("huggingface.co"):
        headers["Authorization"] = f"Bearer {hf_token}"
    github_token = load_github_token()
    if github_token and official_domain("github.com"):
        headers["Authorization"] = f"Bearer {github_token}"
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def _get_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers=request_headers(url))
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def _is_rate_limited(exc: Exception) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code in {403, 429} and "rate limit" in str(exc).lower()


def _rate_limit_detail(source: str, model_id: str = "", url: str = "") -> dict[str, Any]:
    name = model_id.replace("hf:", "").replace("github:", "").strip() or url or "rate-limited model"
    source_label = "Hugging Face" if source in {"hf", "Hugging Face"} or "huggingface.co" in url else "GitHub"
    detail = enrich_model(
        ModelMetadata(
            id=f"{'hf' if source_label == 'Hugging Face' else 'github'}:{name}",
            name=name,
            source=source_label,
            task_type=infer_task(name),
            license="unknown",
            vram_estimate=estimate_vram(name),
            medical_tags=[hint for hint in MEDICAL_HINTS if hint in name.lower()],
            url=url or (f"https://huggingface.co/{name}" if source_label == "Hugging Face" and "/" in name else None),
        ).model_dump(),
        name,
    )
    detail.update(
        {
            "card_readiness": model_card_readiness({**detail, "license": "unknown", "tags": detail.get("medical_tags", [])}),
            "files": [],
            "gated": "unknown",
            "private": "unknown",
            "source_reference": f"{source_label} metadata is temporarily rate-limited. Add a local token or open the source page for manual review.",
            "metadata_unavailable": True,
            "metadata_error": "rate limit exceeded",
        }
    )
    return detail


def search_hugging_face(query: str, limit: int = 20, page: int = 1) -> list[dict[str, Any]]:
    url = "https://huggingface.co/api/models?" + urllib.parse.urlencode({"search": query, "limit": limit * page})
    items = _list_of_dicts(_get_json(url))[(page - 1) * limit : page * limit]
    results = []
    for item in items:
        name = item.get("modelId", "")
        tags = _string_list(item.get("tags"))
        card_data = _card_data(item)
        pipeline_tag = item.get("pipeline_tag") or card_data.get("pipeline_tag") or ""
        datasets = _declared_datasets(tags, card_data)
        text = " ".join([name, pipeline_tag, *datasets, *tags])
        license_name = _declared_license(tags, card_data)
        payload = ModelMetadata(
            id=f"hf:{name}",
            name=name,
            source="Hugging Face",
            task_type=infer_task(text),
            license=license_name,
            size="unknown",
            quantization="quantized" if "q4" in text.lower() or "int4" in text.lower() else "unknown",
            vram_estimate=estimate_vram(text),
            medical_tags=[hint for hint in MEDICAL_HINTS if hint in text.lower()],
            url=f"https://huggingface.co/{name}",
        ).model_dump()
        payload.update(
            {
                "pipeline_tag": pipeline_tag or payload["task_type"],
                "tags": tags[:30],
                "datasets": datasets,
                "downloads": item.get("downloads"),
                "likes": item.get("likes"),
                "last_modified": item.get("lastModified"),
            }
        )
        results.append(enrich_model(payload, text, license_name))
    return sorted(results, key=lambda model: (int(model.get("fit_percent") or 0), int(model.get("maturity_score") or 0)), reverse=True)


def _hf_repo_id(model_id: str = "", url: str = "") -> str:
    raw = model_id.replace("hf:", "").strip()
    if raw:
        return raw
    parsed = urllib.parse.urlparse(url)
    if "huggingface.co" not in parsed.netloc.lower():
        return ""
    return parsed.path.strip("/").split("/tree/")[0].split("/resolve/")[0]


def _hf_readme(repo_id: str) -> str:
    readme_url = f"https://huggingface.co/{repo_id}/raw/main/README.md"
    try:
        req = urllib.request.Request(readme_url, headers=request_headers(readme_url))
        with urllib.request.urlopen(req, timeout=12) as res:
            return res.read(80_000).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _github_repo_id(model_id: str = "", url: str = "") -> str:
    raw = model_id.replace("github:", "").strip()
    if "/" in raw:
        return raw
    parsed = urllib.parse.urlparse(url)
    if "github.com" not in parsed.netloc.lower():
        return ""
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    return "/".join(parts[:2]) if len(parts) >= 2 else ""


def model_detail(source: str, model_id: str = "", url: str = "") -> dict[str, Any]:
    for item in STARTER_MODELS:
        if model_id in {item["id"], item["name"], item["url"]} or url == item["url"]:
            detail = enrich_model(dict(item), " ".join([item["name"], item["task_type"], item.get("reason", ""), " ".join(item.get("medical_tags", []))]), item.get("license", "unknown"))
            detail["card_readiness"] = model_card_readiness({**detail, "tags": detail.get("medical_tags", [])}, item.get("reason", ""))
            detail["source_reference"] = "MedRay internal candidate. No external metadata lookup was needed."
            return detail

    if source in {"hf", "Hugging Face"} or "huggingface.co" in url:
        repo_id = _hf_repo_id(model_id, url)
        if not repo_id:
            raise ValueError("Hugging Face model id is required.")
        api_url = f"https://huggingface.co/api/models/{urllib.parse.quote(repo_id, safe='/')}"
        try:
            data = _get_json(api_url)
        except Exception as exc:
            if _is_rate_limited(exc):
                return _rate_limit_detail("hf", repo_id, url)
            raise
        if not isinstance(data, dict):
            raise ValueError("Hugging Face detail metadata was not an object.")
        tags = _string_list(data.get("tags"))
        card_data = _card_data(data)
        readme = _hf_readme(repo_id)
        license_name = _declared_license(tags, card_data)
        datasets = _declared_datasets(tags, card_data)
        pipeline_tag = data.get("pipeline_tag") or card_data.get("pipeline_tag") or ""
        text = " ".join([repo_id, pipeline_tag, *datasets, *tags, readme[:4000]])
        detail = enrich_model(
            ModelMetadata(
                id=f"hf:{repo_id}",
                name=repo_id,
                source="Hugging Face",
                task_type=infer_task(text),
                license=license_name,
                vram_estimate=estimate_vram(text),
                quantization="quantized" if "q4" in text.lower() or "int4" in text.lower() else "unknown",
                medical_tags=[hint for hint in MEDICAL_HINTS if hint in text.lower()],
                url=f"https://huggingface.co/{repo_id}",
            ).model_dump(),
            text,
            license_name,
        )
        siblings = _list_of_dicts(data.get("siblings"))
        detail.update(
            {
                "pipeline_tag": pipeline_tag or detail["task_type"],
                "library_name": data.get("library_name") or card_data.get("library_name") or "unknown",
                "datasets": datasets,
                "tags": tags[:60],
                "downloads": data.get("downloads"),
                "likes": data.get("likes"),
                "gated": data.get("gated", False),
                "private": data.get("private", False),
                "last_modified": data.get("lastModified"),
                "sha": data.get("sha"),
                "files": [item.get("rfilename") for item in siblings[:20] if isinstance(item, dict) and item.get("rfilename")],
                "card_readiness": model_card_readiness({**data, **detail, "license": license_name}, readme),
                "readme_excerpt": readme[:900],
                "source_reference": "Hugging Face Hub model-card metadata: license, datasets, pipeline_tag, tags, files, gated/private flags.",
            }
        )
        return detail

    if source in {"github", "GitHub"} or "github.com" in url:
        repo_id = _github_repo_id(model_id, url)
        if repo_id:
            try:
                data = _get_json(f"https://api.github.com/repos/{repo_id}")
            except Exception as exc:
                if _is_rate_limited(exc):
                    return _rate_limit_detail("github", repo_id, url)
                raise
            if not isinstance(data, dict):
                raise ValueError("GitHub detail metadata was not an object.")
            topics = _string_list(data.get("topics"))
            license_data = data.get("license") if isinstance(data.get("license"), dict) else {}
            license_name = license_data.get("spdx_id") or "unknown"
            text = " ".join([repo_id, data.get("description") or "", " ".join(topics)])
            detail = enrich_model(
                ModelMetadata(
                    id=f"github:{repo_id}",
                    name=repo_id,
                    source="GitHub",
                    task_type=infer_task(text),
                    license=license_name,
                    vram_estimate=estimate_vram(text),
                    medical_tags=[hint for hint in MEDICAL_HINTS if hint in text.lower()],
                    url=data.get("html_url") or f"https://github.com/{repo_id}",
                ).model_dump(),
                text,
                license_name,
            )
            detail.update(
                {
                    "tags": topics[:30],
                    "last_modified": data.get("updated_at"),
                    "downloads": data.get("stargazers_count"),
                    "likes": data.get("watchers_count"),
                    "private": data.get("private", False),
                    "gated": False,
                    "source_reference": "GitHub repository metadata: license, description, topics, stars, and updated timestamp.",
                }
            )
            detail["card_readiness"] = model_card_readiness({**detail, "tags": topics}, data.get("description") or "")
            return detail

    raise ValueError("Model detail is available for Hugging Face or GitHub candidates.")


def search_github(query: str, limit: int = 20, page: int = 1) -> list[dict[str, Any]]:
    q = urllib.parse.urlencode({"q": query, "per_page": limit, "page": page})
    data = _get_json(f"https://api.github.com/search/repositories?{q}")
    results = []
    items = _list_of_dicts(data.get("items") if isinstance(data, dict) else None)
    for item in items:
        topics = _string_list(item.get("topics"))
        text = " ".join([str(item.get("full_name") or ""), str(item.get("description") or ""), " ".join(topics)])
        license_data = item.get("license") if isinstance(item.get("license"), dict) else {}
        license_name = license_data.get("spdx_id") or "unknown"
        payload = ModelMetadata(
            id=f"github:{item.get('full_name')}",
            name=item.get("full_name"),
            source="GitHub",
            task_type=infer_task(text),
            license=license_name,
            vram_estimate=estimate_vram(text),
            medical_tags=[hint for hint in MEDICAL_HINTS if hint in text.lower()],
            url=item.get("html_url"),
        ).model_dump()
        results.append(enrich_model(payload, text, license_name))
    return sorted(results, key=lambda model: (int(model.get("fit_percent") or 0), int(model.get("maturity_score") or 0)), reverse=True)


def _expanded_xray_queries(query: str) -> list[str]:
    base = " ".join(query.split())
    lower = base.lower()
    candidates = [base]
    if any(term in lower for term in ["detect", "segment", "local", "ground", "yolo", "mask"]):
        candidates.extend(
            [
                "xray detection",
                "chest xray detection",
                "xray segmentation",
                "radiograph object detection",
                "cxr localization",
            ]
        )
    elif any(term in lower for term in ["report", "chat", "assistant", "llm", "qwen", "gemma", "ollama"]):
        candidates.extend(
            [
                "xray report",
                "radiology report generation",
                "chest xray report generation",
                "medical report llm",
                "qwen radiology",
            ]
        )
    elif any(term in lower for term in ["classif", "vision", "vlm", "medgemma", "classifier"]):
        candidates.extend(
            [
                "chest xray classifier",
                "cxr classification",
                "xray vision language",
                "radiograph classification",
                "chexpert densenet",
            ]
        )
    candidates.extend(["chest xray", "cxr", "radiograph"])
    seen: set[str] = set()
    unique = []
    for item in candidates:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:6]


def search_all_sources(query: str, limit: int = 20, page: int = 1) -> dict[str, Any]:
    per_source = max(4, min(limit, 12))
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    inferred_task = infer_task(query)
    include_ollama = inferred_task in {"LLM", "report generation"} or any(term in query.lower() for term in ["ollama", "qwen", "gemma", "llama", "mistral", "chat"])

    used_queries = _expanded_xray_queries(query)
    for search_query in used_queries:
        if len(results) >= limit * 2:
            break
        for label, fn in [
            ("Hugging Face", lambda q=search_query: search_hugging_face(q, per_source, page)),
            ("GitHub", lambda q=search_query: search_github(q, per_source, page)),
        ]:
            try:
                results.extend(fn())
            except Exception as exc:
                message = f"{label}({search_query}): {exc}"
                if message not in errors:
                    errors.append(message)
    if include_ollama:
        try:
            ollama = list_ollama_models()
            results.extend(_list_of_dicts(ollama.get("models"))[:per_source])
            if ollama.get("error") and ollama.get("installed"):
                errors.append(f"Ollama: {ollama['error']}")
        except Exception as exc:
            errors.append(f"Ollama: {exc}")

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted(results, key=lambda model: (int(model.get("fit_percent") or 0), int(model.get("maturity_score") or 0)), reverse=True):
        key = str(item.get("id") or item.get("url") or item.get("name"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return {"source": "All sources", "results": deduped, "errors": errors, "fallback_used": bool(errors) and not bool(deduped), "queries_used": used_queries}


def list_ollama_models() -> dict[str, Any]:
    try:
        tags = ollama_tags()
        models = []
        for m in _list_of_dicts(tags.get("models") if isinstance(tags, dict) else None):
            capabilities = _string_list(m.get("capabilities"))
            task_type = "vision-language" if "vision" in capabilities else ("LLM" if "completion" in capabilities else infer_task(m.get("name", "")))
            payload = enrich_model(
                ModelMetadata(
                    id=f"ollama:{m.get('name')}",
                    name=m.get("name"),
                    source="Ollama",
                    task_type=task_type,
                    size=str(m.get("size", "unknown")),
                    vram_estimate=estimate_vram(m.get("name", "")),
                    status="installed",
                ).model_dump(),
                " ".join([m.get("name", ""), task_type, " ".join(capabilities)]),
            )
            payload["capabilities"] = capabilities
            models.append(payload)
        return {"installed": ollama_installed(), "service": True, "models": models}
    except Exception as exc:
        return {"installed": ollama_installed(), "service": False, "models": [], "error": str(exc)}


def import_local_model(path: str) -> dict[str, Any]:
    validation = validate_local_model_import(path)
    p = Path(validation["artifact_path"])
    meta = ModelMetadata(
        id=validation["id"],
        name=p.name,
        source="local",
        task_type=validation["task"],
        local_path=str(p),
        status=validation["readiness"],
        vram_estimate=estimate_vram(p.name),
    ).model_dump()
    meta = enrich_model(meta, p.name)
    meta["import_validation"] = validation
    upsert_json("model_catalog", meta["id"], meta)
    return {"model": meta, "validation": validation}


class DownloadManager:
    def __init__(self):
        self.jobs: dict[str, dict[str, Any]] = {}
        self.cancel_flags: set[str] = set()
        self.pause_flags: set[str] = set()
        self.workers: dict[str, threading.Thread] = {}
        self.reserved_targets: set[str] = set()
        self.lock = threading.Lock()

    def start(self, url: str, filename: str | None = None) -> dict[str, Any]:
        _validate_manual_download_url(url)
        job_id = str(uuid4())
        target = self._target_path(url, filename, job_id)
        partial = target.with_suffix(target.suffix + ".part")
        created_at = now_iso()
        job = {
            "id": job_id,
            "url": url,
            "name": target.name,
            "source": urllib.parse.urlparse(url).netloc or "manual URL",
            "target_path": str(target),
            "partial_path": str(partial),
            "status": "queued",
            "percent": 0,
            "bytes_read": 0,
            "total_bytes": None,
            "speed_bps": 0,
            "speed": "",
            "eta": "",
            "accept_ranges": False,
            "resumable": False,
            "retryable": False,
            "error": "",
            "created_at": created_at,
            "updated_at": created_at,
            "completed_at": None,
        }
        with self.lock:
            self.jobs[job_id] = job
        upsert_json("downloads", job_id, job)
        self._start_worker(job_id)
        return job

    def _start_worker(self, job_id: str) -> None:
        worker = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        with self.lock:
            self.workers[job_id] = worker
        worker.start()

    def _target_path(self, url: str, filename: str | None, job_id: str) -> Path:
        raw_name = filename or Path(urllib.parse.urlparse(url).path).name or f"download-{job_id}"
        safe_name = "".join(ch for ch in raw_name if ch.isalnum() or ch in "._- ")[:160].strip(" .") or f"download-{job_id}"
        models_dir = get_settings().models_dir.resolve()
        target = (models_dir / safe_name).resolve()
        if models_dir not in target.parents:
            raise ValueError("Download target must stay inside the local models directory.")
        with self.lock:
            partial = target.with_suffix(target.suffix + ".part")
            if str(target) in self.reserved_targets or target.exists() or partial.exists():
                target = target.with_name(f"{target.stem}-{job_id[:8]}{target.suffix}")
            self.reserved_targets.add(str(target))
        return target

    def _persist(self, job: dict[str, Any]) -> None:
        job["updated_at"] = now_iso()
        upsert_json("downloads", job["id"], job)

    def _format_progress(self, job: dict[str, Any], read: int, total: int | None, started: float) -> None:
        elapsed = max(time.time() - started, 0.1)
        speed = max((read - int(job.get("_resume_offset", 0))) / elapsed, 0)
        job["bytes_read"] = read
        job["total_bytes"] = total
        job["percent"] = round((read / total) * 100, 2) if total else 0
        job["speed_bps"] = round(speed, 2)
        job["speed"] = f"{speed / 1024 / 1024:.2f} MB/s"
        job["eta"] = f"{max((total - read) / speed, 0):.0f}s" if total and speed else "unknown"
        job["updated_at"] = now_iso()

    def _run(self, job_id: str) -> None:
        job = self.jobs[job_id]
        target = Path(job["target_path"])
        partial = Path(job["partial_path"])
        try:
            job["status"] = "downloading"
            job["retryable"] = False
            job["error"] = ""
            self._persist(job)
            resume_offset = partial.stat().st_size if partial.exists() else 0
            headers = request_headers(job["url"])
            if resume_offset:
                headers["Range"] = f"bytes={resume_offset}-"
            req = urllib.request.Request(job["url"], headers=headers)
            opener = urllib.request.build_opener(_SafeDownloadRedirectHandler())
            with opener.open(req, timeout=30) as res:
                range_supported = "bytes" in (res.headers.get("Accept-Ranges") or "").lower() or res.status == 206
                content_length = int(res.headers.get("Content-Length") or 0)
                if resume_offset and not range_supported:
                    resume_offset = 0
                total = (resume_offset + content_length) if content_length else None
                if total and total > MAX_MANUAL_DOWNLOAD_BYTES:
                    raise ValueError(f"Manual model download exceeds the {MAX_MANUAL_DOWNLOAD_BYTES} byte safety limit.")
                read = resume_offset
                job["_resume_offset"] = resume_offset
                job["accept_ranges"] = range_supported
                job["resumable"] = range_supported
                started = time.time()
                mode = "ab" if resume_offset and range_supported else "wb"
                with open(partial, mode) as f:
                    while True:
                        if job_id in self.cancel_flags:
                            job["status"] = "cancelled"
                            job["retryable"] = False
                            return
                        if job_id in self.pause_flags:
                            job["status"] = "paused"
                            job["retryable"] = True
                            self._persist(job)
                            return
                        chunk = res.read(1024 * 256)
                        if not chunk:
                            break
                        if read + len(chunk) > MAX_MANUAL_DOWNLOAD_BYTES:
                            raise ValueError(f"Manual model download exceeds the {MAX_MANUAL_DOWNLOAD_BYTES} byte safety limit.")
                        f.write(chunk)
                        read += len(chunk)
                        self._format_progress(job, read, total, started)
                partial.replace(target)
            job["status"] = "completed"
            job["percent"] = 100
            job["completed_at"] = now_iso()
            job["retryable"] = False
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
            job["retryable"] = True
        finally:
            job.pop("_resume_offset", None)
            self.pause_flags.discard(job_id)
            self.cancel_flags.discard(job_id)
            if job.get("status") == "cancelled":
                self._cleanup_partial(job)
            with self.lock:
                self.reserved_targets.discard(str(target.resolve()))
            self._persist(job)

    def list(self) -> list[dict[str, Any]]:
        merged = {item["id"]: item for item in list_json("downloads")}
        merged.update(self.jobs)
        return sorted(merged.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def cancel(self, job_id: str) -> dict[str, Any]:
        self.cancel_flags.add(job_id)
        job = self._get_job(job_id)
        if job.get("status") == "not_found":
            return job
        worker = self.workers.get(job_id)
        job["status"] = "cancelling" if worker and worker.is_alive() else "cancelled"
        job["retryable"] = False
        if job["status"] == "cancelled":
            self._cleanup_partial(job)
        self._persist(job)
        return job

    def pause(self, job_id: str) -> dict[str, Any]:
        job = self._get_job(job_id)
        if job["status"] in {"queued", "downloading"}:
            self.pause_flags.add(job_id)
            job["status"] = "pausing"
            job["retryable"] = True
            self._persist(job)
        return job

    def resume(self, job_id: str) -> dict[str, Any]:
        job = self._get_job(job_id)
        worker = self.workers.get(job_id)
        if job["status"] == "pausing" and worker and worker.is_alive():
            self.pause_flags.discard(job_id)
            job["status"] = "downloading"
            job["retryable"] = False
            self._persist(job)
            return job
        if job["status"] in {"paused", "failed"}:
            if worker and worker.is_alive():
                worker.join(timeout=2)
                if worker.is_alive():
                    return job
            self.pause_flags.discard(job_id)
            self.cancel_flags.discard(job_id)
            job["status"] = "queued"
            job["retryable"] = False
            self.jobs[job_id] = job
            self._persist(job)
            self._start_worker(job_id)
        return job

    def retry(self, job_id: str) -> dict[str, Any]:
        job = self._get_job(job_id)
        if job["status"] in {"failed", "cancelled", "paused"}:
            self._cleanup_partial(job)
            job["bytes_read"] = 0
            job["percent"] = 0
            job["speed"] = ""
            job["eta"] = ""
            job["status"] = "queued"
            job["retryable"] = False
            job["error"] = ""
            job["completed_at"] = None
            self.jobs[job_id] = job
            self._persist(job)
            self._start_worker(job_id)
        return job

    def delete(self, job_id: str) -> dict[str, Any]:
        job = self._get_job(job_id)
        self.cancel_flags.add(job_id)
        worker = self.workers.get(job_id)
        active = worker and worker.is_alive()
        if not active:
            self._cleanup_partial(job)
        job["status"] = "cancelling" if active else ("cancelled" if job.get("status") in {"queued", "downloading", "pausing", "paused"} else job.get("status", "cancelled"))
        job["retryable"] = False
        self.jobs[job_id] = job
        self._persist(job)
        return {"id": job_id, "status": job["status"], "partial_removed": not active}

    def _get_job(self, job_id: str) -> dict[str, Any]:
        if job_id in self.jobs:
            return self.jobs[job_id]
        for item in list_json("downloads"):
            if item.get("id") == job_id:
                self.jobs[job_id] = item
                return item
        return {"id": job_id, "status": "not_found", "retryable": False}

    def _cleanup_partial(self, job: dict[str, Any]) -> None:
        partial_path = job.get("partial_path")
        if not partial_path:
            return
        partial = Path(str(partial_path))
        models_dir = get_settings().models_dir.resolve()
        try:
            resolved = partial.resolve()
            if (models_dir in resolved.parents or resolved == models_dir) and resolved.exists():
                resolved.unlink()
        except Exception as exc:
            job["error"] = f"{job.get('error', '')} Cleanup failed: {exc}".strip()


download_manager = DownloadManager()
