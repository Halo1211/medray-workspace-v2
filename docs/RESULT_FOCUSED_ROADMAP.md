# Result-Focused Roadmap

MedRay v2 should help a clinician or researcher reason toward a diagnosis. It can generate AI candidate diagnoses, annotated findings, differential considerations, and report drafts, but it should not pretend to be the final accountable diagnostician. The product direction is therefore:

> produce better, safer, more reviewable results that a qualified human can use.

This document adds a result layer on top of the existing technical roadmap.

MedRAX is a core foundation for this result layer. The target is not only text output, but a tool-based radiology workflow that can produce candidate diagnosis, pathology classification, image annotations, segmentation/grounding evidence, VQA-style reasoning, and report drafts.

The annotation and reporting outcome is defined in `docs/XRAY_ANNOTATION_DIRECTION.md`. The core product relationship is `study -> finding -> annotation -> report statement -> reviewer decision`, implemented through one shared X-ray workstation with anatomy-specific pipelines rather than a chest-only workflow.

## Result North Star

For each case, MedRay should eventually produce a structured review package:

- image quality and usability;
- body region and projection/view;
- key positive, negative, and uncertain findings;
- AI candidate diagnostic impression with confidence/uncertainty;
- annotations, segmentation masks, or grounding boxes when produced by real tools;
- evidence links from each finding to model output, image metadata, annotations, and trace events;
- differential diagnosis candidates with explicit uncertainty;
- suggested next safe action, such as "review by radiologist", "compare prior", "repeat image if inadequate", or "correlate clinically";
- draft report text that stays watermarked until human review;
- validation/audit bundle for research review.

The UI should make it clear which parts are model signals, which are fallback/template text, and which require human confirmation.

## Result Safety Rules

- Use "AI candidate diagnosis", "diagnostic assistance", "research signal", "draft", and "candidate" language until proper validation and human review exist.
- Do not display "diagnosis confirmed" from model output alone.
- Do not rank urgency or triage priority until a validated protocol exists.
- Do not generate localization graphics unless a localization/segmentation model actually produced coordinates or masks.
- Every result must show source, runtime, model card, and limitations.
- The user should be able to disagree, edit, hide, or mark a result as unsupported.

## v0.4.5 - Result Composer

Goal: turn raw classifier, annotation, segmentation, grounding, VQA, report, and fallback output into reviewable result cards with candidate diagnostic interpretation.

Initial implementation status: backend `ResultCard` schema and composer are wired into the analysis pipeline. Reading Room now has a `Result Cards` panel before report review, and report export summarizes result cards before free-text findings.

Deliverables:

- Result card schema:
  - `finding`
  - `status`
  - `candidate_diagnosis`
  - `probability/confidence`
  - `evidence`
  - `annotation_refs`
  - `source`
  - `uncertainty_reason`
  - `next_safe_action`
- UI panel in Reading Room showing result cards before report text.
- Result cards can reference annotations, grounding boxes, segmentation masks, and model trace events.
- Report generator uses result cards as input instead of free-form findings.
- Trust panel links result cards to model trace and model cards.

Acceptance criteria:

- A user can see why each result exists.
- Fallback/demo results remain visibly different from real model results.
- Low-confidence and unsupported outputs are not worded as confirmed diagnoses.

## v0.4.6 - MedRAX-Style Annotation Layer

Goal: make image evidence first-class, not a decorative overlay.

Initial implementation status: annotations now carry coordinate space and transform metadata fields, and result cards can link to model-produced annotation refs. Fallback review-region overlays remain explicitly separate from pathology localization.

Grounded review update: the Reading Room now supports manual bounding-box creation, selection, move/resize handles, visibility, locking, review decisions, reviewer notes, restore/delete rules, revision history, stable result-card/report-section links, and click-to-focus navigation between image evidence, result cards, and structured report sections. Mobile Reading Room panels stack vertically for annotation work.

Export/source update: annotations now carry source image ID/index, view, and series identity. The review package exports per-image AI-original and reviewed PNGs plus comparison JSON containing source images, original state, reviewed state, manual marks, revision history, and review counts. Audit schema `0.4.0` includes multi-image identity, annotation review summary, grounded review statements, and validation evidence.

Deliverables:

- Annotation panel in Reading Room with label, confidence, source, coordinate type, explanation, and export.
- Grounding/segmentation adapter contract:
  - source model;
  - coordinate/mask type;
  - coordinate space;
  - transform metadata;
  - confidence;
  - explanation.
- Annotation references in result cards.
- Annotation-level validation checks for expected coordinate type and required labels.

Acceptance criteria:

- Fallback annotation is clearly labeled as a review region.
- Model-returned coordinates and segmentation masks are distinguishable.
- Annotated PNG export preserves visible overlays.
- Audit bundle includes annotation provenance.
- Clicking an annotation focuses its linked result card and report statement, and the reverse interaction works as well.
- Annotation review preserves the original model output and stores accepted, rejected, hidden, or redrawn human state separately.
- Multi-view studies retain the source image/view for every annotation.

Remaining v0.4.6 work:

- stabilize the implemented manual point and polygon authoring with real reviewer workflows;
- stabilize the implemented multi-image study navigator and image-switching workflow with real multi-view DICOM studies;
- point placement, polygon completion, shape movement, polygon vertex editing, locking, review, source identity, PNG export, report wording, and validation checks are implemented;
- annotation-level bounding-box spatial validation is now implemented in the Phase 3 pilot.

## v0.4.7 - Anatomy Routing Foundation

Goal: route every plain-radiography study to an explicit anatomy profile before any model inference.

Implementation status: complete for the routing foundation. MedRay now supports chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, and general/unknown profiles. The route records anatomy, laterality, view, confidence, provenance, finding taxonomy, expected views, model slot, selected model, and support status. Reviewers can override the profile in the Reading Room, and unsupported or unknown combinations are visibly blocked.

Next validation work:

- lock and document a reviewed model version for each enabled profile;
- test routing accuracy against a representative multi-anatomy DICOM set;
- validate exclusions, age/view coverage, calibration, and subgroup behavior;
- begin a narrow MSK fracture-localization pilot with box-level reference labels.

## v0.4.8 - MSK Localization Pilot

Goal: connect one reviewed local fracture detector to real, traceable bounding boxes without presenting unvalidated boxes as confirmed pathology.

Implementation status: the Ultralytics-compatible local adapter, MSK-only support gate, original-image coordinate validation, annotation/result-card linking, model trace, confidence threshold, and box-level Validation Workbench metrics are implemented. No weights are bundled, downloaded, or enabled automatically.

Activation gate:

- import a `.pt` artifact under `data/models`;
- complete its required model card and mark it human reviewed;
- configure its `local:` artifact ID in `grounding_model`;
- run held-out box-level validation and inspect IoU, hit rate, failure cases, and subgroup coverage;
- keep all boxes as unconfirmed research candidates until the protocol is complete.

## v0.4.9 - Human Review Loop

Goal: make the user's review part of the case record.

Initial implementation status: result cards can be marked `accepted`, `rejected`, `uncertain`, or `needs_follow_up`, with a reviewer note saved back into the local case payload.

Deliverables:

- Mark result as accepted, rejected, uncertain, or needs follow-up.
- Mark annotation as accepted, rejected, uncertain, or needs follow-up.
- Add reviewer note per finding/result card.
- Save review status in the case payload.
- Export review notes in audit and report JSON.

Acceptance criteria:

- Human review state survives reload.
- Export separates model output from human review.
- Chat can answer from reviewed state but must not silently overwrite it.

## v0.4.10 - Differential Assistance

Goal: help organize differential considerations and candidate diagnoses without making final accountable diagnosis claims.

Current implementation status: foundation complete. Tentative candidates are derived from structured result cards, exclude negative, rejected, and fallback-only outputs, and show evidence for, evidence against/limitations, missing information, uncertainty, human-review state, linked annotations, and source image/series/view identity. The same structure is included in the Reading Room, report JSON/Markdown, and audit bundle. Real-study reviewer validation remains pending.

Deliverables:

- Differential candidates generated from structured findings.
- Evidence-for and evidence-against fields.
- Missing information prompts, such as "prior comparison unavailable" or "clinical history needed".
- Language guardrails that keep recommendations conservative.

Acceptance criteria:

- Differential candidates are explicitly tentative.
- Missing data is visible.
- Report impression remains watermarked and requires qualified review.

## v0.4.11 - Result Validation View

Goal: connect result cards to the Validation Workbench.

Initial implementation status: validation exports include `result_card_matches`, result-card agreement counts/rates, and each matched card's human review status. The live Validation Workbench now marks mismatch counts, groups mismatch/uncertain/skipped/agreement cases, and opens the corresponding case/image directly for review.

Deliverables:

- Validation result table maps labels to result cards.
- Failure-case review groups:
  - missing case;
  - no analysis;
  - unsupported label;
  - model mismatch;
  - uncertain/high disagreement;
  - inadequate image quality.
- Export includes result-card-level agreement, not just case-level metrics.

Acceptance criteria:

- Validation still says agreement/research evaluation, not clinical performance.
- Mismatch review is easy to inspect case by case, with direct navigation to the source case and study image. Failure cases are grouped by mismatch, uncertainty, skipped/no-analysis, and agreement priority.

## v0.4.12 - Grounded Draft Reporting

Goal: generate report statements from structured result cards and reviewed annotations, not directly from unreviewed free-text model output.

Initial implementation status: report export and the Reading Room report panel now include a `Grounded Review Statements` section. Accepted, uncertain, and needs-follow-up result cards can be promoted into cautious report statements with linked reviewed annotation evidence. Rejected and unreviewed result cards are counted as not promoted, so they remain visible for provenance without becoming report findings. Report JSON and audit bundles now preserve the same grounded statements as structured data.

Deliverables:

- Grounded statements summarize reviewed result cards, score, model status, reviewer notes, and linked annotation geometry.
- Standalone reviewed manual annotations can appear as grounded review statements.
- Rejected and unreviewed result cards are excluded from promoted report statements.
- Markdown/PDF/JSON export, audit bundles, and the live report panel expose the grounded-review layer before free-text findings.

Acceptance criteria:

- A report statement can be traced back to a reviewed result card or annotation.
- Human review status controls whether a model signal is promoted.
- The output remains a draft research/education artifact and does not claim final diagnosis.

## Current Hardening Track

Status as of July 25, 2026: the broad defensive reliability pass, structured validation-evidence foundation, multi-image navigator, manual point/polygon authoring, Differential Assistance foundation, DICOM Safety foundation, and initial settings separation are complete. Verification baseline: backend tests `119 passed, 1 skipped`, frontend tests `13 passed`, frontend production build passed, and interactive settings navigation checks passed.

Completed hardening:

- preserve reviewed annotations over stale model annotations, with fallback to original model output only when reviewed state is absent;
- recover malformed legacy multi-image collections and show per-image analysis readiness in the study navigator;
- restore a valid legacy top-level analysis to the selected image when stale active IDs or orphan per-image mappings would otherwise hide it;
- allow validation annotations to be read from the referenced per-image analysis when a legacy case lacks a case-level annotation copy;
- mark validation mismatches in the live result table and open the corresponding case/source image for review;
- tolerate legacy result cards without `annotation_refs`;
- tolerate partial annotations without coordinates during report generation, chat, export, and frontend rendering;
- reject malformed case saves that lack `case_id`;
- keep chat robust when old case history entries are incomplete;
- sanitize malformed findings, result cards, annotations, warnings, model traces, validation rows, external model search results, Ollama tag payloads, and frontend list responses;
- keep Validation Workbench, audit bundle export, annotation PNG export, Model Finder, Runtime Settings, Case Library, and chat review usable when old records contain non-list fields;
- keep local model artifacts inactive until model-card review and human review are complete; keep user-facing confidence conservative until structured protocol evidence is complete.

The structured validation-evidence foundation is implemented. Next result-focused work is one real reviewed artifact exercised end to end:

- use the implemented structured model-card evidence instead of free-text `validation_status`;
- attach/reference an exported Validation Workbench report from the reviewed artifact card;
- verify false-alert burden, missed references, subgroup coverage, and known failure modes for the enabled localization pilot;
- keep report and chat wording conservative until evidence is attached and reviewed.

## v0.4.13 - Structured Validation Evidence

Goal: let the reviewer understand what evidence supports an active local model artifact and where that evidence does not apply.

Implementation status: foundation complete. Model Finder stores and assesses structured evidence, binds it to the exact weights filename and SHA-256, Validation Workbench produces an evidence draft and report reference, and Runtime Settings/audit show the separate human-review and protocol-validation states. End-to-end proof with a real reviewed `.pt` remains pending because none is present under `data/models`.

Deliverables:

- Structured validation evidence fields:
  - protocol ID;
  - dataset/source name;
  - held-out split;
  - case count and label count;
  - anatomy/view/age coverage;
  - metric summary;
  - false-alert burden;
  - known failures and exclusions;
  - subgroup notes;
  - reviewer and review date;
  - artifact hash and weights filename.
- Validation Workbench report attachment or reference from local model cards.
- Runtime/audit display of the evidence ID used for an active `local:` model.
- Clear distinction between `human_reviewed`, `configured_unvalidated`, and `locally_validated_for_protocol`.

Acceptance criteria:

- The app can show why a model is allowed to run and what it has not been validated for.
- Local validation evidence remains bounded to a specific dataset/protocol and is not presented as general clinical validity.
- An active MSK localization model can be audited from case output back to artifact, model card, validation evidence, and reviewer decision.

## v0.4.14 - Settings Separation & Workspace Control Plane

Goal: separate global application preferences from AI runtime controls while keeping both understandable before a reviewer starts an analysis.

Implementation status: initial layer complete. A dedicated General Settings page now owns language, theme, global safety posture, and SQLite database location. A topbar button opens it from every page. Runtime Settings now focuses on backend, model slots, local adapters, hardware, runtime safety, and the roadmap gate. Existing API contracts and safety validation are unchanged.

Deliverables:

- Dedicated General Settings page for global preferences and local data location.
- Persistent Runtime Settings overview with local/cloud posture and CPU/GPU mode.
- Clear database readiness and restart-required state in General Settings.
- Reviewed local model count and grounding activation state in Runtime Settings.
- Topbar access to General Settings from every page.
- Visible roadmap note for the blocked reviewed-artifact milestone.

Acceptance criteria:

- A reviewer can distinguish global application settings from AI runtime settings.
- Model readiness and grounding safety remain visible and conservative.
- Existing local artifact review gates and database restart behavior are unchanged.

## v0.4.15 - Guided Review Navigation & Grounding Research Gate

Goal: make the safe next action obvious while creating a bounded path to evaluate general-purpose visual grounding without presenting it as medical validation.

Implementation status: guided navigation implemented; LocateAnything R1 bounded parser and MedRay annotation conversion complete. Model download, remote-code execution, runtime integration, and user-facing inference intentionally remain unimplemented pending R0 review.

Deliverables:

- Interactive Reading Room steps that navigate to Import, Analysis, Result Cards, and Report.
- Progress derived from actual active-case, per-image analysis, routing, and result-card review state.
- `routing_required` remains an incomplete Analysis step and opens the manual anatomy selector with a nearby recovery message.
- LocateAnything R0-R4 evaluation gates covering license, pinned remote code, parser safety, hardware measurement, radiograph feasibility, and controlled pilot criteria.
- Separate experimental grounding identity if a pilot is ever enabled; no silent reuse of the narrow reviewed detector slot.

Acceptance criteria:

- A new reviewer can see and activate the next available workflow step without opening the full guide.
- Keyboard focus reaches every step and programmatic `aria-current="step"` matches the visible next action.
- Unknown anatomy cannot make the workflow look analysis-complete.
- LocateAnything output remains unavailable to users until exact artifacts, code, prompt set, protocol evidence, and review status are traceable.
- General-purpose grounding scores are never presented as clinical confidence or confirmed diagnosis.

## Later Result Milestones

### v0.5 - DICOM Safety

Implementation status: foundation complete.

- Grouped local tag viewer for patient, study, series, acquisition, private, and other tags.
- Preview of removed, replaced, regenerated, and retained fields before export.
- Private-tag counts and burned-in/recognizable-feature risk warnings.
- Metadata-only de-identified JSON and a new de-identified DICOM copy; source files are never overwritten.
- Burned-in high/unknown risk requires explicit acknowledgement after manual pixel review.
- Instance and reference UIDs are regenerated while SOP class and transfer syntax UIDs remain valid.
- DICOMweb remains disabled and unconfigured.
- Exports use unique filenames and are read back; if nested PHI/private-tag/pixel-integrity verification fails, the new export is removed.
- Multi-frame DICOM preview is explicitly first-frame-only, with MONOCHROME1 and non-finite pixel handling.

Remaining safety work: validate against real vendor sequences, define a formally reviewed PS3.15 profile, add pixel redaction tooling, and test transfer syntax/codec variants before any transfer feature.

### v0.9 - Diagnostic Assistance Pack

Package the case as a human-review artifact:

- result cards;
- candidate diagnostic impression;
- draft report;
- image quality;
- annotations;
- segmentation/grounding outputs when available;
- differential candidates;
- missing data;
- human review notes;
- audit/model cards;
- validation context.

### v1.0 Research-Only Decision Support

Only after validation protocols are documented:

- dataset/protocol-specific performance summary;
- locked model version;
- calibration notes;
- known failure modes;
- user-facing intended-use statement;
- clear boundary between research support and clinical device claims.

## References Used

- FDA Clinical Decision Support Software guidance: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
- DECIDE-AI: https://www.nature.com/articles/s41591-022-01772-9
- TRIPOD+AI: https://www.bmj.com/content/385/bmj-2023-078378
- ACR Data Science Institute: https://www.acr.org/Data-Science-and-Informatics/ACR-Data-Science-Institute
- FDA MLMD transparency principles: https://www.fda.gov/medical-devices/software-medical-device-samd/transparency-machine-learning-enabled-medical-devices-guiding-principles
