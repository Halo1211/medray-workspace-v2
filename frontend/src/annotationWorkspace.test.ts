import { describe, expect, it } from "vitest";
import { commitAnnotationChange, createAnnotationHistory, measureAnnotation, redoAnnotationChange, undoAnnotationChange } from "./annotationWorkspace";
import type { Annotation } from "./types";

const annotation = (id: string, type = "bbox"): Annotation => ({
  id, label: id, confidence: 1, source: "manual user annotation", visible: true, explanation: "test",
  coordinate: { type, x: 10, y: 10, width: 20, height: 10, points: type === "length" ? [[0, 0], [30, 40]] : [] },
});

describe("annotation workspace", () => {
  it("supports bounded undo and redo without mutating snapshots", () => {
    const initial = [annotation("a")];
    const committed = commitAnnotationChange(createAnnotationHistory(initial), [annotation("a"), annotation("b")]);
    const undone = undoAnnotationChange(committed);
    expect(undone.present.map(item => item.id)).toEqual(["a"]);
    expect(committed.present.map(item => item.id)).toEqual(["a", "b"]);
    expect(redoAnnotationChange(undone).present.map(item => item.id)).toEqual(["a", "b"]);
  });

  it("reports calibrated length and ellipse area from DICOM pixel spacing", () => {
    expect(measureAnnotation(annotation("line", "length"), { row_mm: 0.5, column_mm: 0.25 })).toEqual({ kind: "length", value: 21.36, unit: "mm" });
    expect(measureAnnotation(annotation("roi", "ellipse"), { row_mm: 0.5, column_mm: 0.25 })).toEqual({ kind: "area", value: 19.63, unit: "mm²" });
  });

  it("uses pixel units when an image has no physical calibration", () => {
    expect(measureAnnotation(annotation("line", "length"))).toEqual({ kind: "length", value: 50, unit: "px" });
    expect(measureAnnotation(annotation("roi", "ellipse"))).toEqual({ kind: "area", value: 157.08, unit: "px²" });
  });
});
