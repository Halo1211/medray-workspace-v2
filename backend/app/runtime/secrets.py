"""Credentials live outside runtime snapshots, cases, logs and exports."""
import json
import os
import urllib.error
from app.config import get_settings


def _provider_key_records() -> dict[str, str]:
    settings = get_settings()
    records: dict[str, str] = {}
    try:
        payload = json.loads((settings.cache_dir / "provider_keys.json").read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            records.update({str(endpoint).rstrip("/"): str(key) for endpoint, key in payload.items() if str(endpoint).strip() and str(key).strip()})
    except (OSError, ValueError, TypeError):
        pass
    try:
        legacy = json.loads((settings.cache_dir / "provider_key.json").read_text(encoding="utf-8"))
        endpoint = str(legacy.get("base_url") or "").rstrip("/")
        key = str(legacy.get("key") or "")
        if endpoint and key:
            records.setdefault(endpoint, key)
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return records


def provider_key(base_url: str | None = None) -> str:
    records = _provider_key_records()
    if base_url:
        endpoint = base_url.rstrip("/")
        if endpoint in records:
            return records[endpoint]
        if get_settings().openai_base_url.rstrip("/") != endpoint:
            return ""
        return get_settings().openai_api_key
    if records:
        return next(iter(records.values()))
    return get_settings().openai_api_key


def save_provider_key(key: str, base_url: str = "") -> None:
    settings = get_settings()
    path = settings.cache_dir / "provider_keys.json"
    legacy_path = settings.cache_dir / "provider_key.json"
    records = _provider_key_records()
    endpoint = base_url.rstrip("/")
    if not key.strip():
        if endpoint:
            records.pop(endpoint, None)
        else:
            records.clear()
        if records:
            private_json(path, records)
        else:
            path.unlink(missing_ok=True)
        legacy_path.unlink(missing_ok=True)
        return
    if not endpoint:
        endpoint = settings.openai_base_url.rstrip("/")
    records[endpoint] = key.strip()
    private_json(path, records)
    legacy_path.unlink(missing_ok=True)


def private_json(path, payload) -> None:
    temporary = path.with_suffix(".tmp")
    with open(temporary, "w", encoding="utf-8") as stream:
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        json.dump(payload, stream)
    temporary.replace(path)


def safe_error(exc: Exception) -> str:
    """Do not echo remote error bodies, URLs or exception text containing secrets."""
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return "Access denied. Test your sign-in and check permission for this gated/private model."
        if exc.code == 404:
            return "Model or server address was not found. Check the selection and retry."
        if exc.code == 429:
            return "Provider rate limit reached. Wait a moment and retry."
        return f"Provider returned HTTP {exc.code}. Check the service and retry."
    message = str(exc).lower()
    if isinstance(exc, PermissionError):
        return "MedRay cannot write here. Check folder permissions and retry."
    if "space" in message or getattr(exc, "errno", None) == 28:
        return "Not enough disk space. Free space on the model drive and retry."
    if "memory" in message or "cuda" in message:
        return "The model could not allocate memory or start the GPU. Close other apps and use CPU setup."
    if "cloud endpoint blocked" in message:
        return "Cloud endpoint blocked. This address is outside this computer. Enable Online AI explicitly before connecting."
    if isinstance(exc, (TimeoutError, urllib.error.URLError)) or "timed out" in message:
        return "Connection failed or timed out. Start the service, check the address/internet, then retry."
    if "download" in message or "range" in message:
        return "Download interrupted or invalid. Resume, or retry from the beginning."
    return "The operation could not complete. Check the selected model, dependencies and service, then retry."
