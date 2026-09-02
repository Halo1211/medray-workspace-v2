# LocateAnything Evaluation Track

Status: R1 offline parser complete; research candidate only, not an active MedRay model and not a clinically validated X-ray localizer.

## Decision summary

`nvidia/LocateAnything-3B` is worth evaluating as an experimental open-vocabulary grounding engine because it can return bounding boxes or points from a natural-language query and its normalized coordinate format maps cleanly to the MedRay annotation contract. It must not replace the current narrow MSK localization gate or be enabled from a public checkpoint without local X-ray validation.

The public evidence does not disclose medical-image or X-ray training/evaluation. Its reported benchmarks cover general/dense object detection, GUI grounding, documents/OCR, referring expressions, and pointing. MedRay therefore treats every radiographic localization produced by the unadapted model as an unvalidated research hypothesis.

## What is technically useful

- One model supports category detection, phrase grounding, dense detection, text localization, and point localization.
- Parallel Box Decoding predicts a complete box as one unit; Hybrid Mode uses fast decoding and falls back to autoregressive decoding when an output is spatially or structurally uncertain.
- Released box output is `<ref>label</ref><box><x1><y1><x2><y2></box>` with integer coordinates in `[0, 1000]`; point output is `<box><x><y></box>`. This can be normalized into the existing `bbox`, `grounding_box`, and `point` annotation types.
- The worker loads the model once and exposes task-specific methods, making a separately supervised local inference service practical.

## Constraints that block direct activation

1. **No disclosed X-ray benchmark.** The model card and project results do not include radiographs, fracture localization, chest findings, or other medical-image benchmarks.
2. **License boundary.** Code is Apache-2.0, but the released model weights use the NVIDIA License and are limited to non-commercial research/evaluation. Redistribution must preserve the license and notices.
3. **Remote-code boundary.** The official Transformers path uses `trust_remote_code=True`. MedRay must pin reviewed code and artifact hashes, install it in a separate environment, and prohibit network access during case inference.
4. **Hardware uncertainty.** Published throughput uses an H100. An official A100 4K batch-four probe reports about 11.71 GB reserved memory with `la_flash` and 35.12 GB with stock SDPA. This is not evidence that the model fits MedRay's low-VRAM target or typical single-radiograph workflow.
5. **Output is not calibrated pathology confidence.** Coordinate generation and phrase matching do not provide clinical probability, urgency, or diagnostic confirmation.
6. **Public weights are not visual-prompt ready.** The released checkpoint accepts text queries; official visual-prompt-capable weights are still described as future work.

## Proposed adapter boundary

Do not overload the current Ultralytics `grounding_model` path until the registry can represent a multi-file Transformers artifact and its reviewed code snapshot. Add a separate experimental adapter only after R0-R2 below.

Adapter input:

```text
image identity + local image path + fixed query set + inference mode
```

Adapter output:

```text
annotation type + normalized geometry + query/label + model/artifact identity
+ decoding mode + raw-output hash + parser warnings + source image identity
```

Required parser behavior:

- reject coordinates outside `[0, 1000]`, malformed token structures, reversed/zero-area boxes, and non-finite values;
- clamp only after retaining the original output in the trace;
- cap queries, boxes per query, image dimensions, pixels, runtime, and output tokens;
- deduplicate strongly overlapping boxes per query without merging different clinical concepts;
- never translate a grounding score into clinical confidence;
- preserve `model_generated` versus `reviewer_created` provenance.

## Evaluation phases

### R0 - License, artifact, and execution review

- Record the NVIDIA weight license, Qwen component license, code commit, model revision, file manifest, and SHA-256 hashes.
- Review all remote model code before vendoring or pinning it in an isolated environment.
- Confirm the intended deployment remains non-commercial research/evaluation.
- Produce a measured hardware profile on the actual MedRay machine; do not infer it from H100/A100 results.

Exit: reviewed immutable artifact bundle and a documented isolated runner; still unavailable in Runtime Settings.

### R1 - Offline parser and contract test

Implementation status: complete. `backend/app/vision/locate_anything_parser.py` parses only the documented box, point, and `none` structures and can convert valid results into existing MedRay `Annotation` objects. `backend/tests/test_locate_anything_parser.py` covers valid conversion and adversarial failure paths. No model package, weights, remote code, runtime slot, or network inference was added.

- Implement a pure parser for official box, point, and `none` outputs.
- Add adversarial tests for malformed tags, excessive boxes, reversed coordinates, duplicate labels, and partial output.
- Convert valid coordinates to original-image pixels and MedRay annotation schema without invoking the model.

Exit: parser tests pass and no public checkpoint is exposed to users.

### R2 - Generic-image smoke evaluation

- Run the pinned worker offline on non-medical public fixtures first.
- Compare `fast`, `slow`, and `hybrid` for format validity, latency, peak VRAM, and box agreement.
- Verify every annotation, model trace, audit record, PNG export, and source image identity survives the existing pipeline.

Exit: technical integration is reproducible; output remains labeled `experimental_unvalidated`.

### R3 - Radiograph feasibility study

- Define a narrow anatomy and question set before looking at results, for example reviewed MSK fracture reference boxes only.
- Use held-out, rights-cleared, de-identified radiographs with independent human reference boxes.
- Measure per-view and per-subgroup IoU/F1, hit rate, false boxes per image, missed references, parser failure, abstention/`none`, latency, and VRAM.
- Compare against the existing narrow detector baseline and a no-model/manual-review baseline.
- Record prompt sensitivity by testing locked synonymous prompts; do not let free-form prompt selection hide failures.

Exit: a structured Validation Workbench evidence report bound to exact model, code, prompt set, dataset split, and artifact hashes.

### R4 - Optional controlled pilot

- Add a separate `experimental grounding` runtime slot only if R3 meets a pre-registered threshold.
- Limit queries to a reviewed vocabulary for the validated anatomy/protocol.
- Display query, decoding mode, model revision, protocol scope, validation status, and human-review state beside every result.
- Keep report promotion rules unchanged: model output alone cannot become a confirmed diagnosis.

Exit: pilot can be disabled independently and cannot silently fall back into a clinical-looking result.

## Initial go/no-go criteria

R1 parser result: **complete**. The implementation is character-, image-, item-, and label-bounded; rejects malformed, unbalanced, reversed, out-of-range, non-finite, and tampered geometry; removes same-label near-duplicates; hashes raw output; and assigns no fabricated clinical confidence.

Go to R2 generic-image execution: **not yet**. R0 still needs an immutable reviewed code/artifact manifest and measured execution environment before any model code is installed or run.

Go to user-facing integration now: **no**. The current release has no disclosed radiographic validation, uses non-commercial model terms, requires reviewed remote code, and has uncertain local hardware fit.

Replace the narrow MSK detector milestone: **no**. LocateAnything is a complementary research track; the narrow reviewed artifact remains the safer first end-to-end localization milestone.

## Sources reviewed

- Project page: https://research.nvidia.com/labs/lpr/locate-anything/
- Paper: https://arxiv.org/abs/2605.27365
- Code and worker: https://github.com/NVlabs/Eagle/tree/main/Embodied
- Model card: https://huggingface.co/nvidia/LocateAnything-3B
- Weight license: https://github.com/NVlabs/Eagle/blob/main/Embodied/LICENSE_MODEL
