"""General local model-file management. Discovery never executes model code."""
import shutil
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.model_finder.providers import (
    list_local_model_artifacts,
    runtime_model_references,
)
from app.models.schemas import RuntimeConfig
from app.runtime.secrets import safe_error
from app.storage.db import load_runtime_config

router = APIRouter(prefix="/ai-setup/local")


@router.post("/import")
def import_weights(file: Annotated[UploadFile, File()]):
    # A browser file chooser copies one artifact into a dedicated folder. Never
    # deserialize it, overwrite another model, or use an uploaded filename as a path.
    if Path(file.filename or "").suffix.lower() not in {".pt", ".onnx", ".safetensors", ".gguf", ".bin", ".pth"}:
        raise HTTPException(400, "Choose a model weights file. Executables and scripts are not accepted.")
    name = "".join(c for c in Path(file.filename).stem if c.isalnum() or c in " -_")[:60].strip() or "imported"
    root = get_settings().models_dir / ("model-" + name + "-" + uuid4().hex[:10])
    root.mkdir()
    target = root / ("weights" + Path(file.filename).suffix.lower())
    partial = root / "upload.part"
    try:
        total = 0
        with partial.open("wb") as stream:
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)
                if total > 16 * 1024**3 or shutil.disk_usage(root).free < len(chunk) + 64 * 1024**2:
                    raise ValueError("File too large or insufficient disk space.")
                stream.write(chunk)
        if total == 0:
            raise ValueError("The selected model file is empty.")
        partial.replace(target)
        return {"detail": "Model copied. Complete its model card and human review before testing.", "artifact": next(item for item in list_local_model_artifacts() if item["artifact_path"] == str(root))}
    except Exception as exc:
        partial.unlink(missing_ok=True)
        if not any(root.iterdir()):
            root.rmdir()
        raise HTTPException(400, safe_error(exc)) from None
    finally:
        file.file.close()


@router.post("/remove")
def remove(payload: dict):
    model_id = str(payload.get("model_id") or "")
    config = load_runtime_config(RuntimeConfig().model_dump(mode="json"))
    item = next((item for item in list_local_model_artifacts() if item["id"] == model_id), None)
    if item is None:
        raise HTTPException(404, "Model no longer exists.")
    artifact_path = Path(item["artifact_path"]).resolve()
    for _, reference in runtime_model_references(config):
        if not reference:
            continue
        if reference == model_id:
            raise HTTPException(409, "This model is active. Choose another model before removing it.")
        try:
            is_active_path = Path(reference).expanduser().resolve() == artifact_path
        except (OSError, ValueError):
            is_active_path = False
        if is_active_path:
            raise HTTPException(409, "This model is active. Choose another model before removing it.")
    from app.ai_setup.catalog import WEIGHTS_NAME
    if item["name"] == WEIGHTS_NAME:
        raise HTTPException(409, "Manage the built-in classifier through X-ray Vision setup.")
    root = get_settings().models_dir.resolve()
    target = Path(item["artifact_path"])
    if target.is_symlink() or target.resolve().parent != root:
        raise HTTPException(400, "Only managed model artifacts can be removed.")
    trash = root / ".removed"
    trash.mkdir(exist_ok=True)
    if trash.is_symlink() or trash.resolve().parent != root:
        raise HTTPException(400, "Invalid model archive folder.")
    target.rename(trash / (uuid4().hex + "-" + target.name))
    return {"detail": "Removed from My Models. The file is retained in the local model archive; case history is unchanged."}
