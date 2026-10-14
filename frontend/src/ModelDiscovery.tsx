import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./services/api";
import type { HardwarePlan } from "./types";
import type { ModelDetail } from "./aiSetupApi";
import { setupApi } from "./aiSetupApi";

type Language = "id" | "en";
type Destination = "Local AI" | "Online AI" | "My Models" | "Downloads" | "Model Setup";

type SearchPayload = {
  source?: string;
  results?: Record<string, unknown>[];
  models?: Record<string, unknown>[];
  errors?: string[];
  queries_used?: string[];
  fallback_used?: boolean;
  error?: string;
};

type DiscoveryDetail = ModelDetail & {
  url?: string;
  fit_percent?: number;
  hardware_fit_percent?: number;
  vram_estimate?: string;
  quantization?: string;
  library_name?: string;
  datasets?: string[];
  downloads?: number;
  likes?: number;
  last_modified?: string;
  source_reference?: string;
  metadata_unavailable?: boolean;
  metadata_error?: string;
  card_readiness?: {
    status?: string;
    score?: number;
    checks?: { label?: string; passed?: boolean }[];
    missing?: string[];
    action_required?: string;
  };
};

const LIMIT = 12;

function asRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(item => item && typeof item === "object") as Record<string, unknown>[] : [];
}

function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function safeExternalUrl(value: unknown): string {
  try {
    const parsed = new URL(String(value || ""));
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
  } catch {
    return "";
  }
}

function sourceKey(model: Record<string, unknown>, fallback: string): string {
  const id = String(model.id || "");
  if (id.startsWith("hf:")) return "hf";
  if (id.startsWith("github:")) return "github";
  const source = String(model.source || fallback).toLowerCase();
  if (source.includes("hugging")) return "hf";
  if (source.includes("github")) return "github";
  if (source.includes("ollama")) return "ollama";
  return fallback;
}

function downloadFilename(repo: string, file: string): string {
  return `${repo}-${file}`.replaceAll("/", "-").replace(/[^a-zA-Z0-9._-]/g, "-").slice(-220);
}

export function ModelDiscovery({
  language = "en",
  onNavigate,
  onSelected,
  onDownloadsChanged,
}: {
  language?: Language;
  onNavigate: (tab: Destination) => void;
  onSelected: (detail: Record<string, unknown>) => void;
  onDownloadsChanged: () => Promise<void>;
}) {
  const isEn = language === "en";
  const [source, setSource] = useState("all");
  const [query, setQuery] = useState("chest xray cxr radiograph model");
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState<SearchPayload>({});
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<DiscoveryDetail | null>(null);
  const [hardware, setHardware] = useState<HardwarePlan | null>(null);
  const [hardwareBusy, setHardwareBusy] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState("classification_model");
  const [hfConfigured, setHfConfigured] = useState(false);
  const [githubConfigured, setGithubConfigured] = useState(false);
  const [hfToken, setHfToken] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [signInOpen, setSignInOpen] = useState(false);
  const [sortBy, setSortBy] = useState("fit");
  const [authNotice, setAuthNotice] = useState("");
  const detailRef = useRef<HTMLElement>(null);
  const mounted = useRef(false);

  async function refreshHardware() {
    setHardwareBusy(true);
    try {
      setHardware(await api.hardwareRecommendations());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setHardwareBusy(false);
    }
  }

  useEffect(() => {
    let alive = true;
    mounted.current = true;
    Promise.allSettled([api.hardwareRecommendations(), api.huggingFaceStatus(), api.githubStatus()]).then(results => {
      if (!alive) return;
      if (results[0].status === "fulfilled") setHardware(results[0].value);
      if (results[1].status === "fulfilled") setHfConfigured(results[1].value.configured);
      if (results[2].status === "fulfilled") setGithubConfigured(results[2].value.configured);
    });
    return () => { alive = false; mounted.current = false; };
  }, []);

  useEffect(() => {
    if (detail) detailRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [detail]);

  async function search(nextPage = page, nextSource = source, nextQuery = query) {
    setBusy(true);
    setError("");
    setDetail(null);
    try {
      const result = await api.modelSearch(nextSource, nextQuery, LIMIT, nextPage) as SearchPayload;
      if (result.error) throw new Error(result.error);
      setPayload(result);
      setPage(nextPage);
      setSearched(true);
    } catch (exc) {
      setPayload({});
      setSearched(true);
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function selectPurpose(slot: HardwarePlan["runtime_slots"][number]) {
    setSelectedSlot(slot.slot);
    setSource("all");
    setQuery(slot.query);
    await search(1, "all", slot.query);
  }

  async function review(model: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      const selected = await api.modelDetail(sourceKey(model, source), String(model.id || model.name || ""), String(model.url || "")) as unknown as DiscoveryDetail;
      if (!mounted.current) return;
      setDetail(selected);
      onSelected(selected as unknown as Record<string, unknown>);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function queueFile(file: string) {
    if (busy || !detail || detail.source !== "Hugging Face") return;
    const repo = detail.id.replace(/^hf:/, "");
    const path = file.split("/").map(encodeURIComponent).join("/");
    setBusy(true); setError("");
    try {
      await api.downloadModel(`https://huggingface.co/${repo}/resolve/main/${path}`, downloadFilename(repo, file));
      await onDownloadsChanged();
      if (mounted.current) onNavigate("Downloads");
    } catch (exc) {
      if (mounted.current) setError(exc instanceof Error ? exc.message : (isEn ? "Download could not be queued. Please retry." : "Unduhan belum masuk antrean. Coba lagi."));
    } finally { if (mounted.current) setBusy(false); }
  }

  async function updateAccount(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setAuthNotice("");
    try {
      await action();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  const rawResults = asRecords(payload.results).length ? asRecords(payload.results) : asRecords(payload.models);
  const results = useMemo(() => [...rawResults].sort((left, right) => {
    const field = sortBy === "hardware" ? "hardware_fit_percent" : sortBy === "maturity" ? "maturity_score" : "fit_percent";
    return Number(right[field] || 0) - Number(left[field] || 0);
  }), [rawResults, sortBy]);
  const slots = hardware?.runtime_slots || [];
  const errors = asStrings(payload.errors);
  const queries = asStrings(payload.queries_used);

  return <>
    <section className="setupSection discoveryIntro">
      <div className="setupStepTitle"><span>2</span><div><h3>{isEn ? "Find a model for a specific job" : "Cari model untuk fungsi tertentu"}</h3><p>{isEn ? "MedRay ranks public metadata by task fit and this computer's hardware. Ranking is guidance, not proof that a model is safe or compatible." : "MedRay mengurutkan metadata publik berdasarkan fungsi dan hardware komputer ini. Peringkat hanya panduan, bukan bukti model aman atau kompatibel."}</p></div></div>
      {hardware && <div className="hardwareSummary" aria-label={isEn ? "Detected hardware" : "Hardware terdeteksi"}>
        <div><b>{hardware.profile.cpu || (isEn ? "Unknown CPU" : "CPU tidak diketahui")}</b><span>{hardware.profile.cpu_count || "?"} core · {hardware.profile.os}</span></div>
        <div><b>{hardware.profile.ram_gb ? `${hardware.profile.ram_gb} GB RAM` : (isEn ? "RAM unknown" : "RAM tidak diketahui")}</b><span>{hardware.profile.tier_label}</span></div>
        <div><b>{hardware.profile.gpus?.length ? hardware.profile.gpus.map(gpu => gpu.name).join(", ") : (isEn ? "GPU not detected" : "GPU tidak terdeteksi")}</b><span>{hardware.profile.max_vram_gb ? `${hardware.profile.max_vram_gb} GB VRAM` : (isEn ? "VRAM unknown" : "VRAM tidak diketahui")}</span></div>
      </div>}
      <div className="setupActions"><button onClick={refreshHardware} disabled={hardwareBusy}>{hardwareBusy ? (isEn ? "Checking…" : "Memeriksa…") : (isEn ? "Check hardware again" : "Periksa ulang hardware")}</button><button onClick={() => setSignInOpen(true)}>{isEn ? "Sign in" : "Login sumber"}</button><span>{isEn ? "Sign-in is optional for public search." : "Login bersifat opsional untuk pencarian publik."}</span></div>

      <h4>{isEn ? "Choose the model's job" : "Pilih fungsi model"}</h4>
      <div className="purposeGrid">
        {slots.map(slot => <button key={slot.slot} className={selectedSlot === slot.slot ? "selected" : ""} aria-pressed={selectedSlot === slot.slot} disabled={busy} onClick={() => void selectPurpose(slot)}>
          <b>{slot.label}</b><span>{slot.recommendation}</span><em>{isEn ? "Suggested" : "Saran"}: {slot.recommended_model} · {slot.vram_estimate}</em>
        </button>)}
        {!slots.length && <p>{isEn ? "Hardware guidance is loading. You can still search below." : "Panduan hardware sedang dimuat. Anda tetap bisa mencari di bawah."}</p>}
      </div>

      <form className="discoverySearch" onSubmit={event => { event.preventDefault(); void search(1); }}>
        <label>{isEn ? "Search source" : "Sumber pencarian"}<select value={source} onChange={event => { setSource(event.target.value); setPage(1); setDetail(null); }}>
          <option value="all">{isEn ? "All available sources" : "Semua sumber tersedia"}</option>
          <option value="hf">Hugging Face</option><option value="github">GitHub</option><option value="ollama">{isEn ? "Installed Ollama models" : "Model Ollama terpasang"}</option>
        </select></label>
        <label>{isEn ? "What do you need?" : "Model apa yang dibutuhkan?"}<input value={query} onChange={event => setQuery(event.target.value)} placeholder={isEn ? "e.g. chest X-ray classifier" : "contoh: classifier chest X-ray"} /></label>
        <button className="primaryAction" disabled={busy || !query.trim()} type="submit">{busy ? (isEn ? "Searching…" : "Mencari…") : (isEn ? "Find models" : "Cari model")}</button>
      </form>
      {error && <div className="setupError" role="alert">{error}</div>}
      {errors.length > 0 && <p className="setupNotice">{isEn ? "Some sources failed; available results are still shown" : "Sebagian sumber gagal; hasil yang tersedia tetap ditampilkan"}: {errors.slice(0, 2).join(" · ")}</p>}
      {queries.length > 1 && <p className="searchExpansion">{isEn ? "Search expanded" : "Pencarian diperluas"}: {queries.slice(0, 4).join(" · ")}</p>}
    </section>

    <section className="setupSection">
      <div className="setupStepTitle"><span>3</span><div><h3>{isEn ? "Review candidates and compatibility" : "Tinjau kandidat dan kompatibilitas"}</h3><p>{isEn ? "Check runtime, license, provenance, files, and limitations before downloading anything." : "Periksa runtime, lisensi, provenance, file, dan keterbatasan sebelum mengunduh."}</p></div></div>
      <div className="resultToolbar">
        <span>{searched ? `${results.length} ${isEn ? "results on this page" : "hasil di halaman ini"}` : (isEn ? "Run a search to see candidates" : "Jalankan pencarian untuk melihat kandidat")}</span>
        <label>{isEn ? "Sort by" : "Urutkan"}<select value={sortBy} onChange={event => setSortBy(event.target.value)}><option value="fit">{isEn ? "Overall match" : "Kecocokan keseluruhan"}</option><option value="hardware">Hardware</option><option value="maturity">{isEn ? "Metadata maturity" : "Kelengkapan metadata"}</option></select></label>
      </div>
      <div className="discoveryResults">
        {results.map((model, index) => {
          const url = safeExternalUrl(model.url);
          return <article className="discoveryResult" key={String(model.id || index)}>
            <div className="discoveryResultHeader"><div><strong>{String(model.name || model.id || (isEn ? "Unnamed model" : "Model tanpa nama"))}</strong><span>{String(model.source || payload.source || "")}</span></div><b>{String(model.fit_percent ?? "?")}% {isEn ? "match" : "cocok"}</b></div>
            <dl><dt>Hardware </dt><dd>{String(model.hardware_fit_percent ?? "?")}%</dd><dt>{isEn ? "Task " : "Fungsi "}</dt><dd>{String(model.task_type || "unknown")}</dd><dt>VRAM </dt><dd>{String(model.vram_estimate || "unknown")}</dd></dl>
            <p>{String(model.fit_summary || model.reason || model.license || (isEn ? "Review source metadata before use." : "Tinjau metadata sumber sebelum digunakan."))}</p>
            <div className="setupActions"><button disabled={busy || sourceKey(model, source) === "ollama"} onClick={() => void review(model)}>{isEn ? "Review compatibility" : "Tinjau kompatibilitas"}</button>{sourceKey(model, source) === "ollama" && <button onClick={() => onNavigate("Local AI")}>{isEn ? "Set up in Local AI" : "Atur di AI Lokal"}</button>}{url && <a href={url} target="_blank" rel="noreferrer">{isEn ? "Open source page" : "Buka halaman sumber"}</a>}</div>
          </article>;
        })}
        {searched && !results.length && <p>{isEn ? "No candidates found. Try broader terms or another source." : "Kandidat tidak ditemukan. Coba kata yang lebih umum atau sumber lain."}</p>}
      </div>
      {searched && <div className="pagination" aria-label={isEn ? "Search pages" : "Halaman pencarian"}><button disabled={busy || page <= 1} onClick={() => void search(page - 1)}>{isEn ? "Previous" : "Sebelumnya"}</button><span>{isEn ? "Page" : "Halaman"} {page}</span><button disabled={busy || results.length < LIMIT} onClick={() => void search(page + 1)}>{isEn ? "Next" : "Berikutnya"}</button></div>}
    </section>

    {detail && <section ref={detailRef} className="setupSection modelCompatibility" aria-label={isEn ? "Model details" : "Detail model"}>
      <div className="modelDetailHeader"><div><h3>{detail.name}</h3><p>{detail.source} · {detail.pipeline_tag || detail.task_type || "unknown"}</p></div><button onClick={() => setDetail(null)}>{isEn ? "Close" : "Tutup"}</button></div>
      {detail.metadata_unavailable && <p className="setupNotice">{isEn ? "Live metadata is temporarily unavailable" : "Metadata langsung sementara tidak tersedia"}: {detail.metadata_error}</p>}
      <dl className="detailFacts">
        <div><dt>{isEn ? "Compatibility" : "Kompatibilitas"}</dt><dd>{detail.compatibility.status.replaceAll("_", " ")}</dd></div>
        <div><dt>{isEn ? "Required runtime" : "Runtime yang dibutuhkan"}</dt><dd>{detail.compatibility.runtime || (isEn ? "External runtime required" : "Memerlukan runtime eksternal")}</dd></div>
        <div><dt>{isEn ? "License" : "Lisensi"}</dt><dd>{detail.license || (isEn ? "Not declared" : "Tidak dicantumkan")}</dd></div>
        <div><dt>{isEn ? "Estimated hardware" : "Perkiraan hardware"}</dt><dd>{detail.vram_estimate || (isEn ? "Not verified" : "Belum diverifikasi")}</dd></div>
        <div><dt>{isEn ? "Model-card readiness" : "Kesiapan model card"}</dt><dd>{detail.card_readiness?.score ?? "?"}% · {detail.card_readiness?.status || (isEn ? "Needs review" : "Perlu ditinjau")}</dd></div>
        <div><dt>{isEn ? "Access" : "Akses"}</dt><dd>{detail.gated || detail.private ? (isEn ? "Permission or sign-in may be required" : "Mungkin memerlukan izin atau login") : (isEn ? "Public metadata" : "Metadata publik")}</dd></div>
      </dl>
      <p>{detail.compatibility.reason}</p>
      {detail.card_readiness?.missing?.length ? <p><b>{isEn ? "Missing review evidence" : "Bukti yang belum tersedia"}:</b> {detail.card_readiness.missing.join(", ")}</p> : null}
      {detail.readme_excerpt && <details><summary>{isEn ? "Model-card excerpt" : "Cuplikan model card"}</summary><p className="readmeExcerpt">{detail.readme_excerpt}</p></details>}
      <details><summary>{isEn ? "Advanced metadata and review checks" : "Metadata dan pemeriksaan lanjutan"}</summary><dl className="setupChecks"><dt>{isEn ? "Metadata source" : "Sumber metadata"}</dt><dd>{detail.source_reference || detail.source}</dd><dt>{isEn ? "Library" : "Pustaka"}</dt><dd>{detail.library_name || "unknown"}</dd><dt>Dataset</dt><dd>{detail.datasets?.join(", ") || (isEn ? "Not declared" : "Tidak dicantumkan")}</dd><dt>{isEn ? "Updated" : "Diperbarui"}</dt><dd>{detail.last_modified || "unknown"}</dd><dt>{isEn ? "Downloads / stars" : "Unduhan / bintang"}</dt><dd>{detail.downloads ?? "?"} / {detail.likes ?? "?"}</dd></dl>{detail.card_readiness?.checks?.length ? <ul>{detail.card_readiness.checks.map((check, index) => <li key={`${check.label}-${index}`}>{check.passed ? "✓" : "—"} {check.label}</li>)}</ul> : null}</details>
      {detail.files?.length ? <details><summary>{isEn ? `Repository files (${detail.files.length})` : `File repositori (${detail.files.length})`}</summary><p>{isEn ? "Only download a weights/config file when your chosen runtime supports it. Downloaded files stay inactive." : "Unduh file weights/config hanya jika didukung runtime pilihan. File unduhan tetap nonaktif."}</p><div className="repositoryFiles">{detail.files.map(file => <div key={file}><code>{file}</code>{detail.source === "Hugging Face" && <button disabled={busy} onClick={() => void queueFile(file)}>{isEn ? "Queue download" : "Masukkan antrean"}</button>}</div>)}</div></details> : null}
      <div className="setupActions">{detail.compatibility.status === "supported" ? <button className="primaryAction" onClick={() => onNavigate("Model Setup")}>{detail.compatibility.action}</button> : <><button onClick={() => onNavigate("Local AI")}>{isEn ? "Connect a local runtime" : "Hubungkan runtime lokal"}</button><button onClick={() => onNavigate("Online AI")}>{isEn ? "Connect an online provider" : "Hubungkan provider online"}</button></>}<button onClick={() => onNavigate("My Models")}>{isEn ? "Open My Models" : "Buka Model Saya"}</button></div>
    </section>}

    <details className="setupSection discoveryAdvanced" open={signInOpen} onToggle={event => setSignInOpen(event.currentTarget.open)}>
      <summary>{isEn ? "Advanced: source accounts" : "Lanjutan: akun sumber model"}</summary>
      <p>{isEn ? "Public search works without an account. Save a read-only token only for gated/private access or higher API limits." : "Pencarian publik berfungsi tanpa akun. Simpan token read-only hanya untuk akses gated/private atau batas API yang lebih tinggi."}</p>
      <div className="sourceAccounts">
        <section><h4>Hugging Face</h4><p>{hfConfigured ? (isEn ? "Token saved on this computer." : "Token tersimpan di komputer ini.") : (isEn ? "Not connected." : "Belum terhubung.")}</p><label>{isEn ? "Read-access token" : "Token akses baca"}<input type="password" autoComplete="off" value={hfToken} onChange={event => { setHfToken(event.target.value); setAuthNotice(""); }} /></label><div className="setupActions"><button disabled={busy || !hfToken.trim()} onClick={() => void updateAccount(async () => { const status = await api.saveHuggingFaceToken(hfToken); setHfConfigured(status.configured); setHfToken(""); setAuthNotice(isEn ? "Token saved locally." : "Token tersimpan secara lokal."); })}>{isEn ? "Save token" : "Simpan token"}</button><button disabled={busy || (!hfToken.trim() && !hfConfigured)} onClick={() => void updateAccount(async () => { const result = await setupApi.testHf(hfToken); setAuthNotice(result.detail); })}>{isEn ? "Test sign-in" : "Tes login"}</button><button disabled={busy || !hfConfigured} onClick={() => void updateAccount(async () => { const status = await api.clearHuggingFaceToken(); setHfConfigured(status.configured); setAuthNotice(isEn ? "Hugging Face disconnected." : "Koneksi Hugging Face diputus."); })}>{isEn ? "Disconnect" : "Putuskan"}</button><a href="https://huggingface.co/settings/tokens" target="_blank" rel="noreferrer">{isEn ? "Create token" : "Buat token"}</a></div>{authNotice && <p role="status">{authNotice}</p>}</section>
        <section><h4>GitHub</h4><p>{githubConfigured ? (isEn ? "Token saved on this computer." : "Token tersimpan di komputer ini.") : (isEn ? "Not connected." : "Belum terhubung.")}</p><label>{isEn ? "Fine-grained read token" : "Token baca fine-grained"}<input type="password" autoComplete="off" value={githubToken} onChange={event => { setGithubToken(event.target.value); setAuthNotice(""); }} /></label><div className="setupActions"><button disabled={busy || !githubToken.trim()} onClick={() => void updateAccount(async () => { const status = await api.saveGithubToken(githubToken); setGithubConfigured(status.configured); setGithubToken(""); setAuthNotice(isEn ? "GitHub token saved locally." : "Token GitHub tersimpan secara lokal."); })}>{isEn ? "Save token" : "Simpan token"}</button><button disabled={busy || (!githubToken.trim() && !githubConfigured)} onClick={() => void updateAccount(async () => { const result = await setupApi.testGitHub(githubToken); setAuthNotice(result.detail); })}>{isEn ? "Test GitHub sign-in" : "Tes login GitHub"}</button><button disabled={busy || !githubConfigured} onClick={() => void updateAccount(async () => { const status = await api.clearGithubToken(); setGithubConfigured(status.configured); setAuthNotice(isEn ? "GitHub disconnected." : "Koneksi GitHub diputus."); })}>{isEn ? "Disconnect" : "Putuskan"}</button></div></section>
      </div>
    </details>
  </>;
}
