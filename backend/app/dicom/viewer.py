from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from PIL import Image
from pydicom.multival import MultiValue
from pydicom.pixels import apply_modality_lut, apply_voi_lut


def _numbers(value: Any) -> list[float]:
    values = value if isinstance(value, (list, tuple, MultiValue)) else [value]
    result: list[float] = []
    for item in values:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            continue
    return result


def _pixel_spacing(ds) -> dict[str, float] | None:
    values = _numbers(getattr(ds, "PixelSpacing", None) or getattr(ds, "ImagerPixelSpacing", None))
    if len(values) < 2 or values[0] <= 0 or values[1] <= 0:
        return None
    return {"row_mm": values[0], "column_mm": values[1]}


def dicom_viewer_profile(path: str | Path) -> dict[str, Any]:
    ds = pydicom.dcmread(str(path), stop_before_pixels=True)
    centers = _numbers(getattr(ds, "WindowCenter", None))
    widths = _numbers(getattr(ds, "WindowWidth", None))
    explanations = [str(item) for item in (getattr(ds, "WindowCenterWidthExplanation", []) or [])]
    if isinstance(getattr(ds, "WindowCenterWidthExplanation", None), str):
        explanations = [str(ds.WindowCenterWidthExplanation)]
    presets = [
        {
            "name": explanations[index] if index < len(explanations) and explanations[index] else f"DICOM preset {index + 1}",
            "center": center,
            "width": widths[min(index, len(widths) - 1)],
        }
        for index, center in enumerate(centers)
        if widths and widths[min(index, len(widths) - 1)] > 0
    ]
    return {
        "schema_version": "medray-dicom-viewer-v1",
        "number_of_frames": max(1, int(getattr(ds, "NumberOfFrames", 1) or 1)),
        "rows": int(getattr(ds, "Rows", 0) or 0),
        "columns": int(getattr(ds, "Columns", 0) or 0),
        "photometric_interpretation": str(getattr(ds, "PhotometricInterpretation", "")),
        "modality": str(getattr(ds, "Modality", "")),
        "pixel_spacing": _pixel_spacing(ds),
        "window_presets": presets,
        "default_window": presets[0] if presets else None,
        "orientation": _numbers(getattr(ds, "ImageOrientationPatient", None)),
        "frame_of_reference_uid": str(getattr(ds, "FrameOfReferenceUID", "")),
        "supports_window_level": str(getattr(ds, "PhotometricInterpretation", "")).upper() in {"MONOCHROME1", "MONOCHROME2"},
    }


def _select_frame(array: np.ndarray, ds, frame: int) -> np.ndarray:
    frame_count = max(1, int(getattr(ds, "NumberOfFrames", 1) or 1))
    if frame < 0 or frame >= frame_count:
        raise ValueError(f"DICOM frame must be between 0 and {frame_count - 1}.")
    samples = int(getattr(ds, "SamplesPerPixel", 1) or 1)
    if frame_count > 1 and ((samples == 1 and array.ndim >= 3) or (samples > 1 and array.ndim >= 4)):
        return array[frame]
    return array


def render_dicom_frame(
    path: str | Path,
    frame: int = 0,
    window_center: float | None = None,
    window_width: float | None = None,
    invert: bool = False,
) -> bytes:
    ds = pydicom.dcmread(str(path))
    raw = _select_frame(np.asarray(ds.pixel_array), ds, frame)
    modality_pixels = apply_modality_lut(raw, ds)
    if window_center is not None or window_width is not None:
        if window_center is None or window_width is None or not np.isfinite(window_center) or not np.isfinite(window_width) or window_width <= 0:
            raise ValueError("Window center and width must be finite, and width must be greater than zero.")
        array = np.asarray(modality_pixels, dtype=np.float32)
        low = float(window_center) - float(window_width) / 2
        high = float(window_center) + float(window_width) / 2
        array = np.clip(array, low, high)
    else:
        array = np.asarray(apply_voi_lut(modality_pixels, ds), dtype=np.float32)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        raise ValueError("DICOM pixel data contains no finite values.")
    minimum, maximum = float(finite.min()), float(finite.max())
    array = np.nan_to_num(array, nan=minimum, posinf=maximum, neginf=minimum)
    array = (array - minimum) / max(maximum - minimum, 1.0)
    monochrome1 = str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1"
    if monochrome1 ^ bool(invert):
        array = 1.0 - array
    image = Image.fromarray((array * 255).clip(0, 255).astype(np.uint8)).convert("L")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
