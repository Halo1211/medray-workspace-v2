# MedRay v2 Roadmap

MedRay v2 is a local-first research workspace for structured X-ray review. Its purpose is to produce traceable candidate findings, editable annotations, and draft reports while keeping a qualified reviewer accountable for every conclusion.

The roadmap follows four rules:

1. Auditability before stronger automation.
2. Anatomy and study routing before inference.
3. Technical readiness and local validation are separate states.
4. No model output becomes a verified clinical conclusion automatically.

## Current Foundation

The repository currently provides:

- PNG, JPEG, and DICOM study import with multi-image navigation;
- anatomy routing for chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, and general studies;
- editable AI and manual annotations with confidence, provenance, review status, revision history, and reviewed exports;
- result cards, differential candidates, grounded report drafting, and audit bundles;
- a Case Library with metadata, validation labels, search, deletion controls, and an integrated Validation Workbench;
- DICOM tag review and prototype de-identification with explicit risk acknowledgement;
- independent vision, chat, and report connections across local and hosted compatible providers;
- reviewed TorchXRayVision classifier recipes with guided installation and checksum verification;
- model discovery, resumable downloads, model cards, and activation gates;
- English and Indonesian application copy, plus dark and light themes.

See [AI Setup](AI_SETUP.md), [architecture](ARCHITECTURE.md), and [annotation direction](XRAY_ANNOTATION_DIRECTION.md) for implementation details.

## Priority 1: Real Validation Evidence

- Exercise reviewed artifacts on representative, de-identified local datasets.
- Record protocol, split, anatomy/view coverage, sample counts, metrics, calibration, false-alert burden, missed references, and known failure modes.
- Bind every evidence record to an exact model artifact and SHA-256 digest.
- Keep confidence presentation conservative until protocol-specific evidence exists.

## Priority 2: Annotation Quality

- Validate AI box, point, polygon, ellipse, and measurement workflows with real reviewers.
- Add inter-reviewer agreement and correction-effort summaries.
- Improve keyboard operation, focus behavior, and dense-study navigation.
- Preserve AI-original geometry separately from every human revision.

## Priority 3: Provider Reliability

- Add protocol fixtures for more OpenAI-compatible VLM implementations.
- Expand capability discovery beyond model-name lists where providers expose reliable metadata.
- Add clearer timeout, retry, context-size, and structured-output diagnostics.
- Test representative models in LM Studio, llama.cpp, vLLM, LocalAI, Jan, TGI, LiteLLM, and hosted providers.

## Priority 4: DICOM Safety

- Validate de-identification against a formally reviewed profile and real vendor variants.
- Add bounded decode budgets and pixel-redaction assistance.
- Test transfer syntaxes, codecs, nested sequences, burned-in text, and multi-frame studies.
- Keep DICOMweb disabled until authentication, authorization, transfer policy, and audit requirements are implemented.

## Priority 5: Distribution and Operations

- Test clean setup and upgrade paths on supported Windows, Linux, and macOS versions.
- Keep GitHub Actions green on Windows and Linux.
- Add signed releases and reproducible dependency records.
- Publish release notes that identify model, validation, and platform limitations.

## Release Gate

A public research release is ready only when:

- backend tests, frontend tests, type checking, and the production build pass;
- no credentials, patient data, model weights, runtime databases, or generated exports are tracked;
- visible AI output retains provenance, uncertainty, and human-review state;
- setup and recovery paths have been checked on the target operating system;
- the README, safety guidance, screenshots, and known limitations match the shipped behavior.

See [verification and operating limits](VERIFICATION.md) for the current test scope and remaining platform/model validation work.
