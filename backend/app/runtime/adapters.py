from __future__ import annotations

import base64
import ipaddress
import json
import inspect
import time
import shutil
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models.schemas import RuntimeConfig
from app.runtime.secrets import provider_key, safe_error


SAFE_SYSTEM_PROMPT = """You are MedRay v2, an AI radiology research assistant.
Do not claim a definitive diagnosis. Separate objective findings, reasoning, impression, uncertainty, and recommendations.
Always state that outputs require verification by a qualified radiologist/physician.
Use cautious language and clearly state uncertainty."""


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
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("Use an HTTP(S) server address without credentials, query or fragment.")
    if not allow_cloud and not endpoint_is_local(url):
        raise RuntimeError("Cloud endpoint blocked. Enable 'Allow cloud endpoints' explicitly before sending case data to a non-loopback host.")
    if not endpoint_is_local(url) and parsed.scheme != "https":
        raise RuntimeError("Remote AI providers must use HTTPS. Plain HTTP is allowed only for loopback servers on this computer.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Server redirect blocked. Use the final server address and test it explicitly.")


def _json_request(url: str, payload: dict[str, Any] | None = None, timeout: int = 60, max_retries: int = 0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as res:
                return json.loads(res.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError):
            if attempt >= max_retries:
                raise
            time.sleep(min(2 ** attempt, 4))
    raise RuntimeError("Provider request failed.")


def ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def ollama_tags(base_url: str | None = None) -> dict[str, Any]:
    url = (base_url or get_settings().ollama_base_url).rstrip("/") + "/api/tags"
    return _json_request(url, timeout=5)


def ollama_chat(messages: list[dict[str, str]], model: str, base_url: str | None = None, *, temperature: float = 0.2, top_p: float = 0.95, seed: int = -1, max_output_tokens: int = 2048, timeout: int = 180, max_retries: int = 1) -> str:
    url = (base_url or get_settings().ollama_base_url).rstrip("/") + "/api/chat"
    options = {"temperature": temperature, "top_p": top_p, "num_predict": max_output_tokens}
    if seed >= 0:
        options["seed"] = seed
    payload = {"model": model, "messages": [{"role": "system", "content": SAFE_SYSTEM_PROMPT}, *messages], "stream": False, "options": options}
    data = _json_request(url, payload, timeout=timeout, max_retries=max_retries)
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("The AI response has no text content.")
    return content


def ollama_vision(image_path: str, prompt: str, model: str, base_url: str | None = None, *, temperature: float = 0.2, top_p: float = 0.95, seed: int = -1, max_output_tokens: int = 2048, timeout: int = 300, max_retries: int = 1) -> str:
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
        "options": {"temperature": temperature, "top_p": top_p, "num_predict": max_output_tokens, **({"seed": seed} if seed >= 0 else {})},
    }
    data = _json_request(url, payload, timeout=timeout, max_retries=max_retries)
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("The AI response has no text content.")
    return content


def openai_compatible_chat(messages: list[dict[str, Any]], model: str, base_url: str, api_key: str, *, temperature: float = 0.2, top_p: float = 0.95, seed: int = -1, max_output_tokens: int = 2048, timeout: int = 180, max_retries: int = 1) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": [{"role": "system", "content": SAFE_SYSTEM_PROMPT}, *messages], "temperature": temperature, "top_p": top_p, "max_tokens": max_output_tokens}
    if seed >= 0:
        payload["seed"] = seed
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key or 'local'}"},
    )
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as res:
                data = json.loads(res.read().decode("utf-8"))
            break
        except (TimeoutError, urllib.error.URLError):
            if attempt >= max_retries:
                raise
            time.sleep(min(2 ** attempt, 4))
    choices = _list_of_dicts(data.get("choices"))
    message = choices[0].get("message") if choices and isinstance(choices[0].get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("The AI response has no text content.")
    return content


def openai_compatible_vision(image_path: str, prompt: str, model: str, base_url: str, api_key: str, **options: Any) -> str:
    """Standard chat-completions image input; the selected server must support it."""
    import io
    from PIL import Image
    with Image.open(image_path) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
    image_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    return openai_compatible_chat([{"role": "user", "content": [
        {"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}},
    ]}], model, base_url, api_key, **options)


def _runtime_call(function, args: tuple[Any, ...], config: RuntimeConfig) -> str:
    parameters = inspect.signature(function).parameters
    if "temperature" not in parameters:
        return function(*args)
    return function(
        *args,
        temperature=config.temperature,
        top_p=config.top_p,
        seed=config.seed,
        max_output_tokens=config.max_output_tokens,
        timeout=config.request_timeout_seconds,
        max_retries=config.max_retries,
    )


def runtime_task_connection(config: RuntimeConfig | dict[str, Any], task: str) -> dict[str, Any]:
    """Resolve a task-specific tested connection, with legacy runtime fields as fallback."""
    raw = config.model_dump(mode="json") if isinstance(config, RuntimeConfig) else config
    task_connections = raw.get("task_connections") if isinstance(raw.get("task_connections"), dict) else {}
    selected = task_connections.get(task)
    if isinstance(selected, dict) and selected.get("backend") in {"ollama", "openai-compatible"}:
        return {
            "backend": str(selected["backend"]),
            "base_url": str(selected.get("base_url") or ""),
            "model": str(selected.get("model") or ""),
            "allow_cloud": selected.get("allow_cloud") is True,
            "provider": str(selected.get("provider") or ""),
        }
    backend_value = raw.get("primary_backend", "demo")
    backend = backend_value.value if hasattr(backend_value, "value") else str(backend_value)
    model_field = {"vision": "vision_language_model", "chat": "chat_model", "report": "report_model"}.get(task, "")
    return {
        "backend": backend,
        "base_url": str(raw.get("ollama_base_url" if backend == "ollama" else "openai_base_url") or ""),
        "model": str(raw.get(model_field) or ""),
        "allow_cloud": raw.get("allow_cloud") is True,
        "provider": "",
    }


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def chat_response(message: str, history: list[dict[str, str]], config: RuntimeConfig, context: dict[str, Any], language: str = "id") -> dict[str, Any]:
    is_en = language != "id"
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
    language_instruction = "Respond entirely in English, including headings and safety notes." if is_en else "Jawab seluruhnya dalam bahasa Indonesia, termasuk judul dan catatan keselamatan."
    depth_instruction = {
        "focused": "Give a focused response limited to the direct question and the most important safety caveat.",
        "balanced": "Give a balanced response with evidence, uncertainty, and the next safe action.",
        "thorough": "Give a thorough response: systematically review available evidence, limitations, alternatives, and next safe actions.",
    }.get(config.review_depth, "Give a balanced response with evidence and uncertainty.")
    user = {
        "role": "user",
        "content": (
            f"{'Structured case context' if is_en else 'Context kasus terstruktur'}: {json.dumps(focused_context, ensure_ascii=False)[:7000]}\n\n"
            f"{'Additional metadata/runtime' if is_en else 'Metadata/runtime tambahan'}: {json.dumps(raw_case, ensure_ascii=False)[:1500]}\n\n"
            f"{language_instruction} {depth_instruction}\n"
            + ("Safety instruction: a fallback heuristic annotation is only a broad review region, not valid lesion localization.\n\n" if is_en else "Instruksi keamanan: anotasi fallback heuristic hanya area review umum, bukan lokalisasi lesi yang valid.\n\n")
            + f"{'Question' if is_en else 'Pertanyaan'}: {message}"
        ),
    }
    messages = [user] if analysis else history[-6:] + [user]
    connection = runtime_task_connection(config, "chat")
    chat_model = connection["model"]
    if chat_model == "disabled" or chat_model.startswith("demo-"):
        return {"content": demo_reply(message, context, language), "backend": "demo", "fallback": True}
    try:
        if connection["backend"] == "ollama":
            require_allowed_endpoint(connection["base_url"], connection["allow_cloud"])
            content = _runtime_call(ollama_chat, (messages, chat_model, connection["base_url"]), config)
            return {"content": content, "backend": "ollama", "fallback": False}
        if connection["backend"] == "openai-compatible":
            require_allowed_endpoint(connection["base_url"], connection["allow_cloud"])
            content = _runtime_call(openai_compatible_chat, (messages, chat_model, connection["base_url"], provider_key(connection["base_url"])), config)
            return {"content": content, "backend": "openai-compatible", "fallback": False}
    except Exception as exc:
        runtime_note = f"Runtime note: fallback is active because the backend failed: {safe_error(exc)}" if is_en else f"Catatan runtime: fallback aktif karena backend gagal: {safe_error(exc)}"
        return {"content": demo_reply(message, context, language) + f"\n\n{runtime_note}", "backend": "demo", "fallback": True}
    return {"content": demo_reply(message, context, language), "backend": "demo", "fallback": True}


def demo_reply(message: str, context: dict[str, Any], language: str = "id") -> str:
    is_en = language != "id"
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    report = analysis.get("report") if isinstance(analysis.get("report"), dict) else {}
    if "laporan" in message.lower() or "report" in message.lower():
        return report.get("findings", "No active report yet." if is_en else "Belum ada laporan aktif.") + ("\n\nImpression: " if is_en else "\n\nKesan: ") + report.get("impression", "Qualified radiologist/physician verification is required." if is_en else "Perlu verifikasi radiolog/dokter.")
    if "anotasi" in message.lower() or "annotation" in message.lower():
        anns = _list_of_dicts(context.get("annotations")) or _list_of_dicts(analysis.get("annotations"))
        return (f"There are {len(anns)} annotations. Review source and confidence explicitly; fallback regions are not evidence of pathology." if is_en else f"Ada {len(anns)} anotasi. Sumber dan confidence harus dibaca eksplisit; fallback bukan bukti patologi.")
    return ("Demo mode: I can help organize findings, differential considerations, and a report, but no real vision model reviewed the image. Clinical correlation and qualified radiologist/physician verification are required." if is_en else "Mode demo: saya dapat membantu merapikan temuan, diagnosis banding, dan laporan, tetapi belum memeriksa gambar dengan model vision asli. Perlu korelasi klinis dan verifikasi radiolog/dokter.")
