// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { CaseRecord, ValidationLabel } from "./types";

const mocks = vi.hoisted(() => ({ validationLabels: vi.fn(), saveValidationLabel: vi.fn(), deleteValidationLabel: vi.fn(), curatedValidationFixture: vi.fn(), runValidation: vi.fn() }));
vi.mock("./services/api", () => ({ api: mocks, imageUrl: (path: string) => path }));
import { ValidationWorkbench } from "./main";

let host: HTMLDivElement, root: Root;
const openCase = vi.fn();
const makeCase = (id: string, x = 50, annotated = true): CaseRecord => ({
  case_id: id, title: id, metadata: {}, chat_history: [], created_at: "now", updated_at: "now",
  active_image_id: `${id}:0`, images: [{ image_id: `${id}:0`, index: 0, filename: "synthetic.png", image_path: "synthetic.png", metadata: {} }],
  annotations: annotated ? [{ id: "synthetic", label: `${id} annotation`, confidence: 1, source: "manual user annotation", explanation: "test", visible: true, source_image_id: `${id}:0`, coordinate: { type: "bbox", x, y: x, width: 20, height: 20 } }] : [],
});
const reference = (values: Partial<ValidationLabel> = {}): ValidationLabel => ({ case_id: "a", title: "Saved reference", split: "local", expected_body_region: "", expected_findings: [], reference_standard: "synthetic", reviewer: "", notes: "", ...values });
async function render(record: CaseRecord | null) {
  await act(async () => root.render(<ValidationWorkbench activeCase={record} analysis={null} onOpenCase={openCase} />));
}
function input(labelText: string) {
  const label = [...host.querySelectorAll("label")].find(label => label.textContent?.trim() === labelText);
  expect(label, labelText).toBeTruthy();
  return label!.querySelector<HTMLInputElement>("input")!;
}
async function change(labelText: string, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input(labelText), value);
    input(labelText).dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function click(text: string) {
  const button = [...host.querySelectorAll("button")].find(button => button.textContent?.trim() === text);
  expect(button, text).toBeTruthy();
  await act(async () => button!.click());
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
beforeEach(async () => {
  vi.resetAllMocks();
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  mocks.validationLabels.mockResolvedValue([reference()]);
  mocks.saveValidationLabel.mockResolvedValue({});
  mocks.deleteValidationLabel.mockResolvedValue({ deleted: true });
  mocks.runValidation.mockResolvedValue({ metrics: {}, results: [] });
  mocks.curatedValidationFixture.mockResolvedValue({ path: "synthetic-fixture.json" });
  openCase.mockResolvedValue(undefined);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await render(makeCase("a"));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

it("uses zero coordinates from the newly selected case", async () => {
  await render(makeCase("b", 0));
  await act(async () => input("Evaluate geometry").click());
  expect(input("X").value).toBe("0");
  expect(input("Y").value).toBe("0");
});

it("does not carry an annotation reference to an unannotated case", async () => {
  await render(makeCase("b", 0, false));
  expect(input("Expected annotation").value).toBe("");
  await click("Save label");
  expect(mocks.saveValidationLabel.mock.calls[0][0].expected_annotations).toEqual([]);
});

it("preserves a manual reference draft when the same case is refreshed", async () => {
  await change("Expected annotation", "Reviewer reference");
  await render({ ...makeCase("a"), title: "Refreshed case title" });
  expect(input("Expected annotation").value).toBe("Reviewer reference");
});

it("loads and saves a point reference without losing its spatial target", async () => {
  mocks.validationLabels.mockResolvedValue([reference({ expected_annotations: [{ label: "point reference", coordinate_type: "point", required: true, points: [[7, 9]], max_point_distance: 4 }] })]);
  await click("Run");
  await click("Edit");
  expect(input("Evaluate geometry").checked).toBe(true);
  expect(input("X").value).toBe("7");
  expect(input("Y").value).toBe("9");
  await click("Save label");
  expect(mocks.saveValidationLabel.mock.calls[0][0].expected_annotations[0].points).toEqual([[7, 9]]);
});

it("preserves additional reference findings and annotations when editing the first", async () => {
  const secondFinding = { label: "second finding", status: "negative", note: "Keep this note" };
  const secondAnnotation = { label: "second annotation", coordinate_type: "point", required: true, points: [[8, 3]] as [number, number][] };
  mocks.validationLabels.mockResolvedValue([reference({ expected_findings: [{ label: "first finding", status: "positive" }, secondFinding], expected_annotations: [{ label: "first annotation", coordinate_type: "bbox", required: false }, secondAnnotation] })]);
  await click("Run"); await click("Edit"); await click("Save label");
  const payload = mocks.saveValidationLabel.mock.calls[0][0];
  expect(payload.expected_findings).toHaveLength(2);
  expect(payload.expected_findings[1]).toEqual(secondFinding);
  expect(payload.expected_annotations).toHaveLength(2);
  expect(payload.expected_annotations[1]).toEqual(secondAnnotation);
});

it.each(["Save label", "Run", "Run + Export", "Sample Fixture", "Delete"])("shows API failure for %s and recovers its controls", async action => {
  for (const mock of [mocks.saveValidationLabel, mocks.runValidation, mocks.curatedValidationFixture, mocks.deleteValidationLabel]) mock.mockRejectedValue(new Error("Synthetic API failure"));
  await click(action);
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Synthetic API failure");
  expect([...host.querySelectorAll("button")].find(button => button.textContent?.trim() === action)!.disabled).toBe(false);
});

it("does not clear a new case draft when a previous label deletion finishes", async () => {
  const pending = deferred<{ deleted: boolean }>();
  mocks.deleteValidationLabel.mockReturnValue(pending.promise);
  await click("Delete");
  await render(makeCase("b"));
  await act(async () => pending.resolve({ deleted: true }));
  expect(input("Case ID").value).toBe("b");
  expect(input("Title").value).toBe("b");
});

it("does not overwrite refreshed labels with a late initial list", async () => {
  await act(async () => root.unmount());
  const pending = deferred<ValidationLabel[]>();
  mocks.validationLabels.mockReturnValueOnce(pending.promise).mockResolvedValue([reference({ title: "New saved reference" })]);
  root = createRoot(host); await render(makeCase("a"));
  await click("Save label");
  await act(async () => pending.resolve([reference({ title: "Old reference" })]));
  expect(host.querySelector(".labelRow")?.textContent).toContain("New saved reference");
  expect(host.querySelector(".labelRow")?.textContent).not.toContain("Old reference");
});

it("ignores a late initial-list error after a successful refresh", async () => {
  await act(async () => root.unmount());
  const pending = deferred<ValidationLabel[]>();
  mocks.validationLabels.mockReturnValueOnce(pending.promise).mockResolvedValue([reference()]);
  root = createRoot(host); await render(makeCase("a"));
  await click("Save label");
  await act(async () => pending.reject(new Error("OLD LIST FAILURE")));
  expect(host.querySelector('[role="alert"]')).toBeNull();
});

it("shows a failed request to open a validation result case", async () => {
  mocks.runValidation.mockResolvedValue({ metrics: {}, results: [{ case_id: "a", status: "evaluated", matches: [], result_card_matches: [], annotation_checks: [] }] });
  openCase.mockRejectedValue(new Error("Synthetic case open failure"));
  await click("Run"); await click("Open case for review");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Synthetic case open failure");
});

it("preserves polygon reference points during an edit/save round trip", async () => {
  const points: [number, number][] = [[0, 0], [10, 0], [10, 10]];
  mocks.validationLabels.mockResolvedValue([reference({ expected_annotations: [{ label: "polygon reference", coordinate_type: "polygon", required: true, points }] })]);
  await click("Run"); await click("Edit"); await click("Save label");
  expect(mocks.saveValidationLabel.mock.calls[0][0].expected_annotations[0].points).toEqual(points);
});
