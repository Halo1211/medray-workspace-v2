import { describe, expect, it } from "vitest";
import {
  annotationConfidencePercent,
  annotationOrigin,
  buildValidationRerunPrompt,
  caseMetadataDraft,
  createFreshCaseWorkspaceState,
  filterWorkspaceAnnotations,
  mergeCaseMetadata,
} from "./caseWorkspace";
import type { Annotation } from "./types";

const annotation = (patch: Partial<Annotation> = {}): Annotation => ({
  id: "ann-1",
  label: "candidate opacity",
  confidence: 0.873,
  source: "model-returned coordinate",
  coordinate: { type: "bbox", x: 10, y: 20, width: 30, height: 40 },
  explanation: "candidate",
  visible: true,
  review_status: "accepted",
  reviewer_note: "box narrowed to the visible margin",
  ...patch,
});

describe("case workspace", () => {
  it("creates a genuinely empty workspace for a new case", () => {
    expect(createFreshCaseWorkspaceState()).toEqual({
      activeCase: null,
      analysis: null,
      preview: "",
    });
  });

  it("merges editable case details without discarding imported DICOM metadata", () => {
    const metadata = mergeCaseMetadata(
      { SOPInstanceUID: "1.2.3", Rows: 1024 },
      {
        localRecordId: "NPM-23001",
        patientId: "PX-104",
        accessionNumber: "ACC-778",
        studyDescription: "Chest PA",
        clinicalIndication: "Persistent cough",
        notes: "Teaching set",
      },
    );

    expect(metadata).toMatchObject({
      SOPInstanceUID: "1.2.3",
      Rows: 1024,
      LocalRecordID: "NPM-23001",
      PatientID: "PX-104",
      AccessionNumber: "ACC-778",
      StudyDescription: "Chest PA",
      ClinicalIndication: "Persistent cough",
      CaseNotes: "Teaching set",
    });
    expect(caseMetadataDraft(metadata).localRecordId).toBe("NPM-23001");
  });

  it("makes AI provenance and bounded confidence explicit", () => {
    expect(annotationOrigin(annotation())).toBe("ai");
    expect(annotationOrigin(annotation({ source: "manual user annotation" }))).toBe("reviewer");
    expect(annotationOrigin(annotation({ source: "fallback heuristic" }))).toBe("guidance");
    expect(annotationConfidencePercent(0.873)).toBe(87);
    expect(annotationConfidencePercent(2)).toBe(100);
    expect(annotationConfidencePercent(-1)).toBe(0);
  });

  it("builds a bounded AI re-review instruction from reviewer validation", () => {
    const prompt = buildValidationRerunPrompt([annotation()], "en");
    expect(prompt).toContain("Reviewer validation feedback");
    expect(prompt).toContain("candidate opacity");
    expect(prompt).toContain("accepted");
    expect(prompt).toContain("box narrowed");
    expect(prompt.length).toBeLessThan(4000);
  });

  it("filters an annotation review queue by origin, status, and minimum AI confidence", () => {
    const annotations = [
      annotation({ id: "ai-high", confidence: 0.91, review_status: "unreviewed" }),
      annotation({ id: "ai-low", confidence: 0.42, review_status: "unreviewed" }),
      annotation({ id: "manual", source: "manual user annotation", confidence: 1, review_status: "unreviewed" }),
      annotation({ id: "accepted", confidence: 0.95, review_status: "accepted" }),
    ];

    expect(filterWorkspaceAnnotations(annotations, { origin: "ai", reviewStatus: "unreviewed", minimumAiConfidence: 80 }).map(item => item.id)).toEqual(["ai-high"]);
    expect(filterWorkspaceAnnotations(annotations, { origin: "reviewer", reviewStatus: "all", minimumAiConfidence: 100 }).map(item => item.id)).toEqual(["manual"]);
  });
});
