// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AnalysisResult, CaseRecord, DicomViewerProfile, ResultCard } from "./types";

const mocks = vi.hoisted(() => ({ saveCase: vi.fn(), caseDetail: vi.fn(), analyze: vi.fn(), setActiveStudyImage: vi.fn(), upload: vi.fn(), addStudyImage: vi.fn(), dicomViewerProfile: vi.fn(), chat: vi.fn(), exportReport: vi.fn(), exportAnnotations: vi.fn(), exportAnnotationReview: vi.fn() }));
vi.mock("./services/api", () => ({
  api: mocks,
  imageUrl: (path: string) => path,
  dicomPreviewUrl: (caseId: string, imageId: string) => `${caseId}/${imageId}`,
}));
import { ReadingRoom } from "./main";

const makeCase = (id: string, dicom = false): CaseRecord => ({
  case_id: id, title: id, metadata: {}, chat_history: [], created_at: "2026-10-08", updated_at: "2026-10-08",
  active_image_id: `${id}:0`,
  images: [{ image_id: `${id}:0`, index: 0, filename: "image.png", image_path: "image.png", preview_path: "preview.png", metadata: {}, is_dicom: dicom }],
  annotations: [{ id: "annotation", label: "synthetic", confidence: 1, source: "manual user annotation", explanation: "test", visible: true, source_image_id: `${id}:0`, coordinate: { type: "point", x: 10, y: 10, width: 0, height: 0 } }],
});
let host: HTMLDivElement;
let root: Root;
const setActiveCase = vi.fn();
const render = async (record: CaseRecord | null, preview = "") => {
  await act(async () => root.render(<ReadingRoom activeCase={record} setActiveCase={setActiveCase} preview={preview} setPreview={vi.fn()} analysis={null} setAnalysis={vi.fn()} onOpenGuide={vi.fn()} onOpenLibrary={vi.fn()} onNewCase={vi.fn()} />));
};
const click = async (selector: string) => {
  const button = host.querySelector<HTMLButtonElement>(selector);
  expect(button).toBeTruthy();
  await act(async () => button!.click());
};
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.resetAllMocks();
  mocks.saveCase.mockImplementation(async record => record);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

const resultCard = (id: string, refs: string[] = []): ResultCard => ({
  id, finding: id, status: "uncertain", candidate_diagnosis: "", confidence: 0.5, evidence: [], annotation_refs: refs,
  source: "synthetic", uncertainty_reason: "", next_safe_action: "review", review_status: "unreviewed", reviewer_note: "", validation_status: "not_validated", model_trace_refs: [],
});
const caseWithEvidence = (): CaseRecord => {
  const record = makeCase("evidence");
  record.annotations[0].linked_result_card_ids = ["old"];
  record.analysis = {
    case_id: record.case_id, input: {}, image_quality: { score: 1, exposure: "", positioning: "", limitations: [] }, findings: [],
    annotations: record.annotations, result_cards: [resultCard("old", ["annotation"]), resultCard("new")], differential_diagnosis: [],
    systematic_reading: {}, report: { indication: "", technique: "", comparison: "", findings: "", impression: "", recommendation: "", watermark: "synthetic" }, model_trace: [], warnings: [],
  };
  return record;
};
function StatefulRoom({ initial }: { initial: CaseRecord }) {
  const [record, setRecord] = React.useState(initial);
  const [analysis, setAnalysis] = React.useState<AnalysisResult | null>(initial.analysis || null);
  return <ReadingRoom activeCase={record} setActiveCase={next => { setActiveCase(next); if (next) setRecord(next); }} preview="synthetic-preview.png" setPreview={vi.fn()} analysis={analysis} setAnalysis={setAnalysis} onOpenGuide={vi.fn()} onOpenLibrary={vi.fn()} onNewCase={vi.fn()} />;
}
const openAnnotation = async () => {
  const tab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  await click(".annotationSelect");
};
const lastSaved = () => mocks.saveCase.mock.calls[mocks.saveCase.mock.calls.length - 1][0] as CaseRecord;

it("undoes evidence links on both the annotation and result cards", async () => {
  await act(async () => root.render(<StatefulRoom initial={caseWithEvidence()} />));
  await openAnnotation();
  const link = host.querySelector<HTMLSelectElement>('[data-testid="annotation-result-link-annotation"]')!;
  await act(async () => { link.value = "new"; link.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(lastSaved().analysis!.result_cards[1].annotation_refs).toEqual(["annotation"]);
  await click('button[aria-label="Undo annotation change"]');
  expect(lastSaved().annotations[0].linked_result_card_ids).toEqual(["old"]);
  expect(lastSaved().analysis!.result_cards[0].annotation_refs).toEqual(["annotation"]);
  expect(lastSaved().analysis!.result_cards[1].annotation_refs).toEqual([]);
  await click('button[aria-label="Redo annotation change"]');
  expect(lastSaved().analysis!.result_cards[1].annotation_refs).toEqual(["annotation"]);
});

it("restores deleted annotation evidence when deletion is undone", async () => {
  await act(async () => root.render(<StatefulRoom initial={caseWithEvidence()} />));
  await openAnnotation();
  await click('button[title="Delete manual annotation"]');
  expect(lastSaved().annotations).toEqual([]);
  expect(lastSaved().analysis!.result_cards[0].annotation_refs).toEqual([]);
  await click('button[aria-label="Undo annotation change"]');
  expect(lastSaved().annotations).toHaveLength(1);
  expect(lastSaved().analysis!.result_cards[0].annotation_refs).toEqual(["annotation"]);
});

it("does not apply queued old case details to a newly opened case", async () => {
  let finish!: (record: CaseRecord) => void;
  mocks.saveCase.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  await render(makeCase("old"));
  await openAnnotation();
  await click('button[title="Hide annotation"]');
  const save = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Save case details")!;
  await act(async () => save.click());
  await render(makeCase("new"));
  setActiveCase.mockClear();
  await act(async () => finish(makeCase("old")));
  expect(mocks.saveCase).toHaveBeenCalledOnce();
  expect(setActiveCase).not.toHaveBeenCalled();
});

it("refreshes finding notes when another case reuses the same card IDs", async () => {
  const original = caseWithEvidence(); original.analysis!.result_cards[0].reviewer_note = "Old case note";
  await render(original);
  const tab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Findings")!;
  await act(async () => tab.click());
  const next = caseWithEvidence(); next.case_id = "other-case"; next.analysis!.result_cards[0].reviewer_note = "New case note";
  await render(next);
  expect(host.querySelector<HTMLTextAreaElement>(".resultCardsPanel textarea")!.value).toBe("New case note");
});

it("ignores a late finding-review save failure after switching cases", async () => {
  let reject!: (error: Error) => void;
  mocks.saveCase.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail; }));
  await render(caseWithEvidence());
  const tab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Findings")!;
  await act(async () => tab.click());
  const review = host.querySelector<HTMLSelectElement>(".resultCardsPanel select")!;
  await act(async () => { review.value = "accepted"; review.dispatchEvent(new Event("change", { bubbles: true })); });
  const next = caseWithEvidence(); next.case_id = "other-case";
  await render(next);
  await act(async () => reject(new Error("Old finding save failed")));
  expect(host.textContent).not.toContain("Old finding save failed");
});

it.each(["Reviewed PNG", "JSON"])("ignores a stale %s export error in a newly opened case", async label => {
  let reject!: (error: Error) => void;
  const pending = () => new Promise((_resolve, fail) => { reject = fail; });
  mocks.exportAnnotations.mockImplementation(pending);
  mocks.exportReport.mockImplementation(pending);
  await render(caseWithEvidence());
  const tabName = label === "JSON" ? "Report" : "Annotations";
  const tab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === tabName)!;
  await act(async () => tab.click());
  const exportButton = [...host.querySelectorAll<HTMLButtonElement>(label === "JSON" ? ".report button" : ".annotationPanel button")].find(button => button.textContent === label)!;
  await act(async () => exportButton.click());
  const next = caseWithEvidence(); next.case_id = "other-case";
  await render(next);
  await act(async () => reject(new Error("Old export failed")));
  expect(host.textContent).not.toContain("Old export failed");
});

it("prevents restoring geometry while an annotation is locked", async () => {
  const record = makeCase("locked");
  record.annotations[0].locked = true;
  record.annotations[0].original_coordinate = { type: "point", x: 0, y: 0, width: 0, height: 0 };
  await render(record);
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  await click(".annotationSelect");
  const restore = host.querySelector<HTMLButtonElement>('button[title="Restore original AI geometry"]')!;
  expect(restore.disabled).toBe(true);
  await act(async () => restore.click());
  expect(mocks.saveCase).not.toHaveBeenCalled();
});

it("ignores a failed reload after switching to another case", async () => {
  let reject!: (error: Error) => void;
  mocks.saveCase.mockRejectedValue(new Error("Conflict"));
  mocks.caseDetail.mockImplementation(() => new Promise((_resolve, fail) => { reject = fail; }));
  await render(makeCase("old"));
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  await click(".annotationSelect");
  await click('button[title="Hide annotation"]');
  const reload = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent?.includes("Discard unsaved edits"))!;
  await act(async () => reload.click());
  await render(makeCase("new"));
  await act(async () => reject(new Error("Old case reload failed")));
  expect(host.textContent).not.toContain("Old case reload failed");
});

it("clears an unfinished polygon when switching to an equally sized image", async () => {
  const record = makeCase("polygon");
  record.images![0].width = 100; record.images![0].height = 100;
  record.images!.push({ ...record.images![0], image_id: "polygon:1", index: 1 });
  await render(record, "synthetic-preview.png");
  await click('button[aria-label="Draw manual polygon"]');
  const svg = host.querySelector<SVGSVGElement>(".annotationOverlay")!;
  svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100 } as DOMRect);
  await act(async () => svg.dispatchEvent(new MouseEvent("pointerdown", { clientX: 10, clientY: 10, bubbles: true })));
  expect(host.querySelector(".polygonDraft")).not.toBeNull();
  await render({ ...record, active_image_id: "polygon:1" }, "synthetic-preview.png");
  expect(host.querySelector(".polygonDraft")).toBeNull();
});

const prepareOverlay = () => {
  const svg = host.querySelector<SVGSVGElement>(".annotationOverlay")!;
  svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100 } as DOMRect);
  svg.setPointerCapture = vi.fn(); svg.releasePointerCapture = vi.fn(); svg.hasPointerCapture = () => false;
  return svg;
};
const pointer = async (element: Element, type: string, x: number, y: number) => {
  await act(async () => element.dispatchEvent(new MouseEvent(type, { clientX: x, clientY: y, bubbles: true })));
};

it("creates an angle from three points on the current image", async () => {
  const record = makeCase("angle");
  record.images![0].width = 100; record.images![0].height = 100;
  await render(record, "synthetic-preview.png");
  await click('button[aria-label="Measure angle"]');
  const svg = prepareOverlay();
  await pointer(svg, "pointerdown", 40, 10);
  await pointer(svg, "pointerdown", 10, 10);
  expect(mocks.saveCase).not.toHaveBeenCalled();
  await pointer(svg, "pointerdown", 10, 40);
  const saved = mocks.saveCase.mock.calls[0][0] as CaseRecord;
  const angle = saved.annotations[saved.annotations.length - 1];
  expect(angle.coordinate).toMatchObject({ type: "angle", points: [[40, 10], [10, 10], [10, 40]] });
  expect(angle.source_image_id).toBe("angle:0");
});

it("cancels unfinished angle points with Escape", async () => {
  await render(makeCase("cancel-angle"), "synthetic-preview.png");
  await click('button[aria-label="Measure angle"]');
  await pointer(prepareOverlay(), "pointerdown", 10, 10);
  expect(host.querySelector(".angleDraft")).not.toBeNull();
  await act(async () => document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  expect(host.querySelector(".angleDraft")).toBeNull();
  expect(mocks.saveCase).not.toHaveBeenCalled();
});

it.each(["length", "angle"])("edits a %s endpoint and preserves original geometry", async type => {
  const record = makeCase("endpoint");
  record.images![0].width = 100; record.images![0].height = 100;
  const coordinate = { type, x: 10, y: 10, width: 30, height: 30, points: (type === "angle" ? [[40, 10], [10, 10], [10, 40]] : [[10, 10], [40, 40]]) as [number, number][] };
  record.annotations[0].coordinate = coordinate;
  record.annotations[0].original_coordinate = structuredClone(coordinate);
  await render(record, "synthetic-preview.png");
  const svg = prepareOverlay();
  await pointer(host.querySelector(type === "angle" ? ".annotationAngle" : ".annotationLength")!, "pointerdown", 20, 20);
  await pointer(svg, "pointerup", 20, 20);
  mocks.saveCase.mockClear();
  const handle = host.querySelector(".measurementVertex")!;
  expect(handle).not.toBeNull();
  await pointer(handle, "pointerdown", 10, 10);
  await pointer(svg, "pointermove", 60, 10);
  await pointer(svg, "pointerup", 60, 10);
  const saved = mocks.saveCase.mock.calls[mocks.saveCase.mock.calls.length - 1][0] as CaseRecord;
  expect(saved.annotations[0].coordinate.points![0]).toEqual([60, 10]);
  expect(saved.annotations[0].original_coordinate).toEqual(coordinate);
});

it("maps a point through the SVG transform instead of its rotated bounding box", async () => {
  const record = makeCase("rotated");
  record.images![0].width = 100; record.images![0].height = 100;
  await render(record, "synthetic-preview.png");
  await click('button[aria-label="Place manual point"]');
  const svg = prepareOverlay();
  // The overlay viewBox is 1×1 before the synthetic image loads. Rotation
  // maps (0.2, 0.3) to (70, 20) in this screen matrix.
  Object.defineProperty(svg, "getScreenCTM", { value: () => ({ inverse: () => ({ a: 0, b: -0.01, c: 0.01, d: 0, e: 0, f: 1 }) }) });
  await pointer(svg, "pointerdown", 70, 20);
  const coordinate = (mocks.saveCase.mock.calls[0][0] as CaseRecord).annotations[1].coordinate;
  expect(coordinate.type).toBe("point");
  expect(coordinate.x).toBeCloseTo(20);
  expect(coordinate.y).toBeCloseTo(30);
});

it("does not create a point with the secondary mouse button", async () => {
  await render(makeCase("secondary"), "synthetic-preview.png");
  await click('button[aria-label="Place manual point"]');
  const svg = prepareOverlay();
  await act(async () => svg.dispatchEvent(new MouseEvent("pointerdown", { button: 2, clientX: 10, clientY: 10, bubbles: true })));
  expect(mocks.saveCase).not.toHaveBeenCalled();
});

it("does not create a point when the overlay has no measurable size", async () => {
  await render(makeCase("zero-size"), "synthetic-preview.png");
  await click('button[aria-label="Place manual point"]');
  const svg = prepareOverlay();
  svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 0, height: 0 } as DOMRect);
  await pointer(svg, "pointerdown", 0, 0);
  expect(mocks.saveCase).not.toHaveBeenCalled();
});

it("selects geometry without creating an unchanged save and undo entry", async () => {
  const record = makeCase("select-only");
  record.images![0].width = 100; record.images![0].height = 100;
  await render(record, "synthetic-preview.png");
  const svg = prepareOverlay();
  await pointer(host.querySelector(".annotationPoint")!, "pointerdown", 10, 10);
  await pointer(svg, "pointerup", 10, 10);
  expect(mocks.saveCase).not.toHaveBeenCalled();
  expect(host.querySelector<HTMLButtonElement>('button[aria-label="Undo annotation change"]')!.disabled).toBe(true);
});

it("does not save an angle with a zero-length arm and lets the user correct it", async () => {
  const record = makeCase("degenerate-angle");
  record.images![0].width = 100; record.images![0].height = 100;
  await render(record, "synthetic-preview.png");
  await click('button[aria-label="Measure angle"]');
  const svg = prepareOverlay();
  await pointer(svg, "pointerdown", 40, 10);
  await pointer(svg, "pointerdown", 10, 10);
  await pointer(svg, "pointerdown", 10, 10);
  expect(mocks.saveCase).not.toHaveBeenCalled();
  expect(host.querySelector(".angleDraft")).not.toBeNull();
  await pointer(svg, "pointerdown", 10, 40);
  expect(mocks.saveCase).toHaveBeenCalledOnce();
});

it("cancels a box drag with Escape before saving", async () => {
  await render(makeCase("cancel-box"), "synthetic-preview.png");
  await click('button[aria-label="Draw manual bounding box"]');
  const svg = prepareOverlay();
  await pointer(svg, "pointerdown", 10, 10);
  await pointer(svg, "pointermove", 50, 50);
  expect(host.querySelector(".manualDraft")).not.toBeNull();
  await act(async () => document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  await pointer(svg, "pointerup", 50, 50);
  expect(host.querySelector(".manualDraft")).toBeNull();
  expect(mocks.saveCase).not.toHaveBeenCalled();
});

it("uses the same anisotropic DICOM calibration for overlay and panel angles", async () => {
  const record = makeCase("calibrated-angle", true);
  record.images![0].width = 100; record.images![0].height = 100;
  record.annotations[0].coordinate = { type: "angle", x: 0, y: 0, width: 10, height: 10, points: [[10, 10], [0, 0], [10, 0]] };
  mocks.dicomViewerProfile.mockResolvedValue({ schema_version: "test", number_of_frames: 1, rows: 100, columns: 100, pixel_spacing: { row_mm: 2, column_mm: 1 }, window_presets: [], default_window: null, supports_window_level: false, orientation: [], frame_of_reference_uid: "" });
  await render(record, "synthetic-preview.png");
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  expect(host.querySelector(".annotationLabel")!.textContent).toContain("63.43°");
  expect(host.querySelector(".annotationMeasurement")!.textContent).toBe("63.43 °");
});

it("retains an unsaved edit on conflict and reloads only when explicitly requested", async () => {
  const original = { ...makeCase("conflict"), revision: 1 };
  mocks.saveCase.mockRejectedValue(new Error("This case changed in another operation"));
  const latest = { ...original, revision: 2, title: "Updated elsewhere" };
  mocks.caseDetail.mockResolvedValue(latest);
  await render(original);
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  await click(".annotationSelect");
  await click('button[title="Hide annotation"]');
  expect(setActiveCase.mock.calls[setActiveCase.mock.calls.length - 1][0].annotations[0].visible).toBe(false);
  expect(mocks.caseDetail).not.toHaveBeenCalled();
  const reload = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent?.includes("Discard unsaved edits"));
  expect(reload).toBeTruthy();
  await act(async () => reload!.click());
  expect(mocks.caseDetail).toHaveBeenCalledWith("conflict");
  expect(setActiveCase.mock.calls[setActiveCase.mock.calls.length - 1][0]).toEqual(latest);
});

it("does not replay more edits after the first save fails", async () => {
  mocks.saveCase.mockRejectedValue(new Error("Conflict"));
  await render({ ...makeCase("conflict"), revision: 1 });
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  await click(".annotationSelect");
  await click('button[title="Hide annotation"]');
  await click('button[title="Hide annotation"]');
  expect(mocks.saveCase).toHaveBeenCalledOnce();
});

it("keeps a newer annotation draft when case details finish saving", async () => {
  const pending: Array<{ record: CaseRecord; finish: (record: CaseRecord) => void }> = [];
  mocks.saveCase.mockImplementation(record => new Promise(resolve => pending.push({ record, finish: resolve })));
  function Editor() {
    const [record, setRecord] = React.useState<CaseRecord>({ ...makeCase("identity-pending"), revision: 1 });
    return <ReadingRoom activeCase={record} setActiveCase={next => { setActiveCase(next); if (next) setRecord(next); }} preview="" setPreview={vi.fn()} analysis={null} setAnalysis={vi.fn()} onOpenGuide={vi.fn()} onOpenLibrary={vi.fn()} onNewCase={vi.fn()} />;
  }
  await act(async () => root.render(<Editor />));
  const title = host.querySelector<HTMLInputElement>('.upload input[type="text"]') || [...host.querySelectorAll<HTMLInputElement>('input')].find(input => input.value === "identity-pending")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(title, "Reviewed title");
    title.dispatchEvent(new Event("input", { bubbles: true }));
  });
  const save = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Save case details")!;
  await act(async () => save.click());
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  await click(".annotationSelect");
  await click('button[title="Hide annotation"]');
  expect(pending).toHaveLength(1);
  await act(async () => pending[0].finish({ ...pending[0].record, revision: 2 }));
  expect(pending).toHaveLength(2);
  expect(setActiveCase.mock.calls[setActiveCase.mock.calls.length - 1][0].annotations[0].visible).toBe(false);
  expect(pending[0].record.title).toBe("Reviewed title");
  expect(pending[1].record.title).toBe("Reviewed title");
  expect(pending[1].record.revision).toBe(2);
  await act(async () => pending[1].finish({ ...pending[1].record, revision: 3 }));
});

it("keyboard undo persists the current case even when mounted without a case", async () => {
  await render(null);
  await render(makeCase("current"));
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations");
  expect(tab).toBeTruthy();
  await act(async () => tab!.click());
  await click(".annotationSelect");
  await click('button[title="Hide annotation"]');
  const edited = setActiveCase.mock.calls[setActiveCase.mock.calls.length - 1][0] as CaseRecord;
  expect(edited.annotations[0].visible).toBe(false);
  await render(edited);
  mocks.saveCase.mockClear();
  await act(async () => { document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "z", ctrlKey: true, bubbles: true })); });
  expect(mocks.saveCase).toHaveBeenCalledOnce();
  expect(mocks.saveCase.mock.calls[0][0].case_id).toBe("current");
  expect(mocks.saveCase.mock.calls[0][0].annotations[0].visible).toBe(true);
});

it("adding files appends them to the active case", async () => {
  const record = makeCase("existing");
  mocks.addStudyImage.mockResolvedValue({ case: record, image: record.images![0] });
  mocks.upload.mockResolvedValue({ case: makeCase("unexpected-new"), preview_data_url: "" });
  await render(record);
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  const file = new File(["synthetic"], "second.png", { type: "image/png" });
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  expect(mocks.upload).not.toHaveBeenCalled();
  expect(mocks.addStudyImage).toHaveBeenCalledWith("existing", file);
  expect(setActiveCase.mock.calls[setActiveCase.mock.calls.length - 1][0].case_id).toBe("existing");
});

it("ignores analysis completion after another case is opened", async () => {
  let finish!: (value: unknown) => void;
  mocks.analyze.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  mocks.caseDetail.mockResolvedValue(makeCase("old"));
  await render(makeCase("old"));
  await click(".runAnalysis");
  await render(makeCase("new"));
  setActiveCase.mockClear();
  await act(async () => finish({ case_id: "old", annotations: [] }));
  expect(setActiveCase).not.toHaveBeenCalled();
  expect(host.querySelector<HTMLButtonElement>(".runAnalysis")!.disabled).toBe(false);
});

it("ignores an image-selection response after another case is opened", async () => {
  let finish!: (value: CaseRecord) => void;
  mocks.setActiveStudyImage.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const old = makeCase("old");
  old.images!.push({ ...old.images![0], image_id: "old:1", index: 1 });
  await render(old);
  const images = host.querySelectorAll<HTMLButtonElement>(".studyImageStrip button");
  expect(images.length).toBe(2);
  await act(async () => images[1].click());
  await render(makeCase("new"));
  setActiveCase.mockClear();
  await act(async () => finish({ ...old, active_image_id: "old:1" }));
  expect(setActiveCase).not.toHaveBeenCalled();
});

it("ignores an upload response after another case is opened", async () => {
  let finish!: (value: unknown) => void;
  mocks.addStudyImage.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await render(makeCase("old"));
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, "files", { value: [new File(["synthetic"], "second.png")], configurable: true });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  await render(makeCase("new"));
  setActiveCase.mockClear();
  await act(async () => finish({ case: makeCase("old"), image: makeCase("old").images![0] }));
  expect(setActiveCase).not.toHaveBeenCalled();
});

it("ignores a stale DICOM profile after switching cases", async () => {
  let finishOld!: (value: DicomViewerProfile) => void;
  const profile = (center: number): DicomViewerProfile => ({ schema_version: "test", number_of_frames: 1, rows: 2, columns: 2, photometric_interpretation: "MONOCHROME2", modality: "DX", pixel_spacing: null, window_presets: [], default_window: { name: "test", center, width: 200 }, supports_window_level: true, orientation: [], frame_of_reference_uid: "" });
  mocks.dicomViewerProfile.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; })).mockResolvedValueOnce(profile(200));
  await render(makeCase("old", true));
  await render(makeCase("new", true));
  await act(async () => finishOld(profile(100)));
  const center = host.querySelector<HTMLInputElement>('.dicomViewerControls input[type="number"]');
  expect(center?.value).toBe("200");
});

it("does not show first-image annotations on a reimported DICOM with the same SOP UID", async () => {
  const record = makeCase("same-uid");
  record.images![0].sop_instance_uid = record.images![0].image_id;
  record.images!.push({ ...record.images![0], image_id: "same-uid:1", index: 1 });
  record.active_image_id = "same-uid:1";
  await render(record);
  const tab = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Annotations");
  await act(async () => tab!.click());
  expect(host.querySelector(".annotationSelect")).toBeNull();
});

async function openChatAndSend() {
  const select = host.querySelector<HTMLSelectElement>(".secondaryToolSelect select")!;
  await act(async () => { select.value = "AI Chat"; select.dispatchEvent(new Event("change", { bubbles: true })); });
  const suggestion = [...host.querySelectorAll<HTMLButtonElement>(".chat button")].find(button => button.textContent === "Summarize the main findings")!;
  await act(async () => suggestion.click());
  await act(async () => host.querySelector(".composer")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
}

it("waits for pending annotation writes before sending chat context", async () => {
  const record = makeCase("chat-pending");
  let finishSave!: (value: CaseRecord) => void;
  mocks.saveCase.mockImplementation(() => new Promise(resolve => { finishSave = resolve; }));
  mocks.chat.mockResolvedValue({ history: [], backend: "demo", fallback: false });
  await render(record);
  await openAnnotation();
  await click('button[title="Hide annotation"]');
  await openChatAndSend();
  const callsBeforeSave = mocks.chat.mock.calls.length;
  await act(async () => finishSave(record));
  expect(callsBeforeSave).toBe(0);
  expect(mocks.chat).toHaveBeenCalledOnce();
});

it("updates the chat revision while retaining local edits", async () => {
  let finish!: (value: unknown) => void;
  mocks.chat.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await render({ ...makeCase("same"), revision: 1 });
  await openChatAndSend();
  await render({ ...makeCase("same"), title: "Latest local draft", revision: 2 });
  await act(async () => finish({ case: { ...makeCase("same"), title: "Saved title", revision: 3 }, revision: 3, history: [{ role: "assistant", content: "reply" }], backend: "demo", fallback: false }));
  const updated = setActiveCase.mock.calls[setActiveCase.mock.calls.length - 1][0] as CaseRecord;
  expect(updated.title).toBe("Latest local draft");
  expect(updated.revision).toBe(3);
});

it("ignores a chat snapshot older than the latest saved case", async () => {
  let finish!: (value: unknown) => void;
  mocks.chat.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await render({ ...makeCase("same"), revision: 1 });
  await openChatAndSend();
  await render({ ...makeCase("same"), revision: 4, chat_history: [{ role: "assistant", content: "newer reply", timestamp: "2026-10-14" }] });
  await act(async () => finish({ revision: 3, history: [{ role: "assistant", content: "older reply" }], backend: "demo", fallback: false }));
  expect(host.querySelector(".messages")?.textContent).toContain("newer reply");
});

it("ignores a chat response for a case that is no longer active", async () => {
  let finish!: (value: unknown) => void;
  mocks.chat.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await render(makeCase("old"));
  await openChatAndSend();
  await render(makeCase("new"));
  setActiveCase.mockClear();
  await act(async () => finish({ history: [{ role: "assistant", content: "old reply" }], backend: "demo", fallback: false }));
  expect(setActiveCase).not.toHaveBeenCalled();
  expect(host.querySelector(".messages")?.textContent).not.toContain("old reply");
});

it("merges chat history with the latest local case instead of an old snapshot", async () => {
  let finish!: (value: unknown) => void;
  mocks.chat.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await render(makeCase("same"));
  await openChatAndSend();
  await render({ ...makeCase("same"), title: "Latest title" });
  await act(async () => finish({ history: [{ role: "assistant", content: "reply" }], backend: "demo", fallback: false }));
  const updated = setActiveCase.mock.calls[setActiveCase.mock.calls.length - 1][0] as CaseRecord;
  expect(updated.title).toBe("Latest title");
  expect(updated.chat_history[0].content).toBe("reply");
});

it("does not offer unsupported window controls for a color DICOM", async () => {
  mocks.dicomViewerProfile.mockResolvedValue({ schema_version: "test", number_of_frames: 1, rows: 2, columns: 2, photometric_interpretation: "RGB", modality: "DX", pixel_spacing: null, window_presets: [], default_window: null, supports_window_level: false, orientation: [], frame_of_reference_uid: "" });
  await render(makeCase("color", true));
  expect(host.querySelector('.dicomViewerControls input[type="number"]')).toBeNull();
});

it("does not analyze frame zero while the reviewer is viewing another frame", async () => {
  mocks.dicomViewerProfile.mockResolvedValue({ schema_version: "test", number_of_frames: 2, rows: 2, columns: 2, pixel_spacing: null, window_presets: [], default_window: null, supports_window_level: true, orientation: [], frame_of_reference_uid: "" });
  await render(makeCase("multi-frame", true));
  const frame = host.querySelector<HTMLInputElement>('.dicomViewerControls input[type="range"]')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(frame, "1");
    frame.dispatchEvent(new Event("input", { bubbles: true }));
  });
  const run = host.querySelector<HTMLButtonElement>(".runAnalysis")!;
  expect(run.disabled).toBe(true);
  expect(host.textContent).toContain("AI analysis and PNG exports use frame 1");
  expect(mocks.analyze).not.toHaveBeenCalled();
});

it.each(["JSON", "Annotated PNG"])("shows an export failure for %s in the report panel", async label => {
  mocks.exportReport.mockRejectedValue(new Error("Synthetic export failure"));
  mocks.exportAnnotations.mockRejectedValue(new Error("Synthetic export failure"));
  await render(makeCase("report"));
  const tab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Report")!;
  await act(async () => tab.click());
  const button = [...host.querySelectorAll<HTMLButtonElement>(".report .actions button")].find(button => button.textContent === label)!;
  await act(async () => button.click());
  expect(host.querySelector('.report [role="alert"]')?.textContent).toContain("Synthetic export failure");
});

it("waits for the annotation save before exporting a report", async () => {
  const record = makeCase("pending-save");
  let finishSave!: (value: CaseRecord) => void;
  mocks.saveCase.mockImplementation(() => new Promise(resolve => { finishSave = resolve; }));
  mocks.exportReport.mockResolvedValue({ path: "synthetic-report.json" });
  vi.stubGlobal("alert", vi.fn());
  await render(record);
  const annotationsTab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Annotations")!;
  await act(async () => annotationsTab.click());
  await click(".annotationSelect");
  await click('button[title="Hide annotation"]');
  const reportTab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Report")!;
  await act(async () => reportTab.click());
  const exportButton = [...host.querySelectorAll<HTMLButtonElement>(".report .actions button")].find(button => button.textContent === "JSON")!;
  await act(async () => exportButton.click());
  const calledBeforeSave = mocks.exportReport.mock.calls.length;
  await act(async () => finishSave(record));
  expect(calledBeforeSave).toBe(0);
  expect(mocks.exportReport).toHaveBeenCalledOnce();
});

it("blocks report export when the preceding annotation save failed", async () => {
  mocks.saveCase.mockRejectedValue(new Error("Synthetic save failure"));
  mocks.exportReport.mockResolvedValue({ path: "stale-report.json" });
  vi.stubGlobal("alert", vi.fn());
  await render(makeCase("failed-save"));
  const annotationsTab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Annotations")!;
  await act(async () => annotationsTab.click());
  await click(".annotationSelect");
  await click('button[title="Hide annotation"]');
  const reportTab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Report")!;
  await act(async () => reportTab.click());
  const exportButton = [...host.querySelectorAll<HTMLButtonElement>(".report .actions button")].find(button => button.textContent === "JSON")!;
  await act(async () => exportButton.click());
  expect(mocks.exportReport).not.toHaveBeenCalled();
  expect(host.querySelector('.report [role="alert"]')?.textContent).toContain("Synthetic save failure");
});

it.each(["Reviewed PNG", "AI vs reviewed package"])("shows an export failure for %s in the annotation panel", async label => {
  mocks.exportAnnotations.mockRejectedValue(new Error("Synthetic annotation export failure"));
  mocks.exportAnnotationReview.mockRejectedValue(new Error("Synthetic annotation export failure"));
  await render(makeCase("annotations"));
  const tab = [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Annotations")!;
  await act(async () => tab.click());
  const button = [...host.querySelectorAll<HTMLButtonElement>(".annotationPanel button")].find(button => button.textContent === label)!;
  await act(async () => button.click());
  expect(host.querySelector('.annotationPanel [role="alert"]')?.textContent).toContain("Synthetic annotation export failure");
});
