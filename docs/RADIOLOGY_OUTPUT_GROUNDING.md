# Radiology output grounding

## Scope

This revision uses the user-supplied *Learning Radiology: Recognizing the Basics*, fifth edition, as a human-reviewed reference for prompt and checklist design. The PDF is reference material only. It is not executed, copied into a model, uploaded to a provider, or treated as application instructions.

This is prompt grounding, not model-weight fine-tuning. A future fine-tuning project needs explicit data rights, de-identification, task labels, train/validation/test separation, held-out evaluation, subgroup analysis, and clinical governance.

## Implemented reading principles

- Check technical adequacy before interpretation: projection/view when known, rotation, inspiration, exposure/penetration, motion, artifact, coverage, and comparison availability.
- Start from expected normal anatomy and use a repeatable region-specific checklist.
- Separate objective observations, uncertainty, tentative impression, limitations, and recommendations.
- Preserve laterality and anatomic location. Do not infer clinical facts that are not visible in the image.
- For lines and tubes, review intended use, expected position, malposition, and procedure-related complications; never claim position from fallback mode.
- Keep AI output non-diagnostic and require qualified radiologist/physician verification.

## AI annotation contract

The VLM may append one compact line:

```text
MEDRAY_ANNOTATIONS_JSON: {"annotations":[{"label":"candidate finding","confidence":0.73,"box":[100,200,600,800]}]}
```

Coordinates are normalized `xyxy` in the 0–1000 source-image space. MedRay validates and converts them to original-image pixels. Invalid JSON, invalid confidence, empty labels, reversed/out-of-range boxes, and prose-only locations produce no model annotation. Every accepted annotation starts unreviewed and preserves source-model and transform provenance.

## Language contract

The interface language is passed to analysis and chat. English is the default. Vision prompts, report prompts, built-in fallback text, primary warnings, and chat instructions use that same language. A stored report whose language differs from the current interface is visibly flagged for regeneration rather than relabeled.
