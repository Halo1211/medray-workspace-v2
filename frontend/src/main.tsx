import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Archive,
  Bot,
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  Crosshair,
  Download,
  FileText,
  FolderOpen,
  HardDrive,
  Layers,
  Library,
  Lock,
  MessageSquare,
  MousePointer2,
  Moon,
  Pause,
  Pentagon,
  Plus,
  Circle,
  Ruler,
  Undo2,
  Redo2,
  RotateCw,
  FlipHorizontal2,
  FlipVertical2,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Stethoscope,
  Square,
  Sun,
  Trash2,
  Upload,
  Eye,
  EyeOff,
  Unlock,
  XCircle,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import { api, dicomPreviewUrl, imageUrl } from "./services/api";
import { annotationsForImage, buildGroundedReviewStatements, linkAnnotationEvidence, preferredAnnotations } from "./annotationLinks";
import { coordinatePoints, hasPointCoordinate, hasPolygonCoordinate, isValidPolygonPoints, polygonArea, polygonBounds } from "./annotationGeometry";
import { commitAnnotationChange, createAnnotationHistory, measureAnnotation, redoAnnotationChange, undoAnnotationChange } from "./annotationWorkspace";
import { EMPTY_CASE_METADATA, annotationConfidencePercent, annotationOrigin, buildValidationRerunPrompt, caseMetadataDraft, createFreshCaseWorkspaceState, filterWorkspaceAnnotations, mergeCaseMetadata, type AnnotationWorkspaceFilter, type CaseMetadataDraft } from "./caseWorkspace";
import type { AnalysisResult, Annotation, AnnotationReviewExport, CaseRecord, DatabaseLocation, DicomSafetyReport, DicomTag, DicomViewerProfile, DifferentialCandidate, DownloadJob, HardwarePlan, HuggingFaceAuthStatus, LocalModelArtifact, ModelCard, ReferenceCatalog, ResultCard, ResultEvidence, RuntimeConfig, StudyImage, ValidationLabel, ValidationResult, VisionAdapter } from "./types";
import "./styles.css";
import { AISetup } from "./AISetup";
import { setupApi } from "./aiSetupApi";

type Page = "Dashboard" | "Reading Room" | "Case Library" | "User Guide" | "Model Finder" | "Runtime Settings" | "General Settings" | "About";
type WorkspaceTab = "AI Output" | "Result Cards" | "Annotations" | "Report" | "AI Chat" | "Trust" | "DICOM Safety";
type ImageBoxSize = { displayWidth: number; displayHeight: number; naturalWidth: number; naturalHeight: number };
type AnnotationTool = "select" | "box" | "point" | "polygon" | "ellipse" | "length";
type AnnotationReviewStatus = NonNullable<Annotation["review_status"]>;
type UiLanguage = "id" | "en";

const UI_COPY = {
  id: {
    pages: {
      Dashboard: "Dasbor",
      "Reading Room": "Ruang Baca",
      "User Guide": "Panduan",
      "Model Finder": "Cari Model",
      "Runtime Settings": "AI Setup",
      "General Settings": "Pengaturan Umum",
      "Case Library": "Daftar Kasus",
      About: "Tentang",
    } satisfies Record<Page, string>,
    backendOffline: "Aplikasi belum terhubung",
    starting: "Memulai",
    themeLight: "Terang",
    themeDark: "Gelap",
    languageSwitch: "English",
    interfaceSettings: "Tampilan",
    interfaceDescription: "Atur bahasa antarmuka dan tema aplikasi.",
    theme: "Tema",
    darkMode: "Gelap",
    lightMode: "Terang",
    connectionSettings: "Port & koneksi AI",
    connectionDescription: "Atur alamat koneksi model lokal atau model tersambung.",
    programSetup: "Model AI tambahan (opsional)",
    programSetupDescription: "Aplikasi dapat langsung dipakai. Bagian ini hanya diperlukan jika ingin menghubungkan model AI tambahan.",
    alternativeModels: "Alternatif model",
    alternativeModelsDescription: "Daftar singkat model dan pustaka publik yang dapat dicari melalui Cari Model atau digunakan jika sudah terpasang secara lokal.",
    customModel: "Model khusus",
    customModelDescription: "Masukkan nama model yang sudah dipasang, lalu pilih fungsi analisisnya.",
    customBackend: "Jenis koneksi",
    customSlot: "Target slot",
    customModelName: "Nama model khusus",
    applyCustomModel: "Gunakan model",
    runtimeGuide: "Panduan model AI",
    runtimeGuideDescription: "Lihat cara menghubungkan model tambahan dan fitur yang sudah siap digunakan.",
    runtimeSettings: "Pengaturan AI",
    runtimeDescription: "Pilih sumber model dan pengaturan keamanan analisis.",
    modelSlots: "Slot model",
    runtimeFlags: "Opsi keamanan",
    saveSettings: "Simpan pengaturan",
    testRuntime: "Tes koneksi AI",
    activeCase: "Kasus Aktif",
    noCase: "Belum ada kasus",
    backend: "Mode analisis",
    confidence: "Keyakinan hasil",
    workflow: "Alur kerja",
    caseConsole: "Konsol Kasus",
    upload: "Unggah PNG/JPG/DICOM",
    runWorkflow: "Jalankan Analisis",
    customPrompt: "Instruksi tambahan untuk analisis...",
    uploadToStart: "Unggah X-ray untuk memulai.",
    annotations: "anotasi",
    labels: "label",
    processing: "Memproses...",
    noAnalysis: "Belum ada analisis.",
    metadata: "Metadata",
    noFile: "Belum ada file.",
    quality: "Kualitas",
    results: "Hasil",
    trace: "Jejak proses",
    reportTitle: "Draf Laporan",
    language: "Bahasa",
    indonesian: "Indonesia",
    english: "English",
    reportEmpty: "Belum ada laporan.",
    reportCopy: "Salin Laporan",
    exportDone: "Ekspor selesai",
    caseSearch: "Cari kasus",
    open: "Buka",
    noCases: "Belum ada kasus.",
    chatTitle: "Asisten Radiologi",
    chatPlaceholder: "apa temuan utama? buatkan laporan? jelaskan anotasi?",
    send: "Kirim",
    chooseCase: "Pilih atau unggah kasus terlebih dahulu.",
    disclaimer: "hanya untuk riset, edukasi, dan pembuatan prototipe. Bukan PACS/RIS atau alat diagnosis klinis resmi. Semua output harus diverifikasi oleh radiolog atau dokter.",
  },
  en: {
    pages: {
      Dashboard: "Dashboard",
      "Reading Room": "Reading Room",
      "User Guide": "Guide",
      "Model Finder": "Model Finder",
      "Runtime Settings": "AI Setup",
      "General Settings": "General Settings",
      "Case Library": "Case Library",
      About: "About",
    } satisfies Record<Page, string>,
    backendOffline: "App not connected",
    starting: "Starting",
    themeLight: "Light",
    themeDark: "Dark",
    languageSwitch: "Indonesia",
    interfaceSettings: "Interface",
    interfaceDescription: "Set the app language and visual theme.",
    theme: "Theme",
    darkMode: "Dark",
    lightMode: "Light",
    connectionSettings: "AI ports & connections",
    connectionDescription: "Set local or OpenAI-compatible service addresses used by the runtime.",
    programSetup: "Optional AI models",
    programSetupDescription: "The app works immediately. Use this section only when connecting an additional AI model.",
    alternativeModels: "Model alternatives",
    alternativeModelsDescription: "Public model/library shortlist to search in Model Finder or use when already installed locally.",
    customModel: "Custom model",
    customModelDescription: "Enter a model/endpoint name you installed yourself, then bind it to a runtime slot.",
    customBackend: "Connection type",
    customSlot: "Target slot",
    customModelName: "Custom model name",
    applyCustomModel: "Use custom",
    runtimeGuide: "Runtime guide",
    runtimeGuideDescription: "See how to run local models and what is already connected to the current workflow.",
    runtimeSettings: "AI settings",
    runtimeDescription: "Choose the model source and analysis safety settings.",
    modelSlots: "Model slots",
    runtimeFlags: "Runtime modes",
    saveSettings: "Save settings",
    testRuntime: "Test AI connection",
    activeCase: "Active Case",
    noCase: "No case",
    backend: "Analysis mode",
    confidence: "Confidence",
    workflow: "Workflow",
    caseConsole: "Case Console",
    upload: "Upload PNG/JPG/DICOM",
    runWorkflow: "Run AI Workflow",
    customPrompt: "Custom instruction for the pipeline...",
    uploadToStart: "Upload an X-ray to start.",
    annotations: "annotations",
    labels: "labels",
    processing: "Processing...",
    noAnalysis: "No analysis yet.",
    metadata: "Metadata",
    noFile: "No file.",
    quality: "Quality",
    results: "Results",
    trace: "Trace",
    reportTitle: "Report Draft",
    language: "Language",
    indonesian: "Indonesian",
    english: "English",
    reportEmpty: "No report yet.",
    reportCopy: "Copy Report",
    exportDone: "Export complete",
    caseSearch: "Search cases",
    open: "Open",
    noCases: "No cases yet.",
    chatTitle: "Radiology Assistant",
    chatPlaceholder: "main finding? draft a report? explain annotations?",
    send: "Send",
    chooseCase: "Select or upload a case first.",
    disclaimer: "for research, education, and prototyping only. Not a PACS/RIS or official clinical diagnostic device. All outputs require radiologist/physician verification.",
  },
} satisfies Record<UiLanguage, Record<string, unknown>>;

const LanguageContext = React.createContext<{ language: UiLanguage; copy: typeof UI_COPY["id"] }>({ language: "en", copy: UI_COPY.en });

function useUiLanguage() {
  return React.useContext(LanguageContext);
}

const navGroups: { label: { id: string; en: string }; pages: { name: Page; icon: React.ReactNode }[] }[] = [
  {
    label: { id: "Alur utama", en: "Main workflow" },
    pages: [
      { name: "Dashboard", icon: <Activity size={18} /> },
      { name: "Reading Room", icon: <Stethoscope size={18} /> },
      { name: "Case Library", icon: <Library size={18} /> },
      { name: "User Guide", icon: <BookOpen size={18} /> },
      { name: "Runtime Settings", icon: <Settings size={18} /> },
      { name: "About", icon: <Archive size={18} /> },
    ],
  },
];

const ADVANCED_PAGES = new Set<Page>(["Model Finder"]);

const PAGE_DESCRIPTIONS: Record<UiLanguage, Record<Page, string>> = {
  id: {
    Dashboard: "Mulai atau lanjutkan peninjauan X-ray.",
    "Reading Room": "Impor, analisis, tinjau, lalu siapkan laporan.",
    "Case Library": "Kelola kasus, edit metadata, dan jalankan validasi dalam satu tempat.",
    "User Guide": "Panduan lengkap alur kerja, validasi, dan opsi lanjutan MedRay.",
    "Model Finder": "Cari model tambahan bila diperlukan.",
    "Runtime Settings": "Hubungkan dan atur model AI tambahan.",
    "General Settings": "Atur tampilan dan penyimpanan lokal.",
    About: "Informasi produk, keamanan, dan referensi.",
  },
  en: {
    Dashboard: "Start or continue an X-ray review.",
    "Reading Room": "Import, analyze, review, then prepare a report.",
    "Case Library": "Manage cases, edit metadata, and run validation in one place.",
    "User Guide": "A detailed guide to MedRay workflows, validation, and advanced options.",
    "Model Finder": "Find additional models when needed.",
    "Runtime Settings": "Connect and configure additional AI models.",
    "General Settings": "Configure the interface and local storage.",
    About: "Product identity, storage, intended use, and safety status.",
  },
};

function caseStudyImages(activeCase: CaseRecord | null): StudyImage[] {
  if (!activeCase) return [];
  const images = asList<StudyImage>(activeCase.images);
  if (images.length) return images;
  if (!activeCase.image_path && !activeCase.image_preview) return [];
  const metadata = activeCase.metadata || {};
  return [{
    image_id: String(metadata.SOPInstanceUID || `${activeCase.case_id}:0`),
    index: 0,
    filename: activeCase.title,
    image_path: activeCase.image_path,
    preview_path: activeCase.image_preview,
    metadata,
    file_hashes: activeCase.file_hashes,
    study_id: String(metadata.StudyInstanceUID || activeCase.case_id),
    series_id: String(metadata.SeriesInstanceUID || ""),
    view: String(metadata.ViewPosition || ""),
    laterality: String(metadata.Laterality || ""),
  }];
}

function activeStudyImageClient(activeCase: CaseRecord | null): StudyImage | null {
  const images = caseStudyImages(activeCase);
  return images.find(image => image.image_id === activeCase?.active_image_id) || images[0] || null;
}

function analysisForStudyImage(activeCase: CaseRecord | null, image: StudyImage): Record<string, unknown> | null {
  const analyses = activeCase?.analyses_by_image;
  const perImage = analyses && typeof analyses === "object" && !Array.isArray(analyses)
    ? (analyses as Record<string, unknown>)[image.image_id]
    : undefined;
  if (perImage && typeof perImage === "object" && !Array.isArray(perImage)) return perImage as Record<string, unknown>;
  const activeImage = activeStudyImageClient(activeCase);
  if (activeImage?.image_id === image.image_id && activeCase?.analysis && typeof activeCase.analysis === "object") {
    return activeCase.analysis as unknown as Record<string, unknown>;
  }
  return null;
}

function annotationBelongsToImage(annotation: Annotation, image: StudyImage | null, firstImage: boolean, images: StudyImage[] = []) {
  if (!image) return false;
  const sourceId = String(annotation.source_image_id || "");
  const filename = String(image.filename || "");
  const uniqueFilename = filename && images.filter(item => String(item.filename || "") === filename).length === 1 ? filename : "";
  const acceptedIds = [image.image_id, image.sop_instance_uid, uniqueFilename].filter(Boolean).map(String);
  return annotationsForImage([annotation], image.image_id, firstImage).length === 1 || acceptedIds.includes(sourceId);
}

function App() {
  const [page, setPage] = useState<Page>("Dashboard");
  const [dark, setDark] = useState(() => window.localStorage.getItem("medray-theme") !== "light");
  const [language, setLanguage] = useState<UiLanguage>(() => (window.localStorage.getItem("medray-ui-language") === "id" ? "id" : "en"));
  const copy = UI_COPY[language];
  const [status, setStatus] = useState(copy.starting);
  const [activeCase, setActiveCase] = useState<CaseRecord | null>(null);
  const [preview, setPreview] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [advancedNavOpen, setAdvancedNavOpen] = useState(false);

  useEffect(() => {
    document.body.dataset.theme = dark ? "dark" : "light";
    document.documentElement.lang = language;
    window.localStorage.setItem("medray-theme", dark ? "dark" : "light");
    window.localStorage.setItem("medray-ui-language", language);
    api.health().then(() => setStatus(language === "en" ? "App ready" : "Aplikasi siap")).catch(() => setStatus(copy.backendOffline));
  }, [dark, language, copy.backendOffline]);

  useEffect(() => {
    setAdvancedNavOpen(ADVANCED_PAGES.has(page));
  }, [page]);

  const loadCase = async (id: string, imageId = "") => {
    let c = await api.caseDetail(id);
    // Validation labels may refer to the image identity rather than the
    // currently active image. Resolve common legacy identities before
    // switching, then let the backend persist the selected image safely.
    const requestedImage = imageId
      ? caseStudyImages(c).find(image => [image.image_id, image.sop_instance_uid, image.filename].filter(Boolean).map(String).includes(String(imageId)))
      : undefined;
    if (requestedImage && requestedImage.image_id !== c.active_image_id) {
      c = await api.setActiveStudyImage(id, requestedImage.image_id);
    }
    const image = activeStudyImageClient(c);
    setActiveCase(c);
    setAnalysis(c.analysis || null);
    setPreview(image?.preview_path ? imageUrl(image.preview_path) : "");
    setPage("Reading Room");
  };

  function clearActiveCaseIf(id?: string) {
    if (!id || !activeCase || activeCase.case_id === id) {
      setActiveCase(null);
      setAnalysis(null);
      setPreview("");
    }
  }

  function startNewCase() {
    const fresh = createFreshCaseWorkspaceState();
    setActiveCase(fresh.activeCase);
    setAnalysis(fresh.analysis);
    setPreview(fresh.preview);
    setPage("Reading Room");
  }

  return (
    <LanguageContext.Provider value={{ language, copy }}>
    <div className="app">
      <aside className="rail">
        <div className="brand"><span className="brandMark"><img src="/medray-v2-logo.png" alt="" aria-hidden="true" /></span><span>MedRay <b>v2</b><small>{language === "en" ? "Local X-ray workspace" : "Ruang kerja X-ray lokal"}</small></span></div>
        <nav aria-label={language === "en" ? "Main navigation" : "Navigasi utama"}>
          {navGroups.map(group => group.label.id === "Riset" ? <details className="navDisclosure" key={group.label.id} open={advancedNavOpen} onToggle={event => setAdvancedNavOpen(event.currentTarget.open)}>
            <summary><Layers size={16} /><span>{language === "en" ? "Research" : "Riset"}</span></summary>
            <div className="navGroup">
              {group.pages.map(p => <button key={p.name} className={page === p.name ? "active" : ""} aria-current={page === p.name ? "page" : undefined} onClick={() => setPage(p.name)}>{p.icon}<span>{copy.pages[p.name]}</span></button>)}
            </div>
          </details> : <div className="navGroup" key={group.label.id}>
            <span className="navGroupLabel">{group.label[language]}</span>
            {group.pages.map(p => <button key={p.name} className={page === p.name ? "active" : ""} aria-current={page === p.name ? "page" : undefined} onClick={() => setPage(p.name)}>{p.icon}<span>{copy.pages[p.name]}</span></button>)}
          </div>)}
        </nav>
        <div className="railSafety"><ShieldCheck size={16} /><span>{language === "en" ? "Research only · verify every AI output" : "Khusus riset · verifikasi semua output AI"}</span></div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <h1>{copy.pages[page]}</h1>
            <p>{PAGE_DESCRIPTIONS[language][page]}</p>
          </div>
          <div className="topbarActions">
            <button className={`globalSettingsButton ${page === "General Settings" ? "active" : ""}`} onClick={() => setPage("General Settings")} aria-label={copy.pages["General Settings"]} aria-current={page === "General Settings" ? "page" : undefined}><Settings size={16} /><span>{copy.pages["General Settings"]}</span></button>
            <div className={`status ${status === copy.backendOffline ? "offline" : status === copy.starting ? "connecting" : "online"}`} role="status" aria-live="polite">{status === copy.backendOffline ? <XCircle size={17} /> : status === copy.starting ? <RefreshCw size={17} /> : <CheckCircle2 size={17} />}{status}</div>
          </div>
        </header>
        {page === "Dashboard" && <Dashboard activeCase={activeCase} analysis={analysis} onNavigate={setPage} />}
        {page === "Reading Room" && <ReadingRoom activeCase={activeCase} setActiveCase={setActiveCase} preview={preview} setPreview={setPreview} analysis={analysis} setAnalysis={setAnalysis} onOpenGuide={() => setPage("User Guide")} onNewCase={startNewCase} onOpenLibrary={() => setPage("Case Library")} />}
        {page === "User Guide" && <UserGuide onNavigate={setPage} />}
        {page === "Runtime Settings" && <AISetup language={language} modelTools={detail => <LocalModelManager selectedDetail={detail} />} onLater={() => setPage("Reading Room")} />}
        {page === "General Settings" && <GeneralSettings dark={dark} setDark={setDark} language={language} setLanguage={setLanguage} onOpenRuntime={() => setPage("Runtime Settings")} />}
        {page === "Case Library" && <CaseLibrary activeCase={activeCase} analysis={analysis} onOpen={loadCase} onDeleted={clearActiveCaseIf} onCleared={() => clearActiveCaseIf()} />}
        {page === "About" && <About />}
      </main>
    </div>
    </LanguageContext.Provider>
  );
}

function Dashboard({ activeCase, analysis, onNavigate }: { activeCase: CaseRecord | null; analysis: AnalysisResult | null; onNavigate: (page: Page) => void }) {
  const { language, copy } = useUiLanguage();
  return (
    <section className="dashboardPage">
      <div className="dashboardHero panel">
        <div>
          <span className="eyebrow">{language === "en" ? "Guided workspace" : "Ruang kerja terpandu"}</span>
          <h2>{language === "en" ? "Start an X-ray review in four clear steps" : "Tinjau X-ray dalam empat langkah yang jelas"}</h2>
          <p>{language === "en" ? "Import an image, run the analysis, review the evidence, then prepare a report. AI and model settings are available in AI Setup." : "Impor gambar, jalankan analisis, tinjau bukti, lalu siapkan laporan. Alat lanjutan tetap tersedia saat dibutuhkan."}</p>
          <div className="heroActions">
            <button className="primaryAction" onClick={() => onNavigate("Reading Room")}><Play size={17} />{activeCase ? (language === "en" ? "Continue active case" : "Lanjutkan kasus aktif") : (language === "en" ? "Start a new review" : "Mulai peninjauan baru")}</button>
            <button onClick={() => onNavigate("User Guide")}><BookOpen size={17} />{language === "en" ? "Open the guide" : "Buka panduan"}</button>
          </div>
        </div>
        <div className="activeCaseCard">
          <span>{copy.activeCase}</span>
          <b>{activeCase?.title || copy.noCase}</b>
          <small>{analysis ? (language === "en" ? "Analysis ready for human review" : "Analisis siap ditinjau manusia") : activeCase ? (language === "en" ? "Image ready to analyze" : "Gambar siap dianalisis") : (language === "en" ? "Import PNG, JPG, or DICOM" : "Impor PNG, JPG, atau DICOM")}</small>
        </div>
      </div>
      <ol className="workflowSummary" aria-label={language === "en" ? "Review workflow" : "Alur peninjauan"}>
        {[
          { title: language === "en" ? "Import" : "Impor", done: Boolean(activeCase) },
          { title: language === "en" ? "Analyze" : "Analisis", done: Boolean(analysis) },
          { title: language === "en" ? "Review" : "Tinjau", done: Boolean(analysis?.result_cards?.length) },
          { title: language === "en" ? "Report" : "Laporan", done: false },
        ].map((step, index) => <li className={step.done ? "done" : ""} key={step.title}><span>{step.done ? <CheckCircle2 size={16} /> : index + 1}</span><b>{step.title}</b></li>)}
      </ol>
    </section>
  );
}

function UserGuide({ onNavigate }: { onNavigate: (page: Page) => void }) {
  const { language } = useUiLanguage();
  const isEn = language === "en";
  return <section className="guidePage">
    <div className="guideHero panel">
      <span className="eyebrow">{isEn ? "Quick guide" : "Panduan cepat"}</span>
      <h2>{isEn ? "Use MedRay in four steps" : "Gunakan MedRay dalam empat langkah"}</h2>
      <p>{isEn ? "Start in the Reading Room. No AI model setup is required." : "Mulai dari Ruang Baca. Tidak perlu setup model AI."}</p>
    </div>

    <details className="guideDisclosure panel">
      <summary><span className="guideSummaryNumber">01</span><span><b>{isEn ? "First-time setup" : "Setup pertama kali"}</b><small>{isEn ? "Open only when installing or troubleshooting." : "Buka hanya saat instalasi atau troubleshooting."}</small></span></summary>
      <div className="guideDisclosureBody">
        <div className="setupPaths">
        <div><b>Windows — {isEn ? "easiest" : "paling mudah"}</b><ol><li>{isEn ? "Open the medray-v2 folder" : "Buka folder medray-v2"}</li><li>{isEn ? "Double-click start_medray_v2.bat" : "Klik dua kali start_medray_v2.bat"}</li><li>{isEn ? "Wait until MedRay is ready" : "Tunggu sampai MedRay siap"}</li><li>{isEn ? "Open http://127.0.0.1:5173 if the browser does not open automatically" : "Buka http://127.0.0.1:5173 jika browser tidak terbuka otomatis"}</li></ol><code>start_medray_v2.bat</code></div>
        <div><b>Linux / macOS</b><ol><li>{isEn ? "Open Terminal in the medray-v2 folder" : "Buka Terminal di folder medray-v2"}</li><li>{isEn ? "Run the launcher below" : "Jalankan launcher di bawah"}</li><li>{isEn ? "Wait until MedRay is ready" : "Tunggu sampai MedRay siap"}</li><li>{isEn ? "Open http://127.0.0.1:5173" : "Buka http://127.0.0.1:5173"}</li></ol><code>./start_medray_v2.sh</code></div>
        </div>
        <p className="guideNote">{isEn ? "If the app is not connected, close the launcher, run stop_medray_v2.bat on Windows, then start it again." : "Jika aplikasi belum terhubung, tutup launcher, jalankan stop_medray_v2.bat di Windows, lalu buka kembali start_medray_v2.bat."}</p>
      </div>
    </details>

    <section className="guideSection panel">
      <div className="sectionHeading"><span>02</span><div><h3>{isEn ? "Daily use" : "Cara menggunakan program"}</h3><p>{isEn ? "Complete the review from left to right; advanced settings are optional." : "Selesaikan review dari kiri ke kanan; pengaturan lanjutan bersifat opsional."}</p></div></div>
      <div className="complexFlow" aria-label={isEn ? "Detailed MedRay workflow" : "Alur MedRay terperinci"}>
        <div className="flowLane"><span>1</span><div className="flowNode"><b>{isEn ? "Import study" : "Impor studi"}</b><small>{isEn ? "Label + optional ID/NPM, accession, indication" : "Label + ID/NPM, nomor akses, indikasi opsional"}</small></div><span className="flowArrow">→</span><div className="flowDecision"><b>DICOM?</b><small>{isEn ? "Yes: inspect tags and burned-in risk" : "Ya: periksa tag dan risiko burned-in"}</small></div></div>
        <div className="flowLane"><span>2</span><div className="flowNode"><b>{isEn ? "Confirm active image" : "Konfirmasi gambar aktif"}</b><small>{isEn ? "Choose frame, window, orientation, and body area" : "Pilih frame, window, orientasi, dan area tubuh"}</small></div><span className="flowArrow">→</span><div className="flowDecision"><b>{isEn ? "Routing uncertain?" : "Routing belum pasti?"}</b><small>{isEn ? "Override the body area, then rerun" : "Pilih area tubuh manual, lalu jalankan ulang"}</small></div></div>
        <div className="flowLane"><span>3</span><div className="flowNode"><b>{isEn ? "AI candidate output" : "Kandidat output AI"}</b><small>{isEn ? "Finding + annotation + confidence + source" : "Temuan + anotasi + confidence + sumber"}</small></div><span className="flowArrow">→</span><div className="flowDecision"><b>{isEn ? "Accept, edit, or reject" : "Terima, edit, atau tolak"}</b><small>{isEn ? "Link evidence and add reviewer rationale" : "Tautkan bukti dan tambahkan alasan reviewer"}</small></div></div>
        <div className="flowLane"><span>4</span><div className="flowNode"><b>{isEn ? "Need another AI pass?" : "Perlu tinjauan AI lagi?"}</b><small>{isEn ? "Ask AI to re-review with validation feedback" : "Minta AI meninjau ulang dengan umpan balik validasi"}</small></div><span className="flowArrow loopArrow">↺</span><div className="flowNode finalNode"><b>{isEn ? "Promote reviewed evidence" : "Promosikan bukti tervalidasi"}</b><small>{isEn ? "Draft report → identity check → export" : "Draf laporan → cek identitas → ekspor"}</small></div></div>
      </div>
      <div className="guideChecklist">
        <div><b>1. {isEn ? "Import" : "Impor"}</b><span>{isEn ? "Add a case label, select PNG/JPG/DICOM, then confirm the active image." : "Isi label kasus, pilih PNG/JPG/DICOM, lalu pastikan gambar aktif."}</span></div>
        <div><b>2. {isEn ? "Analyze" : "Analisis"}</b><span>{isEn ? "Use automatic body-area detection unless it is incorrect; optional instructions stay under Reading options." : "Gunakan deteksi area tubuh otomatis kecuali hasilnya salah; instruksi tambahan ada di Opsi lanjutan."}</span></div>
        <div><b>3. Review</b><span>{isEn ? "Read the AI summary, then inspect findings, annotations, source, confidence, and uncertainty." : "Baca ringkasan AI, lalu periksa temuan, anotasi, sumber, tingkat keyakinan, dan ketidakpastian."}</span></div>
        <div><b>4. {isEn ? "Report" : "Laporan"}</b><span>{isEn ? "Only promote reviewed findings. Check identity and DICOM safety before export." : "Masukkan hanya temuan yang sudah ditinjau. Periksa identitas dan keamanan DICOM sebelum ekspor."}</span></div>
      </div>
      <button className="primaryAction" onClick={() => onNavigate("Reading Room")}><Play size={17} />{isEn ? "Open Reading Room" : "Buka Ruang Baca"}</button>
    </section>

    <section className="guideSection panel"><div className="sectionHeading"><span>03</span><div><h3>{isEn ? "Advanced annotations" : "Anotasi lanjutan"}</h3><p>{isEn ? "Use box, point, polygon, ellipse ROI, or calibrated length tools." : "Gunakan kotak, titik, poligon, ROI elips, atau alat ukur panjang terkalibrasi."}</p></div></div><div className="guideChecklist"><div><b>{isEn ? "Edit safely" : "Edit dengan aman"}</b><span>{isEn ? "Select geometry to move it; lock reviewed marks and use Ctrl+Z / Ctrl+Shift+Z for undo/redo." : "Pilih geometri untuk memindahkannya; kunci tanda yang sudah ditinjau dan gunakan Ctrl+Z / Ctrl+Shift+Z untuk undo/redo."}</span></div><div><b>{isEn ? "Ground evidence" : "Tautkan bukti"}</b><span>{isEn ? "Link each annotation to a result card and report section, then record a review decision and note." : "Tautkan setiap anotasi ke kartu hasil dan bagian laporan, lalu simpan keputusan serta catatan review."}</span></div><div><b>{isEn ? "Measurements" : "Pengukuran"}</b><span>{isEn ? "DICOM Pixel Spacing produces millimetres; images without calibration remain explicitly uncalibrated." : "DICOM Pixel Spacing menghasilkan milimeter; gambar tanpa kalibrasi tetap ditandai tidak terkalibrasi."}</span></div></div></section>

    <section className="guideSection panel"><div className="sectionHeading"><span>04</span><div><h3>{isEn ? "DICOM viewer" : "Viewer DICOM"}</h3><p>{isEn ? "Choose frames, use DICOM window presets or manual center/width, invert MONOCHROME display, rotate, flip, zoom, and reset." : "Pilih frame, gunakan preset window DICOM atau center/width manual, inversi tampilan MONOCHROME, putar, balik, zoom, dan reset."}</p></div></div><p className="guideNote">{isEn ? "Display controls do not modify the source DICOM. Use DICOM Safety before exporting, and inspect burned-in pixels separately." : "Kontrol tampilan tidak mengubah DICOM sumber. Gunakan DICOM Safety sebelum ekspor dan periksa pixel burned-in secara terpisah."}</p></section>

    <section className="guideSection panel">
      <div className="sectionHeading"><span>05</span><div><h3>{isEn ? "Case Library, validation, and AI" : "Pustaka kasus, validasi, dan AI"}</h3></div></div>
      <div className="guideChecklist">
        <div><b>{isEn ? "One case workspace" : "Satu ruang kerja kasus"}</b><span>{isEn ? "The registry and validation tools share one continuous page. Open validation above the internally scrollable case registry so it remains reachable with a large library." : "Registri dan alat validasi berada dalam satu halaman berkelanjutan. Buka validasi di atas daftar kasus yang dapat digulir agar tetap mudah dijangkau saat jumlah kasus banyak."}</span></div>
        <div><b>{isEn ? "AI sampling" : "Pengambilan sampel AI"}</b><span>{isEn ? "Temperature controls variation, top-p limits the sampled probability mass, and seed can make supported providers more repeatable. Change one control at a time." : "Temperature mengatur variasi, top-p membatasi massa probabilitas pengambilan sampel, dan seed dapat membuat penyedia yang mendukungnya lebih konsisten. Ubah satu kontrol setiap kali."}</span></div>
        <div><b>{isEn ? "Safety thresholds" : "Ambang keamanan"}</b><span>{isEn ? "Localization and auto-accept thresholds affect what is surfaced, not whether an output is clinically correct. Low confidence requires more scrutiny, not automatic rejection." : "Ambang lokalisasi dan penerimaan otomatis memengaruhi keluaran yang ditampilkan, bukan menentukan kebenaran klinis. Tingkat keyakinan rendah memerlukan pemeriksaan lebih ketat, bukan penolakan otomatis."}</span></div>
        <div><b>{isEn ? "Timeout and retries" : "Batas waktu dan percobaan ulang"}</b><span>{isEn ? "Increase timeout for large local models. Keep retries low to avoid repeating expensive or cloud-bound requests." : "Naikkan batas waktu untuk model lokal besar. Batasi percobaan ulang agar permintaan mahal atau berbasis cloud tidak berulang berlebihan."}</span></div>
        <div><b>{isEn ? "Downloads" : "Unduhan"}</b><span>{isEn ? "Use a trusted direct URL and, when available, a SHA-256 checksum. Parallel byte ranges fall back automatically when unsupported." : "Gunakan URL langsung yang tepercaya dan, jika tersedia, checksum SHA-256. Rentang byte paralel otomatis beralih ke satu aliran bila tidak didukung."}</span></div>
        <div><b>{isEn ? "Reset strategy" : "Strategi reset"}</b><span>{isEn ? "If experiments become difficult to compare, restore the safe preset, set a deterministic seed, and record the runtime snapshot with the validation export." : "Jika eksperimen sulit dibandingkan, pulihkan preset aman, gunakan seed deterministik, dan simpan snapshot runtime bersama ekspor validasi."}</span></div>
      </div>
    </section>

  </section>;
}

export function ReadingRoom(props: {
  activeCase: CaseRecord | null;
  setActiveCase: (c: CaseRecord | null) => void;
  preview: string;
  setPreview: (s: string) => void;
  analysis: AnalysisResult | null;
  setAnalysis: (a: AnalysisResult | null) => void;
  onOpenGuide: () => void;
  onNewCase: () => void;
  onOpenLibrary: () => void;
}) {
  const { language, copy } = useUiLanguage();
  const { activeCase, setActiveCase, preview, setPreview, analysis, setAnalysis, onOpenGuide, onNewCase, onOpenLibrary } = props;
  const [busy, setBusy] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [caseTitle, setCaseTitle] = useState("");
  const [caseMetadata, setCaseMetadata] = useState<CaseMetadataDraft>(EMPTY_CASE_METADATA);
  const [anatomyProfileOverride, setAnatomyProfileOverride] = useState("");
  const [zoom, setZoom] = useState(1);
  const [contrast, setContrast] = useState(100);
  const [brightness, setBrightness] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [flipHorizontal, setFlipHorizontal] = useState(false);
  const [flipVertical, setFlipVertical] = useState(false);
  const [dicomProfile, setDicomProfile] = useState<DicomViewerProfile | null>(null);
  const [dicomFrame, setDicomFrame] = useState(0);
  const [windowCenter, setWindowCenter] = useState<number | undefined>();
  const [windowWidth, setWindowWidth] = useState<number | undefined>();
  const [dicomInvert, setDicomInvert] = useState(false);
  const [showAnn, setShowAnn] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showConf, setShowConf] = useState(true);
  const [annotationTool, setAnnotationTool] = useState<AnnotationTool>("select");
  const [annotationFilter, setAnnotationFilter] = useState<AnnotationWorkspaceFilter>({ origin: "all", reviewStatus: "all", minimumAiConfidence: 0 });
  const [selectedAnnotationId, setSelectedAnnotationId] = useState<string | null>(null);
  const [selectedResultCardId, setSelectedResultCardId] = useState<string | null>(null);
  const [selectedReportStatementId, setSelectedReportStatementId] = useState<string | null>(null);
  const [sideTab, setSideTab] = useState<WorkspaceTab>("AI Output");
  const [error, setError] = useState("");
  const [advancedAnalysisOpen, setAdvancedAnalysisOpen] = useState(false);
  const [annotationHistory, setAnnotationHistory] = useState(() => createAnnotationHistory([]));
  const importSectionRef = useRef<HTMLElement | null>(null);
  const caseLabelRef = useRef<HTMLInputElement | null>(null);
  const analysisSectionRef = useRef<HTMLElement | null>(null);
  const anatomySelectRef = useRef<HTMLSelectElement | null>(null);
  const runAnalysisRef = useRef<HTMLButtonElement | null>(null);
  const workspacePanelRef = useRef<HTMLElement | null>(null);
  const studyImages = caseStudyImages(activeCase);
  const activeImage = activeStudyImageClient(activeCase);
  const activeImageIndex = activeImage ? studyImages.findIndex(image => image.image_id === activeImage.image_id) : -1;
  const allAnnotations = preferredAnnotations(activeCase?.annotations, analysis?.annotations);
  const currentAnnotations = allAnnotations.filter(annotation => annotationBelongsToImage(annotation, activeImage, activeImageIndex === 0, studyImages) && Number(annotation.source_frame_number || 0) === dicomFrame);
  const filteredAnnotations = filterWorkspaceAnnotations(currentAnnotations, annotationFilter);
  const overlayAnnotations = filteredAnnotations.filter(annotation => annotation.source !== "fallback heuristic");
  const annotationsRef = useRef<Annotation[]>(allAnnotations);
  const annotationSaveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const annotationHistoryRef = useRef(annotationHistory);
  const activeImageIsDicom = Boolean(activeImage?.is_dicom || activeImage?.source_path?.toLowerCase().match(/\.(dcm|dicom)$/) || String(activeImage?.format || "").toUpperCase() === "DICOM");
  const displayedPreview = activeCase && activeImage && activeImageIsDicom
    ? dicomPreviewUrl(activeCase.case_id, activeImage.image_id, dicomFrame, windowCenter, windowWidth, dicomInvert)
    : preview;

  useEffect(() => {
    setCaseTitle(activeCase?.title || "");
    setCaseMetadata(caseMetadataDraft(activeCase?.metadata || {}));
  }, [activeCase?.case_id]);

  useEffect(() => {
    annotationsRef.current = allAnnotations;
  }, [allAnnotations]);

  useEffect(() => {
    const history = createAnnotationHistory(preferredAnnotations(activeCase?.annotations, activeCase?.analysis?.annotations));
    annotationHistoryRef.current = history;
    setAnnotationHistory(history);
  }, [activeCase?.case_id]);

  useEffect(() => { annotationHistoryRef.current = annotationHistory; }, [annotationHistory]);

  useEffect(() => {
    setDicomProfile(null);
    setDicomFrame(0);
    setWindowCenter(undefined);
    setWindowWidth(undefined);
    setDicomInvert(false);
    if (!activeCase || !activeImage || !activeImageIsDicom) return;
    api.dicomViewerProfile(activeCase.case_id, activeImage.image_id).then(profile => {
      setDicomProfile(profile);
      setWindowCenter(profile.default_window?.center);
      setWindowWidth(profile.default_window?.width);
    }).catch(exc => setError(String(exc)));
  }, [activeCase?.case_id, activeImage?.image_id, activeImageIsDicom]);

  function revision(action: string, note: string) {
    return { action, timestamp: new Date().toISOString(), actor: "local reviewer", note };
  }

  async function saveAnnotations(nextAnnotations: Annotation[], nextResultCards?: ResultCard[]) {
    if (!activeCase) return;
    annotationsRef.current = nextAnnotations;
    const baseAnalysis = analysis || activeCase.analysis;
    const activeAnnotations = nextAnnotations.filter(annotation => annotationBelongsToImage(annotation, activeImage, activeImageIndex === 0, studyImages));
    const nextAnalysis = baseAnalysis ? {
      ...baseAnalysis,
      annotations: activeAnnotations,
      result_cards: nextResultCards || baseAnalysis.result_cards
    } : undefined;
    const nextCase = {
      ...activeCase,
      annotations: nextAnnotations,
      ...(nextAnalysis ? { analysis: nextAnalysis, report: nextAnalysis.report } : {})
    };
    setAnalysis(nextAnalysis || null);
    setActiveCase(nextCase);
    annotationSaveQueueRef.current = annotationSaveQueueRef.current
      .catch(() => undefined)
      .then(async () => { await api.saveCase(nextCase); })
      .catch(exc => { setError(`${language === "en" ? "Annotation was not saved" : "Anotasi belum tersimpan"}: ${String(exc)}`); });
    await annotationSaveQueueRef.current;
  }

  function recordAnnotationHistory(nextAnnotations: Annotation[]) {
    setAnnotationHistory(current => commitAnnotationChange(current, nextAnnotations));
  }

  function restoreAnnotationHistory(direction: "undo" | "redo") {
    const next = direction === "undo" ? undoAnnotationChange(annotationHistoryRef.current) : redoAnnotationChange(annotationHistoryRef.current);
    if (next === annotationHistoryRef.current) return;
    annotationHistoryRef.current = next;
    setAnnotationHistory(next);
    setSelectedAnnotationId(null);
    void saveAnnotations(next.present);
  }

  async function saveCaseIdentity() {
    if (!activeCase) return;
    const title = caseTitle.trim() || caseMetadata.localRecordId.trim() || activeCase.title;
    setBusy(true);
    setError("");
    try {
      const saved = await api.saveCase({ ...activeCase, title, metadata: mergeCaseMetadata(activeCase.metadata, caseMetadata) });
      setActiveCase(saved);
      setCaseTitle(saved.title);
    } catch (exc) {
      setError(`${language === "en" ? "Case identity was not saved" : "Identitas kasus belum tersimpan"}: ${String(exc)}`);
    } finally {
      setBusy(false);
    }
  }

  function updateAnnotation(id: string, patch: Partial<Annotation>, action = "edited", note = "Annotation updated by reviewer.") {
    const next = annotationsRef.current.map(annotation => annotation.id === id ? {
      ...annotation,
      ...patch,
      revision_history: [...(annotation.revision_history || []), revision(action, note)]
    } : annotation);
    recordAnnotationHistory(next);
    void saveAnnotations(next);
  }

  function reviewAnnotationBatch(ids: string[], status: AnnotationReviewStatus) {
    const selected = new Set(ids);
    if (!selected.size) return;
    const next = annotationsRef.current.map(annotation => selected.has(annotation.id) ? {
      ...annotation,
      review_status: status,
      revision_history: [...(annotation.revision_history || []), revision("reviewed", `Reviewer marked visible AI candidate ${status}.`)]
    } : annotation);
    recordAnnotationHistory(next);
    void saveAnnotations(next);
  }

  function createManualAnnotation(coordinate: Annotation["coordinate"], originalWidth: number, originalHeight: number) {
    if (!activeCase) return;
    const id = crypto.randomUUID();
    const annotation: Annotation = {
      id,
      label: "manual finding",
      confidence: 1,
      source: "manual user annotation",
      coordinate,
      original_coordinate: { ...coordinate },
      explanation: `Reviewer-created ${coordinate.type} requiring a label and review decision.`,
      visible: true,
      locked: false,
      review_status: "unreviewed",
      reviewer_note: "",
      transform_metadata: {
        source_space: "original_image",
        display_space: "original_image",
        scale_x: 1,
        scale_y: 1,
        offset_x: 0,
        offset_y: 0,
        original_width: originalWidth,
        original_height: originalHeight,
        note: "Created interactively in the MedRay Reading Room."
      },
      linked_result_card_ids: [],
      linked_report_statement_id: "",
      source_image_id: String(activeImage?.image_id || activeCase.metadata?.SOPInstanceUID || `${activeCase.case_id}:0`),
      source_image_index: activeImage?.index ?? 0,
      source_frame_number: dicomFrame,
      source_view: String(activeImage?.view || activeCase.metadata?.ViewPosition || ""),
      source_series_id: String(activeImage?.series_id || activeCase.metadata?.SeriesInstanceUID || ""),
      revision_history: [revision("created", `Manual ${coordinate.type} created in the Reading Room.`)]
    };
    setSelectedAnnotationId(id);
    setAnnotationTool("select");
    setShowAnn(true);
    setSideTab("Annotations");
    const next = [...annotationsRef.current, annotation];
    recordAnnotationHistory(next);
    void saveAnnotations(next);
  }

  function deleteManualAnnotation(id: string) {
    const annotation = annotationsRef.current.find(item => item.id === id);
    if (!annotation || !String(annotation.source || "").includes("manual")) return;
    const baseAnalysis = analysis || activeCase?.analysis;
    const nextCards = asList<ResultCard>(baseAnalysis?.result_cards).map(card => ({
      ...card,
      annotation_refs: textList(card.annotation_refs).filter(ref => ref !== id)
    }));
    setSelectedAnnotationId(null);
    const next = annotationsRef.current.filter(item => item.id !== id);
    recordAnnotationHistory(next);
    void saveAnnotations(next, nextCards);
  }

  function selectAnnotation(id: string | null) {
    setSelectedAnnotationId(id);
    if (id) setSideTab("Annotations");
  }

  function focusResultCard(id: string) {
    setSelectedResultCardId(id);
    setSideTab("Result Cards");
  }

  function focusReportStatement(id: string) {
    setSelectedReportStatementId(id);
    setSideTab("Report");
  }

  function linkAnnotation(annotationId: string, resultCardId: string, reportStatementId: string) {
    const baseAnalysis = analysis || activeCase?.analysis;
    const linked = linkAnnotationEvidence(
      annotationsRef.current,
      asList<ResultCard>(baseAnalysis?.result_cards),
      annotationId,
      resultCardId,
      reportStatementId,
      revision("edited", "Grounded evidence links updated by reviewer.")
    );
    recordAnnotationHistory(linked.annotations);
    void saveAnnotations(linked.annotations, linked.cards);
  }

  useEffect(() => {
    function onHistoryShortcut(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable=true]")) return;
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") return;
      event.preventDefault();
      restoreAnnotationHistory(event.shiftKey ? "redo" : "undo");
    }
    window.addEventListener("keydown", onHistoryShortcut);
    return () => window.removeEventListener("keydown", onHistoryShortcut);
  }, []);

  async function onFiles(files?: FileList | null) {
    const selectedFiles = files ? Array.from(files) : [];
    if (!selectedFiles.length) return;
    setBusy(true);
    setError("");
    try {
      const uploaded = await api.upload(selectedFiles[0], activeCase ? "" : (caseTitle.trim() || caseMetadata.localRecordId.trim()));
      let nextCase = uploaded.case;
      for (const file of selectedFiles.slice(1)) {
        const appended = await api.addStudyImage(nextCase.case_id, file);
        nextCase = appended.case;
      }
      if (!activeCase) {
        nextCase = await api.saveCase({
          ...nextCase,
          title: caseTitle.trim() || caseMetadata.localRecordId.trim() || nextCase.title,
          metadata: mergeCaseMetadata(nextCase.metadata, caseMetadata),
        });
      }
      setActiveCase(nextCase);
      setPreview(uploaded.preview_data_url);
      setAnalysis(null);
      setCaseTitle(nextCase.title);
      setAnatomyProfileOverride("");
      setSideTab("Result Cards");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function selectStudyImage(imageId: string) {
    if (!activeCase || imageId === activeImage?.image_id) return;
    setBusy(true);
    setError("");
    try {
      const nextCase = await api.setActiveStudyImage(activeCase.case_id, imageId);
      const nextImage = activeStudyImageClient(nextCase);
      setActiveCase(nextCase);
      setAnalysis(nextCase.analysis || null);
      setPreview(nextImage?.preview_path ? imageUrl(nextImage.preview_path) : "");
      setSelectedAnnotationId(null);
      setSelectedResultCardId(null);
      setSelectedReportStatementId(null);
      setZoom(1);
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function run(instruction = prompt) {
    if (!activeCase) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.analyze(activeCase.case_id, instruction, language, anatomyProfileOverride);
      const refreshed = await api.caseDetail(activeCase.case_id);
      setAnalysis(result);
      setActiveCase(refreshed);
      const history = createAnnotationHistory(preferredAnnotations(refreshed.annotations, refreshed.analysis?.annotations));
      annotationHistoryRef.current = history;
      setAnnotationHistory(history);
      setSideTab("AI Output");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function rerunWithValidationFeedback() {
    const validationPrompt = buildValidationRerunPrompt(currentAnnotations, language);
    const combinedPrompt = [prompt.trim(), validationPrompt].filter(Boolean).join("\n\n");
    await run(combinedPrompt);
  }

  const routeNeedsConfirmation = analysis?.anatomy_route?.support_status === "routing_required" || analysis?.anatomy_route?.profile_id === "general";
  const reviewStatuses = asList<ResultCard>(analysis?.result_cards).map(card => card.review_status || "unreviewed");
  const reviewDone = reviewStatuses.length > 0 && reviewStatuses.every(status => status !== "unreviewed");
  const workflowCurrentIndex = !activeCase ? 0 : (!analysis || routeNeedsConfirmation) ? 1 : !reviewDone ? 2 : 3;
  const workflowStages = [
    { label: language === "en" ? "Import" : "Impor", done: Boolean(activeCase), enabled: true },
    { label: language === "en" ? "Analyze" : "Analisis", done: Boolean(analysis && !routeNeedsConfirmation), enabled: Boolean(activeCase) },
    { label: language === "en" ? "Review" : "Tinjau", done: reviewDone, enabled: Boolean(analysis && !routeNeedsConfirmation) },
    { label: language === "en" ? "Report" : "Laporan", done: false, enabled: Boolean(analysis && !routeNeedsConfirmation) },
  ];
  const nextStepText = routeNeedsConfirmation
    ? (language === "en" ? "Next: confirm the body area, then rerun analysis" : "Berikutnya: konfirmasi area tubuh, lalu analisis ulang")
    : workflowCurrentIndex === 0
      ? (language === "en" ? "Next: add a case label and import images" : "Berikutnya: isi label kasus dan impor gambar")
      : workflowCurrentIndex === 1
        ? (language === "en" ? "Next: run the analysis" : "Berikutnya: jalankan analisis")
        : workflowCurrentIndex === 2
          ? (language === "en" ? "Next: review every finding" : "Berikutnya: tinjau setiap temuan")
          : (language === "en" ? "Next: check the draft report and export" : "Berikutnya: periksa draf laporan dan ekspor");

  function openWorkflowStage(index: number) {
    if (!workflowStages[index]?.enabled) return;
    if (index === 0) {
      importSectionRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      caseLabelRef.current?.focus();
      return;
    }
    if (index === 1) {
      analysisSectionRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      if (routeNeedsConfirmation) {
        setAdvancedAnalysisOpen(true);
        window.setTimeout(() => anatomySelectRef.current?.focus(), 0);
      } else {
        runAnalysisRef.current?.focus();
      }
      return;
    }
    setSideTab(index === 2 ? "Result Cards" : "Report");
    workspacePanelRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  return (
    <div className="reading">
      <div className="readingWorkflow" aria-label={language === "en" ? "Review progress" : "Progres peninjauan"}>
        <div className="readingWorkflowIdentity"><span>{language === "en" ? "Current case" : "Kasus saat ini"}</span><b>{activeCase?.title || (language === "en" ? "No case loaded" : "Belum ada kasus")}</b><small>{nextStepText}</small></div>
        <div className="readingSteps">{workflowStages.map((stage, index) => <button type="button" className={`${stage.done ? "done" : ""} ${workflowCurrentIndex === index ? "current" : ""}`} key={stage.label} onClick={() => openWorkflowStage(index)} disabled={!stage.enabled} aria-current={workflowCurrentIndex === index ? "step" : undefined} aria-label={`${stage.label}: ${stage.done ? (language === "en" ? "complete" : "selesai") : !stage.enabled ? (language === "en" ? "not available yet" : "belum tersedia") : workflowCurrentIndex === index ? (language === "en" ? "next action" : "tindakan berikutnya") : (language === "en" ? "available" : "tersedia")}`}><span>{stage.done ? <CheckCircle2 size={15} /> : index + 1}</span><b>{stage.label}</b></button>)}</div>
        <div className="readingWorkflowActions">
          {activeCase && <button className="primaryAction" onClick={onNewCase}><Plus size={16} />{language === "en" ? "New case" : "Kasus baru"}</button>}
          <button onClick={onOpenLibrary}><Library size={16} />{language === "en" ? "Cases" : "Daftar kasus"}</button>
          <button className="guideShortcut" onClick={onOpenGuide} aria-label={language === "en" ? "Open guide" : "Buka panduan"} title={language === "en" ? "Open guide" : "Buka panduan"}><BookOpen size={16} /></button>
        </div>
      </div>
      <aside className="panel casebar">
        <section className="guidedAction" ref={importSectionRef}>
          <div className="guidedActionHeader"><span>1</span><div><h2>{activeCase ? (language === "en" ? "Current study" : "Studi saat ini") : (language === "en" ? "Import study" : "Impor studi")}</h2><p>{activeCase ? (language === "en" ? "Add images here, or use New case above to start separately." : "Tambahkan gambar di sini, atau gunakan Kasus baru di atas untuk memulai terpisah.") : (language === "en" ? "Add identifiers and choose one or more images." : "Tambahkan identitas lalu pilih satu atau beberapa gambar.")}</p></div></div>
          <label className="compactField">{language === "en" ? "Case label (optional)" : "Label kasus (opsional)"}
            <input ref={caseLabelRef} value={caseTitle} onChange={event => setCaseTitle(event.target.value)} placeholder={language === "en" ? "e.g. Teaching chest case" : "contoh: Kasus toraks pembelajaran"} disabled={busy} />
          </label>
          <details className="caseMetadataEditor" open={!activeCase && Boolean(caseMetadata.localRecordId || caseMetadata.patientId)}>
            <summary>{language === "en" ? "More case details" : "Detail kasus lainnya"}</summary>
            <div className="caseMetadataGrid">
              <label>{language === "en" ? "Local record / NPM" : "Nomor lokal / NPM"}<input value={caseMetadata.localRecordId} onChange={event => setCaseMetadata(current => ({ ...current, localRecordId: event.target.value }))} placeholder="NPM-23001" /></label>
              <label>{language === "en" ? "Patient ID" : "ID pasien"}<input value={caseMetadata.patientId} onChange={event => setCaseMetadata(current => ({ ...current, patientId: event.target.value }))} placeholder="PX-104" /></label>
              <label>{language === "en" ? "Accession number" : "Nomor akses"}<input value={caseMetadata.accessionNumber} onChange={event => setCaseMetadata(current => ({ ...current, accessionNumber: event.target.value }))} placeholder="ACC-2026-001" /></label>
              <label>{language === "en" ? "Study description" : "Deskripsi studi"}<input value={caseMetadata.studyDescription} onChange={event => setCaseMetadata(current => ({ ...current, studyDescription: event.target.value }))} placeholder="Chest PA" /></label>
              <label className="wideField">{language === "en" ? "Clinical indication" : "Indikasi klinis"}<textarea value={caseMetadata.clinicalIndication} onChange={event => setCaseMetadata(current => ({ ...current, clinicalIndication: event.target.value }))} placeholder={language === "en" ? "Short reason for the examination" : "Alasan singkat pemeriksaan"} /></label>
              <label className="wideField">{language === "en" ? "Local notes" : "Catatan lokal"}<textarea value={caseMetadata.notes} onChange={event => setCaseMetadata(current => ({ ...current, notes: event.target.value }))} placeholder={language === "en" ? "Teaching set, protocol, or internal note" : "Set pembelajaran, protokol, atau catatan internal"} /></label>
            </div>
            <small>{language === "en" ? "Stored locally with the case. Imported DICOM identifiers remain intact." : "Disimpan lokal bersama kasus. Identitas DICOM hasil impor tetap dipertahankan."}</small>
          </details>
          <label className="drop"><Upload size={22} /><span>{activeCase ? (language === "en" ? "Add PNG, JPG, or DICOM" : "Tambah PNG, JPG, atau DICOM") : (language === "en" ? "Choose PNG, JPG, or DICOM" : "Pilih PNG, JPG, atau DICOM")}</span><small>{language === "en" ? "Multiple images become one study" : "Beberapa gambar menjadi satu studi"}</small><input type="file" multiple accept=".png,.jpg,.jpeg,.dcm,.dicom" onChange={e => onFiles(e.target.files)} /></label>
          {activeCase && <div className="inlineSuccess"><CheckCircle2 size={16} /><span>{language === "en" ? "Study loaded" : "Studi sudah dimuat"}</span></div>}
          {activeCase && <button onClick={saveCaseIdentity} disabled={busy}>{language === "en" ? "Save case details" : "Simpan detail kasus"}</button>}
        </section>

        <section className={`guidedAction ${!activeCase ? "mutedAction" : ""} ${routeNeedsConfirmation ? "needsAttention" : ""}`} ref={analysisSectionRef}>
          <div className="guidedActionHeader"><span>2</span><div><h2>{language === "en" ? "Run analysis" : "Jalankan analisis"}</h2><p>{language === "en" ? "Automatic body-area detection is recommended." : "Deteksi area tubuh otomatis direkomendasikan."}</p></div></div>
          {routeNeedsConfirmation && <div className="nextAction" role="status">{language === "en" ? "Body area needs confirmation. Choose it below before running the analysis again." : "Area tubuh perlu dikonfirmasi. Pilih area di bawah sebelum menjalankan analisis ulang."}</div>}
          <button ref={runAnalysisRef} className="primaryAction runAnalysis" onClick={() => run()} disabled={!activeCase || busy}><Bot size={17} />{busy ? copy.processing : copy.runWorkflow}</button>
          <details className="advancedOptions" open={advancedAnalysisOpen || routeNeedsConfirmation} onToggle={event => setAdvancedAnalysisOpen(event.currentTarget.open)}>
            <summary>{language === "en" ? "Reading options" : "Opsi analisis lanjutan"}</summary>
            <label className="routeOverride">{language === "en" ? "Body area" : "Area tubuh"}
              <select ref={anatomySelectRef} data-testid="anatomy-profile-override" value={anatomyProfileOverride} onChange={event => setAnatomyProfileOverride(event.target.value)}>
                <option value="">{language === "en" ? "Automatic detection (recommended)" : "Deteksi otomatis (disarankan)"}</option>
                <option value="chest">Chest</option>
                <option value="msk">MSK / trauma</option>
                <option value="abdomen">Abdomen / KUB</option>
                <option value="spine">Spine</option>
                <option value="skull_facial">Skull / facial / sinus</option>
                <option value="general">General / unknown</option>
              </select>
            </label>
            <label className="compactField">{language === "en" ? "Optional instruction" : "Instruksi opsional"}<textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder={copy.customPrompt} /></label>
          </details>
          {analysis?.anatomy_route && <AnatomyRoutePanel route={analysis.anatomy_route} compact />}
        </section>

        <details className="caseDetails">
          <summary>{language === "en" ? "Case details & metadata" : "Detail kasus & metadata"}</summary>
          <WorkspaceStats activeCase={activeCase} analysis={analysis} />
          <Metadata activeCase={activeCase} />
        </details>
      </aside>
      <section className="viewer panel">
        {studyImages.length > 0 && <div className="studyNavigator" aria-label="Study image navigator">
          <div className="studyNavigatorHeader"><b>{language === "en" ? "Study images" : "Gambar studi"}</b><span>{activeImageIndex + 1} / {studyImages.length}</span></div>
          <div className="studyImageStrip">{studyImages.map((image, index) => {
            const imageAnalysis = analysisForStudyImage(activeCase, image);
            return <button
              key={image.image_id}
              className={image.image_id === activeImage?.image_id ? "activeStudyImage" : ""}
              onClick={() => selectStudyImage(image.image_id)}
              disabled={busy}
              title={`${image.filename || `Image ${index + 1}`} / ${image.series_id || "no series"}`}
            >
              {image.preview_path && <img src={imageUrl(image.preview_path)} alt={`Study image ${index + 1}`} />}
              <span>#{index + 1} {image.view || (language === "en" ? "view unknown" : "proyeksi belum diketahui")}{image.laterality ? ` ${image.laterality}` : ""}</span>
              <small>{image.series_id ? `series ${image.series_id}` : image.filename}</small>
              <small className={imageAnalysis ? "studyAnalysisStatus analyzed" : "studyAnalysisStatus"}>
                {imageAnalysis ? (language === "en" ? "✓ analyzed / review" : "✓ sudah dianalisis / perlu ditinjau") : (language === "en" ? "○ not analyzed" : "○ belum dianalisis")}
              </small>
            </button>;
          })}</div>
        </div>}
        {preview && <div className="toolbar">
          <div className="toolGroup"><span>{language === "en" ? "Annotate" : "Anotasi"}</span>
            <button aria-label={language === "en" ? "Select and edit annotation" : "Pilih dan edit anotasi"} title={language === "en" ? "Select and edit annotation" : "Pilih dan edit anotasi"} className={annotationTool === "select" ? "activeTool" : ""} onClick={() => setAnnotationTool("select")}><MousePointer2 size={16} /></button>
            <button aria-label={language === "en" ? "Draw manual bounding box" : "Gambar kotak pembatas manual"} title={language === "en" ? "Draw manual bounding box" : "Gambar kotak pembatas manual"} className={annotationTool === "box" ? "activeTool" : ""} onClick={() => { setAnnotationTool("box"); setShowAnn(true); }} disabled={!preview}><Square size={16} /></button>
            <button aria-label={language === "en" ? "Place manual point" : "Tempatkan titik manual"} title={language === "en" ? "Place manual point" : "Tempatkan titik manual"} className={annotationTool === "point" ? "activeTool" : ""} onClick={() => { setAnnotationTool("point"); setShowAnn(true); }} disabled={!preview}><Crosshair size={16} /></button>
            <button aria-label={language === "en" ? "Draw manual polygon" : "Gambar poligon manual"} title={language === "en" ? "Draw manual polygon; double-click or press Enter to finish" : "Gambar poligon manual; klik dua kali atau tekan Enter untuk selesai"} className={annotationTool === "polygon" ? "activeTool" : ""} onClick={() => { setAnnotationTool("polygon"); setShowAnn(true); }} disabled={!preview}><Pentagon size={16} /></button>
            <button aria-label={language === "en" ? "Draw ellipse ROI" : "Gambar ROI elips"} title={language === "en" ? "Draw ellipse ROI" : "Gambar ROI elips"} className={annotationTool === "ellipse" ? "activeTool" : ""} onClick={() => { setAnnotationTool("ellipse"); setShowAnn(true); }} disabled={!preview}><Circle size={16} /></button>
            <button aria-label={language === "en" ? "Measure length" : "Ukur panjang"} title={language === "en" ? "Measure calibrated length" : "Ukur panjang terkalibrasi"} className={annotationTool === "length" ? "activeTool" : ""} onClick={() => { setAnnotationTool("length"); setShowAnn(true); }} disabled={!preview}><Ruler size={16} /></button>
            <button aria-label={language === "en" ? "Undo annotation change" : "Urungkan perubahan anotasi"} title="Ctrl+Z" onClick={() => restoreAnnotationHistory("undo")} disabled={!annotationHistory.past.length}><Undo2 size={16} /></button>
            <button aria-label={language === "en" ? "Redo annotation change" : "Ulangi perubahan anotasi"} title="Ctrl+Shift+Z" onClick={() => restoreAnnotationHistory("redo")} disabled={!annotationHistory.future.length}><Redo2 size={16} /></button>
          </div>
          <div className="toolGroup"><span>{language === "en" ? "View" : "Tampilan"}</span>
            <button aria-label={language === "en" ? "Zoom in" : "Perbesar"} title={language === "en" ? "Zoom in" : "Perbesar"} onClick={() => setZoom(z => Math.min(4, z + 0.2))}><ZoomIn size={16} /></button>
            <button aria-label={language === "en" ? "Zoom out" : "Perkecil"} title={language === "en" ? "Zoom out" : "Perkecil"} onClick={() => setZoom(z => Math.max(0.4, z - 0.2))}><ZoomOut size={16} /></button>
            <button aria-label={language === "en" ? "Rotate image" : "Putar gambar"} title={language === "en" ? "Rotate 90°" : "Putar 90°"} onClick={() => setRotation(value => (value + 90) % 360)}><RotateCw size={16} /></button>
            <button aria-label={language === "en" ? "Flip image horizontally" : "Balik gambar horizontal"} onClick={() => setFlipHorizontal(value => !value)}><FlipHorizontal2 size={16} /></button>
            <button aria-label={language === "en" ? "Flip image vertically" : "Balik gambar vertikal"} onClick={() => setFlipVertical(value => !value)}><FlipVertical2 size={16} /></button>
            <button aria-label={language === "en" ? "Reset image view" : "Atur ulang tampilan gambar"} title={language === "en" ? "Reset image view" : "Atur ulang tampilan gambar"} onClick={() => { setZoom(1); setContrast(100); setBrightness(100); setRotation(0); setFlipHorizontal(false); setFlipVertical(false); setDicomInvert(false); setDicomFrame(0); setWindowCenter(dicomProfile?.default_window?.center); setWindowWidth(dicomProfile?.default_window?.width); }}><RotateCcw size={16} /></button>
          </div>
          <details className="displayAdjustments"><summary>{language === "en" ? "Image adjustments" : "Atur gambar"}</summary><div><label>{language === "en" ? "Brightness" : "Kecerahan"} <input type="range" min="50" max="160" value={brightness} onChange={e => setBrightness(Number(e.target.value))} /></label><label>{language === "en" ? "Contrast" : "Kontras"} <input type="range" min="50" max="180" value={contrast} onChange={e => setContrast(Number(e.target.value))} /></label></div></details>
        </div>}
        {dicomProfile && <div className="dicomViewerControls">
          <b>DICOM</b>
          {dicomProfile.number_of_frames > 1 && <label>{language === "en" ? "Frame" : "Frame"}<input type="range" min="0" max={dicomProfile.number_of_frames - 1} value={dicomFrame} onChange={event => setDicomFrame(Number(event.target.value))} /><span>{dicomFrame + 1}/{dicomProfile.number_of_frames}</span></label>}
          <label>{language === "en" ? "Window preset" : "Preset window"}<select value={windowCenter != null && windowWidth != null ? `${windowCenter}:${windowWidth}` : "auto"} onChange={event => { if (event.target.value === "auto") { setWindowCenter(undefined); setWindowWidth(undefined); } else { const [center, width] = event.target.value.split(":").map(Number); setWindowCenter(center); setWindowWidth(width); } }}><option value="auto">Auto VOI LUT</option>{dicomProfile.window_presets.map(preset => <option key={`${preset.name}-${preset.center}-${preset.width}`} value={`${preset.center}:${preset.width}`}>{preset.name} · C {preset.center} / W {preset.width}</option>)}</select></label>
          <label>C<input type="number" value={windowCenter ?? ""} onChange={event => setWindowCenter(event.target.value === "" ? undefined : Number(event.target.value))} /></label>
          <label>W<input type="number" min="1" value={windowWidth ?? ""} onChange={event => setWindowWidth(event.target.value === "" ? undefined : Number(event.target.value))} /></label>
          <label><input type="checkbox" checked={dicomInvert} onChange={event => setDicomInvert(event.target.checked)} />{language === "en" ? "Invert" : "Inversi"}</label>
          {dicomProfile.pixel_spacing && <small>{language === "en" ? "Calibrated" : "Terkalibrasi"}: {dicomProfile.pixel_spacing.row_mm} × {dicomProfile.pixel_spacing.column_mm} mm/px</small>}
        </div>}
        <div className="imageStage">
          {displayedPreview ? <div className="imageWrap" style={{ transform: `scale(${zoom}) rotate(${rotation}deg) scaleX(${flipHorizontal ? -1 : 1}) scaleY(${flipVertical ? -1 : 1})`, filter: `brightness(${brightness}%) contrast(${contrast}%)` }}>
            <PreviewImageWithOverlay
              preview={displayedPreview}
              originalImageWidth={Number(activeImage?.width || activeCase?.metadata?.width || activeCase?.metadata?.Columns || 0)}
              originalImageHeight={Number(activeImage?.height || activeCase?.metadata?.height || activeCase?.metadata?.Rows || 0)}
              annotations={showAnn ? overlayAnnotations : []}
              showLabels={showLabels}
              showConf={showConf}
              tool={annotationTool}
              selectedId={selectedAnnotationId}
              onSelect={selectAnnotation}
              onCreate={createManualAnnotation}
              onCoordinateChange={(id, coordinate, action) => updateAnnotation(id, { coordinate }, action, `Reviewer ${action} annotation geometry.`)}
            />
          </div> : <div className="empty">{copy.uploadToStart}</div>}
        </div>
        {preview && <div className="layers">
          <label><input type="checkbox" checked={showAnn} onChange={e => setShowAnn(e.target.checked)} /> {copy.annotations}</label>
          <label><input type="checkbox" checked={showLabels} onChange={e => setShowLabels(e.target.checked)} /> {copy.labels}</label>
          <label><input type="checkbox" checked={showConf} onChange={e => setShowConf(e.target.checked)} /> {language === "en" ? "confidence" : "tingkat keyakinan"}</label>
        </div>}
      </section>
      <aside className="panel aiout workspacePanel" ref={workspacePanelRef}>
        {!activeCase ? <div className="workspaceEmpty"><Bot size={24} /><h3>{language === "en" ? "Review results will appear here" : "Hasil peninjauan akan muncul di sini"}</h3><p>{language === "en" ? "Import an image, then run the analysis." : "Impor gambar, lalu jalankan analisis."}</p></div> : <>
        <div className="sideTabs">
          {(["AI Output", "Result Cards", "Annotations", "Report"] as WorkspaceTab[]).map(tab => <button key={tab} className={sideTab === tab ? "active" : ""} onClick={() => setSideTab(tab)}>{tabIcon(tab)}<span>{tab === "AI Output" ? (language === "en" ? "AI summary" : "Ringkasan AI") : tab === "Result Cards" ? (language === "en" ? "Findings" : "Temuan") : tab === "Annotations" ? (language === "en" ? "Annotations" : "Anotasi") : (language === "en" ? "Report" : "Laporan")}</span></button>)}
        </div>
        <label className="secondaryToolSelect"><span>{language === "en" ? "More tools" : "Alat lainnya"}</span><select value={(["AI Chat", "Trust", "DICOM Safety"] as WorkspaceTab[]).includes(sideTab) ? sideTab : ""} onChange={event => event.target.value && setSideTab(event.target.value as WorkspaceTab)}><option value="">{language === "en" ? "Choose only when needed…" : "Pilih hanya saat dibutuhkan…"}</option>{(["AI Chat", "Trust", "DICOM Safety"] as WorkspaceTab[]).map(tab => <option value={tab} key={tab}>{workspaceTabText(tab, language)}</option>)}</select></label>
        {busy && <div className="warn">{copy.processing}</div>}
        {error && <div className="warn">{error}</div>}
        {sideTab === "AI Output" && (analysis ? <AnalysisView analysis={analysis} /> : <p>{copy.noAnalysis}</p>)}
        {sideTab === "Result Cards" && <ResultCardsPanel
          activeCase={activeCase}
          setActiveCase={setActiveCase}
          analysis={analysis}
          setAnalysis={setAnalysis}
          selectedCardId={selectedResultCardId}
          onSelectCard={setSelectedResultCardId}
          onFocusAnnotation={selectAnnotation}
          onFocusReport={focusReportStatement}
        />}
        {sideTab === "Annotations" && <AnnotationPanel
          activeCase={activeCase}
          annotations={currentAnnotations}
          pixelSpacing={dicomProfile?.pixel_spacing}
          selectedId={selectedAnnotationId}
          onSelect={selectAnnotation}
          onUpdate={updateAnnotation}
          onDelete={deleteManualAnnotation}
          resultCards={(analysis || activeCase?.analysis)?.result_cards || []}
          onLink={linkAnnotation}
          onFocusResultCard={focusResultCard}
          onFocusReport={focusReportStatement}
          onRerunAI={rerunWithValidationFeedback}
          rerunBusy={busy}
          filter={annotationFilter}
          onFilterChange={setAnnotationFilter}
          onBatchReview={reviewAnnotationBatch}
        />}
        {sideTab === "Report" && <ReportPage
          activeCase={activeCase}
          analysis={analysis}
          annotations={currentAnnotations}
          selectedStatementId={selectedReportStatementId}
          onFocusAnnotation={selectAnnotation}
          onFocusResultCard={focusResultCard}
        />}
        {sideTab === "AI Chat" && <ChatPanel activeCase={activeCase} setActiveCase={setActiveCase} />}
        {sideTab === "Trust" && <TrustPanel activeCase={activeCase} analysis={analysis} />}
        {sideTab === "DICOM Safety" && <DicomSafetyPanel activeCase={activeCase} image={activeImage} />}
        </>}
      </aside>
    </div>
  );
}

function tabIcon(tab: WorkspaceTab) {
  if (tab === "Result Cards") return <ClipboardCheck size={15} />;
  if (tab === "Annotations") return <Layers size={15} />;
  if (tab === "Report") return <FileText size={15} />;
  if (tab === "AI Chat") return <MessageSquare size={15} />;
  if (tab === "Trust") return <ShieldCheck size={15} />;
  if (tab === "DICOM Safety") return <ShieldCheck size={15} />;
  return <Bot size={15} />;
}

function friendlyTechnicalText(value: unknown, language: UiLanguage) {
  let text = String(value || "");
  const normalized = text.trim().toLowerCase().replaceAll("_", " ");
  if (language === "en") {
    return text
      .replace(/fallback only/gi, "manual confirmation needed")
      .replace(/fallback/gi, "default mode")
      .replace(/demo(?:-[a-z0-9-]+)?/gi, "default mode")
      .replace(/disabled/gi, "not active");
  }
  if (normalized === "fallback only") return "Perlu konfirmasi manual";
  if (normalized === "fallback" || normalized === "fallback heuristic") return "Mode bawaan";
  if (normalized === "demo global review region") return "Area pemeriksaan umum";
  if (normalized === "fallback no confirmed abnormality") return "Belum ada kelainan yang dikonfirmasi";
  if (normalized === "unknown") return "Belum diketahui";
  if (normalized === "general x-ray") return "X-ray umum";
  if (normalized === "unknown/general x-ray") return "X-ray umum / belum dikenali";
  if (normalized === "not analyzed") return "Belum dianalisis";
  if (normalized.includes("body part is not confidently identified")) return "Area tubuh belum dikenali dengan yakin. Pilih area tubuh secara manual sebelum melanjutkan.";
  return text
    .replace(/fallback[_ -]?only/gi, "perlu konfirmasi manual")
    .replace(/fallback[_ -]?mode/gi, "mode bawaan")
    .replace(/demo[_ -]?mode/gi, "mode bawaan")
    .replace(/fallback/gi, "mode bawaan")
    .replace(/demo(?:-[a-z0-9-]+)?/gi, "mode bawaan")
    .replace(/backend/gi, "layanan aplikasi")
    .replace(/runtime/gi, "pengaturan AI")
    .replace(/disabled/gi, "tidak aktif")
    .replace(/model VLM\/MedRAX/gi, "model AI tambahan")
    .replace(/foreign body/gi, "benda asing")
    .replace(/overexposed/gi, "terlalu terang")
    .replace(/checklist/gi, "daftar pemeriksaan")
    .replace(/reviewer/gi, "pemeriksa")
    .replace(/mode\s+mode bawaan/gi, "mode bawaan")
    .replace(/mode bawaan\s*\/\s*mode bawaan/gi, "mode bawaan");
}

function friendlyAnalysisMode(value: unknown, language: UiLanguage) {
  const mode = String(value || "").toLowerCase();
  if (!mode || mode === "not analyzed") return language === "en" ? "Not analyzed" : "Belum dianalisis";
  if (mode.includes("demo") || mode.includes("fallback") || mode === "disabled") return language === "en" ? "Built-in Demo" : "Demo bawaan";
  if (mode === "ollama" || mode === "huggingface-local") return language === "en" ? "Local AI model" : "Model AI lokal";
  if (mode === "openai-compatible") return language === "en" ? "Connected AI model" : "Model AI tersambung";
  if (mode === "medrax-tool-pipeline") return language === "en" ? "AI tool pipeline" : "Rangkaian alat AI";
  return friendlyTechnicalText(value, language).replaceAll("_", " ");
}

function reviewStatusText(value: unknown, language: UiLanguage) {
  const key = String(value || "unreviewed");
  if (language === "en") return key.replaceAll("_", " ");
  return ({ unreviewed: "belum ditinjau", accepted: "diterima", rejected: "ditolak", uncertain: "belum pasti", needs_follow_up: "perlu tindak lanjut" } as Record<string, string>)[key] || key.replaceAll("_", " ");
}

function workspaceTabText(tab: WorkspaceTab, language: UiLanguage) {
  if (language === "en") return tab;
  return ({ "AI Output": "Output AI", "Result Cards": "Kartu Hasil", Annotations: "Anotasi", Report: "Laporan", "AI Chat": "Chat AI", Trust: "Kepercayaan & asal", "DICOM Safety": "Keamanan DICOM" } as Record<WorkspaceTab, string>)[tab];
}

function WorkspaceStats({ activeCase, analysis }: { activeCase: CaseRecord | null; analysis: AnalysisResult | null }) {
  const { language, copy } = useUiLanguage();
  return <div className="workspaceStats">
    <div><span>{language === "en" ? "Case" : "Kasus"}</span><b>{activeCase ? (language === "en" ? "Ready" : "Siap") : (language === "en" ? "Empty" : "Kosong")}</b></div>
    <div><span>{copy.quality}</span><b>{typeof analysis?.image_quality?.score === "number" ? analysis.image_quality.score.toFixed(2) : "n/a"}</b></div>
    <div><span>{copy.results}</span><b>{analysis?.result_cards?.length || 0}</b></div>
    <div><span>{language === "en" ? copy.trace : "Riwayat proses"}</span><b>{analysis?.model_trace?.length || 0}</b></div>
  </div>;
}

function AnatomyRoutePanel({ route, compact = false }: { route: NonNullable<AnalysisResult["anatomy_route"]>; compact?: boolean }) {
  const { language } = useUiLanguage();
  const taxonomy = textList(route.finding_taxonomy);
  const requiredViews = textList(route.required_views);
  const warnings = textList(route.warnings);
  return <section className={`anatomyRoutePanel ${compact ? "compact" : ""}`}>
    <div className="row"><b>{friendlyTechnicalText(route.profile_label, language)}</b><span>{friendlyTechnicalText(route.support_status || "unknown", language).replaceAll("_", " ")}</span></div>
    <div className="anatomyRouteFacts">
      <span>{language === "en" ? "Anatomy" : "Anatomi"}<b>{friendlyTechnicalText(route.anatomy, language)}</b></span>
      <span>{language === "en" ? "Side" : "Sisi"}<b>{friendlyTechnicalText(route.laterality, language)}</b></span>
      <span>{language === "en" ? "View" : "Proyeksi"}<b>{route.view}</b></span>
      <span>{language === "en" ? "Detection confidence" : "Keyakinan pengenalan"}<b>{typeof route.confidence === "number" ? `${Math.round(route.confidence * 100)}%` : "n/a"} / {friendlyTechnicalText(route.source || "unknown", language).replaceAll("_", " ")}</b></span>
    </div>
    {!compact && <>
      <details className="technicalDisclosure"><summary>{language === "en" ? "Technical details" : "Detail teknis"}</summary><div>
        <small>{route.model_slot}: {friendlyAnalysisMode(route.selected_model, language)}</small>
        <div className="taxonomyChips">{taxonomy.map(item => <span key={item}>{item}</span>)}</div>
        <small>{language === "en" ? "Expected views" : "Proyeksi yang diharapkan"}: {requiredViews.join("; ")}</small>
      </div></details>
    </>}
    {warnings.map((warning, index) => <small className="caution" key={`${route.profile_id}-${index}`}>{friendlyTechnicalText(warning, language)}</small>)}
  </section>;
}

type AnnotationDrag = {
  kind: "draw" | "move" | "resize" | "vertex";
  id?: string;
  handle?: "nw" | "ne" | "sw" | "se";
  vertexIndex?: number;
  startX: number;
  startY: number;
  startCoordinate?: Annotation["coordinate"];
};

function PreviewImageWithOverlay(props: {
  preview: string;
  originalImageWidth: number;
  originalImageHeight: number;
  annotations: Annotation[];
  showLabels: boolean;
  showConf: boolean;
  tool: AnnotationTool;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: (coordinate: Annotation["coordinate"], originalWidth: number, originalHeight: number) => void;
  onCoordinateChange: (id: string, coordinate: Annotation["coordinate"], action: "moved" | "resized") => void;
}) {
  const { preview, originalImageWidth, originalImageHeight, annotations, showLabels, showConf, tool, selectedId, onSelect, onCreate, onCoordinateChange } = props;
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [size, setSize] = useState<ImageBoxSize | null>(null);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const updateSize = () => {
      setSize({
        displayWidth: img.clientWidth || img.naturalWidth,
        displayHeight: img.clientHeight || img.naturalHeight,
        naturalWidth: img.naturalWidth || img.clientWidth,
        naturalHeight: img.naturalHeight || img.clientHeight,
      });
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(img);
    window.addEventListener("resize", updateSize);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateSize);
    };
  }, [preview]);

  return <>
    <img ref={imgRef} src={preview} alt="X-ray preview" onLoad={() => {
      const img = imgRef.current;
      if (!img) return;
      setSize({
        displayWidth: img.clientWidth || img.naturalWidth,
        displayHeight: img.clientHeight || img.naturalHeight,
        naturalWidth: img.naturalWidth || img.clientWidth,
        naturalHeight: img.naturalHeight || img.clientHeight,
      });
    }} />
    <InteractiveAnnotationOverlay
      annotations={annotations}
      originalImageWidth={originalImageWidth}
      originalImageHeight={originalImageHeight}
      showLabels={showLabels}
      showConf={showConf}
      imageSize={size}
      tool={tool}
      selectedId={selectedId}
      onSelect={onSelect}
      onCreate={onCreate}
      onCoordinateChange={onCoordinateChange}
    />
  </>;
}

function annotationColor(annotation: Annotation) {
  const source = String(annotation.source || "");
  if (annotation.review_status === "rejected") return "#94a3b8";
  if (source.includes("manual")) return "#ef4444";
  if (source.includes("fallback")) return "#f59e0b";
  if (source.includes("segmentation")) return "#a78bfa";
  return "#2dd4bf";
}

function hasBoxCoordinate(annotation: Annotation) {
  const coordinate = annotation.coordinate;
  return Boolean(
    coordinate &&
    ["bbox", "grounding_box"].includes(coordinate.type) &&
    Number.isFinite(coordinate.x) &&
    Number.isFinite(coordinate.y) &&
    Number.isFinite(coordinate.width) &&
    Number.isFinite(coordinate.height) &&
    coordinate.width > 0 &&
    coordinate.height > 0
  );
}

function hasEllipseCoordinate(annotation: Annotation) {
  const coordinate = annotation.coordinate;
  return coordinate?.type === "ellipse" && coordinate.width > 0 && coordinate.height > 0;
}

function hasLengthCoordinate(annotation: Annotation) {
  return annotation.coordinate?.type === "length" && coordinatePoints(annotation.coordinate).length === 2;
}

function InteractiveAnnotationOverlay(props: {
  annotations: Annotation[];
  originalImageWidth: number;
  originalImageHeight: number;
  showLabels: boolean;
  showConf: boolean;
  imageSize: ImageBoxSize | null;
  tool: AnnotationTool;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: (coordinate: Annotation["coordinate"], originalWidth: number, originalHeight: number) => void;
  onCoordinateChange: (id: string, coordinate: Annotation["coordinate"], action: "moved" | "resized") => void;
}) {
  const { annotations, originalImageWidth, originalImageHeight, showLabels, showConf, imageSize, tool, selectedId, onSelect, onCreate, onCoordinateChange } = props;
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<AnnotationDrag | null>(null);
  const [draft, setDraft] = useState<{ id?: string; coordinate: Annotation["coordinate"] } | null>(null);
  const [polygonDraft, setPolygonDraft] = useState<[number, number][]>([]);
  const originalWidth = originalImageWidth > 0 ? originalImageWidth : (imageSize?.naturalWidth || 1);
  const originalHeight = originalImageHeight > 0 ? originalImageHeight : (imageSize?.naturalHeight || 1);
  const displayWidth = imageSize?.displayWidth || 1;
  const displayHeight = imageSize?.displayHeight || 1;

  useEffect(() => {
    if (tool !== "polygon") setPolygonDraft([]);
  }, [tool, originalWidth, originalHeight]);

  useEffect(() => {
    function keydown(event: KeyboardEvent) {
      if (tool !== "polygon") return;
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select")) return;
      if (event.key === "Escape") setPolygonDraft([]);
      if (event.key === "Enter") finalizePolygon();
      if (event.key === "Backspace") {
        event.preventDefault();
        setPolygonDraft(current => current.slice(0, -1));
      }
    }
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [tool, polygonDraft, originalWidth, originalHeight]);

  function point(event: React.PointerEvent<SVGSVGElement | SVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: Math.max(0, Math.min(originalWidth, (event.clientX - rect.left) * originalWidth / rect.width)),
      y: Math.max(0, Math.min(originalHeight, (event.clientY - rect.top) * originalHeight / rect.height))
    };
  }

  function startDraw(event: React.PointerEvent<SVGSVGElement>) {
    if (event.target !== event.currentTarget) return;
    if (tool === "select") {
      onSelect(null);
      return;
    }
    const p = point(event);
    if (tool === "point") {
      onCreate({ type: "point", x: p.x, y: p.y, width: 0, height: 0, points: [[p.x, p.y]], coordinate_space: "original_image" }, originalWidth, originalHeight);
      return;
    }
    if (tool === "polygon") {
      setPolygonDraft(current => [...current, [p.x, p.y]]);
      return;
    }
    dragRef.current = { kind: "draw", startX: p.x, startY: p.y };
    const type = tool === "ellipse" ? "ellipse" : tool === "length" ? "length" : "bbox";
    setDraft({ coordinate: { type, x: p.x, y: p.y, width: 0, height: 0, points: type === "length" ? [[p.x, p.y], [p.x, p.y]] : [], coordinate_space: "original_image" } });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function finalizePolygon() {
    const unique = polygonDraft.filter((item, index, list) => index === 0 || Math.hypot(item[0] - list[index - 1][0], item[1] - list[index - 1][1]) >= 2);
    if (unique.length < 3 || polygonArea(unique) < 4) return;
    const bounds = polygonBounds(unique);
    onCreate({ type: "polygon", ...bounds, points: unique, coordinate_space: "original_image" }, originalWidth, originalHeight);
    setPolygonDraft([]);
  }

  function startMove(event: React.PointerEvent<SVGElement>, annotation: Annotation) {
    event.stopPropagation();
    onSelect(annotation.id);
    if (tool !== "select" || annotation.locked || !(hasBoxCoordinate(annotation) || hasEllipseCoordinate(annotation) || hasLengthCoordinate(annotation) || hasPointCoordinate(annotation) || hasPolygonCoordinate(annotation))) return;
    const p = point(event);
    dragRef.current = { kind: "move", id: annotation.id, startX: p.x, startY: p.y, startCoordinate: { ...annotation.coordinate } };
    setDraft({ id: annotation.id, coordinate: { ...annotation.coordinate } });
    svgRef.current?.setPointerCapture(event.pointerId);
  }

  function startVertex(event: React.PointerEvent<SVGCircleElement>, annotation: Annotation, vertexIndex: number) {
    event.stopPropagation();
    onSelect(annotation.id);
    if (tool !== "select" || annotation.locked || !hasPolygonCoordinate(annotation)) return;
    const p = point(event);
    dragRef.current = { kind: "vertex", id: annotation.id, vertexIndex, startX: p.x, startY: p.y, startCoordinate: { ...annotation.coordinate, points: coordinatePoints(annotation.coordinate) } };
    setDraft({ id: annotation.id, coordinate: { ...annotation.coordinate, points: coordinatePoints(annotation.coordinate) } });
    svgRef.current?.setPointerCapture(event.pointerId);
  }

  function startResize(event: React.PointerEvent<SVGRectElement>, annotation: Annotation, handle: AnnotationDrag["handle"]) {
    event.stopPropagation();
    if (annotation.locked || !hasBoxCoordinate(annotation)) return;
    const p = point(event);
    dragRef.current = { kind: "resize", id: annotation.id, handle, startX: p.x, startY: p.y, startCoordinate: { ...annotation.coordinate } };
    setDraft({ id: annotation.id, coordinate: { ...annotation.coordinate } });
    svgRef.current?.setPointerCapture(event.pointerId);
  }

  function move(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const p = point(event);
    if (drag.kind === "draw") {
      const type = draft?.coordinate.type || "bbox";
      setDraft({ coordinate: {
        type,
        x: Math.min(drag.startX, p.x),
        y: Math.min(drag.startY, p.y),
        width: Math.abs(p.x - drag.startX),
        height: Math.abs(p.y - drag.startY),
        points: type === "length" ? [[drag.startX, drag.startY], [p.x, p.y]] : [],
        coordinate_space: "original_image"
      } });
      return;
    }
    const start = drag.startCoordinate;
    if (!start || !drag.id) return;
    if (drag.kind === "vertex" && start.type === "polygon") {
      const points = coordinatePoints(start);
      if (drag.vertexIndex == null || !points[drag.vertexIndex]) return;
      points[drag.vertexIndex] = [p.x, p.y];
      const bounds = polygonBounds(points);
      setDraft({ id: drag.id, coordinate: { ...start, ...bounds, points } });
      return;
    }
    if (drag.kind === "move") {
      if (start.type === "point") {
        const x = Math.max(0, Math.min(originalWidth, start.x + p.x - drag.startX));
        const y = Math.max(0, Math.min(originalHeight, start.y + p.y - drag.startY));
        setDraft({ id: drag.id, coordinate: { ...start, x, y, points: [[x, y]] } });
        return;
      }
      if (start.type === "polygon") {
        const points = coordinatePoints(start);
        const bounds = polygonBounds(points);
        const dx = Math.max(-bounds.x, Math.min(originalWidth - bounds.x - bounds.width, p.x - drag.startX));
        const dy = Math.max(-bounds.y, Math.min(originalHeight - bounds.y - bounds.height, p.y - drag.startY));
        const movedPoints = points.map(item => [item[0] + dx, item[1] + dy] as [number, number]);
        setDraft({ id: drag.id, coordinate: { ...start, ...polygonBounds(movedPoints), points: movedPoints } });
        return;
      }
      if (start.type === "length") {
        const points = coordinatePoints(start);
        const bounds = polygonBounds(points);
        const dx = Math.max(-bounds.x, Math.min(originalWidth - bounds.x - bounds.width, p.x - drag.startX));
        const dy = Math.max(-bounds.y, Math.min(originalHeight - bounds.y - bounds.height, p.y - drag.startY));
        const movedPoints = points.map(item => [item[0] + dx, item[1] + dy] as [number, number]);
        setDraft({ id: drag.id, coordinate: { ...start, ...polygonBounds(movedPoints), points: movedPoints } });
        return;
      }
      const x = Math.max(0, Math.min(originalWidth - start.width, start.x + p.x - drag.startX));
      const y = Math.max(0, Math.min(originalHeight - start.height, start.y + p.y - drag.startY));
      setDraft({ id: drag.id, coordinate: { ...start, x, y } });
      return;
    }
    let left = start.x;
    let top = start.y;
    let right = start.x + start.width;
    let bottom = start.y + start.height;
    if (drag.handle?.includes("w")) left = Math.min(p.x, right - 4);
    if (drag.handle?.includes("e")) right = Math.max(p.x, left + 4);
    if (drag.handle?.includes("n")) top = Math.min(p.y, bottom - 4);
    if (drag.handle?.includes("s")) bottom = Math.max(p.y, top + 4);
    setDraft({ id: drag.id, coordinate: { ...start, x: left, y: top, width: right - left, height: bottom - top } });
  }

  function finish(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag || !draft) return;
    if (svgRef.current?.hasPointerCapture(event.pointerId)) svgRef.current.releasePointerCapture(event.pointerId);
    dragRef.current = null;
    if (drag.kind === "draw") {
      const validLength = draft.coordinate.type === "length" && Math.hypot(draft.coordinate.width, draft.coordinate.height) >= 4;
      const validArea = draft.coordinate.type !== "length" && draft.coordinate.width >= 4 && draft.coordinate.height >= 4;
      if (validLength || validArea) onCreate(draft.coordinate, originalWidth, originalHeight);
    } else if (drag.id) {
      if (draft.coordinate.type === "polygon" && !isValidPolygonPoints(coordinatePoints(draft.coordinate))) {
        setDraft(null);
        return;
      }
      onCoordinateChange(drag.id, draft.coordinate, drag.kind === "move" ? "moved" : "resized");
    }
    setDraft(null);
  }

  function displayCoordinate(annotation: Annotation) {
    const coordinate = draft?.id === annotation.id ? draft.coordinate : annotation.coordinate;
    const sourceWidth = Number(annotation.transform_metadata?.original_width || originalWidth);
    const sourceHeight = Number(annotation.transform_metadata?.original_height || originalHeight);
    if (!coordinate) return null;
    const safeSourceWidth = sourceWidth > 0 ? sourceWidth : originalWidth;
    const safeSourceHeight = sourceHeight > 0 ? sourceHeight : originalHeight;
    return {
      x: coordinate.x * displayWidth / safeSourceWidth,
      y: coordinate.y * displayHeight / safeSourceHeight,
      width: coordinate.width * displayWidth / safeSourceWidth,
      height: coordinate.height * displayHeight / safeSourceHeight
    };
  }

  function displayShapePoints(annotation: Annotation, coordinate = annotation.coordinate) {
    const sourceWidth = Number(annotation.transform_metadata?.original_width || originalWidth) || originalWidth;
    const sourceHeight = Number(annotation.transform_metadata?.original_height || originalHeight) || originalHeight;
    return coordinatePoints(coordinate).map(item => [item[0] * displayWidth / sourceWidth, item[1] * displayHeight / sourceHeight] as [number, number]);
  }

  function displayPoint(annotation: Annotation, coordinate = annotation.coordinate) {
    const sourceWidth = Number(annotation.transform_metadata?.original_width || originalWidth) || originalWidth;
    const sourceHeight = Number(annotation.transform_metadata?.original_height || originalHeight) || originalHeight;
    return { x: coordinate.x * displayWidth / sourceWidth, y: coordinate.y * displayHeight / sourceHeight };
  }

  const handleSize = 9;
  return <svg
    ref={svgRef}
    className={`annotationOverlay ${tool !== "select" ? "drawing" : ""}`}
    viewBox={`0 0 ${displayWidth} ${displayHeight}`}
    onPointerDown={startDraw}
    onPointerMove={move}
    onPointerUp={finish}
    onDoubleClick={event => { if (tool === "polygon") { event.preventDefault(); finalizePolygon(); } }}
    onPointerCancel={() => { dragRef.current = null; setDraft(null); }}
  >
    {annotations.filter(annotation => annotation.visible !== false && hasPointCoordinate(annotation)).map(annotation => {
      const coordinate = draft?.id === annotation.id ? draft.coordinate : annotation.coordinate;
      const p = displayPoint(annotation, coordinate);
      const selected = annotation.id === selectedId;
      const color = annotationColor(annotation);
      const confidenceLabel = annotationOrigin(annotation) === "ai" ? `${annotationConfidencePercent(annotation.confidence)}%` : annotationOrigin(annotation) === "reviewer" ? "manual" : "guide";
      const label = `${showLabels ? annotation.label || "point" : ""}${showLabels && showConf ? " " : ""}${showConf ? confidenceLabel : ""}`;
      return <g key={annotation.id} className={annotation.review_status === "rejected" ? "rejectedAnnotation" : ""}>
        <circle className={`annotationPoint ${selected ? "selected" : ""}`} cx={p.x} cy={p.y} r={selected ? 8 : 6} stroke={color} onPointerDown={event => startMove(event, annotation)} />
        <line className="annotationPointCross" x1={p.x - 11} y1={p.y} x2={p.x + 11} y2={p.y} stroke={color} />
        <line className="annotationPointCross" x1={p.x} y1={p.y - 11} x2={p.x} y2={p.y + 11} stroke={color} />
        {label && <text className="annotationLabel" x={p.x + 10} y={Math.max(14, p.y - 8)} fill={color}>{label}</text>}
      </g>;
    })}
    {annotations.filter(annotation => annotation.visible !== false && hasPolygonCoordinate(annotation)).map(annotation => {
      const coordinate = draft?.id === annotation.id ? draft.coordinate : annotation.coordinate;
      const points = displayShapePoints(annotation, coordinate);
      const selected = annotation.id === selectedId;
      const color = annotationColor(annotation);
      const confidenceLabel = annotationOrigin(annotation) === "ai" ? `${annotationConfidencePercent(annotation.confidence)}%` : annotationOrigin(annotation) === "reviewer" ? "manual" : "guide";
      const label = `${showLabels ? annotation.label || "polygon" : ""}${showLabels && showConf ? " " : ""}${showConf ? confidenceLabel : ""}`;
      return <g key={annotation.id} className={annotation.review_status === "rejected" ? "rejectedAnnotation" : ""}>
        <polygon className={`annotationPolygon ${selected ? "selected" : ""}`} points={points.map(item => item.join(",")).join(" ")} stroke={color} onPointerDown={event => startMove(event, annotation)} />
        {label && <text className="annotationLabel" x={points[0][0] + 5} y={Math.max(14, points[0][1] - 7)} fill={color}>{label}</text>}
        {selected && !annotation.locked && points.map((item, index) => <circle key={index} className="polygonVertex" cx={item[0]} cy={item[1]} r={5} fill={color} onPointerDown={event => startVertex(event, annotation, index)} />)}
      </g>;
    })}
    {annotations.filter(annotation => annotation.visible !== false && hasLengthCoordinate(annotation)).map(annotation => {
      const coordinate = draft?.id === annotation.id ? draft.coordinate : annotation.coordinate;
      const points = displayShapePoints(annotation, coordinate);
      const selected = annotation.id === selectedId;
      const color = annotationColor(annotation);
      return <g key={annotation.id} className={annotation.review_status === "rejected" ? "rejectedAnnotation" : ""}>
        <line className={`annotationLength ${selected ? "selected" : ""}`} x1={points[0][0]} y1={points[0][1]} x2={points[1][0]} y2={points[1][1]} stroke={color} onPointerDown={event => startMove(event, annotation)} />
        <circle cx={points[0][0]} cy={points[0][1]} r={4} fill={color} /><circle cx={points[1][0]} cy={points[1][1]} r={4} fill={color} />
        {showLabels && <text className="annotationLabel" x={(points[0][0] + points[1][0]) / 2 + 5} y={(points[0][1] + points[1][1]) / 2 - 5} fill={color}>{annotation.label}</text>}
      </g>;
    })}
    {annotations.filter(annotation => annotation.visible !== false && hasEllipseCoordinate(annotation)).map(annotation => {
      const box = displayCoordinate(annotation)!;
      const selected = annotation.id === selectedId;
      const color = annotationColor(annotation);
      return <g key={annotation.id} className={annotation.review_status === "rejected" ? "rejectedAnnotation" : ""}>
        <ellipse className={`annotationEllipse ${selected ? "selected" : ""}`} cx={box.x + box.width / 2} cy={box.y + box.height / 2} rx={box.width / 2} ry={box.height / 2} stroke={color} onPointerDown={event => startMove(event, annotation)} />
        {showLabels && <text className="annotationLabel" x={box.x + 5} y={Math.max(14, box.y - 6)} fill={color}>{annotation.label}</text>}
      </g>;
    })}
    {annotations.filter(annotation => annotation.visible !== false && hasBoxCoordinate(annotation)).map(annotation => {
      const box = displayCoordinate(annotation);
      if (!box) return null;
      const selected = annotation.id === selectedId;
      const color = annotationColor(annotation);
      const confidenceLabel = annotationOrigin(annotation) === "ai" ? `${annotationConfidencePercent(annotation.confidence)}%` : annotationOrigin(annotation) === "reviewer" ? "manual" : "guide";
      const label = `${showLabels ? annotation.label || "annotation" : ""}${showLabels && showConf ? " " : ""}${showConf ? confidenceLabel : ""}`;
      const handles = [
        ["nw", box.x, box.y], ["ne", box.x + box.width, box.y],
        ["sw", box.x, box.y + box.height], ["se", box.x + box.width, box.y + box.height]
      ] as const;
      return <g key={annotation.id} className={annotation.review_status === "rejected" ? "rejectedAnnotation" : ""}>
        <rect
          className={`annotationRect ${String(annotation.source || "").includes("fallback") ? "fallback" : ""} ${selected ? "selected" : ""}`}
          x={box.x} y={box.y} width={box.width} height={box.height}
          stroke={color}
          onPointerDown={event => startMove(event, annotation)}
        />
        {label && <text className="annotationLabel" x={box.x + 5} y={Math.max(14, box.y - 6)} fill={color}>{label}</text>}
        {selected && !annotation.locked && handles.map(([handle, x, y]) => <rect
          key={handle}
          className={`resizeHandle ${handle}`}
          x={x - handleSize / 2} y={y - handleSize / 2} width={handleSize} height={handleSize}
          fill={color}
          onPointerDown={event => startResize(event, annotation, handle)}
        />)}
        {selected && annotation.locked && <Lock className="annotationLock" x={box.x + box.width - 18} y={box.y + 5} width={14} height={14} color={color} />}
      </g>;
    })}
    {draft && !draft.id && (() => {
      const box = { x: draft.coordinate.x * displayWidth / originalWidth, y: draft.coordinate.y * displayHeight / originalHeight, width: draft.coordinate.width * displayWidth / originalWidth, height: draft.coordinate.height * displayHeight / originalHeight };
      if (draft.coordinate.type === "length") {
        const points = coordinatePoints(draft.coordinate).map(item => [item[0] * displayWidth / originalWidth, item[1] * displayHeight / originalHeight]);
        return <line className="annotationLength manualDraft" x1={points[0]?.[0]} y1={points[0]?.[1]} x2={points[1]?.[0]} y2={points[1]?.[1]} />;
      }
      if (draft.coordinate.type === "ellipse") return <ellipse className="annotationEllipse manualDraft" cx={box.x + box.width / 2} cy={box.y + box.height / 2} rx={box.width / 2} ry={box.height / 2} />;
      return <rect className="annotationRect manualDraft" x={box.x} y={box.y} width={box.width} height={box.height} />;
    })()}
    {polygonDraft.length > 0 && <g className="polygonDraft">
      <polyline points={polygonDraft.map(item => `${item[0] * displayWidth / originalWidth},${item[1] * displayHeight / originalHeight}`).join(" ")} />
      {polygonDraft.map((item, index) => <circle key={index} cx={item[0] * displayWidth / originalWidth} cy={item[1] * displayHeight / originalHeight} r={4} />)}
      <text x={polygonDraft[0][0] * displayWidth / originalWidth + 6} y={Math.max(14, polygonDraft[0][1] * displayHeight / originalHeight - 8)}>Double-click or Enter to finish</text>
    </g>}
  </svg>;
}

function Metadata({ activeCase }: { activeCase: CaseRecord | null }) {
  const { copy } = useUiLanguage();
  return <div className="meta"><h3>{copy.metadata}</h3>{activeCase ? Object.entries(activeCase.metadata || {}).map(([k, v]) => <div key={k}><span>{k}</span><b>{String(v)}</b></div>) : <p>{copy.noFile}</p>}</div>;
}

function AnalysisView({ analysis }: { analysis: AnalysisResult }) {
  const { language } = useUiLanguage();
  const r = (analysis.systematic_reading || {}) as Record<string, unknown>;
  const warnings = textList(analysis.warnings);
  const annotations = asList<Annotation>(analysis.annotations);
  const readingLabels: Record<string, string> = language === "en" ? {
    body_region: "Body region", adequacy: "Image quality", view_projection: "Projection", alignment_anatomy: "Alignment and anatomy", soft_tissue: "Soft tissue", bone_joint: "Bones and joints", lung_pleura_mediastinum_cardiac: "Chest structures", abdomen: "Abdomen", device_foreign_body: "Devices or foreign bodies", final_impression: "Summary", limitation: "Limitations",
  } : {
    body_region: "Area tubuh", adequacy: "Kualitas gambar", view_projection: "Proyeksi", alignment_anatomy: "Posisi dan anatomi", soft_tissue: "Jaringan lunak", bone_joint: "Tulang dan sendi", lung_pleura_mediastinum_cardiac: "Struktur dada", abdomen: "Abdomen", device_foreign_body: "Alat atau benda asing", final_impression: "Ringkasan", limitation: "Keterbatasan",
  };
  return <div className="analysis">
    {warnings[0] && <div className="warn">{friendlyTechnicalText(warnings[0], language)}</div>}
    {analysis.anatomy_route && <AnatomyRoutePanel route={analysis.anatomy_route} />}
    <h3>{language === "en" ? "Systematic review" : "Pemeriksaan sistematis"}</h3>
    {Object.keys(readingLabels).map(k => <p key={k}><b>{readingLabels[k]}</b><br />{friendlyTechnicalText(r[k] || "-", language)}</p>)}
    <h3>{language === "en" ? "Annotations" : "Anotasi"}</h3>
    {annotations.map(a => <p key={a.id}><Layers size={14} /> <b>{friendlyTechnicalText(a.label || (language === "en" ? "annotation" : "anotasi"), language)}</b> {typeof a.confidence === "number" ? a.confidence.toFixed(2) : "n/a"}<br /><small>{friendlyTechnicalText(a.source, language)}: {friendlyTechnicalText(a.explanation, language)}</small></p>)}
  </div>;
}

function scoreText(card: ResultCard) {
  const score = card.probability ?? card.confidence;
  return typeof score === "number" ? score.toFixed(2) : "n/a";
}

function findingText(card: ResultCard) {
  return String(card.finding || "candidate finding").replaceAll("_", " ");
}

function annotationCoordinateText(annotation: Annotation) {
  const coordinate = annotation.coordinate;
  if (!coordinate) return "coordinate unavailable";
  if (coordinate.type === "point") return `point: x=${Math.round(coordinate.x)}, y=${Math.round(coordinate.y)}`;
  if (coordinate.type === "polygon") return `polygon: ${coordinatePoints(coordinate).length} vertices`;
  return `${coordinate.type}: x=${Math.round(coordinate.x)}, y=${Math.round(coordinate.y)}, w=${Math.round(coordinate.width)}, h=${Math.round(coordinate.height)}`;
}

function ResultCardsPanel(props: {
  activeCase: CaseRecord | null;
  setActiveCase: (c: CaseRecord | null) => void;
  analysis: AnalysisResult | null;
  setAnalysis: (a: AnalysisResult | null) => void;
  selectedCardId: string | null;
  onSelectCard: (id: string | null) => void;
  onFocusAnnotation: (id: string) => void;
  onFocusReport: (id: string) => void;
}) {
  const { language } = useUiLanguage();
  const { activeCase, setActiveCase, analysis, setAnalysis, selectedCardId, onSelectCard, onFocusAnnotation, onFocusReport } = props;
  const currentAnalysis = analysis || activeCase?.analysis || null;
  const cards = asList<ResultCard>(currentAnalysis?.result_cards);
  const differential = asList<DifferentialCandidate>(currentAnalysis?.differential_diagnosis);
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const saveVersionRef = useRef(0);
  const [saveError, setSaveError] = useState("");

  async function updateCard(cardId: string, patch: Partial<ResultCard>) {
    if (!activeCase || !currentAnalysis) return;
    const nextAnalysis = {
      ...currentAnalysis,
      result_cards: asList<ResultCard>(currentAnalysis.result_cards).map(card => card.id === cardId ? { ...card, ...patch } : card)
    };
    const nextAnnotations = preferredAnnotations(activeCase.annotations, nextAnalysis.annotations);
    const activeImage = activeStudyImageClient(activeCase);
    const images = caseStudyImages(activeCase);
    const activeIndex = activeImage ? images.findIndex(image => image.image_id === activeImage.image_id) : -1;
    const activeAnnotations = nextAnnotations.filter(annotation => annotationBelongsToImage(annotation, activeImage, activeIndex === 0, images));
    const syncedAnalysis = { ...nextAnalysis, annotations: activeAnnotations };
    const nextCase = { ...activeCase, analysis: syncedAnalysis, report: syncedAnalysis.report, annotations: nextAnnotations };
    setAnalysis(syncedAnalysis);
    setActiveCase(nextCase);
    setSaveError("");
    const version = ++saveVersionRef.current;
    saveQueueRef.current = saveQueueRef.current
      .catch(() => undefined)
      .then(async () => {
        const savedCase = await api.saveCase(nextCase);
        if (version === saveVersionRef.current) {
          setActiveCase(savedCase);
          setAnalysis(savedCase.analysis || syncedAnalysis);
        }
      })
      .catch(exc => { setSaveError(`${language === "en" ? "Result card was not saved" : "Kartu hasil belum tersimpan"}: ${String(exc)}`); });
    await saveQueueRef.current;
  }

  return <section className="resultCardsPanel">
    <div className="referenceHeader compact">
      <ClipboardCheck size={18} />
      <div>
        <h3>{language === "en" ? "Reviewable result cards" : "Kartu hasil yang dapat ditinjau"}</h3>
        <p>{language === "en" ? "AI candidate diagnosis, evidence, uncertainty, annotations, and human review status." : "Kandidat diagnosis AI, bukti, ketidakpastian, anotasi, dan status tinjauan manusia."}</p>
      </div>
    </div>
    {saveError && <div className="warn">{saveError}</div>}
    {cards.length ? <div className="resultCardList">
      {cards.map(card => <div className={`resultCard ${card.status} ${card.id === selectedCardId ? "selected" : ""}`} key={card.id}>
        <button className="resultCardSelect" onClick={() => onSelectCard(card.id === selectedCardId ? null : card.id)}>
          <b>{friendlyTechnicalText(findingText(card), language)}</b>
          <span>{card.status} / {scoreText(card)}</span>
        </button>
        <p>{friendlyTechnicalText(card.candidate_diagnosis, language)}</p>
        <small>{language === "en" ? "Source" : "Sumber"}: {friendlyTechnicalText(card.source, language)}</small>
        <small>{language === "en" ? "Image" : "Gambar"}: {textList(card.source_image_ids).join(", ") || activeCase?.active_image_id || (language === "en" ? "legacy primary" : "gambar utama lama")}{textList(card.source_views).length ? ` / ${textList(card.source_views).join(", ")}` : ""}</small>
        <div className="resultCardEvidence">
          {asList<ResultEvidence>(card.evidence).slice(0, 4).map((item, index) => <span key={`${card.id}-${index}`}>{friendlyTechnicalText(item.kind, language)}: {friendlyTechnicalText(item.text, language)}</span>)}
        </div>
        <div className="resultCardLinks">
          <span>{language === "en" ? "Annotations" : "Anotasi"}</span>
          <div className="groundedLinkRow">{textList(card.annotation_refs).length ? textList(card.annotation_refs).map(ref => <button key={ref} onClick={() => onFocusAnnotation(ref)}>{ref.slice(0, 8)}</button>) : <small>{language === "en" ? "none" : "tidak ada"}</small>}</div>
          <button className="reportJump" onClick={() => onFocusReport("report:findings")}><FileText size={14} />{language === "en" ? "View report findings" : "Lihat temuan laporan"}</button>
          <span>{language === "en" ? "Trace" : "Jejak"}: {textList(card.model_trace_refs).length ? textList(card.model_trace_refs).join(", ") : (language === "en" ? "not linked" : "belum ditautkan")}</span>
        </div>
        <div className="uncertainty">{friendlyTechnicalText(card.uncertainty_reason, language)}</div>
        <div className="nextAction">{friendlyTechnicalText(card.next_safe_action, language)}</div>
        <label>{language === "en" ? "Human review" : "Tinjauan manusia"}
          <select value={card.review_status} onChange={e => updateCard(card.id, { review_status: e.target.value as ResultCard["review_status"] })}>
            {(["unreviewed", "accepted", "rejected", "uncertain", "needs_follow_up"] as const).map(status => <option value={status} key={status}>{reviewStatusText(status, language)}</option>)}
          </select>
        </label>
        <label>{language === "en" ? "Reviewer note" : "Catatan reviewer"}
          <textarea defaultValue={card.reviewer_note} onBlur={e => updateCard(card.id, { reviewer_note: e.currentTarget.value })} placeholder={language === "en" ? "Optional local reviewer note..." : "Catatan reviewer lokal (opsional)..."} />
        </label>
      </div>)}
    </div> : <p>{language === "en" ? "No result cards yet. Run the AI workflow to compose reviewable candidate outputs." : "Belum ada kartu hasil. Jalankan alur AI untuk menyusun kandidat output yang dapat ditinjau."}</p>}
    <div className="referenceHeader compact differentialHeader">
      <Stethoscope size={18} />
      <div>
        <h3>{language === "en" ? "Tentative differential assistance" : "Bantuan diagnosis banding sementara"}</h3>
        <p>{language === "en" ? "Organized from structured research signals; never a confirmed diagnosis or triage decision." : "Disusun dari sinyal riset terstruktur; bukan diagnosis atau keputusan triase yang terkonfirmasi."}</p>
      </div>
    </div>
    {differential.length ? <div className="resultCardList differentialList">
      {differential.map(item => <div className="resultCard differentialCard" key={item.id}>
        <b>{item.label}</b>
        <small>{item.review_status} / tentative / source {textList(item.source_image_ids).join(", ") || "current image"}</small>
        <div className="differentialEvidence">
          <div><strong>{language === "en" ? "Evidence for" : "Bukti mendukung"}</strong>{textList(item.evidence_for).map((text, index) => <span key={`for-${index}`}>{friendlyTechnicalText(text, language)}</span>)}</div>
          <div><strong>{language === "en" ? "Evidence against / limitations" : "Bukti tidak mendukung / keterbatasan"}</strong>{textList(item.evidence_against).map((text, index) => <span key={`against-${index}`}>{friendlyTechnicalText(text, language)}</span>)}</div>
          <div><strong>{language === "en" ? "Missing information" : "Informasi yang belum ada"}</strong>{textList(item.missing_information).map((text, index) => <span key={`missing-${index}`}>{friendlyTechnicalText(text, language)}</span>)}</div>
        </div>
        <div className="uncertainty">{item.uncertainty}</div>
        <div className="nextAction">{item.next_safe_action}</div>
        <small className="caution">{item.safety_note}</small>
      </div>)}
    </div> : <p>{language === "en" ? "No structured differential candidate is available. This is preferable to inventing unsupported diagnoses." : "Belum ada kandidat diagnosis banding terstruktur. Ini lebih aman daripada mengarang diagnosis tanpa bukti."}</p>}
  </section>;
}

function AnnotationPanel(props: {
  activeCase: CaseRecord | null;
  annotations: Annotation[];
  pixelSpacing?: { row_mm: number; column_mm: number } | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onUpdate: (id: string, patch: Partial<Annotation>, action?: string, note?: string) => void;
  onDelete: (id: string) => void;
  resultCards: ResultCard[];
  onLink: (annotationId: string, resultCardId: string, reportStatementId: string) => void;
  onFocusResultCard: (id: string) => void;
  onFocusReport: (id: string) => void;
  onRerunAI: () => Promise<void>;
  rerunBusy: boolean;
  filter: AnnotationWorkspaceFilter;
  onFilterChange: (filter: AnnotationWorkspaceFilter) => void;
  onBatchReview: (ids: string[], status: AnnotationReviewStatus) => void;
}) {
  const { language } = useUiLanguage();
  const { activeCase, annotations, pixelSpacing, selectedId, onSelect, onUpdate, onDelete, resultCards, onLink, onFocusResultCard, onFocusReport, onRerunAI, rerunBusy, filter, onFilterChange, onBatchReview } = props;
  const annotationList = asList<Annotation>(annotations);
  const visibleAnnotationList = filterWorkspaceAnnotations(annotationList, filter);
  const visibleUnreviewedAiIds = visibleAnnotationList.filter(annotation => annotationOrigin(annotation) === "ai" && (annotation.review_status || "unreviewed") === "unreviewed").map(annotation => annotation.id);
  const cardList = asList<ResultCard>(resultCards);
  const [reviewExport, setReviewExport] = useState<AnnotationReviewExport | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  async function exportPng() {
    if (!activeCase) return;
    const res = await api.exportAnnotations(activeCase.case_id);
    alert(`Annotated PNG: ${res.path}`);
  }
  async function exportReviewPackage() {
    if (!activeCase) return;
    setExportBusy(true);
    try {
      setReviewExport(await api.exportAnnotationReview(activeCase.case_id));
    } finally {
      setExportBusy(false);
    }
  }
  return <section className="annotationPanel">
    <div className="referenceHeader compact">
      <Layers size={18} />
      <div>
        <h3>{language === "en" ? "Interactive annotations" : "Anotasi interaktif"}</h3>
        <p>{language === "en" ? "AI creates candidate annotations. You review, edit, accept, or reject them; every change remains traceable." : "AI membuat kandidat anotasi. Anda dapat meninjau, mengedit, menerima, atau menolaknya; setiap perubahan tetap terlacak."}</p>
      </div>
    </div>
    <div className="annotationValidationLoop">
      <div><b>{language === "en" ? "Human-in-the-loop validation" : "Validasi human-in-the-loop"}</b><span>{language === "en" ? "After correcting annotations, ask AI to inspect the source image again using your decisions as feedback. New output is still unreviewed." : "Setelah mengoreksi anotasi, minta AI meninjau gambar sumber lagi dengan keputusan Anda sebagai umpan balik. Output baru tetap harus ditinjau."}</span></div>
      <button className="primaryAction" onClick={() => void onRerunAI()} disabled={!activeCase || rerunBusy}><Bot size={16} />{rerunBusy ? (language === "en" ? "Re-reviewing…" : "Meninjau ulang…") : (language === "en" ? "Ask AI to re-review" : "Minta AI tinjau ulang")}</button>
    </div>
    <div className="annotationSummary">
      <div><span>Total</span><b>{annotationList.length}</b></div>
      <div><span>{language === "en" ? "AI-generated" : "Dibuat AI"}</span><b>{annotationList.filter(a => annotationOrigin(a) === "ai").length}</b></div>
      <div><span>{language === "en" ? "Segmentation" : "Segmentasi"}</span><b>{annotationList.filter(a => String(a.source || "").includes("segmentation")).length}</b></div>
      <div><span>{language === "en" ? "General guide" : "Panduan umum"}</span><b>{annotationList.filter(a => String(a.source || "").includes("fallback")).length}</b></div>
    </div>
    <div className="annotationQueueControls">
      <label>{language === "en" ? "Origin" : "Asal"}<select value={filter.origin} onChange={event => onFilterChange({ ...filter, origin: event.target.value as AnnotationWorkspaceFilter["origin"] })}><option value="all">{language === "en" ? "All origins" : "Semua asal"}</option><option value="ai">AI</option><option value="reviewer">{language === "en" ? "Reviewer" : "Reviewer"}</option><option value="guidance">{language === "en" ? "Guide" : "Panduan"}</option></select></label>
      <label>{language === "en" ? "Review state" : "Status review"}<select value={filter.reviewStatus} onChange={event => onFilterChange({ ...filter, reviewStatus: event.target.value as AnnotationWorkspaceFilter["reviewStatus"] })}><option value="all">{language === "en" ? "All states" : "Semua status"}</option>{(["unreviewed", "accepted", "rejected", "uncertain", "needs_follow_up"] as const).map(status => <option value={status} key={status}>{reviewStatusText(status, language)}</option>)}</select></label>
      <label className="confidenceFilter"><span>{language === "en" ? "Minimum AI confidence" : "Confidence AI minimum"}<b>{filter.minimumAiConfidence}%</b></span><input type="range" min="0" max="100" step="5" value={filter.minimumAiConfidence} onChange={event => onFilterChange({ ...filter, minimumAiConfidence: Number(event.target.value) })} /></label>
      <span className="annotationQueueCount">{visibleAnnotationList.length} / {annotationList.length} {language === "en" ? "shown" : "ditampilkan"}</span>
    </div>
    <div className="annotationBatchActions">
      <span>{language === "en" ? "Visible unreviewed AI candidates" : "Kandidat AI belum ditinjau yang terlihat"}: <b>{visibleUnreviewedAiIds.length}</b></span>
      <button disabled={!visibleUnreviewedAiIds.length} onClick={() => onBatchReview(visibleUnreviewedAiIds, "accepted")}><CheckCircle2 size={15} />{language === "en" ? "Accept visible" : "Terima yang terlihat"}</button>
      <button disabled={!visibleUnreviewedAiIds.length} onClick={() => onBatchReview(visibleUnreviewedAiIds, "rejected")}><XCircle size={15} />{language === "en" ? "Reject visible" : "Tolak yang terlihat"}</button>
    </div>
    <div className="annotationExportActions">
      <button onClick={exportPng} disabled={!activeCase || !annotationList.length}><Download size={16} />{language === "en" ? "Reviewed PNG" : "PNG hasil tinjauan"}</button>
      <button onClick={exportReviewPackage} disabled={!activeCase || !annotationList.length || exportBusy}><Archive size={16} />{exportBusy ? (language === "en" ? "Exporting..." : "Mengekspor...") : (language === "en" ? "AI vs reviewed package" : "Paket AI vs hasil tinjauan")}</button>
    </div>
    {reviewExport && <div className="reviewExportSummary">
      <b>{language === "en" ? "Review package ready" : "Paket tinjauan siap"}</b>
      <span>{reviewExport.bundle.review_summary.ai_original_count} AI-original / {reviewExport.bundle.review_summary.reviewed_count} reviewed / {reviewExport.bundle.review_summary.changed_count} changed</span>
      <code>{reviewExport.ai_original_png}</code>
      <code>{reviewExport.reviewed_png}</code>
      <code>{reviewExport.comparison_json}</code>
    </div>}
    {visibleAnnotationList.length ? <div className="annotationList">
      {visibleAnnotationList.map(annotation => {
        const selected = annotation.id === selectedId;
        const linkedResultIds = textList(annotation.linked_result_card_ids);
        const origin = annotationOrigin(annotation);
        const originText = origin === "ai" ? (language === "en" ? "AI-generated" : "Dibuat AI") : origin === "reviewer" ? (language === "en" ? "Reviewer-created" : "Dibuat reviewer") : (language === "en" ? "Guidance region" : "Area panduan");
        return <div className={`annotationCard ${selected ? "selected" : ""}`} key={annotation.id}>
          <button className="annotationSelect" onClick={() => onSelect(selected ? null : annotation.id)}>
            <span className="annotationSwatch" style={{ background: annotationColor(annotation) }} />
            <span className="annotationIdentity">
              <b>{friendlyTechnicalText(annotation.label, language)}</b>
              <small>{originText}{origin === "ai" ? ` · ${language === "en" ? "AI confidence" : "Keyakinan AI"} ${annotationConfidencePercent(annotation.confidence)}%` : origin === "reviewer" ? ` · ${language === "en" ? "manual geometry" : "geometri manual"}` : ` · ${language === "en" ? "not a pathology confidence" : "bukan confidence patologi"}`}</small>
            </span>
            <span className="annotationState"><strong className={`annotationConfidence ${origin}`}>{origin === "ai" ? `${annotationConfidencePercent(annotation.confidence)}%` : origin === "reviewer" ? (language === "en" ? "manual" : "manual") : (language === "en" ? "guide" : "panduan")}</strong>{annotation.visible ? <Eye size={15} /> : <EyeOff size={15} />}{reviewStatusText(annotation.review_status, language)}</span>
          </button>
          <code>{annotationCoordinateText(annotation)}</code>
          {measureAnnotation(annotation, pixelSpacing) && <strong className="annotationMeasurement">{measureAnnotation(annotation, pixelSpacing)!.value} {measureAnnotation(annotation, pixelSpacing)!.unit}{!pixelSpacing ? ` (${language === "en" ? "uncalibrated pixels" : "piksel tanpa kalibrasi"})` : ""}</strong>}
          {selected && <div className="annotationEditor">
            <form className="annotationLabelForm" onSubmit={event => {
              event.preventDefault();
              const label = String(new FormData(event.currentTarget).get("annotation_label") || "").trim();
              if (label && label !== annotation.label) onUpdate(annotation.id, { label }, "edited", "Reviewer changed annotation label.");
            }}>
              <label>{language === "en" ? "Label" : "Label"}<input name="annotation_label" defaultValue={annotation.label} /></label>
              <button type="submit" title="Save annotation label"><Save size={16} /></button>
            </form>
            <label>{language === "en" ? "Review" : "Tinjauan"}
              <select value={annotation.review_status || "unreviewed"} onChange={event => onUpdate(
                annotation.id,
                { review_status: event.target.value as AnnotationReviewStatus },
                "reviewed",
                `Reviewer marked annotation ${event.target.value}.`
              )}>
                {(["unreviewed", "accepted", "rejected", "uncertain", "needs_follow_up"] as const).map(status => <option value={status} key={status}>{reviewStatusText(status, language)}</option>)}
              </select>
            </label>
            <div className="groundedLinkEditor">
              <b>{language === "en" ? "Grounded links" : "Tautan berbasis bukti"}</b>
              <label>{language === "en" ? "Result card" : "Kartu hasil"}
                <select data-testid={`annotation-result-link-${annotation.id}`} value={linkedResultIds[0] || ""} onChange={event => onLink(annotation.id, event.target.value, annotation.linked_report_statement_id || "")}>
                  <option value="">{language === "en" ? "Not linked" : "Belum ditautkan"}</option>
                  {cardList.map(card => <option key={card.id} value={card.id}>{friendlyTechnicalText(findingText(card), language)}</option>)}
                </select>
              </label>
              <label>{language === "en" ? "Report section" : "Bagian laporan"}
                <select data-testid={`annotation-report-link-${annotation.id}`} value={annotation.linked_report_statement_id || ""} onChange={event => onLink(annotation.id, linkedResultIds[0] || "", event.target.value)}>
                  <option value="">{language === "en" ? "Not linked" : "Belum ditautkan"}</option>
                  <option value="report:findings">{language === "en" ? "Findings" : "Temuan"}</option>
                  <option value="report:impression">{language === "en" ? "Impression" : "Kesan"}</option>
                </select>
              </label>
              <div className="groundedLinkRow">
                {linkedResultIds[0] && <button onClick={() => onFocusResultCard(linkedResultIds[0])}><ClipboardCheck size={14} />{language === "en" ? "Open result" : "Buka hasil"}</button>}
                {annotation.linked_report_statement_id && <button onClick={() => onFocusReport(annotation.linked_report_statement_id!)}><FileText size={14} />{language === "en" ? "Open report" : "Buka laporan"}</button>}
              </div>
            </div>
            <div className="annotationSourceIdentity">
              <b>{language === "en" ? "Source image" : "Gambar sumber"}</b>
              <span>{annotation.source_image_id || activeCase?.title || "primary"}</span>
              <small>Image #{(annotation.source_image_index ?? 0) + 1}{annotation.source_view ? ` / ${annotation.source_view}` : ""}{annotation.source_series_id ? ` / series ${annotation.source_series_id}` : ""}</small>
              {annotation.source_model && <small>Model: {annotation.source_model}{annotation.source_model_version ? ` / ${annotation.source_model_version}` : ""}</small>}
            </div>
            <label>{language === "en" ? "Reviewer note" : "Catatan reviewer"}
              <textarea defaultValue={annotation.reviewer_note || ""} onBlur={event => {
                if (event.currentTarget.value !== (annotation.reviewer_note || "")) onUpdate(annotation.id, { reviewer_note: event.currentTarget.value }, "edited", "Reviewer note updated.");
              }} placeholder={language === "en" ? "Correction note or decision rationale..." : "Catatan koreksi atau alasan keputusan..."} />
            </label>
            <div className="annotationActions">
              <button title={annotation.visible ? (language === "en" ? "Hide annotation" : "Sembunyikan anotasi") : (language === "en" ? "Show annotation" : "Tampilkan anotasi")} onClick={() => onUpdate(annotation.id, { visible: !annotation.visible }, "visibility", annotation.visible ? "Annotation hidden by reviewer." : "Annotation shown by reviewer.")}>{annotation.visible ? <EyeOff size={16} /> : <Eye size={16} />}{annotation.visible ? (language === "en" ? "Hide" : "Sembunyikan") : (language === "en" ? "Show" : "Tampilkan")}</button>
              <button title={annotation.locked ? (language === "en" ? "Unlock geometry" : "Buka kunci geometri") : (language === "en" ? "Lock geometry" : "Kunci geometri")} onClick={() => onUpdate(annotation.id, { locked: !annotation.locked }, "locked", annotation.locked ? "Annotation unlocked." : "Annotation locked.")}>{annotation.locked ? <Unlock size={16} /> : <Lock size={16} />}{annotation.locked ? (language === "en" ? "Unlock" : "Buka kunci") : (language === "en" ? "Lock" : "Kunci")}</button>
              {annotation.original_coordinate && <button title={language === "en" ? "Restore original AI geometry" : "Pulihkan geometri AI asli"} onClick={() => onUpdate(annotation.id, { coordinate: { ...annotation.original_coordinate! } }, "resized", "Original annotation geometry restored.")}><RotateCcw size={16} />{language === "en" ? "Restore" : "Pulihkan"}</button>}
              {String(annotation.source || "").includes("manual") && <button className="dangerAction" title={language === "en" ? "Delete manual annotation" : "Hapus anotasi manual"} onClick={() => onDelete(annotation.id)}><Trash2 size={16} />{language === "en" ? "Delete" : "Hapus"}</button>}
            </div>
            <small>{friendlyTechnicalText(annotation.explanation, language)}</small>
            <small>{annotation.revision_history?.length || 0} {language === "en" ? "recorded revision(s)" : "revisi tercatat"}</small>
          </div>}
          {String(annotation.source || "").includes("fallback") && <small className="caution">{language === "en" ? "This is a general review area, not the location of an abnormality." : "Area ini hanya panduan pemeriksaan umum, bukan lokasi kelainan."}</small>}
        </div>;
      })}
    </div> : <p>{annotationList.length ? (language === "en" ? "No annotations match these filters." : "Tidak ada anotasi yang cocok dengan filter ini.") : (language === "en" ? "No annotations yet. Run analysis or create one manually." : "Belum ada anotasi. Jalankan analisis atau buat anotasi manual.")}</p>}
  </section>;
}

function TrustPanel({ activeCase, analysis }: { activeCase: CaseRecord | null; analysis: AnalysisResult | null }) {
  const { language } = useUiLanguage();
  const [cards, setCards] = useState<ModelCard[]>([]);
  useEffect(() => { api.modelCards().then(value => setCards(asList<ModelCard>(value))).catch(() => setCards([])); }, []);
  async function exportAudit() {
    if (!activeCase) return;
    const res = await api.exportAudit(activeCase.case_id);
    alert(`Audit bundle: ${res.path}`);
  }
  const hashes = (analysis?.input_hashes || activeCase?.file_hashes) as AnalysisResult["input_hashes"] | undefined;
  const runtime = analysis?.runtime_snapshot || activeCase?.runtime || {};
  const trace = asList<AnalysisResult["model_trace"][number]>(analysis?.model_trace || activeCase?.analysis?.model_trace);
  const cardById = new Map(asList<ModelCard>(cards).map(card => [card.id, card]));
  const tracedCards = trace.map(item => cardById.get(item.model)).filter(Boolean) as ModelCard[];
  return <div className="trust">
    <div className="referenceHeader compact">
      <ShieldCheck size={18} />
      <div>
        <h3>{language === "en" ? "Why this output exists" : "Mengapa output ini ada"}</h3>
        <p>{language === "en" ? "Input identity, AI configuration, and processing history are retained for local audit." : "Identitas input, konfigurasi AI, dan riwayat proses disimpan untuk audit lokal."}</p>
      </div>
    </div>
    <div className="trustGrid">
      <div><b>Input hash</b><span>{hashes?.input?.digest ? `${hashes.input.digest.slice(0, 16)}...` : (language === "en" ? "not captured yet" : "belum direkam")}</span></div>
      <div><b>Preview hash</b><span>{hashes?.preview?.digest ? `${hashes.preview.digest.slice(0, 16)}...` : (language === "en" ? "not captured yet" : "belum direkam")}</span></div>
      <div><b>{language === "en" ? "Analysis mode" : "Mode analisis"}</b><span>{friendlyAnalysisMode(runtime.primary_backend || "not analyzed", language)}</span></div>
      <div><b>Trace</b><span>{trace.length} stage(s)</span></div>
    </div>
    {tracedCards.length > 0 && <div className="modelCardSummary">
      {tracedCards.map(card => <div key={card.id}><b>{card.name}</b><span>{card.clinical_status}</span></div>)}
    </div>}
    <button onClick={exportAudit} disabled={!activeCase}><Download size={16} />Audit JSON</button>
  </div>;
}

function DicomSafetyPanel({ activeCase, image }: { activeCase: CaseRecord | null; image: StudyImage | null }) {
  const { language } = useUiLanguage();
  const [report, setReport] = useState<DicomSafetyReport | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [exports, setExports] = useState<string[]>([]);
  const [exportChecks, setExportChecks] = useState<string[]>([]);
  const isDicom = Boolean(image?.is_dicom || image?.source_path?.toLowerCase().match(/\.(dcm|dicom)$/) || String(image?.format || "").toUpperCase() === "DICOM");

  useEffect(() => {
    setReport(null);
    setAcknowledged(false);
    setExports([]);
    setExportChecks([]);
    setError("");
    if (!activeCase || !image || !isDicom) return;
    setBusy(true);
    api.dicomSafety(activeCase.case_id, image.image_id)
      .then(setReport)
      .catch(exc => setError(String(exc)))
      .finally(() => setBusy(false));
  }, [activeCase?.case_id, image?.image_id, isDicom]);

  async function exportMetadata() {
    if (!activeCase || !image) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.exportDicomMetadata(activeCase.case_id, image.image_id);
      setExports(current => [...current, result.path]);
      const verification = result.payload.verification as Record<string, unknown> | undefined;
      setExportChecks(current => [...current, language === "en" ? `Metadata verification: ${verification?.passed === true ? "passed" : "review required"}` : `Verifikasi metadata: ${verification?.passed === true ? "lulus" : "perlu ditinjau"}`]);
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function exportDicom() {
    if (!activeCase || !image) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.exportDeidentifiedDicom(activeCase.case_id, image.image_id, acknowledged);
      setExports(current => [...current, String(result.path || "")].filter(Boolean));
      const verification = result.verification as Record<string, unknown> | undefined;
      setExportChecks(current => [...current, language === "en" ? `DICOM readback verification: ${verification?.passed === true ? "passed" : "review required"}` : `Verifikasi baca ulang DICOM: ${verification?.passed === true ? "lulus" : "perlu ditinjau"}`]);
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  if (!activeCase || !image) return <section className="dicomSafety"><h3>{language === "en" ? "DICOM Safety" : "Keamanan DICOM"}</h3><p>{language === "en" ? "Load a study image first." : "Muat gambar studi terlebih dahulu."}</p></section>;
  if (!isDicom) return <section className="dicomSafety"><h3>{language === "en" ? "DICOM Safety" : "Keamanan DICOM"}</h3><p>{language === "en" ? "The active image is not DICOM. DICOMweb remains disabled." : "Gambar aktif bukan DICOM. DICOMweb tetap dinonaktifkan."}</p></section>;
  const risk = report?.burned_in_annotation_risk;
  const requiresAcknowledgement = risk?.level === "high" || risk?.level === "unknown";
  const groups = ["patient", "study", "series", "acquisition", "private", "other"];
  return <section className="dicomSafety">
    <div className="referenceHeader compact"><ShieldCheck size={18} /><div><h3>{language === "en" ? "DICOM Safety" : "Keamanan DICOM"}</h3><p>{language === "en" ? "Local tag review and prototype de-identification. Verify every export before sharing." : "Tinjauan tag lokal dan de-identifikasi prototipe. Verifikasi setiap ekspor sebelum dibagikan."}</p></div></div>
    {busy && <div className="warn">{language === "en" ? "Reading local DICOM safety data..." : "Membaca data keamanan DICOM lokal..."}</div>}
    {error && <div className="warn">{error}</div>}
    {report && <>
      <div className={`dicomRisk ${risk?.level || "unknown"}`}>
        <b>{language === "en" ? "Burned-in annotation risk" : "Risiko anotasi tertanam"}: {risk?.level || (language === "en" ? "unknown" : "tidak diketahui")}</b>
        <span>{risk?.reason}</span>
        <small>{language === "en" ? "Pixel data is retained unchanged during export." : "Data piksel dipertahankan tanpa perubahan saat ekspor."}</small>
      </div>
      <div className="dicomFacts">
        <div><span>{language === "en" ? "Private tags" : "Tag privat"}</span><b>{report.private_tag_count}</b></div>
        <div><span>DICOMweb</span><b>{report.dicomweb_status}</b></div>
        <div><span>{language === "en" ? "Source hash" : "Hash sumber"}</span><b>{report.source_sha256.slice(0, 16)}...</b></div>
        <div><span>{language === "en" ? "Frames" : "Frame"}</span><b>{report.pixel_data_summary?.number_of_frames ?? (language === "en" ? "unknown" : "tidak diketahui")}</b></div>
        <div><span>Transfer syntax</span><b>{report.pixel_data_summary?.transfer_syntax_uid || "unknown"}</b></div>
        <div><span>Pixel export</span><b>{report.pixel_data_summary?.export_behavior || "review required"}</b></div>
      </div>
      {textList(report.warnings).map((warning, index) => <small className="caution" key={index}>{warning}</small>)}
      <div className="deidPreview">
        <h4>{language === "en" ? "De-identification preview" : "Pratinjau de-identifikasi"}</h4>
        {asList<DicomSafetyReport["deidentification_preview"][number]>(report.deidentification_preview).map((item, index) => <div key={`${item.keyword}-${index}`}><b>{item.keyword}</b><span>{item.action}</span><small>{item.replacement || "removed"}</small></div>)}
      </div>
      <div className="dicomTagViewer">
        <h4>{language === "en" ? "Local tag viewer" : "Penampil tag lokal"}</h4>
        <div className="warn compactWarn">{language === "en" ? "May contain sensitive patient data. Values stay in this local application." : "Mungkin mengandung data pasien sensitif. Nilai tetap berada di aplikasi lokal ini."}</div>
        {groups.map(group => {
          const tags = asList<DicomTag>(report.tag_groups?.[group]);
          return <details key={group} open={group === "patient" || group === "private"}>
            <summary>{group} ({tags.length})</summary>
            <div className="dicomTagList">{tags.length ? tags.map((tag, index) => <div key={`${tag.tag}-${index}`}>
              <code>{tag.tag}</code><b>{tag.keyword || tag.name}</b><span>{String(tag.value ?? "")}</span><small>{tag.action}</small>
            </div>) : <p>{language === "en" ? "No tags in this group." : "Tidak ada tag dalam grup ini."}</p>}</div>
          </details>;
        })}
      </div>
      {requiresAcknowledgement && <label className="dicomAcknowledgement"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} /> {language === "en" ? "I manually reviewed the pixel image for burned-in identifiers and accept the residual risk for this local prototype export." : "Saya telah meninjau gambar piksel untuk identitas yang tertanam dan menerima risiko tersisa pada ekspor prototipe lokal ini."}</label>}
      <div className="actions">
        <button onClick={exportMetadata} disabled={busy}><Download size={16} />{language === "en" ? "De-identified metadata JSON" : "JSON metadata terde-identifikasi"}</button>
        <button onClick={exportDicom} disabled={busy || (requiresAcknowledgement && !acknowledged)}><Download size={16} />{language === "en" ? "De-identified DICOM copy" : "Salinan DICOM terde-identifikasi"}</button>
      </div>
      {exports.map((path, index) => <code className="savedPath" key={`${path}-${index}`}>{path}</code>)}
      {exportChecks.map((check, index) => <small key={`${check}-${index}`}>{check}</small>)}
    </>}
  </section>;
}

function ChatPanel({ activeCase, setActiveCase }: { activeCase: CaseRecord | null; setActiveCase: (c: CaseRecord | null) => void }) {
  const { copy, language } = useUiLanguage();
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [runtimeState, setRuntimeState] = useState<{ backend: string; fallback: boolean } | null>(null);
  async function send() {
    if (!activeCase || !msg.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.chat(activeCase.case_id, msg, language);
      setActiveCase({ ...activeCase, chat_history: res.history });
      setRuntimeState({ backend: res.backend, fallback: res.fallback });
      setMsg("");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }
  return <section className="chat">
    <h2>{copy.chatTitle}</h2>
    <p>{language === "en" ? "Ask about the active image, report, annotations, uncertainty, or provenance. The answer follows the interface language." : "Tanyakan gambar aktif, laporan, anotasi, ketidakpastian, atau asal bukti. Jawaban mengikuti bahasa antarmuka."}</p>
    <div className="groundedLinkRow">{(language === "en" ? ["Summarize the main findings", "Explain the annotations", "What are the limitations?"] : ["Ringkas temuan utama", "Jelaskan anotasi", "Apa keterbatasannya?"]).map(prompt => <button key={prompt} disabled={!activeCase || busy} onClick={() => setMsg(prompt)}>{prompt}</button>)}</div>
    {runtimeState && <small>{language === "en" ? "Response mode" : "Mode jawaban"}: {runtimeState.backend}{runtimeState.fallback ? (language === "en" ? " · safe fallback" : " · fallback aman") : ""}</small>}
    {error && <div className="warn">{error}</div>}
    <div className="messages">{activeCase ? asList<CaseRecord["chat_history"][number]>(activeCase.chat_history).map((m, i) => <div key={i} className={String(m.role || "assistant")}>{String(m.content || "")}</div>) : <p>{copy.chooseCase}</p>}</div>
    <form className="composer" onSubmit={event => { event.preventDefault(); void send(); }}><input value={msg} onChange={e => setMsg(e.target.value)} placeholder={copy.chatPlaceholder} /><button type="submit" disabled={busy || !activeCase || !msg.trim()}><MessageSquare size={17} />{copy.send}</button></form>
  </section>;
}

function ReportPage(props: {
  activeCase: CaseRecord | null;
  analysis: AnalysisResult | null;
  annotations: Annotation[];
  selectedStatementId: string | null;
  onFocusAnnotation: (id: string) => void;
  onFocusResultCard: (id: string) => void;
}) {
  const { activeCase, analysis, annotations, selectedStatementId, onFocusAnnotation, onFocusResultCard } = props;
  const { language: uiLanguage, copy } = useUiLanguage();
  const language = uiLanguage;
  async function exportFmt(format: string) {
    if (!activeCase) return;
    const res = await api.exportReport(activeCase.case_id, format, language);
    alert(`${copy.exportDone}: ${res.path}`);
  }
  async function exportPng() {
    if (!activeCase) return;
    const res = await api.exportAnnotations(activeCase.case_id);
    alert(`Annotated PNG: ${res.path}`);
  }
  const report = analysis?.report || activeCase?.report;
  const resultCards = asList<ResultCard>(analysis?.result_cards || activeCase?.analysis?.result_cards);
  const annotationList = asList<Annotation>(annotations);
  const groundedStatements = buildGroundedReviewStatements(resultCards, annotationList, language);
  const sections = report ? [
    { id: "report:indication", idLabel: "Indikasi", enLabel: "Indication", value: report.indication },
    { id: "report:technique", idLabel: "Teknik", enLabel: "Technique", value: report.technique },
    { id: "report:grounded_review", idLabel: "Statement Review Grounded", enLabel: "Grounded Review Statements", value: groundedStatements.map(statement => statement.text).join("\n") },
    { id: "report:findings", idLabel: "Temuan", enLabel: "Findings", value: report.findings },
    { id: "report:impression", idLabel: "Kesan", enLabel: "Impression", value: report.impression },
    { id: "report:recommendation", idLabel: "Rekomendasi", enLabel: "Recommendation", value: report.recommendation }
  ] : [];
  const reportText = report ? `${language === "en" ? "Case identity" : "Identitas kasus"}: ${activeCase?.case_id}\n${sections.map(section => `${language === "en" ? section.enLabel : section.idLabel}: ${section.value}`).join("\n")}\n${language === "en" ? "Note" : "Catatan"}: ${report.watermark}` : "";
  return <section className="report">
    <div className="row"><h2>{copy.reportTitle}</h2><span>{copy.language}: {language === "en" ? copy.english : copy.indonesian}</span></div>
    {report && report.language && report.language !== language && <div className="warn">{language === "en" ? "This saved report was generated in another language. Run the AI workflow again to regenerate every clinical section in English." : "Laporan tersimpan ini dibuat dalam bahasa lain. Jalankan ulang alur AI agar seluruh bagian klinis dibuat dalam bahasa Indonesia."}</div>}
    {resultCards.length > 0 && <div className="reportResultCards">
      {resultCards.map(card => <button key={card.id} onClick={() => onFocusResultCard(card.id)}><b>{friendlyTechnicalText(findingText(card), uiLanguage)}</b><span>{card.status} / {scoreText(card)} / {card.review_status}</span></button>)}
    </div>}
    {report ? <div className="structuredReport">
      <div className="reportIdentity"><b>{language === "en" ? "Case / image identity" : "Identitas kasus / gambar"}</b><span>{activeCase?.case_id} / {activeCase?.active_image_id || "legacy primary"}</span></div>
      {sections.map(section => {
        const linkedAnnotations = annotationList.filter(annotation => annotation.linked_report_statement_id === section.id);
        return <section id={section.id} className={`reportSection ${selectedStatementId === section.id ? "selected" : ""}`} key={section.id}>
          <b>{language === "en" ? section.enLabel : section.idLabel}</b>
          {section.id === "report:grounded_review" ? <div className="groundedStatements">
            {groundedStatements.map(statement => <div key={statement.id}>
              <p>{statement.text}</p>
              {(statement.resultCardId || statement.annotationIds.length > 0) && <div className="groundedLinkRow">
                {statement.resultCardId && <button onClick={() => onFocusResultCard(statement.resultCardId!)}><ClipboardCheck size={14} />Result card</button>}
                {statement.annotationIds.map(annotationId => {
                  const annotation = annotationList.find(item => item.id === annotationId);
                  return <button key={annotationId} onClick={() => onFocusAnnotation(annotationId)}><Layers size={14} />{annotation?.label || annotationId.slice(0, 8)}</button>;
                })}
              </div>}
            </div>)}
          </div> : <p>{section.value || "-"}</p>}
          {section.id !== "report:grounded_review" && linkedAnnotations.length > 0 && <div className="groundedLinkRow">{linkedAnnotations.map(annotation => <button key={annotation.id} onClick={() => onFocusAnnotation(annotation.id)}><Layers size={14} />{annotation.label}</button>)}</div>}
        </section>;
      })}
      <small>{report.watermark}</small>
    </div> : <p>{copy.reportEmpty}</p>}
    <div className="actions"><button onClick={() => navigator.clipboard.writeText(reportText)}>{copy.reportCopy}</button><button onClick={() => exportFmt("markdown")}><Download size={16} />Markdown</button><button onClick={() => exportFmt("pdf")}><Download size={16} />PDF</button><button onClick={() => exportFmt("json")}><Download size={16} />JSON</button><button onClick={exportPng}>Annotated PNG</button></div>
  </section>;
}

function formatBytes(bytes?: number | null) {
  if (!bytes) return "unknown";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function statusClass(status: string) {
  return `statusChip ${status.toLowerCase().replaceAll("_", "-")}`;
}

function isActiveDownload(job: DownloadJob) {
  return ["queued", "downloading", "pausing", "cancelling"].includes(job.status);
}

function delay(ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

const REQUIRED_LOCAL_CARD_FIELDS = ["intended_use", "task", "license", "dataset_provenance", "limitations"];

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(item => String(item)).filter(Boolean) : [];
}

function safeExternalUrl(value: unknown): string {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : "";
  } catch {
    return "";
  }
}

function evidenceSummary(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return String(value || "");
  const record = value as Record<string, unknown>;
  if (record.summary) return String(record.summary);
  return Object.entries(record).map(([key, item]) => `${key}: ${String(item)}`).join(", ");
}

function splitEvidenceList(value: unknown): string[] {
  return String(value || "").split(/[\n,]/).map(item => item.trim()).filter(Boolean);
}

function asList<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function fileLooksDownloadable(file: string) {
  return /\.(safetensors|bin|gguf|onnx|pt|pth|json|model|txt|md)$/i.test(file);
}

function safeModelFilename(repo: string, file: string) {
  const leaf = file.split("/").pop() || "model-file";
  return `${repo.replace(/[\/\\]/g, "--")}--${leaf}`;
}

function cardDraftFromModel(model: LocalModelArtifact, detail?: Record<string, unknown> | null): Record<string, string | boolean> {
  const existing = (model.card || {}) as Record<string, unknown>;
  const evidence = existing.validation_evidence && typeof existing.validation_evidence === "object" && !Array.isArray(existing.validation_evidence)
    ? existing.validation_evidence as Record<string, unknown>
    : {};
  const coverage = evidence.subgroup_coverage && typeof evidence.subgroup_coverage === "object" && !Array.isArray(evidence.subgroup_coverage)
    ? evidence.subgroup_coverage as Record<string, unknown>
    : {};
  const readiness = ((detail?.card_readiness || {}) as Record<string, unknown>);
  const datasets = textList(readiness.datasets || detail?.datasets);
  const limitations = textList(detail?.safety_notes).join(" ") || String(existing.limitations || "");
  return {
    intended_use: String(existing.intended_use || detail?.fit_summary || "Research signal and diagnostic assistance draft only."),
    task: String(existing.task || readiness.pipeline_tag || detail?.pipeline_tag || detail?.task_type || model.task || "classification"),
    license: String(existing.license || readiness.license || detail?.license || ""),
    dataset_provenance: String(existing.dataset_provenance || datasets.join(", ") || ""),
    hardware: String(existing.hardware || detail?.vram_estimate || "local hardware, review required"),
    limitations: limitations || "Not clinically validated. Requires human review.",
    contraindicated_use: String(existing.contraindicated_use || "No confirmed diagnosis, emergency triage, or autonomous clinical decision."),
    protocol_id: String(evidence.protocol_id || ""),
    validation_dataset_name: String(evidence.dataset_name || ""),
    held_out_split: String(evidence.held_out_split || ""),
    case_count: evidence.case_count == null ? "" : String(evidence.case_count),
    label_count: evidence.label_count == null ? "" : String(evidence.label_count),
    metric_summary: evidenceSummary(evidence.metric_summary),
    false_alert_burden: evidenceSummary(evidence.false_alert_burden),
    missed_reference_summary: evidenceSummary(evidence.missed_reference_summary),
    known_failures: textList(evidence.known_failures).join("\n"),
    coverage_anatomy: textList(coverage.anatomy).join(", "),
    coverage_views: textList(coverage.views).join(", "),
    coverage_age_groups: textList(coverage.age_groups).join(", "),
    coverage_notes: String(coverage.notes || ""),
    validation_reviewer: String(evidence.reviewer || ""),
    review_date: String(evidence.review_date || ""),
    weights_filename: String(evidence.weights_filename || ""),
    artifact_hash: String(evidence.artifact_hash || ""),
    report_reference: String(evidence.report_reference || ""),
    human_reviewed: Boolean(existing.human_reviewed),
  };
}

function mergedCardDraft(model: LocalModelArtifact, draft: Record<string, string | boolean>) {
  return { ...cardDraftFromModel(model), ...draft };
}

function LocalModelManager({ selectedDetail }: { selectedDetail: Record<string, unknown> | null }) {
  const [localModels, setLocalModels] = useState<LocalModelArtifact[]>([]);
  const [cardDrafts, setCardDrafts] = useState<Record<string, Record<string, string | boolean>>>({});
  const [cardErrors, setCardErrors] = useState<Record<string, string[]>>({});
  const [savedCardPaths, setSavedCardPaths] = useState<Record<string, string>>({});
  const [cardBusy, setCardBusy] = useState("");
  const [importPath, setImportPath] = useState("");
  const [importResult, setImportResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedModel = selectedDetail;
  useEffect(() => { void refreshLocalModels().catch(exc => setError(String(exc))); }, []);
  async function refreshLocalModels() {
    setLocalModels(asList<LocalModelArtifact>(await api.localModels()));
  }
  function updateCardDraft(id: string, key: string, value: string | boolean) {
    setCardDrafts({ ...cardDrafts, [id]: { ...(cardDrafts[id] || {}), [key]: value } });
  }
  function prefillCardDraft(model: LocalModelArtifact) {
    setCardDrafts({ ...cardDrafts, [model.id]: cardDraftFromModel(model, selectedModel) });
    setCardErrors({ ...cardErrors, [model.id]: [] });
  }
  async function saveModelCard(model: LocalModelArtifact) {
    setCardBusy(model.id);
    setError("");
    try {
      const draft = mergedCardDraft(model, cardDrafts[model.id] || {});
      const missing = REQUIRED_LOCAL_CARD_FIELDS.filter(field => !String(draft[field] || "").trim());
      if (!draft.human_reviewed) missing.push("human_reviewed");
      if (missing.length) {
        setCardErrors({ ...cardErrors, [model.id]: missing });
        return;
      }
      const saved = await api.saveLocalModelCard({
        artifact_id: model.id,
        artifact_path: model.artifact_path,
        intended_use: draft.intended_use,
        task: draft.task,
        license: draft.license,
        dataset_provenance: draft.dataset_provenance,
        hardware: draft.hardware,
        limitations: draft.limitations,
        contraindicated_use: draft.contraindicated_use,
        validation_evidence: {
          protocol_id: draft.protocol_id,
          dataset_name: draft.validation_dataset_name,
          held_out_split: draft.held_out_split,
          case_count: draft.case_count === "" ? null : Number(draft.case_count),
          label_count: draft.label_count === "" ? null : Number(draft.label_count),
          metric_summary: { summary: draft.metric_summary },
          false_alert_burden: { summary: draft.false_alert_burden },
          missed_reference_summary: { summary: draft.missed_reference_summary },
          known_failures: splitEvidenceList(draft.known_failures),
          subgroup_coverage: {
            anatomy: splitEvidenceList(draft.coverage_anatomy),
            views: splitEvidenceList(draft.coverage_views),
            age_groups: splitEvidenceList(draft.coverage_age_groups),
            notes: draft.coverage_notes,
          },
          reviewer: draft.validation_reviewer,
          review_date: draft.review_date,
          weights_filename: draft.weights_filename,
          artifact_hash: draft.artifact_hash,
          report_reference: draft.report_reference,
        },
        human_reviewed: Boolean(draft.human_reviewed),
      });
      setCardErrors({ ...cardErrors, [model.id]: [] });
      setSavedCardPaths({ ...savedCardPaths, [model.id]: String(saved.card_path || "") });
      await refreshLocalModels();
    } catch (exc) {
      setError(String(exc));
    } finally {
      setCardBusy("");
    }
  }
  async function validateImportFolder() {
    if (!importPath.trim()) return;
    setBusy(true);
    setError("");
    setImportResult(null);
    try {
      const result = await api.importModel(importPath.trim());
      setImportResult(result);
      setLocalModels(asList<LocalModelArtifact>(await api.localModels()));
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  return <section className="setupSection">
    <h3>Imported models &amp; model cards</h3><p>Files in MedRay's model folder are detected automatically. Importing a file does not install its runtime. Load compatible GGUF or other weights in Ollama, LM Studio or your chosen server, then select that server model in Local AI.</p>
    {error && <p role="alert">{error}</p>}
    <label>Import a model file<input type="file" accept=".pt,.pth,.onnx,.safetensors,.gguf,.bin" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) { setBusy(true); setError(""); void setupApi.importFile(file).then(refreshLocalModels).catch(exc => setError(String(exc))).finally(() => setBusy(false)); } event.target.value = ""; }} /></label>
    <details><summary>Check an existing model folder</summary><p>Enter a folder inside MedRay's model storage. This checks its files without running repository code.</p><label>Folder path<input value={importPath} onChange={event => setImportPath(event.target.value)} /></label><button disabled={busy || !importPath.trim()} onClick={validateImportFolder}>Check folder</button>{importResult && <ImportValidationResult result={importResult} />}</details>
    <LocalRegistryPanel models={localModels.filter(model => !model.name.startsWith("nih-pc-chex-mimic"))} drafts={cardDrafts} errors={cardErrors} savedPaths={savedCardPaths} busyId={cardBusy} onRefresh={() => void refreshLocalModels().catch(exc => setError(String(exc)))} onDraft={updateCardDraft} onPrefill={prefillCardDraft} onSave={saveModelCard} selectedDetail={selectedDetail} onArchive={async model => { try { await setupApi.localAction("remove", model.id); await refreshLocalModels(); } catch (exc) { setError(String(exc)); } }} />
  </section>;
}

function ImportValidationResult({ result }: { result: Record<string, unknown> }) {
  const validation = (result.validation || {}) as Record<string, unknown>;
  const warnings = textList(validation.warnings);
  const files = textList(validation.files).slice(0, 10);
  return <div className="importResult">
    <div className="readinessBand">
      <div><span>Readiness</span><b>{String(validation.readiness || "not scanned")}</b></div>
      <div><span>Likely model</span><b>{String(validation.likely_model ?? false)}</b></div>
      <div><span>Task slot</span><b>{String(validation.task_slot || "classification_model")}</b></div>
      <div><span>Card</span><b>{String(validation.model_card_status || "missing")}</b></div>
    </div>
    {warnings.length > 0 && <div className="warn compactWarn">{warnings.join(" ")}</div>}
    <small>{String(validation.artifact_path || "")}</small>
    {String(validation.card_path || "").trim() && <small>Saved card JSON: {String(validation.card_path)}</small>}
    {files.length > 0 && <div className="fileList"><b>Scanned files</b>{files.map(file => <small key={file}>{file}</small>)}</div>}
  </div>;
}

function LocalRegistryPanel({
  models,
  drafts,
  errors,
  savedPaths,
  busyId,
  onRefresh,
  onDraft,
  onPrefill,
  onSave,
  selectedDetail,
  onArchive,
}: {
  models: LocalModelArtifact[];
  drafts: Record<string, Record<string, string | boolean>>;
  errors: Record<string, string[]>;
  savedPaths: Record<string, string>;
  busyId: string;
  onRefresh: () => void;
  onDraft: (id: string, key: string, value: string | boolean) => void;
  onPrefill: (model: LocalModelArtifact) => void;
  onSave: (model: LocalModelArtifact) => void;
  selectedDetail: Record<string, unknown> | null;
  onArchive: (model: LocalModelArtifact) => void;
}) {
  const installedModels = asList<LocalModelArtifact>(models);
  return <div className="localRegistry">
    <div className="row">
      <div>
        <h3>Local files</h3>
        <p>Review each model card here. Run and test the model through its compatible application in Local AI.</p>
      </div>
      <button onClick={onRefresh}><RefreshCw size={16} />Rescan</button>
    </div>
    <div className="localModelList">{installedModels.length ? installedModels.map(model => {
      const draft = mergedCardDraft(model, drafts[model.id] || {});
      const validationErrors = errors[model.id] || [];
      const cardPath = savedPaths[model.id] || model.card_path || String(model.card?.card_path || "");
      const hints = textList(model.detected_format_hints);
      const warnings = textList(model.warnings);
      const missingFields = textList(model.missing_card_fields);
      const missingEvidence = textList(model.validation_evidence_assessment?.missing_fields);
      return <div className="localModel" key={model.id}>
        <div className="row">
          <b>{model.name}</b>
          <span className={statusClass(model.runtime_eligible ? "installed" : "paused")}>{model.runtime_eligible ? "Card reviewed · runtime test required" : "Needs review"}</span>
        </div>
        <details><summary>Model card, files and validation</summary>
        <small>{model.artifact_type} / {model.artifact_path}</small>
        <small>{model.readiness || "readiness pending"} / {model.task_slot || "classification_model"}</small>
        <small>{model.human_review_status || (model.runtime_eligible ? "human_reviewed" : "human_review_required")} / {model.validation_evidence_status || "structured_evidence_incomplete"}</small>
        <small>{hints.length ? hints.join(", ") : "format not recognized yet"}</small>
        {warnings.length > 0 && <small className="caution">{warnings.join(" ")}</small>}
        {missingFields.length > 0 && <small>Missing card fields: {missingFields.join(", ")}</small>}
        {validationErrors.length > 0 && <div className="warn compactWarn">Required before save: {validationErrors.join(", ")}</div>}
        {cardPath && <small className="savedPath">Saved model-card JSON: {cardPath}</small>}
        <div className="cardDraftGrid">
          <label>Intended use<input className={!String(draft.intended_use || "").trim() ? "fieldMissing" : ""} value={String(draft.intended_use || "")} onChange={e => onDraft(model.id, "intended_use", e.target.value)} placeholder="diagnostic assistance research draft" /></label>
          <label>Task<input className={!String(draft.task || "").trim() ? "fieldMissing" : ""} value={String(draft.task || "")} onChange={e => onDraft(model.id, "task", e.target.value)} placeholder="xray classification / xray report / xray localization" /></label>
          <label>License<input className={!String(draft.license || "").trim() ? "fieldMissing" : ""} value={String(draft.license || "")} onChange={e => onDraft(model.id, "license", e.target.value)} placeholder="license" /></label>
          <label>Dataset/provenance<input className={!String(draft.dataset_provenance || "").trim() ? "fieldMissing" : ""} value={String(draft.dataset_provenance || "")} onChange={e => onDraft(model.id, "dataset_provenance", e.target.value)} placeholder="dataset/provenance" /></label>
          <label>Hardware<input value={String(draft.hardware || "")} onChange={e => onDraft(model.id, "hardware", e.target.value)} placeholder="hardware" /></label>
          <label>Limitations<textarea className={!String(draft.limitations || "").trim() ? "fieldMissing" : ""} value={String(draft.limitations || "")} onChange={e => onDraft(model.id, "limitations", e.target.value)} placeholder="limitations" /></label>
          <label>Contraindicated use<textarea value={String(draft.contraindicated_use || "")} onChange={e => onDraft(model.id, "contraindicated_use", e.target.value)} placeholder="no confirmed diagnosis or triage" /></label>
        </div>
        <h4>Structured local validation evidence</h4>
        <p>Optional for runtime selection, but confidence remains conservative until every evidence field is complete. This records research/prototype evidence, not clinical performance.</p>
        {missingEvidence.length > 0 && <small className="caution">Evidence still needed: {missingEvidence.join(", ")}</small>}
        <div className="cardDraftGrid">
          <label>Protocol ID<input value={String(draft.protocol_id || "")} onChange={e => onDraft(model.id, "protocol_id", e.target.value)} placeholder="MSK-BOX-001" /></label>
          <label>Held-out dataset<input value={String(draft.validation_dataset_name || "")} onChange={e => onDraft(model.id, "validation_dataset_name", e.target.value)} placeholder="dataset name" /></label>
          <label>Held-out split<input value={String(draft.held_out_split || "")} onChange={e => onDraft(model.id, "held_out_split", e.target.value)} placeholder="test-v1 / external holdout" /></label>
          <label>Case count<input type="number" min="0" value={String(draft.case_count || "")} onChange={e => onDraft(model.id, "case_count", e.target.value)} /></label>
          <label>Label count<input type="number" min="0" value={String(draft.label_count || "")} onChange={e => onDraft(model.id, "label_count", e.target.value)} /></label>
          <label>Metric summary<textarea value={String(draft.metric_summary || "")} onChange={e => onDraft(model.id, "metric_summary", e.target.value)} placeholder="box hit rate, mean IoU, threshold, and denominator" /></label>
          <label>False-alert burden<textarea value={String(draft.false_alert_burden || "")} onChange={e => onDraft(model.id, "false_alert_burden", e.target.value)} placeholder="count and alerts per evaluated case" /></label>
          <label>Missed-reference summary<textarea value={String(draft.missed_reference_summary || "")} onChange={e => onDraft(model.id, "missed_reference_summary", e.target.value)} placeholder="missed references and denominator" /></label>
          <label>Known failures<textarea value={String(draft.known_failures || "")} onChange={e => onDraft(model.id, "known_failures", e.target.value)} placeholder="one known failure per line" /></label>
          <label>Anatomy coverage<input value={String(draft.coverage_anatomy || "")} onChange={e => onDraft(model.id, "coverage_anatomy", e.target.value)} placeholder="wrist, ankle" /></label>
          <label>View coverage<input value={String(draft.coverage_views || "")} onChange={e => onDraft(model.id, "coverage_views", e.target.value)} placeholder="AP, lateral" /></label>
          <label>Age-group coverage<input value={String(draft.coverage_age_groups || "")} onChange={e => onDraft(model.id, "coverage_age_groups", e.target.value)} placeholder="adult" /></label>
          <label>Coverage exclusions/notes<textarea value={String(draft.coverage_notes || "")} onChange={e => onDraft(model.id, "coverage_notes", e.target.value)} placeholder="excluded views or subgroups" /></label>
          <label>Validation reviewer<input value={String(draft.validation_reviewer || "")} onChange={e => onDraft(model.id, "validation_reviewer", e.target.value)} /></label>
          <label>Review date<input type="date" value={String(draft.review_date || "")} onChange={e => onDraft(model.id, "review_date", e.target.value)} /></label>
          <label>Weights filename<input value={String(draft.weights_filename || "")} onChange={e => onDraft(model.id, "weights_filename", e.target.value)} placeholder="fracture-detector.pt" /></label>
          <label>SHA-256 artifact hash<input value={String(draft.artifact_hash || "")} onChange={e => onDraft(model.id, "artifact_hash", e.target.value)} placeholder="auto-filled when one weights file is found" /></label>
          <label>Validation report reference<input value={String(draft.report_reference || "")} onChange={e => onDraft(model.id, "report_reference", e.target.value)} placeholder="exported validation report path" /></label>
        </div>
        <div className="actions">
          <label><input type="checkbox" checked={Boolean(draft.human_reviewed)} onChange={e => onDraft(model.id, "human_reviewed", e.target.checked)} /> Human reviewed</label>
          <button onClick={() => onPrefill(model)} disabled={!selectedDetail}><FileText size={16} />Prefill from detail</button>
          <button onClick={() => onSave(model)} disabled={busyId === model.id}><ShieldCheck size={16} />Save card</button>
        </div></details><button onClick={() => onArchive(model)}>Archive model</button>
      </div>;
    }) : <div className="emptyState">No local model artifacts found in data/models.</div>}</div>
  </div>;
}

function ValidationWorkbench({ activeCase, analysis, onOpenCase }: { activeCase: CaseRecord | null; analysis: AnalysisResult | null; onOpenCase: (caseId: string, imageId?: string) => Promise<void> }) {
  const { language } = useUiLanguage();
  const [labels, setLabels] = useState<ValidationLabel[]>([]);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [fixturePath, setFixturePath] = useState("");
  const analysisReading = (analysis?.systematic_reading || {}) as Record<string, unknown>;
  const analysisFindings = asList<AnalysisResult["findings"][number]>(analysis?.findings);
  const firstAnalysisFinding = analysisFindings[0];
  const validationImage = activeStudyImageClient(activeCase);
  const validationImages = caseStudyImages(activeCase);
  const validationImageIndex = validationImage ? validationImages.findIndex(image => image.image_id === validationImage.image_id) : -1;
  const firstReviewedAnnotation = preferredAnnotations(activeCase?.annotations, analysis?.annotations)
    .find(annotation => annotationBelongsToImage(annotation, validationImage, validationImageIndex === 0, validationImages));
  const [labelDraft, setLabelDraft] = useState({
    case_id: activeCase?.case_id || "",
    title: activeCase?.title || "",
    protocol_id: "local-research-protocol",
    dataset_name: "local validation set",
    split: "local",
    anatomy: analysisReading.body_region ? String(analysisReading.body_region) : "",
    view: "",
    age_group: "",
    subgroup_notes: "",
    source_image_id: validationImage?.image_id || "",
    source_image_index: validationImage?.index ?? 0,
    source_series_id: validationImage?.series_id || "",
    source_view: validationImage?.view || "",
    expected_body_region: analysisReading.body_region ? String(analysisReading.body_region) : "",
    quality: "unknown",
    quality_limitations: "",
    finding_label: firstAnalysisFinding?.label || "fallback_no_confirmed_abnormality",
    finding_status: firstAnalysisFinding?.status || "uncertain",
    annotation_label: firstReviewedAnnotation?.label || "",
    annotation_type: firstReviewedAnnotation?.coordinate?.type || "bbox",
    annotation_required: false,
    annotation_spatial: false,
    annotation_x: firstReviewedAnnotation?.coordinate?.x || 0,
    annotation_y: firstReviewedAnnotation?.coordinate?.y || 0,
    annotation_width: firstReviewedAnnotation?.coordinate?.width || 0,
    annotation_height: firstReviewedAnnotation?.coordinate?.height || 0,
    annotation_min_iou: 0.3,
    annotation_max_point_distance: 10,
    annotation_min_vertex_count: 3,
    reviewer: "",
    reference_standard: "local research label",
    protocol_notes: "",
    skip_reason: "",
    notes: "",
  });

  useEffect(() => { api.validationLabels().then(value => setLabels(asList<ValidationLabel>(value))).catch(() => setLabels([])); }, []);
  useEffect(() => {
    setLabelDraft(draft => ({
      ...draft,
      case_id: activeCase?.case_id || draft.case_id,
      title: activeCase?.title || draft.title,
      expected_body_region: analysisReading.body_region ? String(analysisReading.body_region) : draft.expected_body_region,
      finding_label: firstAnalysisFinding?.label || draft.finding_label,
      finding_status: firstAnalysisFinding?.status || draft.finding_status,
      annotation_label: firstReviewedAnnotation?.label || draft.annotation_label,
      annotation_type: firstReviewedAnnotation?.coordinate?.type || draft.annotation_type,
      annotation_x: firstReviewedAnnotation?.coordinate?.x || draft.annotation_x,
      annotation_y: firstReviewedAnnotation?.coordinate?.y || draft.annotation_y,
      annotation_width: firstReviewedAnnotation?.coordinate?.width || draft.annotation_width,
      annotation_height: firstReviewedAnnotation?.coordinate?.height || draft.annotation_height,
      source_image_id: validationImage?.image_id || draft.source_image_id,
      source_image_index: validationImage?.index ?? draft.source_image_index,
      source_series_id: validationImage?.series_id || draft.source_series_id,
      source_view: validationImage?.view || draft.source_view,
    }));
  }, [activeCase, analysisReading.body_region, firstAnalysisFinding?.label, firstAnalysisFinding?.status, firstReviewedAnnotation, validationImage?.image_id, validationImage?.index, validationImage?.series_id, validationImage?.view]);

  function loadLabel(label: ValidationLabel) {
    const expectedFindings = asList<NonNullable<ValidationLabel["expected_findings"]>[number]>(label.expected_findings);
    const expectedAnnotations = asList<NonNullable<ValidationLabel["expected_annotations"]>[number]>(label.expected_annotations);
    const firstFinding = expectedFindings[0];
    const firstAnnotation = expectedAnnotations[0];
    setLabelDraft({
      case_id: label.case_id,
      title: label.title || "",
      protocol_id: label.protocol_id || "local-research-protocol",
      dataset_name: label.dataset_name || "local validation set",
      split: label.split || "local",
      anatomy: label.anatomy || label.expected_body_region || "",
      view: label.view || "",
      age_group: label.age_group || "",
      subgroup_notes: label.subgroup_notes || "",
      source_image_id: label.source_image_id || "",
      source_image_index: label.source_image_index ?? 0,
      source_series_id: label.source_series_id || "",
      source_view: label.source_view || "",
      expected_body_region: label.expected_body_region || "",
      quality: label.expected_image_quality?.diagnostic_quality || "unknown",
      quality_limitations: textList(label.expected_image_quality?.limitations).join(", "),
      finding_label: firstFinding?.label || "",
      finding_status: firstFinding?.status || "uncertain",
      annotation_label: firstAnnotation?.label || "",
      annotation_type: firstAnnotation?.coordinate_type || "bbox",
      annotation_required: Boolean(firstAnnotation?.required),
      annotation_spatial: Boolean(firstAnnotation?.coordinate),
      annotation_x: firstAnnotation?.coordinate?.x || 0,
      annotation_y: firstAnnotation?.coordinate?.y || 0,
      annotation_width: firstAnnotation?.coordinate?.width || 0,
      annotation_height: firstAnnotation?.coordinate?.height || 0,
      annotation_min_iou: firstAnnotation?.min_iou ?? 0.3,
      annotation_max_point_distance: firstAnnotation?.max_point_distance ?? 10,
      annotation_min_vertex_count: firstAnnotation?.min_vertex_count ?? 3,
      reviewer: label.reviewer || "",
      reference_standard: label.reference_standard || "local research label",
      protocol_notes: label.protocol_notes || "",
      skip_reason: label.skip_reason || "",
      notes: label.notes || "",
    });
  }

  async function saveFromActiveCase() {
    const caseId = labelDraft.case_id || activeCase?.case_id;
    if (!caseId) return;
    setBusy(true);
    try {
      await api.saveValidationLabel({
        case_id: caseId,
        title: labelDraft.title || activeCase?.title || caseId,
        protocol_id: labelDraft.protocol_id,
        dataset_name: labelDraft.dataset_name,
        split: labelDraft.split,
        anatomy: labelDraft.anatomy,
        view: labelDraft.view,
        age_group: labelDraft.age_group,
        subgroup_notes: labelDraft.subgroup_notes,
        source_image_id: labelDraft.source_image_id,
        source_image_index: labelDraft.source_image_index,
        source_series_id: labelDraft.source_series_id,
        source_view: labelDraft.source_view,
        expected_body_region: labelDraft.expected_body_region,
        expected_image_quality: {
          diagnostic_quality: labelDraft.quality,
          limitations: labelDraft.quality_limitations.split(",").map(item => item.trim()).filter(Boolean),
          note: "",
        },
        expected_findings: labelDraft.finding_label ? [{ label: labelDraft.finding_label, status: labelDraft.finding_status, note: labelDraft.notes }] : [],
        expected_annotations: labelDraft.annotation_label ? [{
          label: labelDraft.annotation_label,
          coordinate_type: labelDraft.annotation_type,
          required: labelDraft.annotation_required,
          coordinate: labelDraft.annotation_spatial && ["bbox", "grounding_box"].includes(labelDraft.annotation_type) ? {
            x: Number(labelDraft.annotation_x),
            y: Number(labelDraft.annotation_y),
            width: Number(labelDraft.annotation_width),
            height: Number(labelDraft.annotation_height),
          } : null,
          points: labelDraft.annotation_spatial && labelDraft.annotation_type === "point" ? [[Number(labelDraft.annotation_x), Number(labelDraft.annotation_y)]] : [],
          min_iou: Number(labelDraft.annotation_min_iou),
          max_point_distance: Number(labelDraft.annotation_max_point_distance),
          min_vertex_count: Number(labelDraft.annotation_min_vertex_count),
          note: "",
          source_image_id: labelDraft.source_image_id,
        }] : [],
        reviewer: labelDraft.reviewer,
        reference_standard: labelDraft.reference_standard,
        protocol_notes: labelDraft.protocol_notes,
        skip_reason: labelDraft.skip_reason,
        notes: labelDraft.notes,
      });
      setLabels(asList<ValidationLabel>(await api.validationLabels()));
    } finally {
      setBusy(false);
    }
  }

  async function deleteLabel(caseId: string) {
    setBusy(true);
    try {
      await api.deleteValidationLabel(caseId);
      setLabels(asList<ValidationLabel>(await api.validationLabels()));
      if (labelDraft.case_id === caseId) setLabelDraft({ ...labelDraft, case_id: "", title: "" });
    } finally {
      setBusy(false);
    }
  }

  async function writeFixture() {
    setBusy(true);
    try {
      const res = await api.curatedValidationFixture();
      setFixturePath(res.path);
    } finally {
      setBusy(false);
    }
  }

  async function run(exportReport = false) {
    setBusy(true);
    try {
      setResult(await api.runValidation(exportReport));
      setLabels(asList<ValidationLabel>(await api.validationLabels()));
    } finally {
      setBusy(false);
    }
  }

  const labelList = asList<ValidationLabel>(labels);
  const metricEntries = Object.entries((result?.metrics && typeof result.metrics === "object" ? result.metrics : {}) as Record<string, unknown>);
  const validationRows = asList<Record<string, unknown>>(result?.results);

  function mismatchCount(item: Record<string, unknown>) {
    const findingMismatches = asList<Record<string, unknown>>(item.matches).filter(match => match.matched === false).length;
    const resultCardMismatches = asList<Record<string, unknown>>(item.result_card_matches).filter(match => match.matched === false).length;
    const annotationMismatches = asList<Record<string, unknown>>(item.annotation_checks).filter(check => check.required === true && check.matched === false).length;
    return findingMismatches + resultCardMismatches + annotationMismatches;
  }

  function rowGroup(item: Record<string, unknown>) {
    const status = String(item.status || "");
    if (status.startsWith("skipped_")) return "skipped";
    const bodyMismatch = Boolean((item.body_region as Record<string, unknown> | undefined)?.matched === false);
    const qualityMismatch = Boolean((item.image_quality as Record<string, unknown> | undefined)?.matched === false);
    if (mismatchCount(item) > 0 || bodyMismatch || qualityMismatch) return "mismatch";
    const uncertainCard = asList<Record<string, unknown>>(item.result_card_matches).some(match => ["uncertain", "not_reviewed"].includes(String(match.review_status || "")));
    return uncertainCard ? "uncertain" : "agreement";
  }

  function renderValidationRow(item: Record<string, unknown>, index: number) {
    const mismatches = mismatchCount(item);
    return <div className="resultRow" key={String(item.case_id || index)}>
      <div className="row"><b>{String(item.title || item.case_id)}</b><span className={mismatches ? "validationMismatch" : "validationMatch"}>{mismatches ? `${mismatches} mismatch(es)` : "agreement / review"}</span></div>
      <span>{String(item.status)} / {String(item.dataset_name || "no dataset")}</span>
      {"body_region" in item && <small>{`Body: ${String((item.body_region as Record<string, unknown>).expected || "-")} -> ${String((item.body_region as Record<string, unknown>).predicted || "-")}`}</small>}
      {"matches" in item && <small>Findings: {asList<Record<string, unknown>>(item.matches).map(match => `${String(match.label)} ${String(match.expected_status)}->${String(match.predicted_status)}`).join("; ") || "none"}</small>}
      {"result_card_matches" in item && <small>Result cards: {asList<Record<string, unknown>>(item.result_card_matches).map(match => `${String(match.label)} ${String(match.expected_status)}->${String(match.predicted_status)} / ${String(match.review_status)}`).join("; ") || "none"}</small>}
      {"annotation_checks" in item && <small>Annotations: {asList<Record<string, unknown>>(item.annotation_checks).map(check => `${String(check.label)} ${String(check.matched)}${check.spatial_evaluated ? ` / IoU ${String(check.best_iou)} >= ${String(check.min_iou)}` : ""}`).join("; ") || "none"}</small>}
      {String(item.case_id || "") && <button onClick={() => onOpenCase(String(item.case_id), String(item.source_image_id || ""))} disabled={busy || String(item.status).startsWith("skipped_")}>Open case for review</button>}
    </div>;
  }

  const groupedRows = {
    mismatch: validationRows.filter(item => rowGroup(item) === "mismatch"),
    uncertain: validationRows.filter(item => rowGroup(item) === "uncertain"),
    skipped: validationRows.filter(item => rowGroup(item) === "skipped"),
    agreement: validationRows.filter(item => rowGroup(item) === "agreement"),
  };

  return <section className="panel validationPage">
    <div className="row">
      <h2>Validation Workbench</h2>
      <div className="actions"><button onClick={() => run(false)} disabled={busy}><ClipboardCheck size={16} />Run</button><button onClick={() => run(true)} disabled={busy}><Download size={16} />Run + Export</button><button onClick={writeFixture} disabled={busy}><Download size={16} />Sample Fixture</button></div>
    </div>
    <div className="warn">Research-only agreement checks. Bukan sensitivity, specificity, atau performa klinis.</div>
    {fixturePath && <div className="pathNote">Fixture written: {fixturePath}</div>}
    <div className="validationLayout">
      <section className="validationColumn">
        <h3>Research label</h3>
        <label>Case ID<input value={labelDraft.case_id} onChange={e => setLabelDraft({ ...labelDraft, case_id: e.target.value })} placeholder="active case id or fixture id" /></label>
        <label>Title<input value={labelDraft.title} onChange={e => setLabelDraft({ ...labelDraft, title: e.target.value })} placeholder="Validation case title" /></label>
        <details className="formDisclosure"><summary>Protocol & dataset</summary><div>
          <label>Protocol ID<input value={labelDraft.protocol_id} onChange={e => setLabelDraft({ ...labelDraft, protocol_id: e.target.value })} placeholder="MSK-BOX-001" /></label>
          <label>Dataset<input value={labelDraft.dataset_name} onChange={e => setLabelDraft({ ...labelDraft, dataset_name: e.target.value })} /></label>
          <label>Split<select value={labelDraft.split} onChange={e => setLabelDraft({ ...labelDraft, split: e.target.value })}><option value="local">local</option><option value="fixture">fixture</option><option value="train">train</option><option value="validation">validation</option><option value="test">test</option><option value="holdout">holdout</option></select></label>
          <label>Anatomy coverage<input value={labelDraft.anatomy} onChange={e => setLabelDraft({ ...labelDraft, anatomy: e.target.value })} placeholder="wrist / ankle" /></label>
          <label>View<input value={labelDraft.view} onChange={e => setLabelDraft({ ...labelDraft, view: e.target.value })} placeholder="AP / lateral" /></label>
          <label>Age group<input value={labelDraft.age_group} onChange={e => setLabelDraft({ ...labelDraft, age_group: e.target.value })} placeholder="adult" /></label>
          <label>Subgroup exclusions/notes<textarea value={labelDraft.subgroup_notes} onChange={e => setLabelDraft({ ...labelDraft, subgroup_notes: e.target.value })} /></label>
        </div></details>
        <details className="formDisclosure"><summary>Source image & quality</summary><div>
          <label>Source image ID<input value={labelDraft.source_image_id} onChange={e => setLabelDraft({ ...labelDraft, source_image_id: e.target.value })} placeholder="active study image identity" /></label>
          <div className="inlineFields">
            <label>Image index<input type="number" min="0" value={labelDraft.source_image_index} onChange={e => setLabelDraft({ ...labelDraft, source_image_index: Number(e.target.value) })} /></label>
            <label>View<input value={labelDraft.source_view} onChange={e => setLabelDraft({ ...labelDraft, source_view: e.target.value })} /></label>
          </div>
          <label>Series ID<input value={labelDraft.source_series_id} onChange={e => setLabelDraft({ ...labelDraft, source_series_id: e.target.value })} /></label>
          <label>Body region<input value={labelDraft.expected_body_region} onChange={e => setLabelDraft({ ...labelDraft, expected_body_region: e.target.value })} placeholder="Chest X-ray" /></label>
          <label>Image quality<select value={labelDraft.quality} onChange={e => setLabelDraft({ ...labelDraft, quality: e.target.value })}><option value="unknown">unknown</option><option value="adequate">adequate</option><option value="limited">limited</option><option value="non_diagnostic">non_diagnostic</option></select></label>
          <label>Quality limitations<input value={labelDraft.quality_limitations} onChange={e => setLabelDraft({ ...labelDraft, quality_limitations: e.target.value })} placeholder="comma-separated limitations" /></label>
        </div></details>
        <label>Finding label<input value={labelDraft.finding_label} onChange={e => setLabelDraft({ ...labelDraft, finding_label: e.target.value })} /></label>
        <label>Status<select value={labelDraft.finding_status} onChange={e => setLabelDraft({ ...labelDraft, finding_status: e.target.value })}><option value="positive">positive</option><option value="negative">negative</option><option value="uncertain">uncertain</option><option value="not_assessed">not_assessed</option></select></label>
        <details className="formDisclosure"><summary>Expected annotation (optional)</summary><div>
          <label>Expected annotation<input value={labelDraft.annotation_label} onChange={e => setLabelDraft({ ...labelDraft, annotation_label: e.target.value })} placeholder="optional label" /></label>
          <div className="inlineFields">
            <label>Type<select value={labelDraft.annotation_type} onChange={e => setLabelDraft({ ...labelDraft, annotation_type: e.target.value })}><option value="bbox">bbox</option><option value="grounding_box">grounding box</option><option value="point">point</option><option value="polygon">polygon</option><option value="mask">mask</option></select></label>
            <label><input type="checkbox" checked={labelDraft.annotation_required} onChange={e => setLabelDraft({ ...labelDraft, annotation_required: e.target.checked })} /> Required</label>
          </div>
          <label className="checkboxField"><input type="checkbox" checked={labelDraft.annotation_spatial} onChange={e => setLabelDraft({ ...labelDraft, annotation_spatial: e.target.checked })} /> Evaluate geometry</label>
        {labelDraft.annotation_spatial && ["bbox", "grounding_box"].includes(labelDraft.annotation_type) && <div className="inlineFields localizationFields">
          <label>X<input type="number" min="0" value={labelDraft.annotation_x} onChange={e => setLabelDraft({ ...labelDraft, annotation_x: Number(e.target.value) })} /></label>
          <label>Y<input type="number" min="0" value={labelDraft.annotation_y} onChange={e => setLabelDraft({ ...labelDraft, annotation_y: Number(e.target.value) })} /></label>
          <label>Width<input type="number" min="1" value={labelDraft.annotation_width} onChange={e => setLabelDraft({ ...labelDraft, annotation_width: Number(e.target.value) })} /></label>
          <label>Height<input type="number" min="1" value={labelDraft.annotation_height} onChange={e => setLabelDraft({ ...labelDraft, annotation_height: Number(e.target.value) })} /></label>
          <label>Min IoU<input type="number" min="0" max="1" step="0.05" value={labelDraft.annotation_min_iou} onChange={e => setLabelDraft({ ...labelDraft, annotation_min_iou: Number(e.target.value) })} /></label>
        </div>}
        {labelDraft.annotation_spatial && labelDraft.annotation_type === "point" && <div className="inlineFields localizationFields">
          <label>X<input type="number" min="0" value={labelDraft.annotation_x} onChange={e => setLabelDraft({ ...labelDraft, annotation_x: Number(e.target.value) })} /></label>
          <label>Y<input type="number" min="0" value={labelDraft.annotation_y} onChange={e => setLabelDraft({ ...labelDraft, annotation_y: Number(e.target.value) })} /></label>
          <label>Max distance (px)<input type="number" min="0" value={labelDraft.annotation_max_point_distance} onChange={e => setLabelDraft({ ...labelDraft, annotation_max_point_distance: Number(e.target.value) })} /></label>
        </div>}
        {labelDraft.annotation_spatial && labelDraft.annotation_type === "polygon" && <label>Minimum polygon vertices<input type="number" min="3" value={labelDraft.annotation_min_vertex_count} onChange={e => setLabelDraft({ ...labelDraft, annotation_min_vertex_count: Number(e.target.value) })} /></label>}
        </div></details>
        <details className="formDisclosure"><summary>Reviewer & notes</summary><div>
          <label>Reviewer<input value={labelDraft.reviewer} onChange={e => setLabelDraft({ ...labelDraft, reviewer: e.target.value })} placeholder="local reviewer / protocol" /></label>
          <label>Reference standard<input value={labelDraft.reference_standard} onChange={e => setLabelDraft({ ...labelDraft, reference_standard: e.target.value })} /></label>
          <label>Protocol notes<textarea value={labelDraft.protocol_notes} onChange={e => setLabelDraft({ ...labelDraft, protocol_notes: e.target.value })} placeholder="Dataset/protocol notes for export..." /></label>
          <label>Skip reason<input value={labelDraft.skip_reason} onChange={e => setLabelDraft({ ...labelDraft, skip_reason: e.target.value })} placeholder="optional unsupported/skip reason" /></label>
          <label>Notes<textarea value={labelDraft.notes} onChange={e => setLabelDraft({ ...labelDraft, notes: e.target.value })} placeholder="Reference label notes..." /></label>
        </div></details>
        <button className="primaryAction" onClick={saveFromActiveCase} disabled={(!activeCase && !labelDraft.case_id) || busy}><ClipboardCheck size={16} />Save label</button>
      </section>
      <section className="validationColumn">
        <h3>Local labels</h3>
        {labelList.length ? labelList.map(label => <div className="labelRow" key={label.case_id}>
          <b>{label.title || label.case_id}</b>
          <span>{label.case_id}</span>
          <small>{label.dataset_name || "local validation set"} / {label.split || "local"}</small>
          <small>{label.source_image_id || "case-level"}{label.source_view ? ` / ${label.source_view}` : ""}{label.source_series_id ? ` / series ${label.source_series_id}` : ""}</small>
          <small>{label.expected_body_region || "no body region"} / {asList(label.expected_findings).length} finding / {asList(label.expected_annotations).length} annotation</small>
          {label.skip_reason && <small>skip: {label.skip_reason}</small>}
          {label.invalid && <small>{label.error}</small>}
          <div className="labelActions"><button onClick={() => loadLabel(label)} disabled={busy}>Edit</button><button onClick={() => deleteLabel(label.case_id)} disabled={busy}><Trash2 size={15} />Delete</button></div>
        </div>) : <p>No validation labels yet.</p>}
      </section>
      <section className="validationColumn">
        <h3>Metrics</h3>
        {result?.dataset_summary && <div className="summaryBox"><b>Dataset summary</b><pre>{JSON.stringify(result.dataset_summary, null, 2)}</pre></div>}
        {result ? <div className="metricsGrid">
          {metricEntries.map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><b>{String(value ?? "n/a")}</b></div>)}
        </div> : <p>{language === "en" ? "Run validation to view metrics." : "Jalankan validasi untuk melihat metrik."}</p>}
        {result?.runtime_snapshot_summary && <div className="summaryBox"><b>Runtime/model refs</b><pre>{JSON.stringify(result.runtime_snapshot_summary, null, 2)}</pre></div>}
        {result?.false_alert_burden && <div className="summaryBox"><b>False-alert burden</b><pre>{JSON.stringify(result.false_alert_burden, null, 2)}</pre></div>}
        {result?.missed_reference_summary && <div className="summaryBox"><b>Missed-reference review</b><pre>{JSON.stringify(result.missed_reference_summary, null, 2)}</pre></div>}
        {result?.model_card_evidence_draft && <div className="summaryBox"><b>Model-card evidence draft</b><p>Run + Export creates a report reference. Copy the reviewed fields into the matching local model card; weights identity is verified when saved.</p><pre>{JSON.stringify(result.model_card_evidence_draft, null, 2)}</pre></div>}
        {result?.export_path && <p><b>Export:</b><br />{result.export_path}</p>}
        {result && <div className="validationResults">
          <div className="validationQueueSummary"><b>Review queue</b><span>{groupedRows.mismatch.length} mismatch / {groupedRows.uncertain.length} uncertain / {groupedRows.skipped.length} skipped / {groupedRows.agreement.length} agreement</span></div>
          {groupedRows.mismatch.length > 0 && <details className="validationGroup" open><summary>Mismatch / failure review ({groupedRows.mismatch.length})</summary>{groupedRows.mismatch.map(renderValidationRow)}</details>}
          {groupedRows.uncertain.length > 0 && <details className="validationGroup" open><summary>Uncertain / high-disagreement review ({groupedRows.uncertain.length})</summary>{groupedRows.uncertain.map(renderValidationRow)}</details>}
          {groupedRows.skipped.length > 0 && <details className="validationGroup" open><summary>Missing case / no analysis / skipped ({groupedRows.skipped.length})</summary>{groupedRows.skipped.map(renderValidationRow)}</details>}
          {groupedRows.agreement.length > 0 && <details className="validationGroup"><summary>Agreement / reviewed ({groupedRows.agreement.length})</summary>{groupedRows.agreement.map(renderValidationRow)}</details>}
          {!validationRows.length && <p>No validation result rows returned.</p>}
        </div>}
      </section>
    </div>
  </section>;
}

function GeneralSettings({
  dark,
  setDark,
  language,
  setLanguage,
  onOpenRuntime,
}: {
  dark: boolean;
  setDark: (value: boolean) => void;
  language: UiLanguage;
  setLanguage: (value: UiLanguage) => void;
  onOpenRuntime: () => void;
}) {
  const { copy } = useUiLanguage();
  const [databaseLocation, setDatabaseLocation] = useState<DatabaseLocation | null>(null);
  const [databaseFolder, setDatabaseFolder] = useState("");
  const [databaseBusy, setDatabaseBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let alive = true;
    api.databaseLocation().then(database => {
      if (!alive) return;
      setDatabaseLocation(database);
      setDatabaseFolder(database.database_folder || "");
    }).catch(exc => {
      if (alive) setStatus(`Database location failed: ${String(exc)}`);
    }).finally(() => {
      if (alive) setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  async function saveDatabaseLocation() {
    const folder = databaseFolder.trim();
    if (!folder) {
      setStatus(language === "en" ? "Enter a database folder first." : "Isi folder database terlebih dahulu.");
      return;
    }
    setDatabaseBusy(true);
    setStatus("");
    try {
      const next = await api.setDatabaseLocation(folder);
      setDatabaseLocation(next);
      setDatabaseFolder(next.database_folder);
      setStatus(language === "en"
        ? "Database location saved. Restart the backend/launcher before using the app again."
        : "Lokasi database tersimpan. Restart backend/launcher sebelum memakai aplikasi lagi.");
    } catch (exc) {
      setStatus(`Database location failed: ${String(exc)}`);
    } finally {
      setDatabaseBusy(false);
    }
  }

  return <section className="panel settingsPage generalSettingsPage">
    <div className="row">
      <div><h2>{copy.pages["General Settings"]}</h2><p className="settingsLead">{language === "en" ? "Language, appearance, and optional AI connection." : "Bahasa, tampilan, dan koneksi AI opsional."}</p></div>
    </div>
    {status && <div className={status.includes("failed") || status.includes("gagal") ? "warn" : "pathNote"}>{status}</div>}
    <div className="generalSettingsGrid">
      <section className="settingsCard">
        <div className="settingsCardHeader"><Settings size={18} /><div><h3>{copy.interfaceSettings}</h3><p>{copy.interfaceDescription}</p></div></div>
        <div className="settingsGrid compactSettingsGrid">
          <label>{copy.language}<select value={language} onChange={e => setLanguage(e.target.value as UiLanguage)}><option value="id">{copy.indonesian}</option><option value="en">{copy.english}</option></select></label>
          <label>{copy.theme}<select value={dark ? "dark" : "light"} onChange={e => setDark(e.target.value === "dark")}><option value="dark">{copy.darkMode}</option><option value="light">{copy.lightMode}</option></select></label>
        </div>
      </section>
      <section className="settingsCard">
        <div className="settingsCardHeader"><Bot size={18} /><div><h3>{language === "en" ? "Optional AI models" : "Model AI opsional"}</h3><p>{language === "en" ? "The default mode already works. Open this to configure local runtimes, hosted providers, or specialist classifiers." : "Mode bawaan sudah dapat digunakan. Buka bagian ini untuk mengatur runtime lokal, provider online, atau classifier khusus."}</p></div></div>
        <button onClick={onOpenRuntime}>{language === "en" ? "Open AI settings" : "Buka pengaturan AI"}</button>
      </section>
      <details className="settingsDisclosure wideSettingsCard">
        <summary><HardDrive size={17} /><span><b>{language === "en" ? "Database location" : "Penyimpanan lanjutan"}</b><small>{language === "en" ? "Change the case database folder" : "Ubah folder database kasus"}</small></span>{loading && <span className="loadingPill">{language === "en" ? "Loading…" : "Memuat…"}</span>}</summary>
        <section>
          <p>{language === "en" ? "Most users should keep the default location. Restart the backend after changing it." : "Sebagian besar pengguna sebaiknya memakai lokasi bawaan. Restart backend setelah mengubahnya."}</p>
          <div className="databaseLocationGrid">
            <label>{language === "en" ? "SQLite database folder" : "Folder database SQLite"}<input value={databaseFolder} onChange={event => setDatabaseFolder(event.target.value)} placeholder="C:\\MedRayData\\database" disabled={databaseBusy} /></label>
            <div className="databaseLocationFacts"><span>{language === "en" ? "Active now" : "Aktif saat ini"}</span><b>{databaseLocation?.database_path || (language === "en" ? "not loaded" : "belum terbaca")}</b></div>
          </div>
          <button onClick={saveDatabaseLocation} disabled={databaseBusy || !databaseFolder.trim()}><HardDrive size={16} />{databaseBusy ? (language === "en" ? "Saving…" : "Menyimpan…") : (language === "en" ? "Save location" : "Simpan lokasi")}</button>
        </section>
      </details>
    </div>
  </section>;
}

const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
  primary_backend: "demo",
  chat_model: "demo-safe-radiology-assistant",
  vision_language_model: "demo-vlm",
  classification_model: "demo-classifier",
  segmentation_model: "disabled",
  grounding_model: "disabled",
  review_depth: "balanced",
  localization_confidence_threshold: 0.25,
  annotation_auto_accept_threshold: 0.9,
  temperature: 0.2,
  top_p: 0.95,
  seed: -1,
  max_output_tokens: 2048,
  request_timeout_seconds: 180,
  max_retries: 1,
  download_connections: 4,
  chest_xray_model: "inherit",
  msk_xray_model: "inherit",
  abdomen_xray_model: "inherit",
  spine_xray_model: "inherit",
  skull_facial_xray_model: "inherit",
  general_xray_model: "disabled",
  report_model: "demo-report-generator",
  openai_base_url: "http://127.0.0.1:8000/v1",
  ollama_base_url: "http://127.0.0.1:11434",
  allow_cloud: false,
  cpu_only: true,
};

export function CaseLibrary({ activeCase, analysis, onOpen, onDeleted, onCleared }: { activeCase: CaseRecord | null; analysis: AnalysisResult | null; onOpen: (id: string, imageId?: string) => Promise<void>; onDeleted: (id: string) => void; onCleared: () => void }) {
  const { language, copy } = useUiLanguage();
  const [q, setQ] = useState("");
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [validationLabels, setValidationLabels] = useState<ValidationLabel[]>([]);
  const [error, setError] = useState("");
  const [visibleLimit, setVisibleLimit] = useState(15);
  const [editingId, setEditingId] = useState("");
  const [titleDraft, setTitleDraft] = useState("");
  const validationWorkspaceRef = useRef<HTMLDetailsElement | null>(null);

  async function refresh() {
    setError("");
    try {
      const [nextCases, nextLabels] = await Promise.all([api.cases(q), api.validationLabels()]);
      setCases(asList<CaseRecord>(nextCases));
      setValidationLabels(asList<ValidationLabel>(nextLabels));
    } catch (exc) {
      setCases([]);
      setError(String(exc));
    }
  }

  async function removeCase(caseId: string, title: string) {
    if (!window.confirm(language === "en" ? `Delete case "${title || caseId}" with its local images and case exports?` : `Hapus kasus "${title || caseId}" beserta gambar lokal dan ekspor kasus?`)) return;
    setError("");
    try {
      await api.deleteCase(caseId);
      onDeleted(caseId);
      await refresh();
    } catch (exc) {
      setError(String(exc));
    }
  }

  async function clearDatabase() {
    const expected = language === "en" ? "DELETE" : "HAPUS";
    const confirmation = window.prompt(language === "en" ? `This deletes ALL local cases, images, validation labels, and case exports. Type ${expected} to continue:` : `Ini menghapus SEMUA kasus lokal, gambar, label validasi, dan ekspor kasus. Ketik ${expected} untuk lanjut:`);
    if (confirmation !== expected) return;
    setError("");
    try {
      await api.clearCases();
      onCleared();
      await refresh();
    } catch (exc) {
      setError(String(exc));
    }
  }

  async function saveTitle(record: CaseRecord) {
    const title = titleDraft.trim();
    if (!title) return;
    setError("");
    try {
      await api.saveCase({ ...record, title });
      setEditingId("");
      await refresh();
    } catch (exc) { setError(String(exc)); }
  }

  useEffect(() => { refresh(); setVisibleLimit(15); }, [q]);
  const visibleCases = cases.slice(0, visibleLimit);
  const labelledCaseIds = new Set(validationLabels.map(label => label.case_id));
  function openValidationWorkspace() {
    if (!validationWorkspaceRef.current) return;
    validationWorkspaceRef.current.open = true;
    validationWorkspaceRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  return <section className="panel libraryPage">
    <div className="libraryOverview">
      <div><h2>{language === "en" ? "Cases and validation" : "Kasus dan validasi"}</h2><p>{language === "en" ? "Search the registry, see validation state, and work with reference labels without switching pages." : "Cari registri, lihat status validasi, dan kerjakan label referensi tanpa berpindah halaman."}</p></div>
      <button onClick={openValidationWorkspace}><ClipboardCheck size={16} />{activeCase ? (language === "en" ? `Validate ${activeCase.title}` : `Validasi ${activeCase.title}`) : (language === "en" ? "Open validation workspace" : "Buka workspace validasi")}</button>
    </div>
    <details className="validationWorkspace" ref={validationWorkspaceRef}>
      <summary><ClipboardCheck size={18} /><span><b>{language === "en" ? "Validation workspace" : "Workspace validasi"}</b><small>{activeCase ? (language === "en" ? `Current context: ${activeCase.title}. Review AI output first, then save the human reference.` : `Konteks saat ini: ${activeCase.title}. Tinjau output AI, lalu simpan referensi manusia.`) : (language === "en" ? "Open a case in the Reading Room first to prefill its AI findings and annotations." : "Buka kasus di Ruang Baca terlebih dahulu agar temuan dan anotasi AI terisi otomatis.")}</small></span></summary>
      <ValidationWorkbench activeCase={activeCase} analysis={analysis} onOpenCase={onOpen} />
    </details>
    <section className="caseRegistry" aria-label={language === "en" ? "Case registry" : "Registri kasus"}>
    <div className="libraryHeader">
      <div className="filters"><input value={q} onChange={e => setQ(e.target.value)} placeholder={copy.caseSearch} aria-label={copy.caseSearch} /><button onClick={refresh} aria-label={language === "en" ? "Refresh case search" : "Perbarui pencarian kasus"}><Search size={16} /></button></div>
      <details className="libraryManage"><summary>{language === "en" ? "Manage" : "Kelola"}</summary><button className="dangerAction" onClick={clearDatabase}><Trash2 size={16} />{language === "en" ? "Delete all local cases" : "Hapus semua kasus lokal"}</button></details>
    </div>
    <div className="caseListViewport">
    {error && <div className="warn">{error}</div>}
    <p className="resultCount">{cases.length} {language === "en" ? "local cases" : "kasus lokal"}{q ? (language === "en" ? " found" : " ditemukan") : ""}</p>
    {visibleCases.length ? visibleCases.map((c, index) => {
    const caseId = String(c.case_id || "");
    const updated = c.updated_at ? new Date(c.updated_at).toLocaleDateString() : "-";
    const images = caseStudyImages(c);
    const seriesCount = new Set(images.map(image => image.series_id).filter(Boolean)).size;
    const studyCount = new Set(images.map(image => image.study_id).filter(Boolean)).size;
    const title = String(c.title || caseId || "Untitled case");
    const identifier = String(c.metadata?.LocalRecordID || c.metadata?.PatientID || c.metadata?.AccessionNumber || "");
    return <div className={`caseRow ${activeCase?.case_id === caseId ? "activeCaseRow" : ""}`} key={caseId || index}><FolderOpen /><div>{editingId === caseId ? <input aria-label={language === "en" ? "Edit case title" : "Edit judul kasus"} value={titleDraft} onChange={event => setTitleDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter") void saveTitle(c); if (event.key === "Escape") setEditingId(""); }} /> : <b>{title}</b>}<span>{identifier || caseId} · {updated}</span><small>{images.length || 0} image(s) · {studyCount || (images.length ? 1 : 0)} study · {seriesCount || (images.length ? 1 : 0)} series</small><small className={`caseValidationState ${labelledCaseIds.has(caseId) ? "labelled" : "unlabelled"}`}>{labelledCaseIds.has(caseId) ? (language === "en" ? "Reference label saved" : "Label referensi tersimpan") : (language === "en" ? "Not labelled for validation" : "Belum diberi label validasi")}</small></div><div className="caseRowActions">{editingId === caseId ? <><button onClick={() => saveTitle(c)} disabled={!titleDraft.trim()}><Save size={15} />{language === "en" ? "Save" : "Simpan"}</button><button onClick={() => setEditingId("")}>{language === "en" ? "Cancel" : "Batal"}</button></> : <button onClick={() => { setEditingId(caseId); setTitleDraft(title); }}><FileText size={15} />{language === "en" ? "Rename" : "Ubah nama"}</button>}<button className="primaryAction" onClick={() => onOpen(caseId)} disabled={!caseId}>{copy.open}</button><button className="dangerAction iconButton" onClick={() => removeCase(caseId, title)} disabled={!caseId} aria-label={`${language === "en" ? "Delete" : "Hapus"} ${title}`} title={language === "en" ? "Delete case" : "Hapus kasus"}><Trash2 size={15} /></button></div></div>;
  }) : <p>{copy.noCases}</p>}
    {visibleLimit < cases.length && <button className="loadMore" onClick={() => setVisibleLimit(limit => limit + 15)}>{language === "en" ? `Show 15 more (${cases.length - visibleLimit} remaining)` : `Tampilkan 15 lagi (${cases.length - visibleLimit} tersisa)`}</button>}
    </div>
    </section>
  </section>;
}

function About() {
  const { language, copy } = useUiLanguage();
  return <section className="panel about">
    <h2>{language === "en" ? "About MedRay v2" : "Tentang MedRay v2"}</h2>
    <p>{language === "en" ? "MedRay v2 is inspired by MedRay Workspace, MedRAX, and Odysseus. It is local-first and does not upload data to the cloud by default." : "MedRay v2 terinspirasi oleh MedRay Workspace, MedRAX, dan Odysseus. Aplikasi ini local-first dan tidak mengunggah data ke cloud secara default."}</p>
    <p><b>Disclaimer:</b> {copy.disclaimer}</p>
    <div className="aboutFacts"><div><b>{language === "en" ? "Storage" : "Penyimpanan"}</b><span>{language === "en" ? "Local filesystem and SQLite" : "Filesystem lokal dan SQLite"}</span></div><div><b>{language === "en" ? "Intended use" : "Tujuan penggunaan"}</b><span>{language === "en" ? "Research, education, and prototyping" : "Riset, edukasi, dan prototipe"}</span></div><div><b>{language === "en" ? "Clinical status" : "Status klinis"}</b><span>{language === "en" ? "Not a medical device" : "Bukan alat kesehatan"}</span></div></div>
  </section>;
}

const rootElement = document.getElementById("root");

if (rootElement) {
  createRoot(rootElement).render(<App />);
}
