import type { Annotation } from "./types";

export const MAX_POLYGON_VERTICES = 4096;

export function coordinatePoints(coordinate?: Annotation["coordinate"] | null): [number, number][] {
  const points = coordinate?.points;
  if (!Array.isArray(points) || points.length > MAX_POLYGON_VERTICES) return [];
  const finiteNumber = (value: unknown) => (typeof value === "number" || (typeof value === "string" && value.trim() !== "")) && Number.isFinite(Number(value));
  if (!points.every(item => Array.isArray(item) && item.length === 2 && finiteNumber(item[0]) && finiteNumber(item[1]))) return [];
  return points.map(item => [Number(item[0]), Number(item[1])]);
}

export function polygonBounds(points: [number, number][]) {
  if (!points.length) return { x: 0, y: 0, width: 0, height: 0 };
  const xs = points.map(item => item[0]);
  const ys = points.map(item => item[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
}

export function polygonArea(points: [number, number][]) {
  if (points.length > MAX_POLYGON_VERTICES) return 0;
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0) / 2);
}

export function isValidPolygonPoints(points: [number, number][], minimumArea = 4) {
  const area = polygonArea(points);
  return points.length >= 3 && points.length <= MAX_POLYGON_VERTICES && Number.isFinite(area) && area >= minimumArea;
}

export function hasPointCoordinate(annotation: Annotation) {
  return annotation.coordinate?.type === "point" && Number.isFinite(annotation.coordinate.x) && Number.isFinite(annotation.coordinate.y);
}

export function hasPolygonCoordinate(annotation: Annotation) {
  const points = coordinatePoints(annotation.coordinate);
  return annotation.coordinate?.type === "polygon" && isValidPolygonPoints(points, Number.EPSILON);
}

export function isValidAnglePoints(points: [number, number][]) {
  if (points.length !== 3 || !points.every(point => point.every(Number.isFinite))) return false;
  const [a, vertex, b] = points;
  const lengths = [Math.hypot(a[0] - vertex[0], a[1] - vertex[1]), Math.hypot(b[0] - vertex[0], b[1] - vertex[1])];
  return lengths.every(length => Number.isFinite(length) && length > 0);
}

export function hasAngleCoordinate(annotation: Annotation) {
  return annotation.coordinate?.type === "angle" && isValidAnglePoints(coordinatePoints(annotation.coordinate));
}
