// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReadingRoom } from "./main";
import type { CaseRecord } from "./types";

const activeCase: CaseRecord = {
  case_id: "case-1",
  title: "Synthetic review",
  metadata: {},
  annotations: [],
  chat_history: [],
  created_at: "2026-09-07T00:00:00Z",
  updated_at: "2026-09-07T00:00:00Z",
};

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
});

describe("Reading Room case lifecycle", () => {
  it("can leave the active case and start a new case without refreshing", async () => {
    const onNewCase = vi.fn();
    await act(async () => root.render(<ReadingRoom
      activeCase={activeCase}
      setActiveCase={vi.fn()}
      preview=""
      setPreview={vi.fn()}
      analysis={null}
      setAnalysis={vi.fn()}
      onOpenGuide={vi.fn()}
      onOpenLibrary={vi.fn()}
      onNewCase={onNewCase}
    />));

    const button = [...host.querySelectorAll("button")].find(item => item.textContent?.includes("New case"));
    expect(button).toBeTruthy();
    await act(async () => button!.click());
    expect(onNewCase).toHaveBeenCalledOnce();
  });

  it("keeps roadmap out and exposes detailed case identifiers", async () => {
    await act(async () => root.render(<ReadingRoom
      activeCase={null}
      setActiveCase={vi.fn()}
      preview=""
      setPreview={vi.fn()}
      analysis={null}
      setAnalysis={vi.fn()}
      onOpenGuide={vi.fn()}
      onOpenLibrary={vi.fn()}
      onNewCase={vi.fn()}
    />));

    expect(host.querySelector('option[value="Roadmap"]')).toBeNull();
    expect(host.textContent).toContain("Local record / NPM");
    expect(host.textContent).toContain("Accession number");
    expect(host.textContent).toContain("Clinical indication");
  });
});
