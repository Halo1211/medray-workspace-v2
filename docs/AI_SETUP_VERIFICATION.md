# AI Setup Verification

## Current Revision

Verified on September 7, 2026. No patient data or unreviewed remote code was used.

### Automated Checks

- Backend: 238 passed and 1 skipped on Python 3.12 using the project virtual environment.
- Frontend: 42 passed across 8 Vitest files.
- TypeScript compilation and the Vite production build passed.
- `npm audit` reported zero known vulnerabilities.
- `git diff --check` passed; Windows line-ending notices are informational.

Coverage includes provider discovery, task-scoped activation, safe endpoint handling, credential storage boundaries, interrupted downloads, classifier recipe selection, checksum validation, annotation geometry, DICOM handling, report generation, database relocation, and launcher behavior.

### Browser Checks

- The light theme renders readable selected cards, provider summaries, controls, and the MedRay logo.
- Reading Room can open an existing case and start a new case without a page refresh.
- Case Library keeps validation above an internally scrollable case registry.
- Annotation controls expose AI confidence, source and review filters, batch review, manual geometry tools, revision history, and reviewed exports.
- System Check uses provider-neutral actions instead of assuming Ollama.

### Runtime and Classifier Checks

- Vision, chat, and report tasks can retain independent provider assignments.
- Local presets cover Ollama, LM Studio, llama.cpp, vLLM, LocalAI, Jan, Hugging Face TGI, and LiteLLM.
- Hosted presets cover OpenAI, OpenRouter, Groq, Together AI, and custom HTTPS-compatible endpoints.
- Provider keys are stored outside cases and runtime snapshots and are scoped by endpoint.
- TorchXRayVision exposes reviewed All-Datasets, NIH, CheXpert, and RSNA recipes with pinned official URLs and SHA-256 checksums.
- Classifier activation still requires a successful synthetic load and inference test.

## Boundaries

- Technical readiness is not clinical validation.
- Real end-to-end inference has not been exercised against every provider/model combination. The in-app task test is mandatory before activation.
- Arbitrary Hugging Face repositories, raw model weights, and repository scripts are not universal executable runtimes and are never run automatically.
- GPU/CUDA setup, clean installation on every supported operating system, and real vendor DICOM coverage require additional validation.
- The DICOM de-identification workflow is a prototype and is not a claim of DICOM PS3.15 certification.
- All AI findings, annotations, confidence values, and reports remain research candidates until reviewed by a qualified clinician.
