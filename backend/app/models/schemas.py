from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnnotationSource(str, Enum):
    MODEL_COORDINATE = "model-returned coordinate"
    SEGMENTATION_MASK = "segmentation mask"
    FALLBACK_HEURISTIC = "fallback heuristic"
    MANUAL = "manual user annotation"


class RuntimeBackend(str, Enum):
    DEMO = "demo"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai-compatible"
    HF_LOCAL = "huggingface-local"
    MEDRAX = "medrax-tool-pipeline"


MAX_POLYGON_VERTICES = 4096


class Coordinate(BaseModel):
    type: Literal["bbox", "point", "polygon", "mask", "grounding_box"] = "bbox"
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0
    points: list[tuple[float, float]] = []
    mask_path: str | None = None
    coordinate_space: Literal["original_image", "preview_image", "model_input"] = "original_image"

    @model_validator(mode="after")
    def validate_manual_geometry(self) -> "Coordinate":
        if self.type == "point" and not (math.isfinite(self.x) and math.isfinite(self.y)):
            raise ValueError("Point coordinates must be finite.")
        if self.type == "polygon":
            if len(self.points) < 3 or len(self.points) > MAX_POLYGON_VERTICES or not all(math.isfinite(x) and math.isfinite(y) for x, y in self.points):
                raise ValueError("Polygon coordinates require at least three finite vertices.")
            area = abs(sum(self.points[index][0] * self.points[(index + 1) % len(self.points)][1] - self.points[(index + 1) % len(self.points)][0] * self.points[index][1] for index in range(len(self.points))) / 2)
            if area <= 0:
                raise ValueError("Polygon coordinates require non-zero area.")
        return self


class AnnotationTransformMetadata(BaseModel):
    source_space: Literal["original_image", "preview_image", "model_input"] = "original_image"
    display_space: Literal["original_image", "preview_image", "model_input"] = "original_image"
    scale_x: float = 1
    scale_y: float = 1
    offset_x: float = 0
    offset_y: float = 0
    model_input_width: int | None = None
    model_input_height: int | None = None
    original_width: int | None = None
    original_height: int | None = None
    note: str = ""


class AnnotationRevision(BaseModel):
    action: Literal["created", "moved", "resized", "edited", "reviewed", "visibility", "locked"]
    timestamp: str = Field(default_factory=now_iso)
    actor: str = "local reviewer"
    note: str = ""


class AnnotationOriginalState(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    coordinate: Coordinate
    explanation: str
    visible: bool = True
    linked_result_card_ids: list[str] = Field(default_factory=list)
    linked_report_statement_id: str = ""


class Annotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    confidence: float = Field(ge=0, le=1)
    source: AnnotationSource
    source_model: str = ""
    source_model_version: str = ""
    coordinate: Coordinate
    explanation: str
    visible: bool = True
    locked: bool = False
    review_status: Literal["unreviewed", "accepted", "rejected", "uncertain", "needs_follow_up"] = "unreviewed"
    reviewer_note: str = ""
    transform_metadata: AnnotationTransformMetadata = Field(default_factory=AnnotationTransformMetadata)
    linked_result_card_ids: list[str] = []
    linked_report_statement_id: str = ""
    original_coordinate: Coordinate | None = None
    original_state: AnnotationOriginalState | None = None
    source_image_id: str = "primary"
    source_image_index: int = Field(default=0, ge=0)
    source_view: str = ""
    source_series_id: str = ""
    revision_history: list[AnnotationRevision] = Field(default_factory=list)


class Finding(BaseModel):
    label: str
    description: str
    confidence: float = Field(ge=0, le=1)
    probability: float | None = Field(default=None, ge=0, le=1)
    evidence: list[str] = []
    status: Literal["positive", "negative", "uncertain", "not_assessed"] = "uncertain"


class Report(BaseModel):
    indication: str = ""
    technique: str = "Radiografi konvensional; detail proyeksi mengikuti metadata/masukan pengguna."
    comparison: str = "Tidak tersedia."
    findings: str = ""
    impression: str = ""
    recommendation: str = ""
    language: Literal["id", "en"] = "id"
    watermark: str = "AI-assisted draft, not for standalone clinical diagnosis."


class ResultEvidence(BaseModel):
    kind: Literal["finding", "annotation", "model_trace", "image_quality", "metadata", "limitation", "human_review"] = "finding"
    text: str
    ref: str = ""


class ResultCard(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    finding: str
    status: Literal["positive", "negative", "uncertain", "not_assessed"] = "uncertain"
    candidate_diagnosis: str = ""
    probability: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(default=0, ge=0, le=1)
    evidence: list[ResultEvidence] = []
    annotation_refs: list[str] = []
    source: str = "fallback"
    uncertainty_reason: str = ""
    next_safe_action: str = "Review by a qualified radiologist/physician."
    review_status: Literal["unreviewed", "accepted", "rejected", "uncertain", "needs_follow_up"] = "unreviewed"
    reviewer_note: str = ""
    validation_status: Literal["not_validated", "local_agreement_checked", "validation_mismatch", "skipped"] = "not_validated"
    model_trace_refs: list[str] = []
    source_image_ids: list[str] = []
    source_series_ids: list[str] = []
    source_views: list[str] = []


class ImageQuality(BaseModel):
    score: float = Field(ge=0, le=1)
    exposure: str = "unknown"
    positioning: str = "unknown"
    artifacts: list[str] = []
    limitations: list[str] = []


class SystematicReading(BaseModel):
    body_region: str = "unknown/general X-ray"
    adequacy: str = ""
    view_projection: str = ""
    alignment_anatomy: str = ""
    soft_tissue: str = ""
    bone_joint: str = ""
    lung_pleura_mediastinum_cardiac: str = ""
    abdomen: str = ""
    device_foreign_body: str = ""
    abnormality_list: list[str] = []
    positive_findings: list[str] = []
    negative_important_findings: list[str] = []
    differential_diagnosis: list[str] = []
    final_impression: str = ""
    confidence: float = Field(default=0.35, ge=0, le=1)
    limitation: str = ""


class AnatomyRoute(BaseModel):
    profile_id: Literal["chest", "msk", "abdomen", "spine", "skull_facial", "general"] = "general"
    profile_label: str = "General X-ray"
    body_region: str = "Unknown/general X-ray"
    anatomy: str = "unknown"
    laterality: str = "unknown"
    view: str = "unknown"
    confidence: float = Field(default=0.2, ge=0, le=1)
    source: str = "fallback"
    matched_term: str = ""
    model_slot: str = "general_xray_model"
    selected_model: str = "disabled"
    support_status: str = "fallback_only"
    supported_tasks: list[str] = Field(default_factory=list)
    finding_taxonomy: list[str] = Field(default_factory=list)
    required_views: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModelTrace(BaseModel):
    stage: str
    backend: str
    model: str
    status: Literal["ok", "fallback", "skipped", "failed"]
    detail: str = ""
    timestamp: str = Field(default_factory=now_iso)


class AnalysisInput(BaseModel):
    image_path: str | None = None
    filename: str | None = None
    format: str | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = {}
    custom_prompt: str = ""
    source_image_id: str = ""
    source_image_index: int = Field(default=0, ge=0)
    source_series_id: str = ""
    source_view: str = ""


class StudyImage(BaseModel):
    image_id: str
    index: int = Field(default=0, ge=0)
    filename: str = ""
    image_path: str | None = None
    source_path: str | None = None
    is_dicom: bool = False
    preview_path: str | None = None
    format: str | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = {}
    file_hashes: dict[str, Any] = {}
    study_id: str = ""
    series_id: str = ""
    sop_instance_uid: str = ""
    view: str = ""
    laterality: str = ""


class AnalysisResult(BaseModel):
    case_id: str
    input: AnalysisInput
    image_quality: ImageQuality
    findings: list[Finding]
    annotations: list[Annotation]
    result_cards: list[ResultCard] = []
    differential_diagnosis: list[dict[str, Any]]
    anatomy_route: AnatomyRoute = Field(default_factory=AnatomyRoute)
    systematic_reading: SystematicReading
    report: Report
    model_trace: list[ModelTrace]
    input_hashes: dict[str, Any] = {}
    runtime_snapshot: dict[str, Any] = {}
    warnings: list[str] = []


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: str = Field(default_factory=now_iso)


class CaseRecord(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    title: str = "Untitled X-ray case"
    image_path: str | None = None
    image_preview: str | None = None
    metadata: dict[str, Any] = {}
    file_hashes: dict[str, Any] = {}
    images: list[StudyImage] = []
    active_image_id: str = ""
    analyses_by_image: dict[str, Any] = {}
    annotations: list[Annotation] = []
    analysis: AnalysisResult | None = None
    report: Report | None = None
    chat_history: list[ChatMessage] = []
    runtime: dict[str, Any] = {}


class ModelMetadata(BaseModel):
    id: str
    name: str
    source: Literal["Hugging Face", "GitHub", "Ollama", "local", "manual URL"]
    task_type: str = "unknown"
    license: str = "unknown"
    size: str = "unknown"
    quantization: str = "unknown"
    vram_estimate: str = "unknown"
    ram_estimate: str = "unknown"
    supports_cpu: bool = True
    supports_gpu: bool = True
    medical_tags: list[str] = []
    url: str | None = None
    local_path: str | None = None
    status: Literal["available", "downloading", "installed", "failed", "incompatible"] = "available"
    reason: str = ""
    maturity_score: int = Field(default=0, ge=0, le=100)
    fit_summary: str = ""
    cookbook_tags: list[str] = []
    safety_notes: list[str] = []


class RuntimeConfig(BaseModel):
    primary_backend: RuntimeBackend = RuntimeBackend.DEMO
    chat_model: str = "demo-safe-radiology-assistant"
    vision_language_model: str = "demo-vlm"
    classification_model: str = "demo-classifier"
    segmentation_model: str = "disabled"
    grounding_model: str = "disabled"
    localization_confidence_threshold: float = Field(default=0.25, ge=0.05, le=0.95)
    chest_xray_model: str = "inherit"
    msk_xray_model: str = "inherit"
    abdomen_xray_model: str = "inherit"
    spine_xray_model: str = "inherit"
    skull_facial_xray_model: str = "inherit"
    general_xray_model: str = "disabled"
    report_model: str = "demo-report-generator"
    openai_base_url: str = "http://127.0.0.1:8000/v1"
    ollama_base_url: str = "http://127.0.0.1:11434"
    allow_cloud: bool = False
    cpu_only: bool = True
