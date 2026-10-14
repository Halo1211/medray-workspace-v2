import type { Annotation } from "./types";
import { coordinatePoints } from "./annotationGeometry";
import type { AnnotationEvidenceLinks } from "./annotationCaseReview";

export type AnnotationHistory = {
  past: Annotation[][];
  present: Annotation[];
  future: Annotation[][];
  limit: number;
  pastLinks: AnnotationEvidenceLinks[];
  presentLinks: AnnotationEvidenceLinks;
  futureLinks: AnnotationEvidenceLinks[];
};

export type PixelSpacing = { row_mm: number; column_mm: number };
export type AnnotationMeasurement = { kind: "length" | "area" | "angle"; value: number; unit: "px" | "px²" | "mm" | "mm²" | "°" };

const clone = (annotations: Annotation[]) => structuredClone(annotations);

export function createAnnotationHistory(annotations: Annotation[], limit = 50, links: AnnotationEvidenceLinks = {}): AnnotationHistory {
  return { past: [], present: clone(annotations), future: [], limit: Math.max(1, Math.min(200, limit)), pastLinks: [], presentLinks: structuredClone(links), futureLinks: [] };
}

export function commitAnnotationChange(history: AnnotationHistory, annotations: Annotation[], links = history.presentLinks): AnnotationHistory {
  return {
    ...history,
    past: [...history.past, clone(history.present)].slice(-history.limit),
    present: clone(annotations),
    future: [],
    pastLinks: [...history.pastLinks, structuredClone(history.presentLinks)].slice(-history.limit),
    presentLinks: structuredClone(links),
    futureLinks: [],
  };
}

export function undoAnnotationChange(history: AnnotationHistory): AnnotationHistory {
  if (!history.past.length) return history;
  return {
    ...history,
    past: history.past.slice(0, -1),
    present: clone(history.past[history.past.length - 1]),
    future: [clone(history.present), ...history.future].slice(0, history.limit),
    pastLinks: history.pastLinks.slice(0, -1),
    presentLinks: structuredClone(history.pastLinks[history.pastLinks.length - 1]),
    futureLinks: [structuredClone(history.presentLinks), ...history.futureLinks].slice(0, history.limit),
  };
}

export function redoAnnotationChange(history: AnnotationHistory): AnnotationHistory {
  if (!history.future.length) return history;
  return {
    ...history,
    past: [...history.past, clone(history.present)].slice(-history.limit),
    present: clone(history.future[0]),
    future: history.future.slice(1),
    pastLinks: [...history.pastLinks, structuredClone(history.presentLinks)].slice(-history.limit),
    presentLinks: structuredClone(history.futureLinks[0]),
    futureLinks: history.futureLinks.slice(1),
  };
}

function finiteSpacing(spacing?: PixelSpacing | null): PixelSpacing {
  return isCalibrated(spacing) ? spacing! : { row_mm: 1, column_mm: 1 };
}

function isCalibrated(spacing?: PixelSpacing | null): boolean {
  return Boolean(spacing && Number.isFinite(spacing.row_mm) && Number.isFinite(spacing.column_mm) && spacing.row_mm > 0 && spacing.column_mm > 0);
}

const rounded = (value: number) => Math.abs(value) < Number.MAX_VALUE / 100 ? Math.round(value * 100) / 100 : value;

export function measureAnnotation(annotation: Pick<Annotation, "coordinate">, spacing?: PixelSpacing | null): AnnotationMeasurement | null {
  const coordinate = annotation.coordinate;
  if (!coordinate) return null;
  const hasCalibration = isCalibrated(spacing);
  const calibrated = finiteSpacing(spacing);
  const points = coordinatePoints(coordinate);
  if (coordinate.type === "length" && points.length === 2) {
    const dx = (points[1][0] - points[0][0]) * calibrated.column_mm;
    const dy = (points[1][1] - points[0][1]) * calibrated.row_mm;
    const value = Math.hypot(dx, dy);
    return Number.isFinite(value) && value > 0 ? { kind: "length", value: rounded(value), unit: hasCalibration ? "mm" : "px" } : null;
  }
  if (coordinate.type === "ellipse" && coordinate.width > 0 && coordinate.height > 0) {
    const area = Math.PI * coordinate.width * calibrated.column_mm / 2 * coordinate.height * calibrated.row_mm / 2;
    return Number.isFinite(area) && area > 0 ? { kind: "area", value: rounded(area), unit: hasCalibration ? "mm²" : "px²" } : null;
  }
  if (coordinate.type === "angle" && points.length === 3) {
    const [a, vertex, b] = points;
    const va = [(a[0] - vertex[0]) * calibrated.column_mm, (a[1] - vertex[1]) * calibrated.row_mm];
    const vb = [(b[0] - vertex[0]) * calibrated.column_mm, (b[1] - vertex[1]) * calibrated.row_mm];
    const lengthA = Math.hypot(...va);
    const lengthB = Math.hypot(...vb);
    if (!Number.isFinite(lengthA) || !Number.isFinite(lengthB) || !lengthA || !lengthB) return null;
    const cosine = Math.max(-1, Math.min(1, (va[0] / lengthA) * (vb[0] / lengthB) + (va[1] / lengthA) * (vb[1] / lengthB)));
    return { kind: "angle", value: rounded(Math.acos(cosine) * 180 / Math.PI), unit: "°" };
  }
  return null;
}
