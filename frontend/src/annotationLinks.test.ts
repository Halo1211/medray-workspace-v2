import { describe, expect, it } from "vitest";
import { annotationsForImage, buildGroundedReviewStatements, linkAnnotationEvidence, preferredAnnotations } from "./annotationLinks";
import type { Annotation, ResultCard } from "./types";

const annotation: Annotation = {
  id: "annotation-1",
  label: "manual finding",
  confidence: 1,
  source: "manual user annotation",
  coordinate: { type: "bbox", x: 1, y: 2, width: 3, height: 4 },
  explanation: "test",
  visible: true,
  linked_result_card_ids: ["card-old"],
  linked_report_statement_id: "report:findings"
};

function card(id: string, refs: string[]): ResultCard {
  return {
    id,
    finding: id,
    status: "uncertain",
    candidate_diagnosis: "",
    confidence: 0.5,
    evidence: [],
    annotation_refs: refs,
    source: "test",
    uncertainty_reason: "",
    next_safe_action: "review",
    review_status: "unreviewed",
    reviewer_note: "",
    validation_status: "not_validated",
    model_trace_refs: []
  };
}

describe("grounded annotation links", () => {
  it("falls back to analysis annotations when case annotations are empty", () => {
    const analysisAnnotation = { ...annotation, id: "analysis-annotation" };

    expect(preferredAnnotations([], [analysisAnnotation])).toEqual([analysisAnnotation]);
    expect(preferredAnnotations([annotation], [analysisAnnotation])).toEqual([annotation]);
  });

  it("keeps annotations aligned to the selected study image", () => {
    const first = { ...annotation, id: "first", source_image_id: "image-a" };
    const second = { ...annotation, id: "second", source_image_id: "image-b" };
    const legacy = { ...annotation, id: "legacy", source_image_id: "primary" };

    expect(annotationsForImage([first, second, legacy], "image-a", true).map(item => item.id)).toEqual(["first", "legacy"]);
    expect(annotationsForImage([first, second, legacy], "image-b", false).map(item => item.id)).toEqual(["second"]);
  });

  it("ignores malformed annotation collections instead of returning non-arrays", () => {
    const analysisAnnotation = { ...annotation, id: "analysis-annotation" };

    expect(preferredAnnotations("legacy-bad-value" as unknown as Annotation[], [analysisAnnotation])).toEqual([analysisAnnotation]);
    expect(preferredAnnotations("legacy-bad-value" as unknown as Annotation[], null as unknown as Annotation[])).toEqual([]);
  });

  it("moves an annotation reference to exactly one result card", () => {
    const result = linkAnnotationEvidence(
      [annotation],
      [card("card-old", ["annotation-1"]), card("card-new", [])],
      "annotation-1",
      "card-new",
      "report:impression",
      { action: "edited", timestamp: "2026-07-11T00:00:00Z", actor: "reviewer", note: "linked" }
    );

    expect(result.annotations[0].linked_result_card_ids).toEqual(["card-new"]);
    expect(result.annotations[0].linked_report_statement_id).toBe("report:impression");
    expect(result.cards[0].annotation_refs).toEqual([]);
    expect(result.cards[1].annotation_refs).toEqual(["annotation-1"]);
    expect(result.annotations[0].revision_history).toHaveLength(1);
  });

  it("tolerates malformed link inputs", () => {
    const linked = linkAnnotationEvidence(
      "bad-annotations" as unknown as Annotation[],
      "bad-cards" as unknown as ResultCard[],
      "annotation-1",
      "card-new",
      "report:findings",
      { action: "edited", timestamp: "2026-07-11T00:00:00Z", actor: "reviewer", note: "linked" }
    );
    const statements = buildGroundedReviewStatements(
      "bad-cards" as unknown as ResultCard[],
      "bad-annotations" as unknown as Annotation[],
      "id"
    );

    expect(linked.annotations).toEqual([]);
    expect(linked.cards).toEqual([]);
    expect(statements[0].id).toBe("grounded:none");
  });

  it("handles legacy result cards without annotation_refs", () => {
    const legacyCard = { ...card("legacy-card", []) };
    delete (legacyCard as Partial<ResultCard>).annotation_refs;

    const linked = linkAnnotationEvidence(
      [annotation],
      [legacyCard as ResultCard],
      "annotation-1",
      "legacy-card",
      "report:findings",
      { action: "edited", timestamp: "2026-07-11T00:00:00Z", actor: "reviewer", note: "linked" }
    );
    const statements = buildGroundedReviewStatements([{ ...(legacyCard as ResultCard), review_status: "accepted" }], [annotation], "id");

    expect(linked.cards[0].annotation_refs).toEqual(["annotation-1"]);
    expect(statements[0].text).toContain("belum ada anotasi tertaut");
  });

  it("handles legacy non-array annotation reference fields", () => {
    const legacyCard = { ...card("legacy-card", []) };
    (legacyCard as unknown as { annotation_refs: unknown }).annotation_refs = "annotation-1";
    const legacyAnnotation = { ...annotation, review_status: "accepted" as const };
    (legacyAnnotation as unknown as { linked_result_card_ids: unknown }).linked_result_card_ids = "card-old";

    const linked = linkAnnotationEvidence(
      [annotation],
      [legacyCard as ResultCard],
      "annotation-1",
      "legacy-card",
      "report:findings",
      { action: "edited", timestamp: "2026-07-11T00:00:00Z", actor: "reviewer", note: "linked" }
    );
    const statements = buildGroundedReviewStatements([], [legacyAnnotation as Annotation], "id");

    expect(linked.cards[0].annotation_refs).toEqual(["annotation-1"]);
    expect(statements[0].id).toBe("grounded:annotation-1");
  });

  it("builds grounded report statements only from reviewed items", () => {
    const acceptedAnnotation: Annotation = {
      ...annotation,
      id: "annotation-reviewed",
      label: "distal radius candidate box",
      review_status: "accepted",
      linked_result_card_ids: ["card-accepted"],
      coordinate: { type: "grounding_box", x: 10, y: 20, width: 30, height: 40 }
    };
    const accepted = {
      ...card("card-accepted", ["annotation-reviewed"]),
      finding: "candidate_fracture_localization",
      candidate_diagnosis: "AI candidate diagnosis: distal radius fracture cue",
      review_status: "accepted" as const,
      reviewer_note: "Matches subtle cortical step-off."
    };
    const rejected = { ...card("card-rejected", []), finding: "unsupported_elbow_finding", review_status: "rejected" as const };
    const unreviewed = { ...card("card-unreviewed", []), finding: "unreviewed_soft_tissue_swelling" };

    const statements = buildGroundedReviewStatements([accepted, rejected, unreviewed], [acceptedAnnotation], "id");
    const text = statements.map(statement => statement.text).join("\n");

    expect(text).toContain("candidate_fracture_localization");
    expect(text).toContain("distal radius candidate box");
    expect(text).not.toContain("unsupported_elbow_finding");
    expect(text).not.toContain("unreviewed_soft_tissue_swelling");
    expect(text).toContain("1 rejected dan 1 result card belum direview");
  });

  it("handles reviewed annotations with missing coordinates", () => {
    const coordinateMissing = {
      ...annotation,
      id: "annotation-no-coordinate",
      review_status: "accepted" as const,
      linked_result_card_ids: [],
    };
    delete (coordinateMissing as Partial<Annotation>).coordinate;

    const statements = buildGroundedReviewStatements([], [coordinateMissing as Annotation], "id");

    expect(statements[0].text).toContain("koordinat tidak tersedia");
  });

  it("does not show an empty-state statement when there are unpromoted result cards", () => {
    const rejected = { ...card("card-rejected", []), review_status: "rejected" as const };
    const statements = buildGroundedReviewStatements([rejected], [], "id");

    expect(statements).toHaveLength(1);
    expect(statements[0].id).toBe("grounded:not-promoted");
    expect(statements[0].text).not.toContain("Belum ada result card");
  });
});
