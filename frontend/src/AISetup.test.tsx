// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AISetup } from "./AISetup";
import { setupApi, canActivate } from "./aiSetupApi";
import { api } from "./services/api";

vi.mock("./services/api", () => ({ json: vi.fn(), api: {
  downloads: vi.fn(), huggingFaceStatus: vi.fn(), githubStatus: vi.fn(), modelSearch: vi.fn(),
  modelDetail: vi.fn(), hardwareRecommendations: vi.fn(), deleteDownload: vi.fn(),
  pauseDownload: vi.fn(), resumeDownload: vi.fn(), cancelDownload: vi.fn(), retryDownload: vi.fn(),
  downloadModel: vi.fn(), saveHuggingFaceToken: vi.fn(), clearHuggingFaceToken: vi.fn(),
  saveGithubToken: vi.fn(), clearGithubToken: vi.fn(),
} }));
vi.mock("./aiSetupApi", async importOriginal => ({ ...await importOriginal<typeof import("./aiSetupApi")>(), setupApi: { overview: vi.fn(), xray: vi.fn(), ollama: vi.fn(), system: vi.fn(), detail: vi.fn(), testConnection: vi.fn(), connectionModels: vi.fn(), testHf: vi.fn(), testGitHub: vi.fn(), preferences: vi.fn(), keyStatus: vi.fn(), saveKey: vi.fn(), connectionResult: vi.fn(), activateConnection: vi.fn() } }));
const model = { model_id: "xray", display_name: "TorchXRayVision DenseNet-121", source: "GitHub", runtime: "TorchXRayVision", task: "Classification", status: "dependency_missing", ready_for_inference: false, detail: "PyTorch is missing.", recommended_action: "Continue setup", automatic_cpu_setup: true, artifact_status: "not_downloaded", checks: [{ name: "PyTorch", status: "missing" }] };
let host: HTMLDivElement, root: Root;
async function click(text: string) {
  const button = [...host.querySelectorAll("button")].find(button => button.textContent === text);
  expect(button, `button ${text}`).toBeTruthy();
  await act(async () => { button!.click(); });
}
beforeEach(async () => {
  vi.clearAllMocks();
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.mocked(setupApi.overview).mockResolvedValue({ models: [model], runtime: { ollama_base_url: "http://127.0.0.1:11434", review_depth: "balanced" } as never, provider_key_configured: false });
  vi.mocked(api.downloads).mockResolvedValue([]);
  vi.mocked(setupApi.keyStatus).mockResolvedValue({ configured: false });
  vi.mocked(api.githubStatus).mockResolvedValue({ configured: false } as never);
  vi.mocked(api.huggingFaceStatus).mockResolvedValue({ configured: false } as never);
  vi.mocked(api.hardwareRecommendations).mockResolvedValue({
    profile: { detected_at: "now", os: "Windows", cpu: "Test CPU", cpu_count: 8, ram_gb: 16, gpus: [{ name: "Test GPU", vram_gb: 8 }], max_vram_gb: 8, tier: "mid", tier_label: "Mid-range GPU", detection_notes: [] },
    runtime_slots: [
      { slot: "classification_model", label: "X-ray analysis", task: "Classification", recommended_model: "DenseNet", source: "all", query: "chest xray classifier", recommendation: "Start with a reviewed classifier.", vram_estimate: "4GB-6GB", safety_note: "Research only" },
      { slot: "segmentation_model", label: "X-ray localization", task: "Localization", recommended_model: "Detector", source: "all", query: "xray detection", recommendation: "Validate coordinates first.", vram_estimate: "8GB", safety_note: "Research only" },
      { slot: "report_model", label: "Report & chat", task: "Report", recommended_model: "Small LLM", source: "all", query: "xray report llm", recommendation: "Keep human review.", vram_estimate: "4GB-8GB", safety_note: "Research only" },
    ],
    download_help: { queue: "Queued locally", not_runtime: "Not active after download", next_step: "Review and test" },
  });
  vi.mocked(setupApi.ollama).mockResolvedValue({ installed: true, running: true, detail: "Connected", models: [{ name: "local-model", status: "needs_setup", detail: "Test first" }] });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(<AISetup modelTools={() => <p>Model IDs</p>} onLater={vi.fn()} />));
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function changeControl(element: HTMLInputElement | HTMLSelectElement, value: string) {
  await act(async () => {
    const prototype = element instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLSelectElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new Event(element instanceof HTMLInputElement ? "input" : "change", { bubbles: true }));
  });
}

describe("connection setup regression audit", () => {
  it("does not use another provider's key status for the selected server", async () => {
    vi.mocked(setupApi.overview).mockResolvedValue({ models: [], runtime: { ollama_base_url: "http://127.0.0.1:11434" } as never, provider_key_configured: true });
    await click("Refresh status");
    await click("Online AI");
    const disconnect = [...host.querySelectorAll("button")].find(button => button.textContent === "Disconnect key")!;
    expect(disconnect.disabled).toBe(true);
    expect(host.querySelector<HTMLInputElement>('input[type="password"]')?.placeholder).toBe("Paste key");
    expect(setupApi.keyStatus).toHaveBeenCalledWith("https://api.openai.com/v1");
  });

  it("does not carry an unsaved key to a different provider", async () => {
    await click("Online AI");
    await changeControl(host.querySelector<HTMLInputElement>('input[type="password"]')!, "synthetic-key");
    expect(host.querySelector<HTMLInputElement>('input[type="password"]')!.value).toBe("synthetic-key");
    await click("Local AI");
    await click("Online AI");
    expect(host.querySelector<HTMLInputElement>('input[type="password"]')!.value).toBe("");
  });

  it("does not let an earlier key status overwrite a successful save", async () => {
    const pending = deferred<Awaited<ReturnType<typeof setupApi.keyStatus>>>();
    vi.mocked(setupApi.keyStatus).mockReturnValue(pending.promise);
    vi.mocked(setupApi.saveKey).mockResolvedValue({ configured: true });
    await click("Online AI");
    await changeControl(host.querySelector<HTMLInputElement>('input[type="password"]')!, "synthetic-key");
    await click("Save key");
    await act(async () => pending.resolve({ configured: false }));
    expect([...host.querySelectorAll("button")].find(button => button.textContent === "Disconnect key")!.disabled).toBe(false);
  });

  it("ignores key status from a previous server", async () => {
    const pending = deferred<Awaited<ReturnType<typeof setupApi.keyStatus>>>();
    vi.mocked(setupApi.keyStatus).mockReturnValueOnce(pending.promise).mockResolvedValue({ configured: false });
    await click("Online AI");
    await changeControl(host.querySelector<HTMLInputElement>('input[type="url"]')!, "https://other.example/v1");
    await act(async () => pending.resolve({ configured: true }));
    expect([...host.querySelectorAll("button")].find(button => button.textContent === "Disconnect key")!.disabled).toBe(true);
  });

  it("ignores a test result after the task changes", async () => {
    await click("Local AI");
    const modelSelect = [...host.querySelectorAll("select")].find(select => [...select.options].some(option => option.value === "local-model"))!;
    await changeControl(modelSelect, "local-model");
    const pending = deferred<Awaited<ReturnType<typeof setupApi.testConnection>>>();
    vi.mocked(setupApi.testConnection).mockReturnValue(pending.promise);
    await click("Test connection");
    const taskSelect = [...host.querySelectorAll("select")].find(select => [...select.options].some(option => option.value === "chat"))!;
    await changeControl(taskSelect, "chat");
    await act(async () => pending.resolve({ id: "old-test", status: "ready", detail: "OLD TASK SUCCESS" }));
    expect(host.textContent).not.toContain("OLD TASK SUCCESS");
    expect([...host.querySelectorAll("button")].find(button => button.textContent === "Use model")!.disabled).toBe(true);
  });

  it("accepts a successful test when the connection has not changed", async () => {
    await click("Local AI");
    const modelSelect = [...host.querySelectorAll("select")].find(select => [...select.options].some(option => option.value === "local-model"))!;
    await changeControl(modelSelect, "local-model");
    vi.mocked(setupApi.testConnection).mockResolvedValue({ id: "current-test", status: "ready", detail: "CURRENT TASK SUCCESS" });
    await click("Test connection");
    expect(host.textContent).toContain("CURRENT TASK SUCCESS");
    expect([...host.querySelectorAll("button")].find(button => button.textContent === "Use model")!.disabled).toBe(false);
  });

  it("accepts model detection for the current server", async () => {
    await click("Online AI");
    await act(async () => host.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click());
    vi.mocked(setupApi.connectionModels).mockResolvedValue({ models: [{ name: "current-model" }], detail: "CURRENT SERVER SUCCESS" });
    await click("Detect models");
    expect(host.querySelector('option[value="current-model"]')).toBeTruthy();
    expect(host.textContent).toContain("CURRENT SERVER SUCCESS");
  });

  it("ignores model detection results after the server URL changes", async () => {
    await click("Online AI");
    await act(async () => host.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click());
    const pending = deferred<Awaited<ReturnType<typeof setupApi.connectionModels>>>();
    vi.mocked(setupApi.connectionModels).mockReturnValue(pending.promise);
    await click("Detect models");
    await changeControl(host.querySelector<HTMLInputElement>('input[type="url"]')!, "https://other.example/v1");
    await act(async () => pending.resolve({ models: [{ name: "old-server-model" }], detail: "OLD SERVER SUCCESS" }));
    expect(host.querySelector('option[value="old-server-model"]')).toBeNull();
    expect(host.textContent).not.toContain("OLD SERVER SUCCESS");
  });

  it("does not replace an online endpoint when initial overview arrives late", async () => {
    await act(async () => root.unmount());
    const pending = deferred<Awaited<ReturnType<typeof setupApi.overview>>>();
    vi.mocked(setupApi.overview).mockReturnValue(pending.promise);
    root = createRoot(host);
    await act(async () => root.render(<AISetup modelTools={() => null} onLater={vi.fn()} />));
    await click("Online AI");
    await act(async () => pending.resolve({ models: [], runtime: { ollama_base_url: "http://127.0.0.1:5555" } as never, provider_key_configured: false }));
    expect(host.querySelector<HTMLInputElement>('input[type="url"]')!.value).toBe("https://api.openai.com/v1");
  });

  async function reviewDownload() {
    vi.mocked(api.modelSearch).mockResolvedValue({ results: [{ id: "hf:test/model", name: "test/model", source: "Hugging Face" }] });
    vi.mocked(api.modelDetail).mockResolvedValue({ id: "hf:test/model", name: "test/model", source: "Hugging Face", files: ["model.gguf"], compatibility: { status: "configuration_required", runtime: null, reason: "Test", action: "Connect", model_id: null } });
    await click("Find Models");
    await click("Find models");
    await click("Review compatibility");
  }

  it("shows a download queue failure and allows retry", async () => {
    await reviewDownload();
    vi.mocked(api.downloadModel).mockRejectedValue(new Error("Synthetic download queue error"));
    await click("Queue download");
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("Synthetic download queue error");
    expect([...host.querySelectorAll("button")].find(button => button.textContent === "Queue download")!.disabled).toBe(false);
    vi.mocked(api.downloadModel).mockResolvedValue({ id: "retried", status: "queued" } as never);
    await click("Queue download");
    expect(api.downloadModel).toHaveBeenCalledTimes(2);
    expect(host.textContent).toContain("Downloads store files on this computer");
  });

  it("blocks duplicate queue clicks while the request is pending", async () => {
    await reviewDownload();
    const pending = deferred<Awaited<ReturnType<typeof api.downloadModel>>>();
    vi.mocked(api.downloadModel).mockReturnValue(pending.promise);
    await click("Queue download");
    const button = [...host.querySelectorAll("button")].find(button => button.textContent === "Queue download")!;
    expect(button.disabled).toBe(true);
    await click("Queue download");
    expect(api.downloadModel).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve({ id: "queued", status: "queued" } as never));
    expect(host.textContent).toContain("Downloads store files on this computer");
  });

  it("keeps the current page when an earlier download queue finishes", async () => {
    await reviewDownload();
    const pending = deferred<Awaited<ReturnType<typeof api.downloadModel>>>();
    vi.mocked(api.downloadModel).mockReturnValue(pending.promise);
    await click("Queue download");
    await click("Local AI");
    await act(async () => pending.resolve({ id: "queued", status: "queued" } as never));
    expect(host.querySelector('nav button[aria-current="page"]')?.textContent).toBe("Local AI");
  });
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

describe("beginner AI setup", () => {
  it("shows a numbered four-stage setup flow", () => {
    const flow = host.querySelector('[aria-label="AI setup flow"]');
    expect(flow?.textContent).toContain("1");
    expect(flow?.textContent).toContain("Choose a goal");
    expect(flow?.textContent).toContain("2");
    expect(flow?.textContent).toContain("Connect or find");
    expect(flow?.textContent).toContain("3");
    expect(flow?.textContent).toContain("Technical test");
    expect(flow?.textContent).toContain("4");
    expect(flow?.textContent).toContain("Use model");
  });

  it("starts with tasks and keeps technical internals out of Quick Setup", () => {
    expect(host.textContent).toContain("What do you want AI to do?");
    expect(host.textContent).toContain("Use a model I already have");
    expect(host.querySelector("nav")?.textContent).not.toMatch(/Advanced|Localization|X-ray Vision/);
    expect(host.textContent).not.toContain("Technical internals");
    expect(host.textContent).not.toContain("Model IDs");
  });

  it("keeps specialist tools behind an explicit advanced control", async () => {
    expect(host.querySelector("nav")?.textContent).not.toContain("Find Models");
    await click("Show advanced tools");
    expect(host.querySelector("nav")?.textContent).toContain("Find Models");
    expect(host.querySelector("nav")?.textContent).toContain("AI Preferences");
  });

  it("follows the app language for the beginner and connection flow", async () => {
    await act(async () => root.render(<AISetup language="id" modelTools={() => null} onLater={vi.fn()} />));
    expect(host.textContent).toContain("Pilih tujuan");
    expect(host.textContent).toContain("AI ingin dipakai untuk apa?");
    await click("AI Lokal");
    expect(host.textContent).toContain("Pilih fungsi model");
    expect(host.textContent).toContain("Tes koneksi");
  });
  it("shows missing dependencies and setup action without offering activation", async () => {
    await click("My Models");
    await click("Continue setup");
    expect(host.textContent).toContain("PyTorch is missing");
    expect(host.textContent).toContain("Continue setup");
    expect(host.textContent).not.toContain("Use as classifier");
    await click("Continue setup");
    expect(setupApi.xray).toHaveBeenCalledWith("setup", "xray");
  });
  it("requires both backend ready state and successful test for activation", () => {
    expect(canActivate({ ...model, artifact_status: "downloaded" })).toBe(false);
    expect(canActivate({ ...model, status: "ready" })).toBe(false);
    expect(canActivate({ ...model, status: "ready", ready_for_inference: true })).toBe(true);
  });
  it("detects installed Ollama models for selection", async () => {
    await click("Local AI");
    expect(host.querySelector('option[value="local-model"]')).toBeTruthy();
    expect(host.textContent).not.toContain("ollama list");
    expect(host.textContent).toContain("Report drafting");
    expect(host.textContent).not.toContain("Report drafting (Indonesian)");
  });
  it("offers a bounded review-depth control for advanced users", async () => {
    await click("Show advanced tools");
    await click("AI Preferences");
    const depth = [...host.querySelectorAll("select")].find(select => [...select.options].some(option => option.value === "thorough"));
    expect(depth).toBeTruthy();
    expect(depth?.textContent).toContain("Balanced — recommended");
    expect(host.textContent).toContain("does not increase clinical certainty");
    expect(host.textContent).toContain("Temperature");
    expect(host.textContent).toContain("Top-p");
    expect(host.textContent).toContain("Seed");
    expect(host.textContent).toContain("Repeatable review");
    expect(host.textContent).toContain("Maximum output tokens");
    expect(host.textContent).toContain("Request timeout");
    expect(host.textContent).toContain("Download connections");
  });
  it("requires explicit cloud opt-in before testing", async () => {
    await click("Online AI");
    expect(host.textContent).toContain("may leave this computer");
    const checkbox = host.querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
    const button = [...host.querySelectorAll("button")].find(button => button.textContent === "Test connection")!;
    expect(button.disabled).toBe(true);
    expect(setupApi.testConnection).not.toHaveBeenCalled();
  });
  it("makes HF login visible and masks the token", async () => {
    await click("Find Models"); await click("Sign in");
    expect(host.querySelector('input[type="password"]')).toBeTruthy();
    expect(host.textContent).toContain("Sign-in is optional");
  });

  it("restores hardware-guided all-source search, rich ranking, and pagination", async () => {
    vi.mocked(api.modelSearch).mockResolvedValue({
      source: "All sources",
      results: Array.from({ length: 12 }, (_, index) => ({
        id: `hf:test/model-${index}`,
        name: `test/model-${index}`,
        source: "Hugging Face",
        task_type: "classification",
        fit_percent: index === 0 ? 87 : 70,
        hardware_fit_percent: index === 0 ? 92 : 75,
        vram_estimate: "4GB-6GB",
        fit_summary: "Reviewed metadata candidate",
      })),
      errors: [],
      queries_used: ["chest xray", "cxr"],
    });
    await click("Find Models");
    await click("Find models");
    expect(api.modelSearch).toHaveBeenCalledWith("all", expect.any(String), 12, 1);
    expect(host.textContent).toContain("87% match");
    expect(host.textContent).toContain("Hardware 92%");
    expect(host.textContent).toContain("Search expanded");
    await click("Next");
    expect(api.modelSearch).toHaveBeenLastCalledWith("all", expect.any(String), 12, 2);
  });

  it("keeps reviewed discovery metadata available for local model-card prefill", async () => {
    const tools = vi.fn((selected: Record<string, unknown> | null) => <p>Selected detail: {String(selected?.name || "none")}</p>);
    vi.mocked(api.modelSearch).mockResolvedValue({ results: [{ id: "hf:test/model", name: "test/model", source: "Hugging Face", fit_percent: 80 }] });
    vi.mocked(api.modelDetail).mockResolvedValue({ id: "hf:test/model", name: "test/model", source: "Hugging Face", compatibility: { status: "configuration_required", runtime: null, reason: "Use a runtime", action: "Connect", model_id: null } });
    await act(async () => root.render(<AISetup modelTools={tools} onLater={vi.fn()} />));
    await click("Find Models");
    await click("Find models");
    await click("Review compatibility");
    await click("My Models");
    expect(host.textContent).toContain("Selected detail: test/model");
    expect(tools).toHaveBeenLastCalledWith(expect.objectContaining({ name: "test/model" }));
  });

  it("can remove completed download history", async () => {
    vi.mocked(api.downloads).mockResolvedValue([{ id: "done", url: "https://example.test/model.gguf", name: "model.gguf", target_path: "model.gguf", status: "completed" }]);
    await click("Refresh status");
    await click("Show advanced tools");
    await click("Downloads");
    await click("Remove from list");
    expect(api.deleteDownload).toHaveBeenCalledWith("done");
  });
  it("shows backend failure without claiming setup is ready", async () => {
    vi.mocked(setupApi.overview).mockRejectedValue(new Error("Backend offline. Start MedRay and retry."));
    await click("Refresh status");
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("Backend offline");
  });
});
