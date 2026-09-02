# MSK Fracture Localization Pilot

MedRay Phase 3 provides a runtime adapter for a narrow, local MSK fracture detector. It does not bundle model weights and does not activate a community model automatically. A detector becomes runnable only after its local artifact and model card pass human review.

## Supported Contract

- Runtime slot: `grounding_model`
- Runtime value: a reviewed `local:` artifact ID
- Artifact: an Ultralytics-compatible `.pt` object detector
- Anatomy gate: `msk` only
- Imported classes: labels containing `fracture`, `fractured`, or `break`
- Output: `grounding_box` coordinates in original-image pixels
- Default confidence threshold: `0.25`, configurable from `0.05` to `0.95`
- Maximum displayed candidates: 20 per image

The adapter rejects invalid, non-finite, zero-area, and out-of-canvas geometry. Out-of-canvas edges are clamped to the original image. Ultralytics detection results expose `xyxy` pixel boxes, class IDs, and confidence values; MedRay converts those to `x`, `y`, `width`, and `height` while preserving model and source-image provenance.

## Activation

1. Place a top-level model artifact folder under `data/models` with its `.pt` weights, README/model card, and license.
2. Import the folder through Model Finder.
3. Complete `intended_use`, `task`, `license`, `dataset_provenance`, and `limitations`.
4. Add structured local validation evidence: protocol/dataset/split, counts, metric and failure summaries, coverage, reviewer/date, validation report reference, and exact `.pt` weights filename. MedRay computes and verifies its SHA-256 when the card is saved.
5. Confirm that the task is object detection/localization and mark the card human reviewed. Human review permits selection; incomplete structured evidence remains visibly conservative/unvalidated.
6. Install the optional runtime dependencies from `backend/requirements-optional.txt`.
7. Set the resulting `local:` artifact ID as `grounding_model` in Runtime Settings.
8. Keep anatomy routing on Auto or explicitly select MSK/trauma for the study.

## Validation Protocol

Reference annotations should use `grounding_box` with original-image `x`, `y`, `width`, and `height`. The Validation Workbench reports:

- best IoU between each reference box and same-label candidate boxes;
- localization hit at the configured minimum IoU;
- box hit rate across spatially evaluated labels;
- mean best IoU;
- missing, skipped, and failed cases.

The default minimum IoU is `0.30` because this is an early review-assistance pilot, not a boundary-segmentation claim. The threshold must be declared in the protocol and should not be changed after looking at held-out results.

## Required Model Review

Before activation, document supported bones/joints, projections, pediatric/adult coverage, detector classes, training and external datasets, annotation policy, exclusions, license, threshold selection, calibration limitations, and known failure modes. A model trained for one region must not be represented as supporting all MSK radiographs.

Boxes remain unconfirmed candidate review cues. They are not fracture confirmation, exact fracture boundaries, clinical triage, or a substitute for radiologist/physician interpretation.

## Technical References

- Ultralytics object-detection results and `xyxy` coordinates: https://docs.ultralytics.com/tasks/detect/
- Hugging Face object-detection post-processing to target image size: https://huggingface.co/docs/transformers/tasks/object_detection
