import { describe, expect, it } from "vitest";
import { coordinatePoints, hasPointCoordinate, hasPolygonCoordinate, isValidPolygonPoints, polygonArea, polygonBounds } from "./annotationGeometry";
import type { Annotation } from "./types";

function shape(type: string, coordinate: Annotation["coordinate"]): Annotation {
  return { id: type, label: type, confidence: 1, source: "manual user annotation", coordinate, explanation: "test", visible: true };
}

describe("annotation geometry", () => {
  it("normalizes finite polygon vertices and computes bounds and area", () => {
    const points = coordinatePoints({ type: "polygon", x: 0, y: 0, width: 0, height: 0, points: [[1, 1], [9, 1], [5, 7]] });
    expect(polygonBounds(points)).toEqual({ x: 1, y: 1, width: 8, height: 6 });
    expect(polygonArea(points)).toBe(24);
  });

  it("rejects collinear polygons while accepting manual points", () => {
    expect(hasPolygonCoordinate(shape("polygon", { type: "polygon", x: 0, y: 0, width: 2, height: 2, points: [[0, 0], [1, 1], [2, 2]] }))).toBe(false);
    expect(hasPointCoordinate(shape("point", { type: "point", x: 4, y: 5, width: 0, height: 0, points: [[4, 5]] }))).toBe(true);
    expect(isValidPolygonPoints([[0, 0], [1, 1], [2, 2]])).toBe(false);
    expect(isValidPolygonPoints([[0, 0], [5, 0], [0, 5]])).toBe(true);
  });

  it("rejects oversized polygons before expensive geometry work", () => {
    const points = Array.from({ length: 4097 }, (_, index) => [index, index % 2] as [number, number]);
    expect(coordinatePoints({ type: "polygon", x: 0, y: 0, width: 0, height: 0, points })).toEqual([]);
    expect(isValidPolygonPoints(points)).toBe(false);
  });
});
