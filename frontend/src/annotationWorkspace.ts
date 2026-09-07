import type { Annotation } from "./types";

export type AnnotationHistory = {
  past: Annotation[][];
  present: Annotation[];
  future: Annotation[][];
  limit: number;
};

export type PixelSpacing = { row_mm: number; column_mm: number };
export type AnnotationMeasurement = { kind: "length" | "area" | "angle"; value: number; unit: "px" | "px²" | "mm" | "mm²" | "°" };

const clone = (annotations: Annotation[]) => structuredClone(annotations);

export function createAnnotationHistory(annotations: Annotation[], limit = 50): AnnotationHistory {
  return { past: [], present: clone(annotations), future: [], limit: Math.max(1, Math.min(200, limit)) };
}

export function commitAnnotationChange(history: AnnotationHistory, annotations: Annotation[]): AnnotationHistory {
  return {
    ...history,
    past: [...history.past, clone(history.present)].slice(-history.limit),
    present: clone(annotations),
    future: [],
  };
}

export function undoAnnotationChange(history: AnnotationHistory): AnnotationHistory {
  if (!history.past.length) return history;
  return {
    ...history,
    past: history.past.slice(0, -1),
    present: clone(history.past[history.past.length - 1]),
    future: [clone(history.present), ...history.future].slice(0, history.limit),
  };
}

export function redoAnnotationChange(history: AnnotationHistory): AnnotationHistory {
  if (!history.future.length) return history;
  return {
    ...history,
    past: [...history.past, clone(history.present)].slice(-history.limit),
    present: clone(history.future[0]),
    future: history.future.slice(1),
  };
}

function finiteSpacing(spacing?: PixelSpacing | null): PixelSpacing {
  return spacing && spacing.row_mm > 0 && spacing.column_mm > 0 ? spacing : { row_mm: 1, column_mm: 1 };
}

const rounded = (value: number) => Math.round(value * 100) / 100;

export function measureAnnotation(annotation: Annotation, spacing?: PixelSpacing | null): AnnotationMeasurement | null {
  const coordinate = annotation.coordinate;
  const hasCalibration = Boolean(spacing && spacing.row_mm > 0 && spacing.column_mm > 0);
  const calibrated = finiteSpacing(spacing);
  const points = coordinate.points || [];
  if (coordinate.type === "length" && points.length === 2) {
    const dx = (points[1][0] - points[0][0]) * calibrated.column_mm;
    const dy = (points[1][1] - points[0][1]) * calibrated.row_mm;
    return { kind: "length", value: rounded(Math.hypot(dx, dy)), unit: hasCalibration ? "mm" : "px" };
  }
  if (coordinate.type === "ellipse" && coordinate.width > 0 && coordinate.height > 0) {
    const area = Math.PI * coordinate.width * calibrated.column_mm / 2 * coordinate.height * calibrated.row_mm / 2;
    return { kind: "area", value: rounded(area), unit: hasCalibration ? "mm²" : "px²" };
  }
  if (coordinate.type === "angle" && points.length === 3) {
    const [a, vertex, b] = points;
    const va = [(a[0] - vertex[0]) * calibrated.column_mm, (a[1] - vertex[1]) * calibrated.row_mm];
    const vb = [(b[0] - vertex[0]) * calibrated.column_mm, (b[1] - vertex[1]) * calibrated.row_mm];
    const denominator = Math.hypot(...va) * Math.hypot(...vb);
    if (!denominator) return null;
    const cosine = Math.max(-1, Math.min(1, (va[0] * vb[0] + va[1] * vb[1]) / denominator));
    return { kind: "angle", value: rounded(Math.acos(cosine) * 180 / Math.PI), unit: "°" };
  }
  return null;
}
