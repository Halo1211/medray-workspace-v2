import { describe, expect, it } from "vitest";
import { applyCaseAnnotations, captureAnnotationEvidence, restoreAnnotationEvidence } from "./annotationCaseReview";
import { commitAnnotationChange, createAnnotationHistory, redoAnnotationChange, undoAnnotationChange } from "./annotationWorkspace";
import type { AnalysisResult, Annotation, CaseRecord, ResultCard } from "./types";

const card = (refs: string[]): ResultCard => ({ id: "same-card", finding: "synthetic", status: "uncertain", candidate_diagnosis: "", confidence: 1, evidence: [], annotation_refs: refs, source: "test", uncertainty_reason: "", next_safe_action: "review", review_status: "unreviewed", reviewer_note: "", validation_status: "", model_trace_refs: [] });
const annotation = (id: string, image: string): Annotation => ({ id, label: id, confidence: 1, source: "manual user annotation", explanation: "synthetic", visible: true, source_image_id: image, coordinate: { type: "point", x: 1, y: 2, width: 0, height: 0 } });
const analysis = (annotations: Annotation[], refs: string[]): AnalysisResult => ({ case_id: "synthetic", input: {}, image_quality: { score: 1, exposure: "", positioning: "", limitations: [] }, findings: [], annotations, result_cards: [card(refs)], differential_diagnosis: [], systematic_reading: {}, report: { indication: "", technique: "", comparison: "", findings: "", impression: "", recommendation: "", watermark: "test" }, model_trace: [], warnings: [] });
const fixture = (): CaseRecord => {
  const a = annotation("a", "image-a"), b = annotation("b", "image-b");
  const analyses = { "image-a": analysis([a], ["a"]), "image-b": analysis([b], ["b"]) };
  return { case_id: "synthetic", title: "synthetic", metadata: {}, chat_history: [], created_at: "", updated_at: "", active_image_id: "image-b", annotations: [a, b], analyses_by_image: analyses, analysis: analyses["image-b"], images: ["image-a", "image-b"].map((id, index) => ({ image_id: id, index, filename: `${id}.png`, metadata: {} })) };
};

describe("case annotation evidence", () => {
  it("restores links in an inactive image even when both images reuse a card ID", () => {
    const record = fixture();
    const after = captureAnnotationEvidence(record);
    const before = structuredClone(after);
    before["image-a"]["same-card"] = [];
    record.analyses_by_image!["image-a"].result_cards[0].annotation_refs = [];
    const restored = restoreAnnotationEvidence(record, before, after);
    expect(restored.analyses_by_image!["image-a"].result_cards[0].annotation_refs).toEqual(["a"]);
    expect(restored.analysis!.result_cards[0].annotation_refs).toEqual(["b"]);
    expect(record.analyses_by_image!["image-a"].result_cards[0].annotation_refs).toEqual([]);
  });

  it("preserves later reviewer decisions, notes, and unrelated references", () => {
    const record = fixture();
    const before = captureAnnotationEvidence(record), after = structuredClone(before);
    after["image-b"]["same-card"] = [];
    record.analysis!.result_cards[0] = { ...record.analysis!.result_cards[0], review_status: "accepted", reviewer_note: "Latest review", annotation_refs: ["b", "added-later"] };
    const restored = restoreAnnotationEvidence(record, before, after);
    expect(restored.analysis!.result_cards[0]).toMatchObject({ review_status: "accepted", reviewer_note: "Latest review", annotation_refs: ["added-later"] });
  });

  it("updates annotation caches for each image without mixing source identities", () => {
    const record = fixture();
    const changed = [{ ...record.annotations[0], label: "edited a" }, record.annotations[1]];
    const updated = applyCaseAnnotations(record, changed);
    expect(updated.analyses_by_image!["image-a"].annotations.map(item => item.label)).toEqual(["edited a"]);
    expect(updated.analysis!.annotations.map(item => item.id)).toEqual(["b"]);
    expect(record.analyses_by_image!["image-a"].annotations[0].label).toBe("a");
  });

  it("bounds and clones evidence history alongside annotation history", () => {
    const record = fixture();
    const original = captureAnnotationEvidence(record);
    let history = createAnnotationHistory(record.annotations, 1, original);
    const changed = structuredClone(original); changed["image-a"]["same-card"] = [];
    history = commitAnnotationChange(history, record.annotations, changed);
    changed["image-a"]["same-card"].push("mutated later");
    expect(history.presentLinks["image-a"]["same-card"]).toEqual([]);
    expect(undoAnnotationChange(history).presentLinks).toEqual(original);
    expect(redoAnnotationChange(undoAnnotationChange(history)).presentLinks).toEqual(history.presentLinks);
    history = commitAnnotationChange(history, record.annotations, original);
    expect(history.pastLinks).toHaveLength(1);
    expect(history.futureLinks).toEqual([]);
  });

  it("tolerates malformed legacy analysis and card collections", () => {
    const record = fixture();
    record.analysis!.result_cards = "legacy-invalid" as unknown as ResultCard[];
    record.analyses_by_image!["image-a"] = null as unknown as AnalysisResult;
    expect(captureAnnotationEvidence(record)).toEqual({ "image-b": {} });
    expect(restoreAnnotationEvidence(record, {}, {}).analysis!.result_cards).toEqual([]);
  });

  it("handles card IDs which overlap Object prototype keys", () => {
    const record = fixture();
    record.analysis!.result_cards[0].id = "constructor";
    const after = captureAnnotationEvidence(record);
    expect(restoreAnnotationEvidence(record, { "image-b": {} }, after).analysis!.result_cards[0].annotation_refs).toEqual(["b"]);
  });
});
