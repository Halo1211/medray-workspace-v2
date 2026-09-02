# X-ray Annotation and Reporting Direction

MedRay v2 should use annotation to improve review, reporting, and validation across plain radiography. Annotation is not a decorative overlay and must not be treated as proof of disease by itself. Its product role is to connect a candidate finding to visible image evidence, a report statement, model provenance, and a human decision.

## Product Outcome

For each supported X-ray study, the intended review flow is:

1. Identify study type, anatomy, laterality, projection, image count, and technical adequacy.
2. Route the study to an anatomy-specific tool profile.
3. Produce structured positive, negative, and uncertain findings.
4. Localize supported findings with a box, point, polygon, mask, or anatomical region.
5. Link each localization to one finding and one report sentence.
6. Let the reviewer accept, reject, edit, hide, or redraw the annotation and finding.
7. Generate a draft report from reviewed structured evidence.
8. Preserve model output, edits, timing, and final review state for audit and validation.

The central data relationship is:

`study -> finding -> annotation -> report statement -> reviewer decision`

## One X-ray Workstation, Multiple Anatomy Pipelines

Chest X-ray references are useful as the first mature example, but they must not define the product boundary. MedRay should share one review interface and one evidence contract while allowing separate models, taxonomies, prompts, and validation protocols per anatomy family.

Initial anatomy profiles:

- Chest: lungs, pleura, heart, mediastinum, hila, bones, devices, and other visible structures.
- Musculoskeletal and trauma: fracture, dislocation, subluxation, alignment, joint space, bone lesion, soft-tissue abnormality, and hardware.
- Abdomen/KUB: bowel gas pattern, obstruction/ileus features, free air when assessable, calcification, organ silhouette, bones, and devices.
- Spine: alignment, vertebral height, disc spaces, degenerative change, fracture, destructive lesion, and hardware.
- Skull, facial bones, and sinus: alignment, fracture, sinus opacity/fluid level, bone lesion, and foreign body.
- Other plain radiographs: use a general quality/anatomy checklist until a reviewed specialty profile exists.

Models must declare supported anatomy, views, age groups, findings, output type, and known exclusions. Unsupported combinations should be marked `not assessed`, not inferred by a general report model.

## Annotation Contract

Every annotation should eventually contain:

- anatomy and laterality;
- finding label and finding identifier;
- coordinate type and coordinate space;
- original image, view, and series/image index;
- source model, model version, and inference trace;
- confidence or probability, including calibration status;
- transform metadata from model input to original image;
- linked report statement identifier;
- reviewer status and reviewer correction history;
- visibility state and reason for hiding;
- optional mask checksum or derived-image path.

An annotation may be an anatomical region, candidate pathology localization, device localization, measurement anchor, or manual reviewer mark. These types must remain visually distinguishable. Heatmaps or attention maps may be shown as model explanation aids, but must not be represented as precise lesion boundaries.

## Reading Room Behavior

The highest-value interaction is a bidirectional grounded review:

- Clicking a result card highlights its annotation and report sentence.
- Clicking an annotation opens the linked finding, confidence, source, and report sentence.
- Accepting or rejecting a finding applies to its linked annotation and draft statement only after explicit confirmation.
- Editing a report statement never silently changes the model output; it creates a human-reviewed version.
- Multiple views in one study stay grouped, and each annotation records which image produced the evidence.
- The reviewer can compare AI-visible, AI-hidden, and human-edited states without losing provenance.

## Reporting Direction

Draft reporting should use image data together with available clinical indication, procedure/view, prior comparison, and reviewed structured findings. The report generator should not invent missing clinical history.

The report pipeline should operate in two stages:

1. Evidence composition: normalize findings, anatomy, negation, uncertainty, locations, comparisons, and device status into structured entities.
2. Language realization: generate concise professional findings and a prioritized impression from those entities.

This separation is inspired by structural-entity approaches such as SEI and reduces dependence on stylistic text matching. Similar-case retrieval may later assist wording or differential review, but retrieved cases must be traceable and must never be copied as patient-specific truth.

## Evaluation Outcomes

Model quality and product usefulness should be evaluated separately.

Model-level outcomes:

- finding sensitivity, specificity, precision, and calibration under a documented protocol;
- localization hit rate and box-level sensitivity;
- IoU or Dice only where a suitable reference box or mask exists;
- laterality, anatomy, and view correctness;
- report factuality, clinical entity agreement, negation, uncertainty, and omission rate;
- subgroup and unsupported-case analysis.

Human-workflow outcomes:

- report completion time and edit distance from AI draft to final reviewed text;
- annotation acceptance, rejection, redraw, and hide rates;
- false-alert burden per examination;
- discrepancy rate before and after AI assistance;
- time to notice urgent candidate findings under a prospective protocol;
- reviewer confidence and alert-fatigue indicators.

Commercial claims such as turnaround-time reduction or high AUC are inspiration for measurable outcomes, not evidence that MedRay has achieved them. MedRay must generate its own versioned local results before showing any performance claim.

## Build Order

### Phase 1: Grounded Review MVP

- [x] Add annotation review status, reviewer note, and edit history.
- [x] Link annotation, result card, and report statement with stable identifiers.
- [x] Add click-to-focus behavior between image, findings, and report.
- [x] Support manual box creation, move/resize, hide, accept, reject, lock, restore, and delete for manual marks.
- [x] Persist source image ID/index, view, and series identity on each annotation.
- [x] Export AI-original and reviewed PNGs with a comparison/provenance JSON bundle.
- [ ] Add manual point/polygon tools and explicit redraw workflow.
- [ ] Add a full multi-image study navigator and per-view image switching.

Implementation status: the grounded bounding-box review workflow, stable evidence links, source-image identity contract, and separate original/reviewed exports are implemented. Full multi-image navigation and point/polygon authoring remain additive viewer work and do not block Anatomy Routing.

### Phase 2: Anatomy Routing

Status: foundation implemented. Every study is routed before inference, and the reviewer can override the detected profile when the available metadata is incomplete or incorrect.

- [x] Add explicit study/anatomy/view routing before model inference.
- [x] Define finding taxonomies and systematic reading requirements per anatomy profile.
- [x] Register separate model slots for chest, MSK/trauma, abdomen, spine, skull/facial, and general X-ray groups.
- [x] Reject unsupported model-study combinations visibly.
- [x] Add reviewer profile override and expose route provenance, confidence, model slot, and limitations in the Reading Room.
- [ ] Validate a versioned model for each enabled anatomy profile before presenting its outputs as assessed findings.

Implementation status: routing prioritizes DICOM body-part metadata, then study/series/protocol descriptions, filename, and user prompt. Unknown/general studies remain `routing_required` and do not enter model inference. Anatomy-specific model slots may inherit the common VLM, name a reviewed model, or remain disabled; configured but unvalidated models are labeled accordingly.

### Phase 3: Real Localization

Status: runtime-ready pilot foundation implemented; reviewed model weights and a local reference set are still required before real localization can be enabled.

- [x] Add a reviewed-local-artifact adapter for a narrow MSK fracture bounding-box indication.
- [x] Restrict the detector to MSK-routed studies and reject non-local or non-reviewed runtime configurations.
- [x] Validate, clamp, and reject detector coordinates in original-image pixel space.
- [x] Preserve detector model ID, weights identity, source image, confidence, original geometry, and transform notes.
- [x] Add reference boxes, IoU, localization hit rate, and mean best IoU to the Validation Workbench.
- [ ] Select and human-review a versioned `.pt` detector artifact with documented anatomy/view/age coverage, license, dataset provenance, and exclusions.
- [ ] Validate the locked artifact on a representative held-out local MSK dataset before enabling it for user studies.

The implementation deliberately does not bundle or auto-download community fracture weights. Setup and acceptance requirements are documented in `docs/MSK_LOCALIZATION_PILOT.md`.

### Phase 4: Grounded Draft Reporting

- Generate report statements from structured findings and linked regions.
- Add clinical indication and prior comparison only when supplied.
- Evaluate omissions, hallucinations, negation, laterality, and edit burden.
- Add Indonesian professional reporting as a language-realization layer over the same structured evidence.

### Phase 5: Workflow Study

- Measure time, edit burden, false alerts, and reviewer agreement.
- Compare unaided and AI-assisted review under a documented protocol.
- Keep triage disabled until urgent-finding performance and alert burden are prospectively validated.

## Reference Interpretation

- GE/Lunit and qXR demonstrate the practical value of abnormality scores, visual localization, written location descriptions, worklist flags, and workflow integration.
- The FDA qXR-Detect record demonstrates indication-bounded outputs, region-of-interest localization, box-level testing, subgroup analysis, controlled model updates, and release traceability.
- PadChest-GR demonstrates sentence-level grounded reporting and provides a useful data-shape reference for `region-to-text` and `text-to-region` evaluation.
- The all-radiograph prospective reporting study by Huang et al. demonstrates that draft reports can be evaluated on documentation efficiency and peer-reviewed quality for both chest and non-chest radiographs.
- Fracture-assistance studies demonstrate a path for extending annotation outcomes to multiple MSK body regions, while preserving radiologist confirmation.
- SEI contributes structured factual entities, clinical indication, and similar-case retrieval concepts.
- The example report/chat applications demonstrate modular VLM, report, chat, multilingual, and translation components, but are implementation references rather than clinical-validation evidence.

## Sources

- GE/Lunit Thoracic Care Suite: https://hospitalsmagazine.com/ge-healthcare-launches-new-ai-suite-to-detect-chest-x-ray-abnormalities/
- FDA qXR-Detect K251934: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID=K251934
- qXR product overview: https://www.qure.ai/product/qxr
- PadChest-GR, NEJM AI: https://ai.nejm.org/doi/full/10.1056/AIdbp2401120
- Efficiency and Quality of Generative AI-Assisted Radiograph Reporting: https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2834943
- Improving Radiographic Fracture Recognition Performance and Efficiency Using Artificial Intelligence: https://pubs.rsna.org/doi/10.1148/radiol.210937
- Chest X-ray report generation and chatbot example: https://github.com/ammarlodhi255/Chest-xray-report-generation-app-with-chatbot-end-to-end-implementation
- SEI: https://github.com/mk-runner/SEI
- Medical Reports Generator: https://github.com/lchaloupsky/Medical-Reports-Generator
