import json
import sqlite3
import time
from contextlib import closing
from functools import cached_property, lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.storage.files import atomic_write_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_LOCATION_CONFIG = PROJECT_ROOT / ".medray-database-location.json"
DATABASE_FILENAME = "medray_v2.sqlite3"


def _configured_database_path() -> Path | None:
    try:
        payload = json.loads(DATABASE_LOCATION_CONFIG.read_text(encoding="utf-8"))
        value = payload.get("database_path") if isinstance(payload, dict) else ""
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser().resolve()
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MEDRAY_", extra="ignore")

    app_name: str = "MedRay v2"
    app_version: str = "0.2.0-alpha.1"
    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path = Field(default=Path(__file__).resolve().parents[2] / "data")
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    ollama_base_url: str = "http://127.0.0.1:11434"
    openai_base_url: str = "http://127.0.0.1:8000/v1"
    openai_api_key: str = ""
    openai_model: str = "local-model"
    default_backend: str = "demo"

    @property
    def cases_dir(self) -> Path:
        return self.data_dir / "cases"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @cached_property
    def db_path(self) -> Path:
        return _configured_database_path() or (self.data_dir / DATABASE_FILENAME)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for directory in [settings.data_dir, settings.cases_dir, settings.models_dir, settings.cache_dir, settings.exports_dir, settings.db_path.parent]:
        directory.mkdir(parents=True, exist_ok=True)
    return settings


def database_location_info() -> dict[str, str | bool]:
    settings = get_settings()
    configured = _configured_database_path()
    active_path = settings.db_path.resolve()
    pending_path = configured if configured and configured != active_path else None
    return {
        "database_path": str(active_path),
        "database_folder": str(active_path.parent),
        "default_database_path": str(settings.data_dir / DATABASE_FILENAME),
        "configured": bool(configured),
        "restart_required": pending_path is not None,
        "pending_database_path": str(pending_path) if pending_path else "",
    }


def set_database_folder(folder: str) -> dict[str, str | bool]:
    raw = str(folder or "").strip()
    if not raw:
        raise ValueError("Database folder is required.")
    target_folder = Path(raw).expanduser()
    if not target_folder.is_absolute():
        target_folder = (PROJECT_ROOT / target_folder).resolve()
    else:
        target_folder = target_folder.resolve()
    target_folder.mkdir(parents=True, exist_ok=True)
    if not target_folder.is_dir():
        raise ValueError("Database location must be a folder.")

    settings = get_settings()
    current_path = settings.db_path.resolve()
    target_path = (target_folder / DATABASE_FILENAME).resolve()
    if target_path == current_path:
        return {**database_location_info(), "restart_required": False, "copied_existing_database": False}
    if _configured_database_path() == target_path and target_path.exists():
        return {**database_location_info(), "restart_required": True, "copied_existing_database": False}
    if target_path.exists() and not target_path.is_file():
        raise ValueError("Target database path is not a file.")
    if target_path.exists():
        raise ValueError("A database already exists in that folder; choose an empty folder to avoid overwriting data.")

    copied_existing = False
    try:
        if current_path.exists():
            # Capture committed WAL pages too; copying the .sqlite3 file alone
            # can silently omit recent cases while the app is running.
            target_path.open("xb").close()
            copied_existing = True
            started = time.monotonic()
            def check_backup(status, remaining, total):
                if time.monotonic() - started > 10:
                    raise TimeoutError("Database backup is busy. Close other database sessions and retry.")
            with closing(sqlite3.connect(current_path, timeout=5)) as source, closing(sqlite3.connect(target_path)) as destination:
                source.backup(destination, pages=256, progress=check_backup, sleep=0.1)
        atomic_write_text(
            DATABASE_LOCATION_CONFIG,
            json.dumps({"database_path": str(target_path)}, indent=2),
        )
    except Exception:
        if copied_existing:
            target_path.unlink(missing_ok=True)
        raise
    return {
        "database_path": str(target_path),
        "database_folder": str(target_folder),
        "default_database_path": str(settings.data_dir / DATABASE_FILENAME),
        "configured": True,
        "restart_required": True,
        "copied_existing_database": copied_existing,
        "previous_database_path": str(current_path),
        "pending_database_path": str(target_path),
    }
