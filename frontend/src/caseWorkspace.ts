import type { Annotation, AnalysisResult, CaseRecord } from "./types";

export type CaseMetadataDraft = {
  localRecordId: string;
  patientId: string;
  accessionNumber: string;
  studyDescription: string;
  clinicalIndication: string;
  notes: string;
};

export type FreshCaseWorkspaceState = {
  activeCase: CaseRecord | null;
  analysis: AnalysisResult | null;
  preview: string;
};

const METADATA_FIELDS: Record<keyof CaseMetadataDraft, string> = {
  localRecordId: "LocalRecordID",
  patientId: "PatientID",
  accessionNumber: "AccessionNumber",
  studyDescription: "StudyDescription",
  clinicalIndication: "ClinicalIndication",
  notes: "CaseNotes",
};

export const EMPTY_CASE_METADATA: CaseMetadataDraft = {
  localRecordId: "",
  patientId: "",
  accessionNumber: "",
  studyDescription: "",
  clinicalIndication: "",
  notes: "",
};

export function createFreshCaseWorkspaceState(): FreshCaseWorkspaceState {
  return { activeCase: null, analysis: null, preview: "" };
}

export function caseMetadataDraft(metadata: Record<string, unknown> = {}): CaseMetadataDraft {
  return Object.fromEntries(
    Object.entries(METADATA_FIELDS).map(([draftKey, metadataKey]) => [draftKey, String(metadata[metadataKey] ?? "")]),
  ) as CaseMetadataDraft;
}

export function mergeCaseMetadata(metadata: Record<string, unknown> = {}, draft: CaseMetadataDraft): Record<string, unknown> {
  const next = { ...metadata };
  for (const [draftKey, metadataKey] of Object.entries(METADATA_FIELDS) as [keyof CaseMetadataDraft, string][]) {
    const value = draft[draftKey].trim();
    if (value) next[metadataKey] = value;
    else delete next[metadataKey];
  }
  return next;
}

export type AnnotationOrigin = "ai" | "reviewer" | "guidance";

export function annotationOrigin(annotation: Pick<Annotation, "source">): AnnotationOrigin {
  const source = String(annotation.source || "").toLowerCase();
  if (source.includes("manual") || source.includes("reviewer")) return "reviewer";
  if (source.includes("fallback") || source.includes("heuristic") || source.includes("guide")) return "guidance";
  return "ai";
}

export function annotationConfidencePercent(confidence: number): number {
  const bounded = Math.max(0, Math.min(1, Number.isFinite(confidence) ? confidence : 0));
  return Math.round(bounded * 100);
}

export type AnnotationWorkspaceFilter = {
  origin: AnnotationOrigin | "all";
  reviewStatus: NonNullable<Annotation["review_status"]> | "all";
  minimumAiConfidence: number;
};

export function filterWorkspaceAnnotations(annotations: Annotation[], filter: AnnotationWorkspaceFilter): Annotation[] {
  const minimum = Math.max(0, Math.min(100, filter.minimumAiConfidence));
  return annotations.filter(annotation => {
    const origin = annotationOrigin(annotation);
    if (filter.origin !== "all" && origin !== filter.origin) return false;
    if (filter.reviewStatus !== "all" && (annotation.review_status || "unreviewed") !== filter.reviewStatus) return false;
    return origin !== "ai" || annotationConfidencePercent(annotation.confidence) >= minimum;
  });
}

export function buildValidationRerunPrompt(annotations: Annotation[], language: "id" | "en"): string {
  const reviewed = annotations
    .filter(annotation => annotation.review_status && annotation.review_status !== "unreviewed")
    .slice(0, 30)
    .map(annotation => ({
      label: String(annotation.label || "").slice(0, 160),
      decision: annotation.review_status,
      note: String(annotation.reviewer_note || "").slice(0, 300),
      geometry: annotation.coordinate?.type || "unknown",
    }));
  const heading = language === "en"
    ? "Reviewer validation feedback is provided below. Re-review the source image independently, compare it with these corrections, and return new candidate findings and annotations. Do not treat reviewer feedback as ground truth; explain uncertainty and do not claim a diagnosis."
    : "Umpan balik validasi reviewer tersedia di bawah. Tinjau ulang gambar sumber secara independen, bandingkan dengan koreksi ini, lalu berikan kandidat temuan dan anotasi baru. Jangan anggap umpan balik reviewer sebagai ground truth; jelaskan ketidakpastian dan jangan mengklaim diagnosis.";
  return `${heading}\n\nReviewer validation feedback:\n${JSON.stringify(reviewed)}`.slice(0, 3999);
}
