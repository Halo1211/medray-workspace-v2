import type { Annotation, ResultCard } from "./types";

const PROMOTED_REVIEW_STATUSES = new Set(["accepted", "uncertain", "needs_follow_up"]);

export type GroundedReviewStatement = {
  id: string;
  text: string;
  annotationIds: string[];
  resultCardId?: string;
};

export function preferredAnnotations(caseAnnotations?: Annotation[], analysisAnnotations?: Annotation[]) {
  const reviewed = Array.isArray(caseAnnotations) ? caseAnnotations : [];
  const modelOutput = Array.isArray(analysisAnnotations) ? analysisAnnotations : [];
  if (reviewed.length > 0) return reviewed;
  if (modelOutput.length > 0) return modelOutput;
  return reviewed;
}

export function annotationsForImage(annotations: Annotation[], imageId: string, isFirstImage = false) {
  return safeList<Annotation>(annotations).filter(annotation => {
    const sourceId = String(annotation.source_image_id || "");
    return sourceId === imageId || (isFirstImage && ["", "primary"].includes(sourceId));
  });
}

function safeList<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(item => String(item)).filter(Boolean) : [];
}

export function linkAnnotationEvidence(
  annotations: Annotation[],
  cards: ResultCard[],
  annotationId: string,
  resultCardId: string,
  reportStatementId: string,
  revision: { action: string; timestamp: string; actor: string; note: string }
) {
  const annotationList = safeList<Annotation>(annotations);
  const cardList = safeList<ResultCard>(cards);
  const nextAnnotations = annotationList.map(annotation => annotation.id === annotationId ? {
    ...annotation,
    linked_result_card_ids: resultCardId ? [resultCardId] : [],
    linked_report_statement_id: reportStatementId,
    revision_history: [...(annotation.revision_history || []), revision]
  } : annotation);

  const nextCards = cardList.map(card => {
    const refs = stringList(card.annotation_refs).filter(ref => ref !== annotationId);
    return { ...card, annotation_refs: card.id === resultCardId ? [...refs, annotationId] : refs };
  });

  return { annotations: nextAnnotations, cards: nextCards };
}

function scoreText(card: ResultCard) {
  const score = card.probability ?? card.confidence;
  return typeof score === "number" ? score.toFixed(2) : "n/a";
}

function annotationLocation(annotation: Annotation, language: "id" | "en") {
  const coordinate = annotation.coordinate;
  if (!coordinate) return language === "en" ? "coordinate unavailable" : "koordinat tidak tersedia";
  if (coordinate.type === "point") {
    return `point x=${Number.isFinite(coordinate.x) ? coordinate.x.toFixed(0) : "n/a"}, y=${Number.isFinite(coordinate.y) ? coordinate.y.toFixed(0) : "n/a"}`;
  }
  if (coordinate.type === "polygon") return `polygon (${coordinatePointsForText(coordinate).length} vertices)`;
  if (!["bbox", "grounding_box"].includes(coordinate.type)) return coordinate.type || "unknown";
  const label = language === "en" ? "box" : "kotak";
  const x = Number.isFinite(coordinate.x) ? coordinate.x.toFixed(0) : "n/a";
  const y = Number.isFinite(coordinate.y) ? coordinate.y.toFixed(0) : "n/a";
  const width = Number.isFinite(coordinate.width) ? coordinate.width.toFixed(0) : "n/a";
  const height = Number.isFinite(coordinate.height) ? coordinate.height.toFixed(0) : "n/a";
  return `${label} x=${x}, y=${y}, w=${width}, h=${height}`;
}

function coordinatePointsForText(coordinate: Annotation["coordinate"]) {
  return Array.isArray(coordinate.points) ? coordinate.points.filter(item => Array.isArray(item) && item.length === 2) : [];
}

export function buildGroundedReviewStatements(cards: ResultCard[], annotations: Annotation[], language: "id" | "en"): GroundedReviewStatement[] {
  const cardList = safeList<ResultCard>(cards);
  const annotationList = safeList<Annotation>(annotations);
  const annotationsById = new Map(annotationList.map(annotation => [annotation.id, annotation]));
  const statements: GroundedReviewStatement[] = [];

  cardList
    .filter(card => PROMOTED_REVIEW_STATUSES.has(card.review_status || "unreviewed"))
    .forEach(card => {
      const reviewedLinked = stringList(card.annotation_refs)
        .map(ref => annotationsById.get(ref))
        .filter((annotation): annotation is Annotation => Boolean(annotation && PROMOTED_REVIEW_STATUSES.has(annotation.review_status || "unreviewed")));
      const evidence = reviewedLinked.length
        ? reviewedLinked.map(annotation => `${annotation.label}: ${(annotation.review_status || "unreviewed").replaceAll("_", " ")}, ${annotationLocation(annotation, language)}`).join("; ")
        : language === "en" ? "no reviewed linked annotation" : "belum ada anotasi tertaut yang sudah direview";
      const note = card.reviewer_note ? (language === "en" ? ` Reviewer note: ${card.reviewer_note}` : ` Catatan reviewer: ${card.reviewer_note}`) : "";
      statements.push({
        id: `grounded:${card.id}`,
        resultCardId: card.id,
        annotationIds: reviewedLinked.map(annotation => annotation.id),
        text: language === "en"
          ? `Reviewed ${(card.review_status || "unreviewed").replaceAll("_", " ")} candidate: ${card.finding} -> ${card.candidate_diagnosis || "AI candidate diagnosis"} (model status ${card.status}, score ${scoreText(card)}). Evidence: ${evidence}.${note}`
          : `Kandidat sudah direview (${(card.review_status || "unreviewed").replaceAll("_", " ")}): ${card.finding} -> ${card.candidate_diagnosis || "kandidat diagnosis AI"} (status model ${card.status}, skor ${scoreText(card)}). Bukti: ${evidence}.${note}`
      });
    });

  annotationList
    .filter(annotation => PROMOTED_REVIEW_STATUSES.has(annotation.review_status || "unreviewed") && !stringList(annotation.linked_result_card_ids).length)
    .forEach(annotation => {
      const note = annotation.reviewer_note ? (language === "en" ? ` Reviewer note: ${annotation.reviewer_note}` : ` Catatan reviewer: ${annotation.reviewer_note}`) : "";
      statements.push({
        id: `grounded:${annotation.id}`,
        annotationIds: [annotation.id],
        text: language === "en"
          ? `Standalone reviewed annotation (${(annotation.review_status || "unreviewed").replaceAll("_", " ")}): ${annotation.label} at ${annotationLocation(annotation, language)}.${note}`
          : `Anotasi mandiri sudah direview (${(annotation.review_status || "unreviewed").replaceAll("_", " ")}): ${annotation.label} pada ${annotationLocation(annotation, language)}.${note}`
      });
    });

  const rejected = cardList.filter(card => card.review_status === "rejected").length;
  const unreviewed = cardList.filter(card => (card.review_status || "unreviewed") === "unreviewed").length;
  if (rejected || unreviewed) {
    statements.push({
      id: "grounded:not-promoted",
      annotationIds: [],
      text: language === "en"
        ? `Not promoted into report findings: ${rejected} rejected and ${unreviewed} unreviewed result card(s).`
        : `Tidak dipromosikan menjadi temuan laporan: ${rejected} rejected dan ${unreviewed} result card belum direview.`
    });
  }

  if (!statements.length) {
    statements.push({
      id: "grounded:none",
      annotationIds: [],
      text: language === "en"
        ? "No reviewed result card or standalone reviewed annotation has been promoted into a grounded report statement yet."
        : "Belum ada result card atau anotasi mandiri yang sudah direview untuk dipromosikan menjadi statement laporan grounded."
    });
  }

  return statements;
}
