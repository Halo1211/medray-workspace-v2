from __future__ import annotations

import base64
import hashlib
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from app.storage.db import safe_case_path
from PIL import Image, ImageStat


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
        preview_path = Path(str(path) + ".preview.png")
        img.convert("RGB").save(preview_path)
    return str(preview_path)


def _read_dicom(path: Path) -> tuple[Path, dict[str, Any]]:
    try:
        import pydicom
        from app.dicom.viewer import render_dicom_frame
    except Exception as exc:
        raise RuntimeError("DICOM membutuhkan pydicom. Jalankan installer dependency terlebih dahulu.") from exc

    ds = pydicom.dcmread(str(path))
    number_of_frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
    png_path = Path(str(path) + ".dicom.png")
    png_path.write_bytes(render_dicom_frame(path))
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
    suffix = Path(upload_file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".dcm", ".dicom"}:
        raise ValueError("Choose a PNG, JPEG, WebP, BMP or DICOM image file.")
    case_id = case_id or str(uuid4())
    target = safe_case_path(case_id, upload_file.filename or "image")
    while True:
        if any(path.exists() for path in (target, Path(str(target) + ".preview.png"), Path(str(target) + ".dicom.png"), Path(str(target) + ".dicom.png.preview.png"))):
            target = target.with_name(f"{target.stem}-{uuid4().hex[:8]}{target.suffix}")
            continue
        created_paths: set[Path] = set()
        buffer = None
        try:
            buffer = target.open("xb")
            created_paths.add(target)
            image_path = Path(str(target) + ".dicom.png") if suffix in {".dcm", ".dicom"} else target
            derivatives = [Path(str(image_path) + ".preview.png")]
            if image_path != target:
                derivatives.insert(0, image_path)
            for derivative in derivatives:
                with derivative.open("xb"):
                    pass
                created_paths.add(derivative)
            break
        except OSError as exc:
            if buffer is not None:
                buffer.close()
            for reserved_path in created_paths:
                reserved_path.unlink(missing_ok=True)
            if not isinstance(exc, FileExistsError):
                raise
            # Reserve previews too: another upload may use a derived filename.
            target = target.with_name(f"{target.stem}-{uuid4().hex[:8]}{target.suffix}")
    try:
        with buffer:
            shutil.copyfileobj(upload_file.file, buffer)

        suffix = target.suffix.lower()
        metadata: dict[str, Any] = {}
        image_path = target
        if suffix in {".dcm", ".dicom"}:
            created_paths.add(Path(str(target) + ".dicom.png"))
            image_path, metadata = _read_dicom(target)
            created_paths.add(image_path)
            fmt = "DICOM"
        else:
            fmt = suffix.replace(".", "").upper()
            with Image.open(target) as source:
                if source.mode in {"I", "F"} or source.mode.startswith("I;16"):
                    pixels = np.asarray(source, dtype=np.float64)
                    if not np.isfinite(pixels).all():
                        raise ValueError("Image pixels must contain finite intensities.")
                    minimum, maximum = float(pixels.min()), float(pixels.max())
                    scaled = np.zeros(pixels.shape, dtype=np.uint8)
                    if maximum > minimum:
                        scaled = np.rint((pixels - minimum) * (255.0 / (maximum - minimum))).clip(0, 255).astype(np.uint8)
                    # Keep the source unchanged; inference and preview use the
                    # same documented 8-bit rendering instead of clipping at 255.
                    image_path = target.with_name(f"{target.stem}-{uuid4().hex}.normalized.png")
                    with image_path.open("xb"):
                        pass
                    created_paths.add(image_path)
                    Image.fromarray(scaled).save(image_path, format="PNG")
                    metadata.update({"source_mode": source.mode, "pixel_normalization": "linear_min_max_to_uint8", "source_pixel_min": minimum, "source_pixel_max": maximum})

                    preview_reservation = Path(str(image_path) + ".preview.png")
                    with preview_reservation.open("xb"):
                        pass
                    created_paths.add(preview_reservation)
                    unused_preview = Path(str(target) + ".preview.png")
                    unused_preview.unlink()
                    created_paths.discard(unused_preview)

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
        created_paths.add(Path(str(image_path) + ".preview.png"))
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
