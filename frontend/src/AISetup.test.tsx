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
vi.mock("./aiSetupApi", async importOriginal => ({ ...await importOriginal<typeof import("./aiSetupApi")>(), setupApi: { overview: vi.fn(), xray: vi.fn(), ollama: vi.fn(), system: vi.fn(), detail: vi.fn(), testConnection: vi.fn(), connectionModels: vi.fn(), testHf: vi.fn(), testGitHub: vi.fn(), preferences: vi.fn() } }));
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
