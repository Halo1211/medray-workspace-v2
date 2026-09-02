export type Annotation = {
  id: string;
  label: string;
  confidence: number;
  source: string;
  source_model?: string;
  source_model_version?: string;
  coordinate: { type: string; x: number; y: number; width: number; height: number; points?: [number, number][]; mask_path?: string; coordinate_space?: string };
  explanation: string;
  visible: boolean;
  locked?: boolean;
  review_status?: "unreviewed" | "accepted" | "rejected" | "uncertain" | "needs_follow_up";
  reviewer_note?: string;
  transform_metadata?: Record<string, unknown>;
  linked_result_card_ids?: string[];
  linked_report_statement_id?: string;
  original_coordinate?: Annotation["coordinate"] | null;
  original_state?: {
    label: string;
    confidence: number;
    coordinate: Annotation["coordinate"];
    explanation: string;
    visible: boolean;
    linked_result_card_ids?: string[];
    linked_report_statement_id?: string;
  } | null;
  source_image_id?: string;
  source_image_index?: number;
  source_view?: string;
  source_series_id?: string;
  revision_history?: { action: string; timestamp: string; actor: string; note: string }[];
};

export type AnnotationReviewExport = {
  reviewed_png: string;
  ai_original_png: string;
  reviewed_pngs?: Record<string, string>;
  ai_original_pngs?: Record<string, string>;
  comparison_json: string;
  bundle: {
    schema_version: string;
    case_id: string;
    source_images: Record<string, unknown>[];
    ai_original_annotations: Annotation[];
    reviewed_annotations: Annotation[];
    review_summary: {
      ai_original_count: number;
      reviewed_count: number;
      manual_count: number;
      changed_count: number;
      review_status_counts: Record<string, number>;
    };
  };
};

export type ResultEvidence = {
  kind: string;
  text: string;
  ref: string;
};

export type ResultCard = {
  id: string;
  finding: string;
  status: "positive" | "negative" | "uncertain" | "not_assessed";
  candidate_diagnosis: string;
  probability?: number | null;
  confidence: number;
  evidence: ResultEvidence[];
  annotation_refs: string[];
  source: string;
  uncertainty_reason: string;
  next_safe_action: string;
  review_status: "unreviewed" | "accepted" | "rejected" | "uncertain" | "needs_follow_up";
  reviewer_note: string;
  validation_status: string;
  model_trace_refs: string[];
  source_image_ids?: string[];
  source_series_ids?: string[];
  source_views?: string[];
};

export type DifferentialCandidate = {
  id: string;
  kind: string;
  label: string;
  finding: string;
  tentative: boolean;
  review_status: string;
  eligible_for_report_review: boolean;
  evidence_for: string[];
  evidence_against: string[];
  missing_information: string[];
  uncertainty: string;
  next_safe_action: string;
  result_card_id: string;
  annotation_refs: string[];
  source_image_ids: string[];
  source_series_ids: string[];
  source_views: string[];
  safety_note: string;
};

export type StudyImage = {
  image_id: string;
  index: number;
  filename: string;
  image_path?: string;
  source_path?: string;
  is_dicom?: boolean;
  preview_path?: string;
  format?: string;
  width?: number;
  height?: number;
  metadata: Record<string, unknown>;
  file_hashes?: Record<string, unknown>;
  study_id?: string;
  series_id?: string;
  sop_instance_uid?: string;
  view?: string;
  laterality?: string;
};

export type DicomTag = {
  tag: string;
  keyword: string;
  name: string;
  vr: string;
  value?: unknown;
  is_private: boolean;
  action: string;
};

export type DicomSafetyReport = {
  schema_version: string;
  generated_at: string;
  source_sha256: string;
  tag_groups: Record<string, DicomTag[]>;
  tag_counts: Record<string, number>;
  private_tag_count: number;
  burned_in_annotation_risk: {
    level: "high" | "unknown" | "low_declared" | string;
    burned_in_annotation: string;
    recognizable_visual_features: string;
    reason: string;
  };
  pixel_data_summary?: {
    declared_by_image_attributes: boolean;
    number_of_frames: number;
    transfer_syntax_uid: string;
    compressed: boolean;
    export_behavior: string;
  };
  deidentification_preview: { keyword: string; action: string; replacement: string }[];
  warnings: string[];
  dicomweb_status: string;
};

export type AnalysisResult = {
  case_id: string;
  input: Record<string, unknown>;
  image_quality: { score: number; exposure: string; positioning: string; limitations: string[] };
  findings: { label: string; description: string; confidence: number; status: string }[];
  annotations: Annotation[];
  result_cards: ResultCard[];
  differential_diagnosis: DifferentialCandidate[];
  anatomy_route?: AnatomyRoute;
  systematic_reading: Record<string, unknown> & { confidence?: number };
  report: { indication: string; technique: string; comparison: string; findings: string; impression: string; recommendation: string; watermark: string };
  model_trace: { stage: string; backend: string; model: string; status: string; detail: string }[];
  input_hashes?: Record<string, { algorithm?: string; digest?: string; bytes?: number; status?: string; path?: string }>;
  runtime_snapshot?: Record<string, unknown>;
  warnings: string[];
};

export type AnatomyRoute = {
  profile_id: "chest" | "msk" | "abdomen" | "spine" | "skull_facial" | "general";
  profile_label: string;
  body_region: string;
  anatomy: string;
  laterality: string;
  view: string;
  confidence: number;
  source: string;
  matched_term: string;
  model_slot: keyof RuntimeConfig;
  selected_model: string;
  support_status: string;
  supported_tasks: string[];
  finding_taxonomy: string[];
  required_views: string[];
  warnings: string[];
};

export type CaseRecord = {
  case_id: string;
  title: string;
  image_path?: string;
  image_preview?: string;
  metadata: Record<string, unknown>;
  file_hashes?: Record<string, unknown>;
  images?: StudyImage[];
  active_image_id?: string;
  analyses_by_image?: Record<string, AnalysisResult>;
  annotations: Annotation[];
  analysis?: AnalysisResult;
  report?: AnalysisResult["report"];
  chat_history: { role: "user" | "assistant" | "system"; content: string; timestamp: string }[];
  runtime?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type RuntimeConfig = {
  primary_backend: string;
  chat_model: string;
  vision_language_model: string;
  classification_model: string;
  segmentation_model: string;
  grounding_model: string;
  localization_confidence_threshold: number;
  chest_xray_model: string;
  msk_xray_model: string;
  abdomen_xray_model: string;
  spine_xray_model: string;
  skull_facial_xray_model: string;
  general_xray_model: string;
  report_model: string;
  openai_base_url: string;
  ollama_base_url: string;
  allow_cloud: boolean;
  cpu_only: boolean;
};

export type DatabaseLocation = {
  database_path: string;
  database_folder: string;
  default_database_path: string;
  configured: boolean;
  restart_required: boolean;
  pending_database_path?: string;
  copied_existing_database?: boolean;
  previous_database_path?: string;
};

export type HuggingFaceAuthStatus = {
  configured: boolean;
  storage: string;
  exported: boolean;
  usage: string;
};

export type DownloadJob = {
  id: string;
  url: string;
  name?: string;
  source?: string;
  target_path: string;
  partial_path?: string;
  status: "queued" | "downloading" | "paused" | "completed" | "failed" | "cancelled" | "installed" | "not_found" | string;
  percent?: number;
  bytes_read?: number;
  total_bytes?: number | null;
  speed_bps?: number;
  speed?: string;
  eta?: string;
  accept_ranges?: boolean;
  resumable?: boolean;
  retryable?: boolean;
  error?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
};

export type LocalModelArtifact = {
  id: string;
  name: string;
  source: string;
  artifact_path: string;
  artifact_type: "folder" | "file" | string;
  state: string;
  runtime_eligible: boolean;
  model_card_status: string;
  missing_card_fields: string[];
  human_review_status?: string;
  validation_evidence_status?: string;
  validation_evidence_assessment?: {
    status?: string;
    complete?: boolean;
    missing_fields?: string[];
    confidence_posture?: string;
    safety_note?: string;
  };
  task?: string;
  task_slot?: keyof RuntimeConfig;
  readiness?: string;
  detected_format_hints: string[];
  files: string[];
  file_count?: number;
  likely_model?: boolean;
  missing_required_files?: Record<string, boolean>;
  warnings: string[];
  card?: Record<string, unknown> | null;
  card_path?: string;
  safety_note: string;
};

export type VisionAdapter = {
  id: string;
  name: string;
  task: string;
  status: string;
  available: boolean;
  missing_dependencies: string[];
  runtime_field: keyof RuntimeConfig;
  runtime_backend?: string;
  model_card_id: string;
  install_hint: string;
  safety_note: string;
};

export type ReferenceSource = {
  name: string;
  kind: string;
  url: string;
  why_it_matters: string;
  medray_action: string;
};

export type MaturityGap = {
  area: string;
  current: string;
  next: string;
};

export type ReferenceCatalog = {
  version: string;
  scope: string;
  sources: ReferenceSource[];
  inspiration_patterns?: {
    pattern: string;
    inspired_by: string[];
    medray_takeaway: string;
  }[];
  maturity_gaps: MaturityGap[];
  recommended_next_builds: string[];
};

export type AuditBundle = {
  schema_version: string;
  generated_at: string;
  case: Record<string, unknown>;
  input_hashes: Record<string, { algorithm?: string; digest?: string; bytes?: number; status?: string; path?: string }>;
  runtime_snapshot: Record<string, unknown>;
  immutable_model_trace: AnalysisResult["model_trace"];
  model_cards: ModelCard[];
  output_summary: Record<string, unknown>;
  why_this_output_exists: Record<string, string>;
};

export type ModelCard = {
  id: string;
  name: string;
  version: string;
  source: string;
  task: string;
  clinical_status: string;
  intended_use: string;
  limitations: string[];
  requires_opt_in_cloud: boolean | string;
};

export type ModelCookbook = {
  version: string;
  principles: string[];
  hardware_recommendations: { tier: string; recommendation: string }[];
  starter_models?: Record<string, unknown>[];
  cookbooks: {
    id: string;
    title: string;
    best_for: string;
    query: string;
    sources: string[];
    hardware: string;
    steps: string[];
    safety: string;
  }[];
};

export type HardwarePlan = {
  profile: {
    detected_at: string;
    os: string;
    cpu: string;
    cpu_count?: number | null;
    ram_gb?: number | null;
    gpus: { name: string; vram_gb?: number | null; vendor?: string }[];
    max_vram_gb?: number | null;
    tier: string;
    tier_label: string;
    detection_notes: string[];
  };
  runtime_slots: {
    slot: keyof RuntimeConfig;
    label: string;
    task: string;
    recommended_model: string;
    starter_id?: string;
    source: string;
    includes?: string[];
    query: string;
    recommendation: string;
    vram_estimate: string;
    safety_note: string;
  }[];
  download_help: {
    queue: string;
    not_runtime: string;
    next_step: string;
  };
};

export type ValidationLabel = {
  case_id: string;
  title: string;
  protocol_id?: string;
  dataset_name?: string;
  split: string;
  anatomy?: string;
  view?: string;
  age_group?: string;
  subgroup_notes?: string;
  source_image_id?: string;
  source_image_index?: number | null;
  source_series_id?: string;
  source_view?: string;
  expected_body_region: string;
  expected_image_quality?: { diagnostic_quality: string; limitations: string[]; note?: string };
  expected_findings: { label: string; status: string; note?: string }[];
  expected_annotations?: {
    label: string;
    coordinate_type: string;
    required: boolean;
    coordinate?: { x: number; y: number; width: number; height: number } | null;
    min_iou?: number;
    points?: [number, number][];
    max_point_distance?: number;
    min_vertex_count?: number;
    note?: string;
    source_image_id?: string;
  }[];
  reference_standard: string;
  reviewer: string;
  protocol_notes?: string;
  skip_reason?: string;
  notes: string;
  created_at?: string;
  updated_at?: string;
  invalid?: boolean;
  error?: string;
};

export type ValidationResult = {
  schema_version: string;
  generated_at: string;
  evaluation_status: string;
  dataset_summary?: Record<string, unknown>;
  protocol_notes?: string[];
  runtime_snapshot_summary?: Record<string, unknown>;
  model_card_refs?: string[];
  failure_cases?: Record<string, unknown>[];
  false_alert_burden?: Record<string, unknown>;
  missed_reference_summary?: Record<string, unknown>;
  model_card_evidence_draft?: Record<string, unknown>;
  metrics: Record<string, number | null>;
  results: Record<string, unknown>[];
  limitations: string[];
  export_path?: string;
};
