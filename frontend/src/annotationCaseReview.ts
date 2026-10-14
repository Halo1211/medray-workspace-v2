import { annotationMatchesStudyImage } from "./annotationLinks";
import type { AnalysisResult, Annotation, CaseRecord, ResultCard } from "./types";

/** Card IDs may repeat between images, so evidence history is scoped by image. */
export type AnnotationEvidenceLinks = Record<string, Record<string, string[]>>;

const refs = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
const activeId = (record: CaseRecord) => record.active_image_id || (Array.isArray(record.images) ? record.images[0]?.image_id : "") || "primary";
const cards = (analysis: AnalysisResult): ResultCard[] => Array.isArray(analysis.result_cards) ? analysis.result_cards.filter(card => card && typeof card.id === "string") : [];

function analysesForCase(record: CaseRecord): Record<string, AnalysisResult> {
  const analyses: Record<string, AnalysisResult> = Object.create(null);
  for (const [id, analysis] of Object.entries(record.analyses_by_image || {})) {
    if (analysis && typeof analysis === "object" && !Array.isArray(analysis)) analyses[id] = analysis;
  }
  if (record.analysis && typeof record.analysis === "object" && !Array.isArray(record.analysis)) analyses[activeId(record)] = record.analysis;
  return analyses;
}

export function captureAnnotationEvidence(record: CaseRecord): AnnotationEvidenceLinks {
  return Object.fromEntries(Object.entries(analysesForCase(record)).map(([imageId, analysis]) => [
    imageId, Object.fromEntries(cards(analysis).map(card => [card.id, [...refs(card.annotation_refs)]])),
  ]));
}

/** Update every cached image view, including views currently outside the viewer. */
export function applyCaseAnnotations(record: CaseRecord, annotations: Annotation[], activeAnalysis = record.analysis): CaseRecord {
  const images = Array.isArray(record.images) ? record.images : [];
  const analyses = analysesForCase(record);
  const imageId = activeId(record);
  if (activeAnalysis) analyses[imageId] = activeAnalysis;
  for (const [id, analysis] of Object.entries(analyses)) {
    const index = images.findIndex(image => image.image_id === id);
    const imageAnnotations = images.length
      ? annotations.filter(annotation => index >= 0 && annotationMatchesStudyImage(annotation, images[index], index === 0, images))
      : annotations;
    analyses[id] = { ...analysis, annotations: imageAnnotations };
  }
  const analysis = analyses[imageId];
  return { ...record, annotations, analyses_by_image: analyses, ...(analysis ? { analysis, report: analysis.report } : {}) };
}

/** Restore only changed references; later finding reviews and notes remain intact. */
export function restoreAnnotationEvidence(record: CaseRecord, before: AnnotationEvidenceLinks, after: AnnotationEvidenceLinks): CaseRecord {
  const analyses = analysesForCase(record);
  for (const [imageId, analysis] of Object.entries(analyses)) {
    analyses[imageId] = { ...analysis, result_cards: cards(analysis).map(card => {
      const previous = refs(before[imageId]?.[card.id]);
      const target = refs(after[imageId]?.[card.id]);
      const changed = new Set([...previous.filter(id => !target.includes(id)), ...target.filter(id => !previous.includes(id))]);
      if (!changed.size) return card;
      const targetIds = new Set(target);
      const current = refs(card.annotation_refs);
      const currentIds = new Set(current);
      return { ...card, annotation_refs: [...current.filter(id => !changed.has(id) || targetIds.has(id)), ...target.filter(id => changed.has(id) && !currentIds.has(id))] };
    }) };
  }
  const analysis = analyses[activeId(record)];
  return { ...record, analyses_by_image: analyses, ...(analysis ? { analysis, report: analysis.report } : {}) };
}
