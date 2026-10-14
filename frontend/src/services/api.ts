import type { AnalysisResult, AnatomyRoute, AnnotationReviewExport, AuditBundle, CaseRecord, DatabaseLocation, DicomSafetyReport, DicomViewerProfile, DownloadJob, HardwarePlan, HuggingFaceAuthStatus, LocalModelArtifact, ModelCard, ReferenceCatalog, RuntimeConfig, StudyImage, ValidationLabel, ValidationResult, VisionAdapter } from "../types";

const CONFIGURED_API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8765/api";
let activeApiBase = CONFIGURED_API_BASE;

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); this.name = "ApiError"; }
}

async function tryFetch(url: string, init?: RequestInit, timeoutMs = 5000) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (init?.signal?.aborted) throw new Error("Request cancelled.");
  init?.signal?.addEventListener("abort", cancel, { once: true });
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    return { response, body: await response.text() };
  } finally {
    window.clearTimeout(timer);
    init?.signal?.removeEventListener("abort", cancel);
  }
}

function isMedRayHealth(health: unknown): boolean {
  if (!health || typeof health !== "object") return false;
  const value = health as Record<string, unknown>;
  return value.ok === true && (value.service === "medray-v2" || value.app === "MedRay v2");
}

async function discoverApiBase(signal?: AbortSignal | null) {
  const pageHost = window.location.hostname || "127.0.0.1";
  const alternateHost = pageHost === "localhost" ? "127.0.0.1" : "localhost";
  const candidates = [
    CONFIGURED_API_BASE,
    ...Array.from({ length: 11 }, (_item, index) => `http://${pageHost}:${8765 + index}/api`),
    ...Array.from({ length: 11 }, (_item, index) => `http://${alternateHost}:${8765 + index}/api`),
  ].filter((value, index, list) => list.indexOf(value) === index);
  const failures: string[] = [];
  for (const base of candidates) {
    try {
      const { response: res, body } = await tryFetch(`${base}/health`, { signal }, 1200);
      if (res.ok) {
        const health: unknown = JSON.parse(body);
        if (isMedRayHealth(health)) {
          activeApiBase = base;
          return base;
        }
      }
      failures.push(`${base} -> HTTP ${res.status}`);
    } catch {
      if (signal?.aborted) throw new Error("Request cancelled.");
      failures.push(`${base} -> no response`);
      // keep trying nearby backend ports
    }
  }
  throw new Error(`Backend offline. Jalankan start_medray_v2.bat lalu tunggu sampai Backend ready. Checked: ${failures.slice(0, 4).join("; ")}`);
}

export async function json<T>(path: string, init?: RequestInit): Promise<T> {
  let buffered: Awaited<ReturnType<typeof tryFetch>>;
  const method = String(init?.method || "GET").toUpperCase();
  const retryable = method === "GET" || method === "HEAD" || method === "OPTIONS";
  const timeout = path === "/ai-setup/local/import" ? 600000 : path.startsWith("/analysis/") || path.startsWith("/chat/") ? 360000 : 30000;
  try {
    buffered = await tryFetch(`${activeApiBase}${path}`, init, timeout);
  } catch {
    if (init?.signal?.aborted) throw new Error("Request cancelled.");
    if (!retryable) throw new Error("Backend request timed out or failed; the operation was not retried automatically.");
    const base = await discoverApiBase(init?.signal);
    buffered = await tryFetch(`${base}${path}`, init, timeout);
  }
  if (path === "/health" && retryable) {
    let validHealth = false;
    if (buffered.response.ok) {
      try { validHealth = isMedRayHealth(JSON.parse(buffered.body)); } catch { /* invalid health response */ }
    }
    if (!validHealth) {
      const base = await discoverApiBase(init?.signal);
      buffered = await tryFetch(`${base}${path}`, init, timeout);
    }
  }
  const res = buffered.response;
  if (!res.ok) {
    let detail = `Request failed (${res.status}). Please retry.`;
    try { const body = JSON.parse(buffered.body); if (typeof body.detail === "string") detail = body.detail; } catch { /* keep readable fallback */ }
    throw new ApiError(detail, res.status);
  }
  return JSON.parse(buffered.body) as T;
}

export const api = {
  health: () => json<{ ok: boolean; app: string; version: string }>("/health"),
  references: () => json<ReferenceCatalog>("/references"),
  anatomyProfiles: () => json<(Omit<AnatomyRoute, "anatomy" | "laterality" | "view" | "confidence" | "source" | "matched_term" | "selected_model" | "support_status" | "warnings"> & { id: string })[]>("/anatomy/profiles"),
  validationLabels: () => json<ValidationLabel[]>("/validation/labels"),
  saveValidationLabel: (payload: Partial<ValidationLabel>) => json<{ path: string; label: ValidationLabel }>("/validation/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }),
  deleteValidationLabel: (caseId: string) => json<{ deleted: boolean; case_id: string; path: string }>(`/validation/labels/${encodeURIComponent(caseId)}`, { method: "DELETE" }),
  curatedValidationFixture: () => json<{ path: string; fixture: Record<string, unknown> }>("/validation/fixtures/curated-sample"),
  runValidation: (exportReport = false) => json<ValidationResult>("/validation/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ export: exportReport })
  }),
  exportValidation: () => json<{ path: string; report: ValidationResult }>("/validation/export", { method: "POST" }),
  modelCards: () => json<ModelCard[]>("/model-cards"),
  hardwareRecommendations: () => json<HardwarePlan>("/models/hardware-recommendations"),
  upload: (file: File, caseTitle = "") => {
    const form = new FormData();
    form.append("file", file);
    form.append("case_title", caseTitle);
    return json<{ case: CaseRecord; image: Record<string, unknown>; preview_data_url: string }>("/upload", { method: "POST", body: form });
  },
  addStudyImage: (caseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return json<{ case: CaseRecord; image: StudyImage }>(`/cases/${encodeURIComponent(caseId)}/images`, { method: "POST", body: form });
  },
  setActiveStudyImage: (caseId: string, imageId: string) => json<CaseRecord>(`/cases/${encodeURIComponent(caseId)}/active-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_id: imageId })
  }),
  dicomSafety: (caseId: string, imageId: string) => json<DicomSafetyReport>(`/dicom/${encodeURIComponent(caseId)}/images/${encodeURIComponent(imageId)}/safety`),
  dicomViewerProfile: (caseId: string, imageId: string) => json<DicomViewerProfile>(`/dicom/${encodeURIComponent(caseId)}/images/${encodeURIComponent(imageId)}/viewer-profile`),
  exportDicomMetadata: (caseId: string, imageId: string) => json<{ path: string; payload: Record<string, unknown> }>(`/dicom/${encodeURIComponent(caseId)}/images/${encodeURIComponent(imageId)}/export-metadata`, { method: "POST" }),
  exportDeidentifiedDicom: (caseId: string, imageId: string, acknowledgeBurnedInRisk: boolean) => json<Record<string, unknown>>(`/dicom/${encodeURIComponent(caseId)}/images/${encodeURIComponent(imageId)}/export-deidentified`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ acknowledge_burned_in_risk: acknowledgeBurnedInRisk })
  }),
  analyze: (caseId: string, customPrompt: string, language = "id", anatomyProfileOverride = "") => {
    const form = new FormData();
    form.append("custom_prompt", customPrompt);
    form.append("language", language);
    form.append("anatomy_profile_override", anatomyProfileOverride);
    return json<AnalysisResult>(`/analysis/${encodeURIComponent(caseId)}`, { method: "POST", body: form });
  },
  cases: (q = "") => json<CaseRecord[]>(`/cases?q=${encodeURIComponent(q)}`),
  caseDetail: (id: string) => json<CaseRecord>(`/cases/${encodeURIComponent(id)}`),
  deleteCase: (id: string) => json<Record<string, unknown>>(`/cases/${encodeURIComponent(id)}`, { method: "DELETE" }),
  clearCases: () => json<Record<string, unknown>>("/cases", { method: "DELETE" }),
  saveCase: (payload: CaseRecord) => json<CaseRecord>("/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(payload.revision !== undefined ? { "If-Match": `"${payload.revision}"` } : {}) },
    body: JSON.stringify(payload)
  }),
  chat: (caseId: string, message: string, language: "id" | "en" = "en") => json<{ history: CaseRecord["chat_history"]; backend: string; fallback: boolean; revision?: number; case?: CaseRecord }>(`/chat/${encodeURIComponent(caseId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, language })
  }),
  runtime: () => json<RuntimeConfig>("/runtime"),
  databaseLocation: () => json<DatabaseLocation>("/storage/database"),
  setDatabaseLocation: (databaseFolder: string) => json<DatabaseLocation>("/storage/database", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ database_folder: databaseFolder })
  }),
  saveRuntime: (config: RuntimeConfig) => json<RuntimeConfig>("/runtime", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config)
  }),
  runtimeHealth: () => json<Record<string, unknown>>("/runtime/health"),
  visionAdapters: () => json<VisionAdapter[]>("/runtime/vision-adapters"),
  huggingFaceStatus: () => json<HuggingFaceAuthStatus>("/runtime/huggingface"),
  saveHuggingFaceToken: (token: string) => json<HuggingFaceAuthStatus>("/runtime/huggingface-token", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) }),
  clearHuggingFaceToken: () => json<HuggingFaceAuthStatus>("/runtime/huggingface-token", { method: "DELETE" }),
  githubStatus: () => json<HuggingFaceAuthStatus>("/runtime/github"),
  saveGithubToken: (token: string) => json<HuggingFaceAuthStatus>("/runtime/github-token", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) }),
  clearGithubToken: () => json<HuggingFaceAuthStatus>("/runtime/github-token", { method: "DELETE" }),
  modelSearch: (source: string, q: string, limit: number, page: number) => json<Record<string, unknown>>(`/models/search?source=${encodeURIComponent(source)}&q=${encodeURIComponent(q)}&limit=${encodeURIComponent(String(limit))}&page=${encodeURIComponent(String(page))}`),
  modelDetail: (source: string, id: string, url?: string) => json<Record<string, unknown>>(`/models/detail?source=${encodeURIComponent(source)}&id=${encodeURIComponent(id)}&url=${encodeURIComponent(url || "")}`),
  importModel: (path: string) => json<Record<string, unknown>>("/models/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }),
  localModels: () => json<LocalModelArtifact[]>("/models/local"),
  saveLocalModelCard: (payload: Record<string, unknown>) => json<Record<string, unknown>>("/models/model-card", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
  downloadModel: (url: string, filename?: string, connections?: number, checksumSha256?: string) => json<DownloadJob>("/models/download", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, filename, connections, checksum_sha256: checksumSha256 }) }),
  downloads: () => json<DownloadJob[]>("/models/downloads"),
  pauseDownload: (id: string) => json<DownloadJob>(`/models/downloads/${encodeURIComponent(id)}/pause`, { method: "POST" }),
  resumeDownload: (id: string) => json<DownloadJob>(`/models/downloads/${encodeURIComponent(id)}/resume`, { method: "POST" }),
  cancelDownload: (id: string) => json<DownloadJob>(`/models/downloads/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  retryDownload: (id: string) => json<DownloadJob>(`/models/downloads/${encodeURIComponent(id)}/retry`, { method: "POST" }),
  deleteDownload: (id: string) => json<{ id: string; status: string; partial_removed: boolean }>(`/models/downloads/${encodeURIComponent(id)}`, { method: "DELETE" }),
  exportReport: (caseId: string, format: string, language: string) => json<{ path: string }>(`/reports/${encodeURIComponent(caseId)}/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format, language }) }),
  exportAudit: (caseId: string) => json<{ path: string; bundle: AuditBundle }>(`/audit/${encodeURIComponent(caseId)}/export`),
  exportAnnotations: (caseId: string) => json<{ path: string }>(`/annotations/${encodeURIComponent(caseId)}/export`, { method: "POST" }),
  exportAnnotationReview: (caseId: string) => json<AnnotationReviewExport>(`/annotations/${encodeURIComponent(caseId)}/export-review-package`, { method: "POST" })
};

export const imageUrl = (path?: string) => path ? `${activeApiBase}/image?path=${encodeURIComponent(path)}` : "";
export const dicomPreviewUrl = (caseId: string, imageId: string, frame = 0, windowCenter?: number, windowWidth?: number, invert = false) => {
  const query = new URLSearchParams({ frame: String(frame), invert: String(invert) });
  if (Number.isFinite(windowCenter)) query.set("window_center", String(windowCenter));
  if (Number.isFinite(windowWidth)) query.set("window_width", String(windowWidth));
  return `${activeApiBase}/dicom/${encodeURIComponent(caseId)}/images/${encodeURIComponent(imageId)}/preview?${query}`;
};
