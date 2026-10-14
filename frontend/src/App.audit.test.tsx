// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { CaseRecord } from "./types";

const mocks = vi.hoisted(() => ({ health: vi.fn(), cases: vi.fn(), caseDetail: vi.fn(), validationLabels: vi.fn(), saveCase: vi.fn() }));
vi.mock("./services/api", () => ({ api: mocks, imageUrl: (path: string) => path, dicomPreviewUrl: () => "" }));
import { App } from "./main";

let root: Root;
let host: HTMLDivElement;
const record = (id: string): CaseRecord => ({ case_id: id, title: id, metadata: {}, annotations: [], chat_history: [], created_at: "2026-10-14", updated_at: "2026-10-14" });
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.resetAllMocks();
  vi.stubGlobal("localStorage", { getItem: vi.fn(() => null), setItem: vi.fn() });
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  mocks.health.mockResolvedValue({ ok: true });
  mocks.cases.mockResolvedValue([record("old"), record("new")]);
  mocks.validationLabels.mockResolvedValue([]);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it.each(["getItem", "setItem"] as const)("starts when browser preference %s is blocked", async method => {
  vi.spyOn(window.localStorage, method).mockImplementation(() => { throw new DOMException("Browser storage blocked", "SecurityError"); });
  await expect(act(async () => root.render(<App />))).resolves.toBeUndefined();
  expect(host.querySelector("h1")?.textContent).toBe("Dashboard");
  expect(host.textContent).toContain("App ready");
});

async function openLibrary() {
  await act(async () => root.render(<App />));
  const button = [...host.querySelectorAll<HTMLButtonElement>("nav button")].find(button => button.textContent === "Case Library")!;
  await act(async () => button.click());
}

it("keeps the most recently requested case when opens complete out of order", async () => {
  let old!: (value: CaseRecord) => void;
  let latest!: (value: CaseRecord) => void;
  mocks.caseDetail.mockImplementation((id: string) => new Promise(resolve => { if (id === "old") old = resolve; else latest = resolve; }));
  await openLibrary();
  const buttons = host.querySelectorAll<HTMLButtonElement>(".caseRowActions .primaryAction");
  await act(async () => buttons[0].click());
  await act(async () => buttons[1].click());
  await act(async () => latest(record("new")));
  await act(async () => old(record("old")));
  expect([...host.querySelectorAll<HTMLInputElement>("input")].map(input => input.value)).toContain("new");
  expect([...host.querySelectorAll<HTMLInputElement>("input")].map(input => input.value)).not.toContain("old");
});

it("shows case-open errors in the library", async () => {
  mocks.caseDetail.mockRejectedValue(new Error("Synthetic case read failure"));
  await openLibrary();
  await act(async () => host.querySelector<HTMLButtonElement>(".caseRowActions .primaryAction")!.click());
  expect(host.querySelector(".caseListViewport .warn")?.textContent).toContain("Synthetic case read failure");
});

it("ignores a case open after the reviewer navigates away", async () => {
  let finish!: (value: CaseRecord) => void;
  mocks.caseDetail.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await openLibrary();
  await act(async () => host.querySelector<HTMLButtonElement>(".caseRowActions .primaryAction")!.click());
  const guide = [...host.querySelectorAll<HTMLButtonElement>("nav button")].find(button => button.textContent === "Guide")!;
  await act(async () => guide.click());
  await act(async () => finish(record("old")));
  expect(host.querySelector("h1")?.textContent).toBe("Guide");
});

it("does not let an unmounted editor replace a newly opened case after saving", async () => {
  const old = { ...record("old"), revision: 1, active_image_id: "old:0", images: [{ image_id: "old:0", index: 0, filename: "synthetic.png", preview_path: "synthetic.png", image_path: "synthetic.png", metadata: {} }], annotations: [{ id: "manual", label: "synthetic", confidence: 1, source: "manual user annotation", explanation: "synthetic", visible: true, source_image_id: "old:0", coordinate: { type: "point", x: 10, y: 10, width: 0, height: 0 } }] };
  mocks.caseDetail.mockImplementation(async id => id === "old" ? old : record("new"));
  let finish!: (value: CaseRecord) => void;
  mocks.saveCase.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await openLibrary();
  await act(async () => host.querySelectorAll<HTMLButtonElement>(".caseRowActions .primaryAction")[0].click());
  await act(async () => [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Annotations")!.click());
  await act(async () => host.querySelector<HTMLButtonElement>(".annotationSelect")!.click());
  await act(async () => host.querySelector<HTMLButtonElement>('button[title="Hide annotation"]')!.click());
  await act(async () => [...host.querySelectorAll<HTMLButtonElement>("nav button")].find(button => button.textContent === "Case Library")!.click());
  await act(async () => host.querySelectorAll<HTMLButtonElement>(".caseRowActions .primaryAction")[1].click());
  await act(async () => finish({ ...old, revision: 2 }));
  expect([...host.querySelectorAll<HTMLInputElement>("input")].map(input => input.value)).toContain("new");
});

it("retains the saved revision and local draft when returning to the same case", async () => {
  const old: CaseRecord = { ...record("old"), revision: 1, active_image_id: "old:0", images: [{ image_id: "old:0", index: 0, filename: "synthetic.png", preview_path: "synthetic.png", image_path: "synthetic.png", metadata: {} }], annotations: [{ id: "manual", label: "synthetic", confidence: 1, source: "manual user annotation", explanation: "synthetic", visible: true, source_image_id: "old:0", coordinate: { type: "point", x: 10, y: 10, width: 0, height: 0 } }] };
  mocks.caseDetail.mockResolvedValue(old);
  let finish!: (value: CaseRecord) => void;
  mocks.saveCase.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })).mockImplementation(async value => value);
  await openLibrary();
  await act(async () => host.querySelectorAll<HTMLButtonElement>(".caseRowActions .primaryAction")[0].click());
  const annotations = () => [...host.querySelectorAll<HTMLButtonElement>(".sideTabs button")].find(button => button.textContent === "Annotations")!;
  await act(async () => annotations().click());
  await act(async () => host.querySelector<HTMLButtonElement>(".annotationSelect")!.click());
  await act(async () => host.querySelector<HTMLButtonElement>('button[title="Hide annotation"]')!.click());
  await act(async () => [...host.querySelectorAll<HTMLButtonElement>("nav button")].find(button => button.textContent === "Case Library")!.click());
  await act(async () => finish({ ...old, revision: 2 }));
  await act(async () => [...host.querySelectorAll<HTMLButtonElement>("nav button")].find(button => button.textContent === "Reading Room")!.click());
  await act(async () => annotations().click());
  await act(async () => host.querySelector<HTMLButtonElement>(".annotationSelect")!.click());
  const show = host.querySelector<HTMLButtonElement>('button[title="Show annotation"]');
  expect(show).not.toBeNull();
  await act(async () => show!.click());
  expect(mocks.saveCase.mock.calls[1][0].revision).toBe(2);
});
