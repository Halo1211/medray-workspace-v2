from __future__ import annotations

import json
import hashlib
import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _is_windows_reserved_name(value: str) -> bool:
    return value.rstrip(" .").split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES


def connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                image_path TEXT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_catalog (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runtime_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS downloads (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                target_path TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )


def upsert_json(table: str, key: str, payload: dict[str, Any], key_column: str = "id") -> None:
    if table not in {"model_catalog", "downloads"}:
        raise ValueError("Unsupported table")
    with connect() as conn:
        if table == "model_catalog":
            conn.execute(
                "INSERT OR REPLACE INTO model_catalog (id, source, name, payload, status) VALUES (?, ?, ?, ?, ?)",
                (key, payload.get("source", "local"), payload.get("name", key), json.dumps(payload), payload.get("status", "available")),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO downloads (id, url, target_path, payload) VALUES (?, ?, ?, ?)",
                (key, payload.get("url", ""), payload.get("target_path", ""), json.dumps(payload)),
            )


def list_json(table: str) -> list[dict[str, Any]]:
    if table not in {"model_catalog", "downloads"}:
        raise ValueError("Unsupported table")
    with connect() as conn:
        rows = conn.execute(f"SELECT payload FROM {table}").fetchall()
    return [payload for row in rows if (payload := _decode_mapping(row["payload"])) is not None]


def _decode_mapping(raw: Any) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def save_case(payload: dict[str, Any]) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    created_at = payload.get("created_at") or timestamp
    updated_at = payload.get("updated_at") or created_at
    payload = {**payload, "created_at": created_at, "updated_at": updated_at}
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO cases (case_id, title, image_path, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload["case_id"],
                payload.get("title", "Untitled X-ray case"),
                payload.get("image_path"),
                json.dumps(payload),
                created_at,
                updated_at,
            ),
        )


def list_cases(query: str = "") -> list[dict[str, Any]]:
    like = f"%{query.lower()}%"
    with connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM cases WHERE lower(title) LIKE ? OR lower(case_id) LIKE ? ORDER BY updated_at DESC",
            (like, like),
        ).fetchall()
    return [payload for row in rows if (payload := _decode_mapping(row["payload"])) is not None]


def get_case(case_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return _decode_mapping(row["payload"]) if row else None


def _remove_case_directory(root: Path, case_id: str) -> bool:
    safe_id = safe_path_component(case_id, "case", 100)
    target = (root / safe_id).resolve()
    resolved_root = root.resolve()
    if not target.is_relative_to(resolved_root) or target == resolved_root:
        raise ValueError("Refusing to remove a case directory outside the configured data root.")
    if not target.exists():
        return False
    if not target.is_dir():
        raise ValueError("Refusing to remove a case path that is not a directory.")
    shutil.rmtree(target)
    return True


def _remove_case_directories(root: Path) -> int:
    """Remove all case subdirectories, including orphaned filesystem data."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    removed = 0
    for child in root.iterdir():
        if not child.is_dir():
            continue
        target = child.resolve()
        if not target.is_relative_to(root) or target == root:
            raise ValueError("Refusing to remove a case directory outside the configured data root.")
        shutil.rmtree(target)
        removed += 1
    return removed


def delete_case(case_id: str) -> dict[str, Any]:
    settings = get_settings()
    removed_case_dir = _remove_case_directory(settings.cases_dir, case_id)
    removed_export_dir = _remove_case_directory(settings.exports_dir, case_id)
    with connect() as conn:
        cursor = conn.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
        deleted = cursor.rowcount > 0
    return {
        "deleted": deleted,
        "case_id": case_id,
        "removed_case_dir": removed_case_dir,
        "removed_export_dir": removed_export_dir,
    }


def clear_case_database() -> dict[str, Any]:
    settings = get_settings()
    with connect() as conn:
        rows = conn.execute("SELECT case_id FROM cases").fetchall()
        case_ids = [str(row["case_id"]) for row in rows]
    removed_case_dirs = _remove_case_directories(settings.cases_dir)
    removed_export_dirs = _remove_case_directories(settings.exports_dir)
    with connect() as conn:
        conn.execute("DELETE FROM cases")
    return {
        "cleared": True,
        "deleted_case_count": len(case_ids),
        "removed_case_dirs": removed_case_dirs,
        "removed_export_dirs": removed_export_dirs,
    }


def save_runtime_config(payload: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO runtime_config (id, payload) VALUES (1, ?)", (json.dumps(payload),))


def load_runtime_config(default: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM runtime_config WHERE id = 1").fetchone()
    return _decode_mapping(row["payload"]) or default if row else default


def safe_case_path(case_id: str, filename: str) -> Path:
    settings = get_settings()
    cases_root = settings.cases_dir.resolve()
    cleaned_case_id = safe_path_component(case_id, "case", 100)
    case_dir = cases_root / cleaned_case_id
    if case_dir.is_symlink():
        raise ValueError("Refusing to write a case through a symbolic link.")
    case_dir.mkdir(parents=True, exist_ok=True)
    resolved_case_dir = case_dir.resolve()
    if not resolved_case_dir.is_relative_to(cases_root) or resolved_case_dir == cases_root:
        raise ValueError("Refusing to write a case outside the configured data root.")
    cleaned = safe_filename_component(filename, "image", 120)
    return case_dir / cleaned


def safe_path_component(value: Any, fallback: str = "item", max_length: int = 100) -> str:
    raw = str(value)
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "._-")[:max_length].strip(".")
    if not cleaned:
        cleaned = fallback
    if cleaned != raw or _is_windows_reserved_name(cleaned):
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        prefix_length = max(1, max_length - len(digest) - 1)
        prefix = cleaned[:prefix_length].rstrip(".") or fallback[:prefix_length]
        cleaned = f"{prefix}-{digest}"[:max_length]
    return cleaned


def safe_filename_component(value: Any, fallback: str = "image", max_length: int = 120) -> str:
    raw = str(value)
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "._- ")[:max_length].strip(" .")
    if not cleaned:
        cleaned = fallback
    if cleaned != raw or _is_windows_reserved_name(cleaned):
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        suffix = Path(cleaned).suffix
        if len(suffix) > 16:
            suffix = ""
        stem = cleaned[:-len(suffix)] if suffix else cleaned
        stem_length = max(1, max_length - len(suffix) - len(digest) - 1)
        stem = stem[:stem_length].rstrip(" .") or fallback[:stem_length]
        cleaned = f"{stem}-{digest}{suffix}"[:max_length]
    return cleaned
