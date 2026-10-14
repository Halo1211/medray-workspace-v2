from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from PIL import Image
from pydicom.multival import MultiValue
from pydicom.pixels import (
    apply_color_lut,
    apply_modality_lut,
    apply_voi_lut,
    apply_windowing,
)


def _number_values(value: Any) -> list[float | None]:
    values = value if isinstance(value, (list, tuple, MultiValue)) else [value]
    result: list[float | None] = []
    for item in values:
        try:
            number = float(item)
            result.append(number if np.isfinite(number) else None)
        except (TypeError, ValueError):
            result.append(None)
    return result


def _pixel_spacing(ds) -> dict[str, float] | None:
    values = _number_values(getattr(ds, "PixelSpacing", None) or getattr(ds, "ImagerPixelSpacing", None))
    if len(values) != 2 or any(value is None or value <= 0 for value in values):
        return None
    return {"row_mm": values[0], "column_mm": values[1]}


def dicom_viewer_profile(path: str | Path) -> dict[str, Any]:
    ds = pydicom.dcmread(str(path), stop_before_pixels=True)
    centers = _number_values(getattr(ds, "WindowCenter", None))
    widths = _number_values(getattr(ds, "WindowWidth", None))
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
        if center is not None and widths and widths[min(index, len(widths) - 1)] is not None and widths[min(index, len(widths) - 1)] > 0
    ]
    orientation = _number_values(getattr(ds, "ImageOrientationPatient", None))
    supports_window_level = str(getattr(ds, "PhotometricInterpretation", "")).upper() in {"MONOCHROME1", "MONOCHROME2"}
    if not supports_window_level:
        presets = []
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
        "orientation": orientation if len(orientation) == 6 and all(value is not None for value in orientation) else [],
        "frame_of_reference_uid": str(getattr(ds, "FrameOfReferenceUID", "")),
        "supports_window_level": supports_window_level,
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
    photometric = str(getattr(ds, "PhotometricInterpretation", "")).upper()
    if int(getattr(ds, "SamplesPerPixel", 1) or 1) > 1 or photometric == "PALETTE COLOR":
        if window_center is not None or window_width is not None:
            raise ValueError("Window/level is supported only for monochrome DICOM images.")
        if photometric == "PALETTE COLOR":
            raw = apply_color_lut(raw, ds)
            bits = int(ds.RedPaletteColorLookupTableDescriptor[2])
        else:
            bits = int(ds.BitsStored)
        array = np.asarray(raw, dtype=np.float64) / (2 ** bits - 1)
        if invert:
            array = 1.0 - array
        image = Image.fromarray((array * 255).clip(0, 255).astype(np.uint8)).convert("RGB")
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
    modality_pixels = apply_modality_lut(raw, ds)
    explicit_window = window_center is not None or window_width is not None
    if explicit_window:
        if window_center is None or window_width is None or not np.isfinite(window_center) or not np.isfinite(window_width) or window_width <= 0:
            raise ValueError("Window center and width must be finite, and width must be greater than zero.")
        ds.WindowCenter = window_center
        ds.WindowWidth = window_width
        array = np.asarray(apply_windowing(modality_pixels, ds), dtype=np.float64)
    else:
        array = np.asarray(apply_voi_lut(modality_pixels, ds), dtype=np.float64)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        raise ValueError("DICOM pixel data contains no finite values.")
    if not explicit_window and ds.get("VOILUTSequence"):
        minimum, maximum = 0.0, float(2 ** int(ds.VOILUTSequence[0].LUTDescriptor[2]) - 1)
    elif explicit_window or (ds.get("WindowCenter") is not None and ds.get("WindowWidth") is not None):
        if ds.get("ModalityLUTSequence"):
            minimum, maximum = 0.0, float(2 ** int(ds.ModalityLUTSequence[0].LUTDescriptor[2]) - 1)
        elif ds.PixelRepresentation == 0:
            minimum, maximum = 0.0, float(2 ** int(ds.BitsStored) - 1)
        else:
            minimum, maximum = float(-(2 ** (int(ds.BitsStored) - 1))), float(2 ** (int(ds.BitsStored) - 1) - 1)
        if ds.get("RescaleSlope") is not None and ds.get("RescaleIntercept") is not None:
            minimum = minimum * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
            maximum = maximum * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
    else:
        minimum, maximum = float(finite.min()), float(finite.max())
    array = np.nan_to_num(array, nan=minimum, posinf=maximum, neginf=minimum)
    extent = maximum - minimum
    array = (array - minimum) / (extent if extent else 1.0)
    monochrome1 = photometric == "MONOCHROME1"
    if monochrome1 ^ bool(invert):
        array = 1.0 - array
    image = Image.fromarray((array * 255).clip(0, 255).astype(np.uint8)).convert("L")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
