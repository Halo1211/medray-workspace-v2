import type { Annotation } from "./types";

export const MAX_POLYGON_VERTICES = 4096;

export function coordinatePoints(coordinate?: Annotation["coordinate"] | null): [number, number][] {
  return Array.isArray(coordinate?.points)
    ? coordinate.points.length <= MAX_POLYGON_VERTICES ? coordinate.points
      .filter(item => Array.isArray(item) && item.length === 2 && Number.isFinite(Number(item[0])) && Number.isFinite(Number(item[1])))
      .map(item => [Number(item[0]), Number(item[1])]) : []
    : [];
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
  return points.length >= 3 && points.length <= MAX_POLYGON_VERTICES && polygonArea(points) >= minimumArea;
}

export function hasPointCoordinate(annotation: Annotation) {
  return annotation.coordinate?.type === "point" && Number.isFinite(annotation.coordinate.x) && Number.isFinite(annotation.coordinate.y);
}

export function hasPolygonCoordinate(annotation: Annotation) {
  const points = coordinatePoints(annotation.coordinate);
  return annotation.coordinate?.type === "polygon" && isValidPolygonPoints(points, Number.EPSILON);
}
