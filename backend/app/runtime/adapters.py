from __future__ import annotations

import base64
import ipaddress
import json
import shutil
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models.schemas import RuntimeConfig


SAFE_SYSTEM_PROMPT = """You are MedRay v2, an AI radiology research assistant.
Do not claim a definitive diagnosis. Separate objective findings, reasoning, impression, uncertainty, and recommendations.
Always state that outputs require verification by a qualified radiologist/physician.
Use cautious language such as possible, likely, perlu korelasi klinis, and perlu verifikasi klinisi."""


def endpoint_is_local(url: str) -> bool:
    """Return True only for loopback HTTP(S) endpoints."""
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
        hostname = str(parsed.hostname or "").rstrip(".").lower()
        if parsed.scheme not in {"http", "https"} or not hostname:
            return False
        if hostname == "localhost":
            return True
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def require_allowed_endpoint(url: str, allow_cloud: bool) -> None:
    if not allow_cloud and not endpoint_is_local(url):
        raise RuntimeError("Cloud endpoint blocked. Enable 'Allow cloud endpoints' explicitly before sending case data to a non-loopback host.")


def _json_request(url: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def ollama_tags(base_url: str | None = None) -> dict[str, Any]:
    url = (base_url or get_settings().ollama_base_url).rstrip("/") + "/api/tags"
    return _json_request(url, timeout=5)


def ollama_chat(messages: list[dict[str, str]], model: str, base_url: str | None = None) -> str:
    url = (base_url or get_settings().ollama_base_url).rstrip("/") + "/api/chat"
    payload = {"model": model, "messages": [{"role": "system", "content": SAFE_SYSTEM_PROMPT}, *messages], "stream": False}
    data = _json_request(url, payload, timeout=180)
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    return str(message.get("content") or "")


def ollama_vision(image_path: str, prompt: str, model: str, base_url: str | None = None) -> str:
    url = (base_url or get_settings().ollama_base_url).rstrip("/") + "/api/chat"
    image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SAFE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            },
        ],
        "stream": False,
    }
    data = _json_request(url, payload, timeout=300)
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    return str(message.get("content") or "")


def openai_compatible_chat(messages: list[dict[str, str]], model: str, base_url: str, api_key: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": [{"role": "system", "content": SAFE_SYSTEM_PROMPT}, *messages], "temperature": 0.2}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key or 'local'}"},
    )
    with urllib.request.urlopen(req, timeout=180) as res:
        data = json.loads(res.read().decode("utf-8"))
    choices = _list_of_dicts(data.get("choices"))
    message = choices[0].get("message") if choices and isinstance(choices[0].get("message"), dict) else {}
    return str(message.get("content") or "")


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def chat_response(message: str, history: list[dict[str, str]], config: RuntimeConfig, context: dict[str, Any]) -> dict[str, Any]:
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    annotations = _list_of_dicts(context.get("annotations")) or _list_of_dicts(analysis.get("annotations"))
    fallback_annotations = [
        ann for ann in annotations if "fallback" in str(ann.get("source", "")).lower()
    ]
    focused_context = {
        "case_id": context.get("case_id"),
        "title": context.get("title"),
        "analysis_findings": _list_of_dicts(analysis.get("findings")),
        "annotations": annotations,
        "annotation_provenance_note": (
            "Important: fallback heuristic annotations are broad review regions only, not valid lesion localization."
            if fallback_annotations
            else "Only treat annotations as localization evidence when source is a real reviewed model or human annotation."
        ),
        "result_cards": _list_of_dicts(analysis.get("result_cards")),
        "report": analysis.get("report") if isinstance(analysis.get("report"), dict) else (context.get("report") if isinstance(context.get("report"), dict) else {}),
        "warnings": _string_list(analysis.get("warnings")),
        "model_trace": _list_of_dicts(analysis.get("model_trace")),
    }
    raw_case = {
        "metadata": context.get("metadata") if isinstance(context.get("metadata"), dict) else {},
        "runtime": context.get("runtime") if isinstance(context.get("runtime"), dict) else {},
    }
    user = {
        "role": "user",
        "content": (
            f"Context kasus terstruktur: {json.dumps(focused_context, ensure_ascii=False)[:7000]}\n\n"
            f"Metadata/runtime tambahan: {json.dumps(raw_case, ensure_ascii=False)[:1500]}\n\n"
            "Instruksi keamanan: jika anotasi source-nya fallback heuristic, jelaskan bahwa itu bukan lokalisasi lesi valid dan hanya area review umum.\n\n"
            f"Pertanyaan: {message}"
        ),
    }
    messages = [user] if analysis else history[-6:] + [user]
    try:
        if config.primary_backend.value == "ollama":
            require_allowed_endpoint(config.ollama_base_url, config.allow_cloud)
            content = ollama_chat(messages, config.chat_model, config.ollama_base_url)
            return {"content": content, "backend": "ollama", "fallback": False}
        if config.primary_backend.value == "openai-compatible":
            settings = get_settings()
            require_allowed_endpoint(config.openai_base_url, config.allow_cloud)
            content = openai_compatible_chat(messages, config.chat_model, config.openai_base_url, settings.openai_api_key)
            return {"content": content, "backend": "openai-compatible", "fallback": False}
    except Exception as exc:
        return {"content": demo_reply(message, context) + f"\n\nCatatan runtime: fallback aktif karena backend gagal: {exc}", "backend": "demo", "fallback": True}
    return {"content": demo_reply(message, context), "backend": "demo", "fallback": True}


def demo_reply(message: str, context: dict[str, Any]) -> str:
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    report = analysis.get("report") if isinstance(analysis.get("report"), dict) else {}
    if "laporan" in message.lower() or "report" in message.lower():
        return report.get("findings", "Belum ada laporan aktif.") + "\n\nKesan: " + report.get("impression", "Perlu verifikasi radiolog/dokter.")
    if "anotasi" in message.lower():
        anns = _list_of_dicts(context.get("annotations")) or _list_of_dicts(analysis.get("annotations"))
        return f"Ada {len(anns)} anotasi. Sumber dan confidence harus dibaca eksplisit; fallback bukan bukti patologi."
    return "Mode demo: saya dapat membantu merapikan temuan, DDx, dan laporan, tetapi belum memeriksa gambar dengan model vision asli. Perlu korelasi klinis dan verifikasi radiolog/dokter."
