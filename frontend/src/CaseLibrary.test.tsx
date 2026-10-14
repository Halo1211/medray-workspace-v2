// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { cases } = vi.hoisted(() => ({
  cases: Array.from({ length: 30 }, (_item, index) => ({
    case_id: `case-${index + 1}`,
    title: `Synthetic case ${index + 1}`,
    metadata: {},
    annotations: [],
    chat_history: [],
    created_at: "2026-09-07T00:00:00Z",
    updated_at: "2026-09-07T00:00:00Z",
  })),
}));

vi.mock("./services/api", () => ({
  api: {
    cases: vi.fn().mockResolvedValue(cases),
    validationLabels: vi.fn().mockResolvedValue([]),
  },
  imageUrl: vi.fn((path: string) => path),
  dicomPreviewUrl: vi.fn((caseId: string, imageId: string) => `${caseId}/${imageId}`),
}));

import { CaseLibrary } from "./main";
import { api } from "./services/api";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.mocked(api.cases).mockReset().mockResolvedValue(cases);
});

describe("Case Library layout", () => {
  it("ignores an older search result arriving after the current query", async () => {
    let finishOld!: (value: typeof cases) => void;
    vi.mocked(api.cases).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; })).mockResolvedValueOnce([{ ...cases[0], title: "Current query result" }]);
    await act(async () => root.render(<CaseLibrary activeCase={null} analysis={null} onOpen={vi.fn()} onDeleted={vi.fn()} onCleared={vi.fn()} />));
    const input = host.querySelector<HTMLInputElement>(".libraryHeader input")!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "Current");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => finishOld(cases));
    expect(host.textContent).toContain("Current query result");
    expect(host.textContent).not.toContain("Synthetic case 30");
  });
  it("keeps validation reachable before a paginated long case registry", async () => {
    await act(async () => {
      root.render(<CaseLibrary activeCase={null} analysis={null} onOpen={vi.fn()} onDeleted={vi.fn()} onCleared={vi.fn()} />);
      await Promise.resolve();
    });

    const workspace = host.querySelector(".validationWorkspace");
    const registry = host.querySelector(".caseRegistry");
    expect(workspace).toBeTruthy();
    expect(registry).toBeTruthy();
    expect(workspace!.compareDocumentPosition(registry!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(host.textContent).toContain("Show 15 more (15 remaining)");
  });
});
