# MedRay v2 Roadmap

MedRay v2 is a local-first X-ray AI research workstation. The product goal is to help a qualified reviewer produce traceable findings, annotations, candidate diagnostic impressions, and draft reports across X-ray studies, while avoiding unsupported clinical claims.

All outputs remain research, education, and prototyping artifacts. They require radiologist/physician verification and must not be presented as autonomous final diagnosis or validated clinical triage.

## Product North Star

MedRay v2 should support:

- importing X-ray and DICOM cases;
- routing studies to the right anatomy profile before inference;
- running transparent AI-assisted workflows with model trace and limitations;
- reviewing model findings, annotations, uncertainty, and report statements;
- linking `study -> finding -> annotation -> report statement -> reviewer decision`;
- configuring only reviewed local model artifacts;
- exporting reproducible audit, report, PNG, and validation bundles.

MedRAX remains an architectural inspiration: MedRay should behave like a tool-oriented, reviewable radiology workspace rather than a black-box text generator.

## Priority Order

1. Auditability before stronger AI.
2. Anatomy routing before model inference.
3. Model cards before model activation.
4. Human review state before report promotion.
5. Validation workbench before performance claims.
6. DICOM de-identification before DICOMweb transfer.
7. Result cards and grounded report statements before final diagnosis wording.

## Current Program State

Status updated August 25, 2026:

- Phase 1 Grounded Review: implemented for bounding boxes, reviewer points, and reviewer polygons. Manual creation, geometry editing, hide/show, lock, restore/delete, review status, reviewer notes, revision history, image identity, result-card links, report-section links, reviewed PNG, AI-original PNG, comparison JSON, and audit separation are in place. Point/polygon authoring is manual-only; it does not fabricate AI localization.
- Phase 2 Anatomy Routing: implemented foundation. Chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, and general/unknown profiles are routed before inference. Unknown/general studies are blocked with `routing_required`, and chest classifiers are not run on non-chest exams.
- Phase 3 MSK Localization Pilot: implemented runtime and validation foundation. The Ultralytics local detector adapter is gated to MSK, requires reviewed `local:` artifacts, imports only fracture-like classes, clamps/validates boxes, links result cards to annotations, and supports IoU/hit-rate metrics. No reviewed `.pt` weights are currently enabled, so `grounding_model` should remain `disabled`.
- Phase 4 Grounded Draft Reporting: initial implementation complete. Grounded review statements are generated from reviewed result cards and reviewed annotations, then included in live report UI, Markdown/PDF/JSON export, and audit bundles.
- Model Finder/runtime safety: implemented. Downloads/imports remain inactive until a complete local model card and human review exist. Runtime save rejects unreviewed `local:*` IDs and direct `data/models` paths.
- Structured validation evidence: implemented foundation. Local cards now record protocol/dataset/split, case and label counts, metric and false-alert summaries, missed references, known failures, anatomy/view/age coverage, reviewer/date, report reference, exact weights filename, and verified SHA-256. Runtime and audit distinguish `human_reviewed` from `locally_validated_for_protocol`; incomplete evidence keeps confidence conservative.
- Multi-image study navigator: implemented foundation. One case can contain multiple images and series identities; the Reading Room switches active images without carrying analysis across views, and annotations, result cards, grounded statements, validation labels, PNG review exports, Case Library counts, and audit records retain source image/view/series identity. Legacy single-image cases migrate in memory and on save.
- DICOM Safety: implemented foundation. The active DICOM image has a grouped local tag viewer, explicit remove/replace/retain preview, private-tag counts, burned-in annotation/recognizable-feature risk, metadata-only de-identified JSON, acknowledgement-gated de-identified DICOM copy, regenerated instance/reference UIDs, source/export hashes, audit summary, and disabled DICOMweb status. Exports never overwrite source data and remain prototype outputs requiring manual tag and pixel verification.
- Differential Assistance: implemented foundation. Tentative candidates are derived only from structured result cards, omit negative/rejected/fallback-only signals, expose evidence for, evidence against/limitations, missing information, uncertainty, review state, and source image identity, and flow into the Reading Room, report JSON/Markdown, and audit bundle. They remain diagnostic assistance for human review, not confirmed diagnoses or triage decisions.
- Latest bug/hardening pass: fixed per-image Validation Workbench lookup leaking active-image findings/result cards into another view; blocked zero-area polygon edits; sanitized nested patient identifiers in DICOM sequences; added first-frame multi-frame preview, MONOCHROME1 inversion, non-finite pixel handling, accurate UID actions, strict boolean acknowledgement, unique export filenames, and readback verification that removes a failed export.
- Latest multi-image stabilization: malformed legacy `images` and `analyses_by_image` payloads now recover safely, Validation Workbench can fall back to annotations stored only in the referenced per-image analysis, and the Reading Room navigator shows which study images have an analysis ready for human review.
- Legacy active-analysis recovery: when an old case has a stale `active_image_id` or orphan `analyses_by_image` entries, normalization now selects a valid image, removes unusable/orphan mappings, and restores the legacy top-level analysis to that active image instead of silently hiding it.
- Validation review navigation: each validation result row now exposes mismatch/agreement status and can open the corresponding local case and referenced study image directly in the Reading Room.
- Validation failure triage: the live workbench groups rows into mismatch/failure, uncertain/high-disagreement, skipped/no-analysis, and agreement queues for prioritized human review.
- Case identity and cleanup: uploads no longer use the image filename as the case title; reviewers can save an NPM/patient label locally, delete one case, or clear all case records, images, validation labels, and case exports with explicit confirmation. Model artifacts and runtime configuration remain untouched.
- Database location control: General Settings can persist a custom SQLite folder, copy the active database without overwriting an existing target, and clearly require a backend restart before the new location is used.
- Settings separation: global preferences now live in a dedicated General Settings page reachable from a topbar button on every page. Runtime Settings is reserved for AI backend, model, adapter, hardware, and runtime safety controls; the existing runtime and database safety gates remain unchanged.
- Current hardening pass: completed for the major legacy/partial/null collection and mapping paths. Chat history, study metadata/hashes, report and annotation geometry, audit export, runtime adapter responses, validation labels, corrupted database JSON, and all case-scoped export paths now fail safely or normalize malformed data. Case IDs can no longer escape local case/export directories.
- Current verification baseline: backend tests `119 passed, 1 skipped`; frontend tests `13 passed`; frontend production build passed. Interactive browser verification passed for General Settings access, Runtime Settings separation, global topbar navigation, and no console errors. This workspace is currently not a git repository.
- Security/usability sweep (July 25, 2026): completed a repository-wide feature/file review and security scan workflow; added hard limits for polygon geometry, unique-filename image binding, loopback-only launchers, and bounded/private-network-safe manual model downloads. GUI guidance is documented in `docs/GUI_USABILITY_GUIDE.md` using staged disclosure, explicit status/provenance, reversible actions, keyboard/focus support, and safety copy without removing features. Security scan artifacts remain under the active Codex Security scan directory.
- Security regression verification: backend tests `122 passed, 1 skipped` after the new boundary tests; focused model/security tests `24 passed`; frontend tests `14 passed`; frontend production build passed. Global Python test invocation is not supported because it lacks `pydantic_settings`; the project `.venv` is the validated runtime.
- Guided workflow usability: the Reading Room progress strip is now an interactive, keyboard-focusable navigator. It derives the actual next step from case, analysis, routing, and review state; a `routing_required` result or unresolved `general` profile keeps Analysis current, surfaces a nearby explanation, opens the anatomy selector, and does not imply that analysis is complete.
- LocateAnything research decision: `nvidia/LocateAnything-3B` is documented as a complementary experimental grounding candidate, not an active X-ray model. Parser-only work may proceed, but user-facing activation is gated by non-commercial license review, pinned remote-code review, measured local hardware fit, and held-out radiograph validation. See `docs/LOCATE_ANYTHING_EVALUATION.md`.
- LocateAnything R1 parser: implemented without downloading or running the model. The bounded parser accepts only official bbox, point, and `none` tokens, restores normalized coordinates to original-image pixels, rejects malformed/out-of-range/reversed/tampered geometry, removes same-label near-duplicates, hashes the raw output, and converts valid results to unreviewed model-coordinate annotations with zero fabricated confidence. Focused verification: `17 passed`; full backend verification: `141 passed, 1 skipped`.
- GUI simplification pass: completed across every live page. Persistent navigation now keeps the four daily-use destinations visible and places advanced tools behind one disclosure; repeated global copy was replaced by short page-specific guidance; the dashboard uses a compact four-step status strip; Reading Room removes inactive image/result controls before a case exists; Case Library shows 15 records at a time and moves destructive bulk cleanup under `Kelola`; Validation groups optional research metadata; Runtime Settings works as four real content tabs; Model Finder hides direct-download controls until requested; and About keeps the full research catalog available on demand. Narrow-viewport browser verification passed on all nine pages with no horizontal overflow. Frontend tests: `14 passed`; production build passed.

## Result-Focused Milestones

The detailed result roadmap lives in `docs/RESULT_FOCUSED_ROADMAP.md`.

- v0.4.5 Result Composer: implemented.
- v0.4.6 MedRAX-style Annotation Layer: implemented for bounding boxes, manual points/polygons, and the multi-image navigation foundation.
- v0.4.7 Anatomy Routing Foundation: implemented.
- v0.4.8 MSK Localization Pilot: implemented foundation; no reviewed weights active.
- v0.4.9 Human Review Loop: implemented for result cards and annotations.
- v0.4.10 Differential Assistance: implemented foundation; real-study reviewer validation remains pending.
- v0.4.11 Result Validation View: implemented.
- v0.4.12 Grounded Draft Reporting: implemented initial layer.
- v0.4.14 Settings Separation & Workspace Control Plane: implemented initial layer.

## Current Sprint Recommendation

The old v0.4a Model Finder sprint is no longer the main active build; it is now part of the safety foundation. The v0.4b reliability sweep, v0.4.13 structured-evidence foundation, multi-image navigator, point/polygon reviewer authoring, and v0.5 DICOM Safety foundation are complete. The active blocked focus remains one reviewed local artifact exercised end to end; differential assistance and real-study validation can continue independently.

1. Keep `grounding_model=disabled` until a narrow, reviewed fracture detector artifact exists under `data/models`; the organized Runtime Settings overview now surfaces this gate directly.
2. Exercise one reviewed local artifact end to end through Model Finder, local registry, Runtime Settings, analysis trace, Validation Workbench, audit export, chat review, and Differential Assistance. No `.pt` weights are currently present under `data/models`, so this requires a real reviewed artifact rather than a synthetic model output.
3. Run representative task-based usability sessions on the simplified GUI: first-time setup, one-image review, multi-image navigation, provenance explanation, annotation correction, report review, and stopping a risky DICOM export. Record completion rate, time, help requests, wrong clicks, near misses, and SUS; implementation alone is not usability validation.
4. Add the remaining security fixes from the scan backlog: approved-root/confirmation policy for database relocation, server-owned review/provenance transitions, safe DICOM/export symlink handling, bounded upload/DICOM decode budgets, and safe runtime model revalidation.
5. Stabilize the implemented multi-image flow with real multi-view studies while keeping legacy single-image compatibility.
6. Stabilize the implemented manual point/polygon authoring with real reviewer workflows.
7. Stabilize the implemented v0.5 DICOM Safety flow against real vendor DICOM variants and a formally reviewed de-identification protocol.
8. Complete LocateAnything R0 before R2: review and hash an immutable code/artifact manifest, document the isolated dependency environment, and pre-register the generic-image hardware/format evaluation. R1 parser work is complete. Do not activate the public checkpoint in Runtime Settings or replace the narrow MSK artifact gate.

## v0.4.13 - Structured Validation Evidence

Goal: make the confidence and audit posture of an active reviewed model depend on explicit local evidence, not a free-text `validation_status`.

Implementation status: foundation complete. The old free-text field is no longer required. Structured evidence is normalized and assessed, exact weights identity is SHA-256-bound, Validation Workbench exports an attachable/referenceable evidence draft, and Runtime Settings plus audit bundles expose the evidence status. A real artifact still needs to be exercised end to end.

Deliverables:

- Model-card evidence fields for protocol ID, dataset name, split, sample count, anatomy/view/age coverage, metric summary, subgroup notes, known failures, reviewer, review date, and artifact hash.
- Validation Workbench export that can be attached or referenced from a local model card.
- Runtime Settings display that distinguishes `human_reviewed` from `locally_validated_for_protocol`.
- Audit bundle entries that record which validation evidence was used when a model was active.
- False-alert burden and missed-reference review summaries for localization pilots.

Acceptance criteria:

- A `local:` model can be selected only when the card is human reviewed; user-facing confidence should remain conservative until structured evidence is present.
- A reviewer can tell which dataset/protocol supported the active model and which anatomy/view coverage is excluded.
- Validation evidence remains research/prototype evidence and is not worded as clinical performance.

## v0.5 - DICOM Safety

Goal: make DICOM handling safer before adding transfer or broader study management.

Implementation status: foundation complete. Tag review, de-identification preview, private-tag and burned-in warnings, safe metadata/DICOM copies, source preservation, unique non-overwriting output names, readback verification, study/series counts, multi-frame first-frame preview, MONOCHROME1 handling, and explicit DICOMweb-disabled state are implemented. This is a prototype basic profile, not certification of PS3.15 compliance; broader vendor-specific sequences, pixel redaction, and formal protocol validation remain pending.

Deliverables:

- DICOM tag viewer grouped into patient, study, series, acquisition, and private tags.
- De-identification preview before export.
- Metadata-only JSON export and optional de-identified DICOM export.
- Private tag and burned-in annotation risk warnings.
- Series/study grouping in Case Library and Reading Room.

Acceptance criteria:

- The user sees which tags will be removed before export.
- Export does not overwrite source data.
- Private tags are flagged.
- DICOMweb remains disabled unless explicitly configured.

## References and Guardrails

- FDA MLMD transparency principles, FDA AI lifecycle guidance, NIST AI RMF, DICOM PS3.15, C2PA, STARD-AI, CLAIM, DECIDE-AI, TRIPOD+AI, and ACR DSI inform the transparency, review, validation, and evidence-export posture.
- Use "AI candidate diagnosis", "diagnostic assistance", "research signal", "draft", and "human review" language.
- Do not display "diagnosis confirmed" from model output alone.
- Do not rank urgency or triage priority until a validated protocol exists.
- Do not generate localization graphics unless a real localization/segmentation model produced coordinates or masks.
