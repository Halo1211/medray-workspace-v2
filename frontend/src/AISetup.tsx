import React, { useEffect, useRef, useState } from "react";
import { api } from "./services/api";
import { setupApi, canActivate, statusLabel, busyDownload } from "./aiSetupApi";
import type { SetupOverview, Connection, ConnectionTest, OllamaStatus, ModelDetail, SystemCheck } from "./aiSetupApi";
import type { DownloadJob } from "./types";
import "./aiSetup.css";
import { RuntimePreferences } from "./RuntimePreferences";
import { ModelDiscovery } from "./ModelDiscovery";
import { providerById, providersForLocation } from "./aiProviders";

type Tab = "Quick Setup" | "Model Setup" | "X-ray Classifiers" | "Local AI" | "Online AI" | "Find Models" | "My Models" | "Downloads" | "AI Preferences" | "System Check";
const guidedTabs: Tab[] = ["Quick Setup", "Local AI", "Online AI", "X-ray Classifiers", "My Models", "System Check"];
const advancedTabs: Tab[] = ["Find Models", "Downloads", "AI Preferences"];
const tabLabels: Record<"id" | "en", Record<Tab, string>> = {
  en: { "Quick Setup": "Quick Setup", "Model Setup": "Model Setup", "X-ray Classifiers": "X-ray Classifiers", "Local AI": "Local AI", "Online AI": "Online AI", "Find Models": "Find Models", "My Models": "My Models", Downloads: "Downloads", "AI Preferences": "AI Preferences", "System Check": "System Check" },
  id: { "Quick Setup": "Mulai", "Model Setup": "Setup Model", "X-ray Classifiers": "Classifier X-ray", "Local AI": "AI Lokal", "Online AI": "AI Online", "Find Models": "Cari Model", "My Models": "Model Saya", Downloads: "Unduhan", "AI Preferences": "Preferensi AI", "System Check": "Pemeriksaan Sistem" },
};
const initialConnection: Connection = { backend: "ollama", provider: "Ollama", task: "vision", base_url: "http://127.0.0.1:11434", model: "", allow_cloud: false };
const errorText = (error: unknown) => error instanceof Error ? error.message : "The operation failed. Please retry.";

export function AISetup({ modelTools, onLater, language = "en" }: { modelTools: (detail: Record<string, unknown> | null) => React.ReactNode; onLater: () => void; language?: "id" | "en" }) {
  const isEn = language === "en";
  const copy = (en: string, id: string) => isEn ? en : id;
  const [tab, setTab] = useState<Tab>("Quick Setup");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [data, setData] = useState<SetupOverview | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<DownloadJob[]>([]);
  const [connection, setConnection] = useState<Connection>(initialConnection);
  const [test, setTest] = useState<ConnectionTest | null>(null);
  const [connectionActivated, setConnectionActivated] = useState(false);
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const [key, setKey] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const connectionVersion = useRef(0);
  const viewVersion = useRef(0);
  const runVersion = useRef(0);
  const keyStatusVersion = useRef(0);
  const [detail, setDetail] = useState<ModelDetail | null>(null);
  const [system, setSystem] = useState<SystemCheck | null>(null);
  const [serverModels, setServerModels] = useState<{ name: string }[]>([]);
  const [providerId, setProviderId] = useState("ollama");
  const [selectedClassifierId, setSelectedClassifierId] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [downloadName, setDownloadName] = useState("");
  const [downloadConnections, setDownloadConnections] = useState(4);
  const [downloadChecksum, setDownloadChecksum] = useState("");

  async function refresh() {
    const [overview, downloads] = await Promise.all([setupApi.overview(), api.downloads()]);
    setData(overview); setJobs(downloads);
  }
  async function run(action: () => Promise<unknown>, message = "", isCurrent = () => true) {
    const view = viewVersion.current;
    const operation = ++runVersion.current;
    const current = () => view === viewVersion.current && isCurrent();
    setBusy(true); setError(""); setNotice("");
    try { await action(); if (current() && message) setNotice(message); }
    catch (exc) { if (current()) setError(errorText(exc)); }
    finally { if (operation === runVersion.current) setBusy(false); }
  }
  function runConnection(action: (current: () => boolean) => Promise<unknown>, message = "") {
    const version = connectionVersion.current;
    const current = () => version === connectionVersion.current;
    return run(() => action(current), message, current);
  }
  function resetConnectionContext() {
    connectionVersion.current++;
    setTest(null); setConnectionActivated(false); setKey(""); setServerModels([]); setOllama(null);
  }
  async function saveConnectionKey(value: string, current: () => boolean) {
    const status = await setupApi.saveKey(value, connection.base_url);
    if (!current()) return;
    keyStatusVersion.current++;
    setKeyConfigured(status.configured); setKey(""); setTest(null);
    await refresh();
  }
  useEffect(() => {
    let alive = true;
    const initialVersion = connectionVersion.current;
    Promise.all([setupApi.overview(), api.downloads()]).then(([overview, downloads]) => {
      if (!alive) return;
      setData(overview); setJobs(downloads);
      setDownloadConnections(overview.runtime.download_connections || 4);
      if (connectionVersion.current === initialVersion) setConnection(current => ({ ...current, base_url: overview.runtime.ollama_base_url }));
    }).catch(exc => { if (alive) setError(errorText(exc)); });
    return () => { alive = false; connectionVersion.current++; viewVersion.current++; runVersion.current++; };
  }, []);
  useEffect(() => {
    const request = ++keyStatusVersion.current;
    setKeyConfigured(false);
    if (connection.backend !== "openai-compatible" || !connection.base_url.trim()) return;
    let alive = true;
    setupApi.keyStatus(connection.base_url).then(status => { if (alive && request === keyStatusVersion.current) setKeyConfigured(status.configured); })
      .catch(() => { if (alive && request === keyStatusVersion.current) setKeyConfigured(false); });
    return () => { alive = false; };
  }, [connection.backend, connection.base_url]);
  const classifiers = data?.models.filter(model => model.runtime === "TorchXRayVision") || [];
  const xray = classifiers.find(model => model.model_id === selectedClassifierId) || classifiers[0];
  const xrayBusy = classifiers.some(model => ["installing", "downloading", "testing"].includes(model.status));
  useEffect(() => {
    if (!xrayBusy && !jobs.some(busyDownload)) return;
    let alive = true;
    const timer = window.setTimeout(() => {
      Promise.all([setupApi.overview(), api.downloads()]).then(([overview, downloads]) => {
        if (alive) { setData(overview); setJobs(downloads); }
      }).catch(exc => { if (alive) setError(errorText(exc)); });
    }, 2000);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [xrayBusy, data, jobs]);
  useEffect(() => {
    if (test?.status !== "testing") return;
    let alive = true;
    const timer = window.setTimeout(() => setupApi.connectionResult(test.id).then(value => { if (alive) setTest(value); }).catch(exc => { if (alive) { setError(errorText(exc)); setTest(null); } }), 1500);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [test]);
  function choose(next: Tab) {
    viewVersion.current++; runVersion.current++; setBusy(false); resetConnectionContext();
    setTab(next); setError(""); setNotice("");
    if (advancedTabs.includes(next)) setAdvancedOpen(true);
    if (next === "Local AI") {
      setProviderId("ollama");
      setConnection({ ...initialConnection, base_url: data?.runtime.ollama_base_url || initialConnection.base_url });
      void runConnection(async current => { const result = await setupApi.ollama(data?.runtime.ollama_base_url || initialConnection.base_url); if (current()) setOllama(result); });
    }
    if (next === "Online AI") {
      const provider = providerById("openai");
      setProviderId(provider.id);
      setConnection({ backend: provider.backend, provider: provider.name, task: "vision", base_url: provider.baseUrl, model: "", allow_cloud: false });
    }
    if (next === "System Check") void run(async () => setSystem(await setupApi.system()));
    if (next === "My Models") void runConnection(async current => { await refresh(); if (!current()) return; const result = await setupApi.ollama(data?.runtime.ollama_base_url || initialConnection.base_url); if (current()) setOllama(result); });
  }
  function changeConnection(values: Partial<Connection>) {
    connectionVersion.current++; setConnection(current => ({ ...current, ...values })); setTest(null); setConnectionActivated(false); setNotice(""); setError("");
    if (values.base_url !== undefined || values.backend !== undefined) { setServerModels([]); setOllama(null); setKey(""); setKeyConfigured(false); }
  }
  function selectProvider(id: string) {
    const provider = providerById(id);
    setProviderId(provider.id);
    changeConnection({ provider: provider.name, backend: provider.backend, base_url: provider.baseUrl, model: "", allow_cloud: false });
    if (provider.backend === "ollama") void runConnection(async current => { const result = await setupApi.ollama(provider.baseUrl); if (current()) setOllama(result); });
  }
  async function xrayAction(action: string) { await setupApi.xray(action, xray?.model_id); await refresh(); }
  async function downloadAction(job: DownloadJob, action: "pause" | "resume" | "cancel" | "retry" | "delete") {
    if (action === "delete") await api.deleteDownload(job.id);
    else await ({ pause: api.pauseDownload, resume: api.resumeDownload, cancel: api.cancelDownload, retry: api.retryDownload })[action](job.id);
    await refresh();
  }
  const queue = <section className="setupSection"><h3>{copy("Downloads", "Unduhan")}</h3><p>{copy("Downloads store files on this computer. A successful model test is a separate step.", "File unduhan disimpan di komputer ini. Model tetap perlu lulus tes sebelum dapat digunakan.")}</p>
    {!jobs.length && <p>{copy("No downloads yet.", "Belum ada unduhan.")}</p>}
    {jobs.map(job => <article className="setupDownload" key={job.id}><strong>{job.source === "github.com" && (job.name || "").startsWith("nih-pc") ? "TorchXRayVision weights" : job.name}</strong>
      <span>{statusLabel(job.status, language)} · {((job.bytes_read || 0) / 1024 / 1024).toFixed(1)} MB {job.total_bytes ? `${copy("of", "dari")} ${(job.total_bytes / 1024 / 1024).toFixed(1)} MB` : copy("received", "diterima")}</span>
      <small>{job.transfer_mode === "segmented" ? `${job.connections_used || 1} ${copy("parallel connections", "koneksi paralel")}` : copy("Single-stream / automatic fallback", "Single-stream / fallback otomatis")}{job.checksum_status === "verified" ? ` · SHA-256 ${copy("verified", "terverifikasi")}` : ""}</small>
      {busyDownload(job) && <progress aria-label="Download progress" max={100} value={job.total_bytes ? job.percent : undefined} />}
      {job.error && <p>{job.error}</p>}
      <div className="setupActions">{job.status === "downloading" && <button disabled={busy} onClick={() => run(() => downloadAction(job, "pause"))}>{copy("Pause", "Jeda")}</button>}
        {["paused", "failed"].includes(job.status) && <button disabled={busy} onClick={() => run(() => downloadAction(job, "resume"))}>{copy("Resume", "Lanjutkan")}</button>}
        {["failed", "cancelled"].includes(job.status) && <button disabled={busy} onClick={() => run(() => downloadAction(job, "retry"))}>{copy("Retry", "Coba lagi")}</button>}
        {["downloading", "queued", "paused"].includes(job.status) && <button disabled={busy} onClick={() => run(() => downloadAction(job, "cancel"))}>{copy("Cancel", "Batalkan")}</button>}
        {["completed", "failed", "cancelled"].includes(job.status) && <button disabled={busy} onClick={() => run(() => downloadAction(job, "delete"))}>{copy("Remove from list", "Hapus dari daftar")}</button>}</div>
    </article>)}</section>;

  const activeStep = tab === "Quick Setup" ? 1
    : ["Local AI", "Online AI"].includes(tab) ? (connectionActivated ? 4 : test ? 3 : 2)
    : ["Find Models", "My Models", "Downloads", "X-ray Classifiers"].includes(tab) ? 2
    : tab === "Model Setup" ? (xray?.active ? 4 : 3) : 4;
  const flow = isEn
    ? ["Choose a goal", "Connect or find", "Technical test", "Use model"]
    : ["Pilih tujuan", "Hubungkan atau cari", "Tes teknis", "Gunakan model"];
  const selectedProvider = providerById(providerId);
  const activeTaskConnection = data?.runtime.task_connections?.[connection.task as "vision" | "chat" | "report"];

  return <section className="aiSetup">
    <header className="setupHeader"><div><p>{isEn ? "Follow the four stages below. MedRay will keep optional technical settings out of the way until you need them." : "Ikuti empat tahap di bawah. Pengaturan teknis opsional disembunyikan sampai Anda membutuhkannya."}</p></div><button disabled={busy} onClick={() => run(refresh)}>{isEn ? "Refresh status" : "Perbarui status"}</button></header>
    <ol className="setupFlow" aria-label="AI setup flow">{flow.map((label, index) => { const step = index + 1; return <li key={label} className={step < activeStep ? "complete" : step === activeStep ? "active" : ""}><span>{step}</span><b>{label}</b></li>; })}</ol>
    <div className="setupLayout"><nav className="setupTabs" aria-label="AI Setup sections">
      {guidedTabs.map(item => <button key={item} aria-current={tab === item ? "page" : undefined} onClick={() => choose(item)}>{tabLabels[language][item]}</button>)}
      <button className="advancedToggle" aria-expanded={advancedOpen} onClick={() => setAdvancedOpen(value => !value)}>{advancedOpen ? (isEn ? "Hide advanced tools" : "Sembunyikan alat lanjutan") : (isEn ? "Show advanced tools" : "Tampilkan alat lanjutan")}</button>
      {advancedOpen && advancedTabs.map(item => <button key={item} aria-current={tab === item ? "page" : undefined} onClick={() => choose(item)}>{tabLabels[language][item]}</button>)}
    </nav><div className="setupContent">
    {error && <div className="setupError" role="alert"><strong>{copy("Could not complete this step.", "Langkah ini belum berhasil.")}</strong><p>{error}</p><button onClick={() => run(refresh)}>{copy("Retry status check", "Periksa ulang status")}</button></div>}
    {notice && <p role="status" className="setupNotice">{notice}</p>}
    {!data && !error && <p role="status">Checking MedRay…</p>}
    {tab === "Quick Setup" && <section className="setupSection"><div className="setupStepTitle"><span>1</span><div><h3>{isEn ? "What do you want AI to do?" : "AI ingin dipakai untuk apa?"}</h3><p>{isEn ? "Choose the closest goal. You can change it later." : "Pilih tujuan yang paling sesuai. Pilihan ini dapat diubah nanti."}</p></div></div>
      <div className="setupChoices">
        <article><strong>Built-in Demo</strong><p>{isEn ? "Try the complete workflow without installing a model." : "Coba alur lengkap tanpa memasang model."}</p><button disabled={busy || !data} onClick={() => run(async () => { await setupApi.demo(); await refresh(); }, isEn ? "Built-in Demo is active. You can open the Reading Room." : "Demo bawaan aktif. Anda dapat membuka Ruang Baca.")}>{isEn ? "Use Demo" : "Gunakan Demo"}</button></article>
        <article><strong>{isEn ? "Use a model I already have" : "Gunakan model yang sudah ada"}</strong><p>{isEn ? "Review detected models or import a weights file." : "Tinjau model yang terdeteksi atau impor file weights."}</p><button onClick={() => choose("My Models")}>{isEn ? "My Models" : "Model Saya"}</button></article>
        <article><strong>{isEn ? "Run a specialist chest X-ray classifier" : "Jalankan classifier khusus X-ray toraks"}</strong><p>{isEn ? "Choose among reviewed all-dataset, NIH, CheXpert, or RSNA recipes with guided installation." : "Pilih resep all-dataset, NIH, CheXpert, atau RSNA yang ditinjau dengan instalasi terpandu."}</p><button onClick={() => choose("X-ray Classifiers")}>{isEn ? "Choose classifier" : "Pilih classifier"}</button></article>
        <article><strong>{isEn ? "Image review or chat with local AI" : "Tinjau gambar atau chat dengan AI lokal"}</strong><p>{isEn ? "Connect Ollama, LM Studio, Jan, llama.cpp, vLLM, LocalAI, TGI, or LiteLLM." : "Hubungkan Ollama, LM Studio, Jan, llama.cpp, vLLM, LocalAI, TGI, atau LiteLLM."}</p><button onClick={() => choose("Local AI")}>{isEn ? "Local AI" : "AI Lokal"}</button></article>
        <article><strong>{isEn ? "Use an online AI provider" : "Gunakan provider AI online"}</strong><p>{isEn ? "You must explicitly allow case data to leave this computer." : "Anda harus memberi izin sebelum data kasus keluar dari komputer."}</p><button onClick={() => choose("Online AI")}>{isEn ? "Online AI" : "AI Online"}</button></article>
        <article><strong>{isEn ? "Find or download a model" : "Cari atau unduh model"}</strong><p>{isEn ? "Search Hugging Face, GitHub, and installed Ollama models." : "Cari di Hugging Face, GitHub, dan model Ollama yang terpasang."}</p><button onClick={() => choose("Find Models")}>{isEn ? "Find Models" : "Cari Model"}</button></article>
      </div><div className="setupActions"><button onClick={onLater}>{copy("Configure later", "Atur nanti")}</button></div>
      <p className="setupSafety">{copy("Research and education only. Every AI output requires verification by a qualified physician. “Ready” means technically tested, not clinically validated.", "Hanya untuk riset dan edukasi. Setiap keluaran AI harus diverifikasi dokter yang berkualifikasi. Status “Siap” berarti sudah diuji secara teknis, bukan tervalidasi secara klinis.")}</p>
    </section>}
    {tab === "X-ray Classifiers" && <section className="setupSection"><div className="setupStepTitle"><span>2</span><div><h3>{copy("Specialist chest X-ray classifiers", "Classifier khusus X-ray toraks")}</h3><p>{copy("Classifiers return bounded pathology scores; they do not draw annotations or replace VLM review. Pick a training cohort that matches your research question, then validate it on your own data.", "Classifier menghasilkan skor patologi terbatas; classifier tidak menggambar anotasi atau menggantikan tinjauan VLM. Pilih cohort pelatihan yang sesuai dengan pertanyaan riset, lalu validasi pada data Anda sendiri.")}</p></div></div><div className="classifierGrid">{classifiers.map(item => <article key={item.model_id} className={item.active ? "active" : ""}><div><strong>{item.display_name}</strong>{item.active && <span className="activeBadge">{copy("Active", "Aktif")}</span>}</div><p>{item.dataset}</p><small>{item.scope}</small><dl><dt>{copy("Input", "Input")}</dt><dd>{item.resolution} × {item.resolution}</dd><dt>{copy("Setup", "Setup")}</dt><dd>{item.automatic_setup ? copy("One guided flow", "Satu alur terpandu") : copy("Manual", "Manual")}</dd><dt>{copy("Status", "Status")}</dt><dd>{statusLabel(item.status, language)}</dd></dl><button onClick={() => { setSelectedClassifierId(item.model_id); choose("Model Setup"); }}>{item.ready_for_inference ? copy("Review or activate", "Tinjau atau aktifkan") : copy("Set up classifier", "Setup classifier")}</button></article>)}</div><p className="setupSafety">{copy("Dataset-specific models leave unsupported labels untrained. MedRay excludes empty targets, but their probabilities still require local calibration and qualified review.", "Model khusus dataset tidak melatih semua label. MedRay mengecualikan target kosong, tetapi probabilitasnya tetap memerlukan kalibrasi lokal dan tinjauan tenaga berkualifikasi.")}</p></section>}
    {tab === "Model Setup" && xray && <>
      <section className="setupSection"><button onClick={() => choose("X-ray Classifiers")}>{copy("Back to X-ray Classifiers", "Kembali ke Classifier X-ray")}</button><h3>{xray.display_name}</h3><p>{copy("Specialist chest X-ray classification · runs on this computer", "Klasifikasi khusus X-ray toraks · berjalan di komputer ini")}</p><p><b>{copy("Training source", "Sumber pelatihan")}:</b> {xray.dataset}</p><p>{xray.scope}</p>
        <strong className="setupStatus">{statusLabel(xray.status, language)}{xray.active ? copy(" · Active classifier", " · Classifier aktif") : ""}</strong><p role="status">{xray.detail}</p>
        <dl className="setupChecks">{xray.checks?.map(check => <React.Fragment key={check.name}><dt>{check.name}</dt><dd>{check.status}</dd></React.Fragment>)}</dl>
        <p>{copy("The guided setup installs MedRay's CPU dependencies, downloads official weights, then tests a synthetic image. Allow several minutes and at least 3 GB of free space.", "Setup terpandu memasang dependensi CPU MedRay, mengunduh weights resmi, lalu menguji gambar sintetis. Sediakan beberapa menit dan ruang kosong minimal 3 GB.")}</p>
        <div className="setupActions">
          {!canActivate(xray) && <button disabled={busy || xrayBusy || (!xray.automatic_cpu_setup && xray.status === "dependency_missing")} onClick={() => run(() => xrayAction("setup"))}>{xrayBusy ? copy("Setup in progress…", "Setup berlangsung…") : copy("Continue setup", "Lanjutkan setup")}</button>}
          {xray.artifact_status !== "downloaded" && <button disabled={busy || xrayBusy} onClick={() => run(() => xrayAction("download"))}>{copy("Download weights", "Unduh bobot model")}</button>}
          {xray.artifact_status === "downloaded" && <button disabled={busy || xrayBusy} onClick={() => run(() => xrayAction("test"))}>{copy("Test model", "Uji model")}</button>}
          {canActivate(xray) && <button disabled={busy || xray.active} onClick={() => run(() => xrayAction("activate"), copy("TorchXRayVision is active for chest classification. Open the Reading Room to use it.", "TorchXRayVision aktif untuk klasifikasi toraks. Buka Ruang Baca untuk menggunakannya."))}>{xray.active ? copy("Active classifier", "Classifier aktif") : copy("Use as classifier", "Gunakan sebagai classifier")}</button>}
          <button onClick={() => choose("System Check")}>{copy("Check this computer", "Periksa komputer ini")}</button>
        </div>
        <details><summary>GPU or guided installation</summary><p>This wizard uses a known CPU build. GPU installation depends on your OS, driver and CUDA support. MedRay does not guess a CUDA build. On other architectures, install matching dependencies in MedRay's environment before testing.</p><a href="https://pytorch.org/get-started/locally/" target="_blank" rel="noreferrer">Open official PyTorch guided setup</a></details>
        <details><summary>{copy("Model details", "Detail model")}</summary><p>{copy(`Source: ${xray.source}. Runtime: ${xray.runtime}. Input: chest X-ray; grayscale, center-cropped and resized to ${xray.resolution || 224} × ${xray.resolution || 224}. Outputs are uncalibrated research signals. This is not lesion localization or segmentation.`, `Sumber: ${xray.source}. Runtime: ${xray.runtime}. Masukan: X-ray dada; skala abu-abu, dipotong dari tengah, lalu diubah menjadi ${xray.resolution || 224} × ${xray.resolution || 224}. Keluaran merupakan sinyal riset yang belum dikalibrasi, bukan lokalisasi atau segmentasi lesi.`)}</p><a href="https://github.com/mlmed/torchxrayvision" target="_blank" rel="noreferrer">{copy("Read official model documentation and license", "Baca dokumentasi dan lisensi model resmi")}</a><pre>{JSON.stringify(xray.job, null, 2)}</pre></details>
      </section><button onClick={() => choose("Downloads")}>{copy("View download progress", "Lihat progres unduhan")}</button></>}
    {(tab === "Local AI" || tab === "Online AI") && <section className="setupSection setupConnection"><div className="setupStepTitle"><span>2</span><div><h3>{tab === "Online AI" ? copy("Online AI", "AI Online") : copy("Connect local AI", "Hubungkan AI lokal")}</h3><p>{copy("Choose a task and a running model service. MedRay will test this exact combination before it can be used.", "Pilih fungsi dan layanan model yang sedang berjalan. MedRay akan menguji kombinasi ini sebelum model dapat digunakan.")}</p></div></div>
      <label>{tab === "Local AI" ? copy("Application / runtime", "Aplikasi / runtime") : copy("Provider", "Provider")}<select value={providerId} onChange={event => selectProvider(event.target.value)}>{providersForLocation(tab === "Local AI" ? "local" : "online").map(provider => <option key={provider.id} value={provider.id}>{provider.name}</option>)}</select></label>
      <div className="providerSummary"><div><b>{selectedProvider.name}</b><span>{selectedProvider.backend === "ollama" ? "Native Ollama API" : "OpenAI-compatible API"}</span></div><div className="providerCapabilities">{selectedProvider.capabilities.map(capability => <span key={capability}>{capability === "vision" ? "VLM" : capability === "chat" ? copy("chat", "percakapan") : copy("report", "laporan")}</span>)}</div><p>{language === "en" ? selectedProvider.note : selectedProvider.noteId}</p>{selectedProvider.docsUrl && <a href={selectedProvider.docsUrl} target="_blank" rel="noreferrer">{copy("Open official setup documentation", "Buka dokumentasi setup resmi")}</a>}</div>
      <label>{copy("What should this model do?", "Pilih fungsi model")}<select value={connection.task} onChange={event => changeConnection({ task: event.target.value })}><option value="vision">{copy("Image review / VLM", "Tinjau gambar / VLM")}</option><option value="chat">{copy("Chat assistant", "Asisten chat")}</option><option value="report">{copy("Report drafting", "Penyusunan laporan")}</option></select></label>
      {connection.backend === "ollama" ? <>
        <p>{copy("Installed", "Terpasang")}: {ollama ? ollama.installed ? copy("Yes", "Ya") : copy("Not detected on PATH", "Tidak ditemukan di PATH") : copy("Not checked", "Belum diperiksa")} · {copy("Running", "Berjalan")}: {ollama ? ollama.running ? copy("Yes", "Ya") : copy("No", "Tidak") : copy("Not checked", "Belum diperiksa")}</p>
        {ollama && !ollama.running && <p>{ollama.installed ? copy("Open the Ollama app, then retry.", "Buka aplikasi Ollama, lalu coba lagi.") : copy("Install or open Ollama, then retry.", "Pasang atau buka Ollama, lalu coba lagi.")} {ollama.detail}</p>}
        <div className="setupActions"><a href="https://ollama.com/download" target="_blank" rel="noreferrer">{copy("Ollama install guide", "Panduan instalasi Ollama")}</a><button disabled={busy} onClick={() => runConnection(async current => { const result = await setupApi.ollama(connection.base_url); if (current()) setOllama(result); })}>{copy("Retry / refresh models", "Coba lagi / perbarui model")}</button></div>
        <label>{copy("Installed model", "Model terpasang")}<select value={connection.model} onChange={event => changeConnection({ model: event.target.value })}><option value="">{copy("Select an installed model", "Pilih model yang terpasang")}</option>{ollama?.models.map(model => <option key={model.name} value={model.name}>{model.name}</option>)}</select></label>
        {ollama?.running && !ollama.models.length && <p>{copy("No installed models. Use the Ollama app to download or import a compatible model, then refresh. Image review requires a vision model; MedRay tests it with a synthetic image.", "Belum ada model terpasang. Unduh atau impor model yang kompatibel melalui aplikasi Ollama, lalu perbarui daftar. Tinjau gambar memerlukan model vision dan akan diuji dengan gambar sintetis.")}</p>}
        <details><summary>{copy("Connection address", "Alamat koneksi")}</summary><label>Ollama URL<input value={connection.base_url} onChange={event => changeConnection({ base_url: event.target.value })} /></label></details>
      </> : <>
        <p>{copy("Use any server that implements the compatible chat-completions protocol. Image review requires a vision model; report drafting requires structured text output. Test the task you want to use.", "Gunakan server yang mendukung protokol chat-completions kompatibel. Tinjau gambar membutuhkan model vision, sedangkan penyusunan laporan membutuhkan keluaran teks terstruktur. Uji fungsi yang ingin Anda gunakan.")}</p>
        {tab === "Local AI" && <><ol><li>{copy(`Install and open ${selectedProvider.name}.`, `Pasang dan buka ${selectedProvider.name}.`)}</li><li>{copy("Download and load a model that supports the selected task.", "Unduh dan muat model yang mendukung fungsi terpilih.")}</li><li>{copy("Enable its local API server, then click Detect models.", "Aktifkan server API lokal, lalu klik Deteksi model.")}</li></ol></>}
        <label>Server URL<input type="url" value={connection.base_url} onChange={event => changeConnection({ base_url: event.target.value })} placeholder={tab === "Online AI" ? "https://your-provider.example/v1" : "http://127.0.0.1:1234/v1"} /></label>
        <div className="setupActions"><button disabled={busy || !connection.base_url || (tab === "Online AI" && !connection.allow_cloud)} onClick={() => runConnection(async current => { const result = await setupApi.connectionModels(connection); if (!current()) return; setServerModels(result.models); setNotice(result.models.length ? result.detail : copy("No models are exposed by this server. Load one in the server application, then retry.", "Server ini belum menyediakan model. Muat model di aplikasi server, lalu coba lagi.")); })}>{copy("Detect models", "Deteksi model")}</button></div>
        <label>{copy("Detected models", "Model terdeteksi")}<select value={connection.model} onChange={event => changeConnection({ model: event.target.value })}><option value="">{copy("Choose a model", "Pilih model")}</option>{serverModels.map(model => <option key={model.name} value={model.name}>{model.name}</option>)}</select></label>
        <details><summary>{copy("My provider requires a model name manually", "Provider saya memerlukan nama model manual")}</summary><label>{copy("Model name", "Nama model")}<input value={connection.model} onChange={event => changeConnection({ model: event.target.value })} placeholder={copy("Name shown by your server or provider", "Nama yang ditampilkan server atau provider")} /></label></details>
        <label>{copy("API key (optional for some local servers)", "API key (opsional untuk beberapa server lokal)")}<input type="password" autoComplete="off" value={key} onChange={event => { connectionVersion.current++; setKey(event.target.value); setTest(null); }} placeholder={keyConfigured ? copy("A key is saved on this computer", "Key tersimpan di komputer ini") : copy("Paste key", "Tempel key")} /></label>
        <div className="setupActions"><button disabled={busy || !key.trim() || !connection.base_url} onClick={() => runConnection(current => saveConnectionKey(key, current), copy("API key saved locally.", "API key disimpan secara lokal."))}>{copy("Save key", "Simpan key")}</button><button disabled={busy || !keyConfigured} onClick={() => runConnection(current => saveConnectionKey("", current), copy("Saved key removed. Keys supplied by the launcher environment must be removed from that environment.", "Key tersimpan telah dihapus. Key dari environment launcher harus dihapus dari environment tersebut."))}>{copy("Disconnect key", "Putuskan key")}</button></div>
      </>}
      {tab === "Online AI" && <div className="setupSafety"><p>{copy("Data sent to this provider may leave this computer.", "Data yang dikirim ke provider dapat keluar dari komputer ini.")}</p><label className="setupCheck"><input type="checkbox" checked={connection.allow_cloud} onChange={event => changeConnection({ allow_cloud: event.target.checked })} />{copy("I allow this online provider to receive case data when I use it.", "Saya mengizinkan provider online ini menerima data kasus saat digunakan.")}</label></div>}
      {test && <p role="status"><strong>{statusLabel(test.status, language)}</strong> — {test.detail}</p>}
      <p className="taskAssignmentNote">{activeTaskConnection ? copy(`Currently assigned for this task: ${activeTaskConnection.provider || activeTaskConnection.backend} · ${activeTaskConnection.model}. Activating a replacement changes only ${connection.task}; other task assignments remain active.`, `Saat ini untuk fungsi ini: ${activeTaskConnection.provider || activeTaskConnection.backend} · ${activeTaskConnection.model}. Aktivasi pengganti hanya mengubah ${connection.task}; fungsi lain tetap aktif.`) : copy(`No tested provider is assigned to ${connection.task} yet. Vision, chat, and report can each use a different server.`, `Belum ada provider teruji untuk ${connection.task}. Vision, chat, dan laporan dapat memakai server yang berbeda.`)}</p>
      <div className="connectionStages"><div><span>3</span><div><b>{copy("Technical test", "Tes teknis")}</b><p>{copy("Uses only a generated test prompt or synthetic image.", "Hanya memakai prompt uji atau gambar sintetis yang dibuat otomatis.")}</p><button disabled={busy || !connection.model || !connection.base_url || !!key || test?.status === "testing" || (tab === "Online AI" && !connection.allow_cloud)} onClick={() => runConnection(async current => { const result = await setupApi.testConnection({ ...connection, language }); if (current()) setTest(result); })}>{copy("Test connection", "Tes koneksi")}</button></div></div>
        <div><span>4</span><div><b>{copy("Use model", "Gunakan model")}</b><p>{copy("Activation is limited to the task selected above.", "Aktivasi hanya berlaku untuk fungsi yang dipilih di atas.")}</p><button disabled={busy || test?.status !== "ready" || !!key} onClick={() => runConnection(async current => { await setupApi.activateConnection({ ...connection, language }, test!.id); if (!current()) return; setConnectionActivated(true); await refresh(); }, copy("Model activated for the selected task.", "Model diaktifkan untuk fungsi yang dipilih."))}>{copy("Use model", "Gunakan model")}</button></div></div></div>
      {!!key && <p>{copy("Save the key before testing.", "Simpan key sebelum menjalankan tes.")}</p>}
    </section>}
    {tab === "Find Models" && <ModelDiscovery language={language} onNavigate={choose} onSelected={value => setDetail(value as unknown as ModelDetail)} onDownloadsChanged={refresh} />}
    {tab === "My Models" && <><section className="setupSection"><div className="setupStepTitle"><span>2</span><div><h3>{copy("My Models", "Model Saya")}</h3><p>{copy("Model readiness is checked by MedRay. Clinical validation is separate from technical readiness.", "Kesiapan teknis model diperiksa MedRay. Validasi klinis tetap merupakan proses terpisah.")}</p></div></div>
      {!!data?.runtime.task_connections && Object.entries(data.runtime.task_connections).map(([task, assigned]) => assigned && <article className="setupModelRow activeProviderRow" key={task}><div><strong>{task === "vision" ? copy("Image review / VLM", "Tinjau gambar / VLM") : task === "chat" ? copy("Chat assistant", "Asisten chat") : copy("Report drafting", "Penyusunan laporan")}</strong><p>{assigned.provider || assigned.backend} · {assigned.model}</p><small>{assigned.base_url}</small></div><button onClick={() => choose(assigned.allow_cloud ? "Online AI" : "Local AI")}>{copy("Change", "Ubah")}</button></article>)}
      {data?.models.filter(model => !model.model_id.startsWith("local:")).map(model => <article className="setupModelRow" key={model.model_id}><div><strong>{model.display_name}</strong><p>{model.task} · {model.runtime}</p><b>{statusLabel(model.status, language)}{model.active ? copy(" · Active", " · Aktif") : ""}</b><p>{model.detail}</p></div><button disabled={busy} onClick={() => model.model_id === "demo" ? run(async () => { await setupApi.demo(); await refresh(); }, copy("Built-in Demo activated.", "Demo bawaan diaktifkan.")) : model.runtime === "TorchXRayVision" ? (setSelectedClassifierId(model.model_id), choose("Model Setup")) : choose("Local AI")}>{model.recommended_action}</button></article>)}
      {ollama?.models.map(model => <article className="setupModelRow" key={model.name}><div><strong>{model.name}</strong><p>Ollama · Installed · Test the desired task before use</p></div><button onClick={() => { choose("Local AI"); setConnection({ ...initialConnection, model: model.name, base_url: data?.runtime.ollama_base_url || initialConnection.base_url }); }}>Set up / use</button></article>)}
      <button onClick={() => choose("Local AI")}>{copy("Detect server models", "Deteksi model server")}</button></section>{modelTools(detail as unknown as Record<string, unknown> | null)}</>}
    {tab === "System Check" && <section className="setupSection"><h3>{copy("MedRay System Check", "Pemeriksaan Sistem MedRay")}</h3><button disabled={busy} onClick={() => run(async () => setSystem(await setupApi.system()))}>{copy("Run checks again", "Jalankan pemeriksaan lagi")}</button>
      {system && <><p><strong>{statusLabel(system.overall, language)}</strong></p><dl className="setupChecks">{system.checks.map(check => <React.Fragment key={check.name}><dt>{check.name}</dt><dd>{statusLabel(check.status, language)} · {check.detail}</dd></React.Fragment>)}<dt>Frontend</dt><dd>{copy("Loaded in this browser", "Dimuat di browser ini")}</dd></dl><h4>{copy("This computer", "Komputer ini")}</h4><dl className="setupChecks"><dt>OS / CPU</dt><dd>{system.hardware.os} · {system.hardware.cpu}</dd><dt>RAM</dt><dd>{system.hardware.ram_gb ? `${system.hardware.ram_gb} GB` : copy("Unknown", "Tidak diketahui")}</dd><dt>GPU / VRAM</dt><dd>{system.hardware.gpus.length ? system.hardware.gpus.map(gpu => `${gpu.name}: ${gpu.vram_gb} GB`).join(", ") : copy("Unknown / not detected", "Tidak diketahui / tidak terdeteksi")}</dd><dt>CUDA</dt><dd>{system.hardware.cuda}</dd></dl><p>{copy("Choose a runtime for the model and task you need. Installed packages and GPU memory alone do not establish model readiness.", "Pilih runtime sesuai model dan fungsi yang dibutuhkan. Paket terpasang dan memori GPU saja tidak membuktikan kesiapan model.")}</p><div className="setupActions"><button onClick={() => choose("X-ray Classifiers")}>{copy("Check specialist classifiers", "Periksa classifier khusus")}</button><button onClick={() => choose("Local AI")}>{copy("Configure AI providers", "Atur provider AI")}</button><button onClick={() => choose("Find Models")}>{copy("Check model sources", "Periksa sumber model")}</button></div></>}
    </section>}
    {tab === "Downloads" && <><section className="setupSection"><h3>{copy("Download a model file", "Unduh file model")}</h3><p>{copy("Uses adaptive HTTP byte ranges like desktop download managers when the server supports them, then safely falls back to one stream. Hugging Face users should prefer Hub/Xet downloads for repository snapshots.", "Menggunakan rentang byte HTTP adaptif seperti pengelola unduhan desktop bila server mendukungnya, lalu beralih dengan aman ke satu aliran. Untuk snapshot repositori Hugging Face, utamakan unduhan Hub/Xet.")}</p><label>File URL<input type="url" value={downloadUrl} onChange={event => setDownloadUrl(event.target.value)} /></label><label>{copy("Save as (optional)", "Simpan sebagai (opsional)")}<input value={downloadName} onChange={event => setDownloadName(event.target.value)} /></label><label>{copy("Parallel connections", "Koneksi paralel")}<input type="number" min="1" max="16" value={downloadConnections} onChange={event => setDownloadConnections(Number(event.target.value))} /></label><label>{copy("Expected SHA-256 (recommended, optional)", "SHA-256 yang diharapkan (disarankan, opsional)")}<input value={downloadChecksum} onChange={event => setDownloadChecksum(event.target.value.trim())} pattern="[0-9a-fA-F]{64}" /></label><button disabled={busy || !downloadUrl.trim() || downloadConnections < 1 || downloadConnections > 16 || (!!downloadChecksum && !/^[0-9a-f]{64}$/i.test(downloadChecksum))} onClick={() => run(async () => { await api.downloadModel(downloadUrl, downloadName || undefined, downloadConnections, downloadChecksum || undefined); setDownloadUrl(""); setDownloadName(""); setDownloadChecksum(""); await refresh(); })}>{copy("Start download", "Mulai unduh")}</button></section>{queue}</>}
    {tab === "AI Preferences" && data && <RuntimePreferences language={language} runtime={data.runtime} onSaved={refresh} onConnect={() => choose("Local AI")} />}
  </div></div></section>;
}
