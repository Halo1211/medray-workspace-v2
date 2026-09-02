from __future__ import annotations

import base64
import hashlib
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageStat

from app.storage.db import safe_case_path


def file_hash(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "algorithm": "sha256",
        "digest": digest.hexdigest(),
        "bytes": path.stat().st_size,
        "status": "ok",
    }


def _image_preview(path: Path, max_size: int = 768) -> str:
    with Image.open(path) as img:
        img.thumbnail((max_size, max_size))
        preview_path = path.with_suffix(".preview.png")
        img.convert("RGB").save(preview_path)
    return str(preview_path)


def _read_dicom(path: Path) -> tuple[Path, dict[str, Any]]:
    try:
        import numpy as np
        import pydicom
        from pydicom.pixels import apply_voi_lut
    except Exception as exc:
        raise RuntimeError("DICOM membutuhkan pydicom. Jalankan installer dependency terlebih dahulu.") from exc

    ds = pydicom.dcmread(str(path))
    arr = np.asarray(apply_voi_lut(ds.pixel_array, ds))
    number_of_frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
    samples_per_pixel = int(getattr(ds, "SamplesPerPixel", 1) or 1)
    if number_of_frames > 1:
        if samples_per_pixel == 1 and arr.ndim >= 3:
            arr = arr[0]
        elif samples_per_pixel > 1 and arr.ndim >= 4:
            arr = arr[0]
    arr = np.asarray(arr, dtype="float32")
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise RuntimeError("DICOM pixel data contains no finite values.")
    minimum = float(finite.min())
    maximum = float(finite.max())
    arr = np.nan_to_num(arr, nan=minimum, posinf=maximum, neginf=minimum)
    arr = (arr - minimum) / max(maximum - minimum, 1.0)
    if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
        arr = 1.0 - arr
    arr = (arr * 255).clip(0, 255).astype("uint8")
    img = Image.fromarray(arr).convert("L")
    png_path = path.with_suffix(".dicom.png")
    img.save(png_path)
    metadata = {
        "PatientID": str(getattr(ds, "PatientID", "")),
        "StudyDate": str(getattr(ds, "StudyDate", "")),
        "Modality": str(getattr(ds, "Modality", "")),
        "BodyPartExamined": str(getattr(ds, "BodyPartExamined", "")),
        "ViewPosition": str(getattr(ds, "ViewPosition", "")),
        "Laterality": str(getattr(ds, "Laterality", "") or getattr(ds, "ImageLaterality", "")),
        "StudyInstanceUID": str(getattr(ds, "StudyInstanceUID", "")),
        "SeriesInstanceUID": str(getattr(ds, "SeriesInstanceUID", "")),
        "SOPInstanceUID": str(getattr(ds, "SOPInstanceUID", "")),
        "Rows": int(getattr(ds, "Rows", 0) or 0),
        "Columns": int(getattr(ds, "Columns", 0) or 0),
        "NumberOfFrames": number_of_frames,
        "PhotometricInterpretation": str(getattr(ds, "PhotometricInterpretation", "")),
        "BurnedInAnnotation": str(getattr(ds, "BurnedInAnnotation", "")),
        "RecognizableVisualFeatures": str(getattr(ds, "RecognizableVisualFeatures", "")),
    }
    return png_path, {k: v for k, v in metadata.items() if v not in ("", 0)}


def ingest_upload(upload_file, case_id: str | None = None) -> dict[str, Any]:
    case_id = case_id or str(uuid4())
    target = safe_case_path(case_id, upload_file.filename or "image")
    if target.exists():
        target = target.with_name(f"{target.stem}-{uuid4().hex[:8]}{target.suffix}")
    created_paths: set[Path] = {target}
    try:
        with target.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

        suffix = target.suffix.lower()
        metadata: dict[str, Any] = {}
        image_path = target
        if suffix in {".dcm", ".dicom"}:
            image_path, metadata = _read_dicom(target)
            created_paths.add(image_path)
            fmt = "DICOM"
        else:
            fmt = suffix.replace(".", "").upper()

        with Image.open(image_path) as img:
            width, height = img.size
            stat = ImageStat.Stat(img.convert("L"))
            metadata.update(
                {
                    "width": width,
                    "height": height,
                    "format": fmt or img.format or "image",
                    "mode": img.mode,
                    "mean_luminance": round(stat.mean[0], 2),
                    "contrast_stddev": round(stat.stddev[0], 2),
                    "file_size_bytes": target.stat().st_size,
                }
            )
        preview_path = Path(_image_preview(image_path))
        created_paths.add(preview_path)
        return {
            "case_id": case_id,
            "filename": upload_file.filename,
            "source_path": str(target),
            "is_dicom": suffix in {".dcm", ".dicom"},
            "stored_path": str(image_path),
            "preview_path": str(preview_path),
            "metadata": metadata,
            "hashes": {"input": file_hash(target), "preview": file_hash(preview_path)},
            "format": metadata.get("format", fmt),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
        }
    except Exception:
        for path in sorted(created_paths, key=lambda item: len(item.parts), reverse=True):
            path.unlink(missing_ok=True)
        try:
            target.parent.rmdir()
        except OSError:
            pass
        raise


def image_to_data_url(path: str) -> str:
    p = Path(path)
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")
