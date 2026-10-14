import { json } from "./services/api";
import type { RuntimeConfig, DownloadJob } from "./types";

export interface SetupModel {
  model_id: string; display_name: string; source: string; task: string; runtime: string;
  status: string; ready_for_inference: boolean; detail: string; recommended_action: string;
  active?: boolean; artifact_status?: string; automatic_cpu_setup?: boolean;
  automatic_setup?: boolean; dataset?: string; scope?: string; resolution?: number;
  checks?: { name: string; status: string }[];
  job?: { status: string; download_id?: string; error_type?: string };
}
export interface SetupOverview { models: SetupModel[]; runtime: RuntimeConfig; provider_key_configured: boolean }
export interface Connection { backend: string; task: string; base_url: string; model: string; allow_cloud: boolean; provider?: string; language?: "id" | "en" }
export interface ConnectionTest { id: string; status: string; detail: string }
export interface ModelDetail { id: string; name: string; source: string; task_type?: string; pipeline_tag?: string; license?: string; vram_estimate?: string; gated?: boolean; private?: boolean; files?: string[]; readme_excerpt?: string; compatibility: { status: string; runtime: string | null; reason: string; action: string; model_id: string | null } }
export interface OllamaStatus { installed: boolean; running: boolean; detail: string; models: { name: string; status: string; detail: string }[] }
export interface SystemCheck { overall: string; checks: { name: string; status: string; detail: string }[]; hardware: { os: string; cpu: string; ram_gb: number | null; gpus: { name: string; vram_gb: number }[]; disk_free_gb: number | null; cuda: string; architecture: string } }
const post = <T,>(path: string, payload: unknown = {}) => json<T>(`/ai-setup${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const setupApi = {
  preferences: (values: Partial<RuntimeConfig>) => post<RuntimeConfig>("/preferences", values),
  connectionModels: (config: Connection) => post<{ models: { name: string }[]; detail: string }>("/connection/models", config),
  localAction: (action: string, model_id = "") => post(`/local/${action}`, { model_id }),
  importFile: (file: File) => { const form = new FormData(); form.append("file", file); return json("/ai-setup/local/import", { method: "POST", body: form }); },
  overview: () => json<SetupOverview>("/ai-setup"),
  xray: (action: string, model_id?: string) => post(`/xray/${action}`, model_id ? { model_id } : {}),
  demo: () => post("/demo"),
  system: () => json<SystemCheck>("/ai-setup/system"),
  ollama: (url: string) => json<OllamaStatus>(`/ai-setup/ollama?base_url=${encodeURIComponent(url)}`),
  testHf: (token: string) => post<{ ok: boolean; detail: string }>("/hf/test", { token }),
  testGitHub: (token: string) => post<{ ok: boolean; detail: string }>("/github/test", { token }),
  saveKey: (key: string, base_url: string) => post<{ configured: boolean }>("/provider-key", { key, base_url }),
  keyStatus: (base_url: string) => json<{ configured: boolean }>(`/ai-setup/provider-key?base_url=${encodeURIComponent(base_url)}`),
  detail: (source: string, id: string) => json<ModelDetail>(`/ai-setup/compatibility?source=${encodeURIComponent(source)}&id=${encodeURIComponent(id)}`),
  testConnection: (config: Connection) => post<ConnectionTest>("/connection/test", config),
  connectionResult: (id: string) => json<ConnectionTest>(`/ai-setup/connection/test/${id}`),
  activateConnection: (config: Connection, test_id: string) => post("/connection/activate", { ...config, test_id }),
};
export function statusLabel(status: string, language: "id" | "en" = "en") {
  const labels = language === "en"
    ? { ready: "Ready", needs_setup: "Needs setup", dependency_missing: "Dependency missing", downloading: "Downloading", installing: "Installing", testing: "Testing", configuration_required: "Configuration required", incompatible: "Incompatible", connection_failed: "Connection failed", needs_review: "Needs review", needs_validation: "Needs validation", error: "Error", core_ready: "Core ready" }
    : { ready: "Siap", needs_setup: "Perlu setup", dependency_missing: "Dependensi belum ada", downloading: "Mengunduh", installing: "Memasang", testing: "Menguji", configuration_required: "Perlu konfigurasi", incompatible: "Tidak kompatibel", connection_failed: "Koneksi gagal", needs_review: "Perlu ditinjau", needs_validation: "Perlu divalidasi", error: "Gagal", core_ready: "Core siap" };
  return (labels as Record<string, string>)[status] || status.replaceAll("_", " ");
}
export function canActivate(model: SetupModel) { return model.status === "ready" && model.ready_for_inference; }
export function busyDownload(job: DownloadJob) { return ["queued", "downloading", "pausing", "cancelling"].includes(job.status); }
