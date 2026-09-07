import React, { useState } from "react";
import type { RuntimeConfig } from "./types";
import { setupApi } from "./aiSetupApi";

const areas = [
  ["chest_xray_model", "Chest", "Toraks"], ["msk_xray_model", "MSK / trauma", "MSK / trauma"],
  ["abdomen_xray_model", "Abdomen / KUB", "Abdomen / KUB"], ["spine_xray_model", "Spine", "Tulang belakang"],
  ["skull_facial_xray_model", "Skull / face", "Tengkorak / wajah"], ["general_xray_model", "Unknown body area", "Area tubuh belum diketahui"],
] as const;
const tasks = [["vision_language_model", "Image review", "Tinjau gambar"], ["chat_model", "Chat", "Chat"], ["report_model", "Report drafting", "Penyusunan laporan"], ["classification_model", "Specialist classification", "Klasifikasi spesialis"]] as const;

export function RuntimePreferences({ runtime, onSaved, onConnect, language = "en" }: { runtime: RuntimeConfig; onSaved: () => Promise<void>; onConnect: () => void; language?: "id" | "en" }) {
  const isEn = language === "en";
  const copy = (en: string, id: string) => isEn ? en : id;
  const modelName = (value: string) => !value || value === "disabled" ? copy("Off", "Nonaktif") : value.startsWith("demo") ? copy("Built-in Demo", "Demo bawaan") : value.startsWith("torchxrayvision:") ? "TorchXRayVision DenseNet-121" : value;
  const [draft, setDraft] = useState<Partial<RuntimeConfig>>({
    cpu_only: runtime.cpu_only,
    review_depth: runtime.review_depth || "balanced",
    localization_confidence_threshold: runtime.localization_confidence_threshold ?? 0.25,
    annotation_auto_accept_threshold: runtime.annotation_auto_accept_threshold ?? 0.9,
    temperature: runtime.temperature ?? 0.2,
    top_p: runtime.top_p ?? 0.95,
    seed: runtime.seed ?? -1,
    max_output_tokens: runtime.max_output_tokens ?? 2048,
    request_timeout_seconds: runtime.request_timeout_seconds ?? 180,
    max_retries: runtime.max_retries ?? 1,
    download_connections: runtime.download_connections ?? 4,
    ...Object.fromEntries(areas.map(([key]) => [key, runtime[key]])),
  });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function save() {
    setBusy(true); setMessage("");
    try { await setupApi.preferences(draft); await onSaved(); setMessage(copy("AI preferences saved.", "Preferensi AI disimpan.")); }
    catch (error) { setMessage(error instanceof Error ? error.message : copy("Could not save preferences.", "Preferensi belum berhasil disimpan.")); }
    finally { setBusy(false); }
  }
  function applyPreset(preset: "safe" | "repeatable" | "exploratory") {
    const values = preset === "safe"
      ? { temperature: 0.2, top_p: 0.95, seed: -1, max_output_tokens: 2048, max_retries: 1 }
      : preset === "repeatable"
        ? { temperature: 0.1, top_p: 0.9, seed: 42, max_output_tokens: 2048, max_retries: 1 }
        : { temperature: 0.55, top_p: 0.9, seed: -1, max_output_tokens: 4096, max_retries: 1 };
    setDraft(current => ({ ...current, ...values }));
    setMessage(copy("Preset loaded. Review the values, then save.", "Preset dimuat. Tinjau nilainya, lalu simpan."));
  }
  return <>
    <section className="setupSection"><h3>{copy("Active models by task", "Model aktif per fungsi")}</h3><p>{copy("Connections and model tests are configured in Local AI or Online AI. These assignments show what MedRay will use.", "Koneksi dan tes model diatur melalui AI Lokal atau AI Online. Daftar ini menunjukkan model yang akan digunakan MedRay.")}</p>
      <dl className="setupChecks">{tasks.map(([key, en, id]) => <React.Fragment key={key}><dt>{copy(en, id)}</dt><dd>{modelName(String(runtime[key]))}</dd></React.Fragment>)}</dl>
      <p>{copy("Connection", "Koneksi")}: {runtime.primary_backend} · {runtime.allow_cloud ? copy("Online access allowed", "Akses online diizinkan") : copy("Local access only", "Hanya akses lokal")}</p><button onClick={onConnect}>{copy("Choose or change a model", "Pilih atau ganti model")}</button>
    </section>
    <section className="setupSection"><h3>{copy("Processing preferences", "Preferensi pemrosesan")}</h3><label>{copy("AI review depth", "Kedalaman tinjauan AI")}<select value={draft.review_depth || "balanced"} onChange={event => setDraft({ ...draft, review_depth: event.target.value as RuntimeConfig["review_depth"] })}><option value="focused">{copy("Focused — fastest", "Fokus — paling cepat")}</option><option value="balanced">{copy("Balanced — recommended", "Seimbang — disarankan")}</option><option value="thorough">{copy("Thorough — most detailed", "Menyeluruh — paling rinci")}</option></select></label><p>{copy("Controls prompt detail and checklist coverage. It does not increase clinical certainty or validate a model.", "Mengatur rincian prompt dan cakupan checklist. Pilihan ini tidak meningkatkan kepastian klinis atau memvalidasi model.")}</p><label className="setupCheck"><input type="checkbox" checked={draft.cpu_only} onChange={event => setDraft({ ...draft, cpu_only: event.target.checked })} />{copy("Prefer CPU for MedRay's embedded adapters", "Utamakan CPU untuk adapter bawaan MedRay")}</label><p>{copy("External applications manage their own GPU and memory settings. The embedded TorchXRayVision recipe uses CPU.", "Aplikasi eksternal mengatur GPU dan memorinya sendiri. Resep TorchXRayVision bawaan menggunakan CPU.")}</p>
      <div className="preferencePresets" aria-label={copy("Inference presets", "Preset inferensi")}>
        <span><b>{copy("Starting presets", "Preset awal")}</b><small>{copy("Load values first; nothing changes until you save.", "Muat nilai terlebih dahulu; tidak ada perubahan sampai Anda menyimpan.")}</small></span>
        <button onClick={() => applyPreset("safe")}>{copy("Safe default", "Bawaan aman")}</button>
        <button onClick={() => applyPreset("repeatable")}>{copy("Repeatable review", "Review konsisten")}</button>
        <button onClick={() => applyPreset("exploratory")}>{copy("Exploratory draft", "Draf eksploratif")}</button>
      </div>
      <details><summary>{copy("Advanced inference controls", "Kontrol inferensi lanjutan")}</summary>
        <p>{copy("Sampling controls are provider-dependent. For comparable validation runs, keep the model and all values fixed and use a non-negative seed.", "Kontrol sampling bergantung pada provider. Untuk membandingkan run validasi, pertahankan model dan semua nilai, lalu gunakan seed non-negatif.")}</p>
        <div className="advancedPreferenceGrid">
          <label>{copy("Temperature", "Temperature")}<input type="number" min="0" max="2" step="0.05" value={draft.temperature ?? 0.2} onChange={event => setDraft({ ...draft, temperature: Number(event.target.value) })} /><small>{copy("Lower is steadier; higher varies wording and candidates.", "Lebih rendah lebih stabil; lebih tinggi memvariasikan kata dan kandidat.")}</small></label>
          <label>Top-p<input type="number" min="0.05" max="1" step="0.05" value={draft.top_p ?? 0.95} onChange={event => setDraft({ ...draft, top_p: Number(event.target.value) })} /><small>{copy("Probability mass available during sampling.", "Massa probabilitas yang tersedia saat sampling.")}</small></label>
          <label>{copy("Seed (-1 = automatic)", "Seed (-1 = otomatis)")}<input type="number" min="-1" max="2147483647" step="1" value={draft.seed ?? -1} onChange={event => setDraft({ ...draft, seed: Number(event.target.value) })} /><small>{copy("A fixed seed improves repeatability when supported.", "Seed tetap meningkatkan konsistensi jika didukung.")}</small></label>
          <label>{copy("Maximum output tokens", "Token keluaran maksimum")}<input type="number" min="128" max="32768" step="128" value={draft.max_output_tokens ?? 2048} onChange={event => setDraft({ ...draft, max_output_tokens: Number(event.target.value) })} /></label>
          <label>{copy("Request timeout (seconds)", "Batas waktu request (detik)")}<input type="number" min="10" max="900" step="10" value={draft.request_timeout_seconds ?? 180} onChange={event => setDraft({ ...draft, request_timeout_seconds: Number(event.target.value) })} /></label>
          <label>{copy("Retry attempts", "Percobaan ulang")}<input type="number" min="0" max="5" step="1" value={draft.max_retries ?? 1} onChange={event => setDraft({ ...draft, max_retries: Number(event.target.value) })} /></label>
          <label>{copy("Download connections", "Koneksi download")}<input type="number" min="1" max="16" step="1" value={draft.download_connections ?? 4} onChange={event => setDraft({ ...draft, download_connections: Number(event.target.value) })} /></label>
          <label>{copy("Localization confidence threshold", "Ambang keyakinan lokalisasi")}<input type="number" min="0.05" max="0.95" step="0.05" value={draft.localization_confidence_threshold ?? 0.25} onChange={event => setDraft({ ...draft, localization_confidence_threshold: Number(event.target.value) })} /></label>
          <label>{copy("Annotation auto-accept suggestion threshold", "Ambang saran terima otomatis anotasi")}<input type="number" min="0.5" max="0.99" step="0.01" value={draft.annotation_auto_accept_threshold ?? 0.9} onChange={event => setDraft({ ...draft, annotation_auto_accept_threshold: Number(event.target.value) })} /></label>
        </div>
        <p>{copy("These controls are bounded and recorded with the runtime snapshot. Auto-accept remains a visual suggestion; human review is still required.", "Kontrol ini dibatasi dan direkam dalam snapshot runtime. Terima otomatis tetap hanya saran visual; tinjauan manusia tetap wajib.")}</p>
      </details>
      <h4>{copy("Image review by body area", "Tinjau gambar per area tubuh")}</h4><p>{copy("Use the selected image-review model or disable automatic review for an area. Existing specialist assignments are preserved. Configure and test models through their connection before assigning them.", "Gunakan model tinjau gambar yang dipilih atau nonaktifkan tinjauan otomatis untuk suatu area. Penetapan spesialis yang sudah ada dipertahankan. Hubungkan dan uji model sebelum menetapkannya.")}</p>
      {areas.map(([key, en, id]) => <label key={key}>{copy(en, id)}<select value={String(draft[key] || "inherit")} onChange={event => setDraft({ ...draft, [key]: event.target.value })}><option value="inherit">{copy("Use selected image-review model", "Gunakan model tinjau gambar terpilih")}</option><option value="disabled">{copy("Do not run image review", "Jangan jalankan tinjau gambar")}</option>{runtime.vision_language_model && !["disabled", "demo-vlm"].includes(runtime.vision_language_model) && <option value={runtime.vision_language_model}>{runtime.vision_language_model}</option>}{runtime[key] && !["inherit", "disabled", runtime.vision_language_model].includes(runtime[key]) && <option value={runtime[key]}>{runtime[key]} ({copy("existing assignment", "penetapan yang ada")})</option>}</select></label>)}
      <button disabled={busy} onClick={save}>{copy("Save preferences", "Simpan preferensi")}</button>{message && <p role="status">{message}</p>}
    </section>
  </>;
}
