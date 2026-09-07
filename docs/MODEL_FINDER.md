# Model Finder

Model Finder is an advanced AI Setup section for locating candidate artifacts. It does not activate search results or claim that a repository can run in MedRay.

## Sources

- Combined Hugging Face, GitHub, and installed Ollama search.
- Optional, locally stored Hugging Face and GitHub credentials.
- Local file or folder import.
- Direct HTTP/HTTPS artifact download.

## Search result metadata

Results may include task, license, size, quantization, estimated VRAM/RAM, source, local path, maturity score, fit summary, safety notes, gated/private status, and repository files. Missing metadata remains unknown rather than being guessed.

Fit and maturity scores are triage heuristics. They do not establish runtime compatibility, calibration, or clinical performance.

## Runtime boundary

- GGUF and similar artifacts must be loaded in a runtime that supports their architecture.
- OpenAI-compatible servers are tested separately for vision, chat, or report drafting.
- Raw classifier, detector, or segmentation weights require a specific reviewed adapter.
- Downloading or importing an artifact never activates it.
- Repository scripts and remote code are never executed automatically.

## Download manager

Each job records source, target, downloaded bytes, total bytes, progress, transfer mode, connection count, timestamps, error state, and optional checksum status. Supported actions are pause, resume, cancel, retry, and remove from the queue.

The downloader probes range support, creates bounded byte segments, validates each response, assembles segments deterministically, and verifies the optional SHA-256 digest before promoting the final file. It falls back to a single stream when range requests are unsupported.

## Authentication

Source sign-in is optional and revocable. Tokens are masked, stored locally, and excluded from reports, validation exports, logs, screenshots, and runtime responses. Hugging Face sign-in can enable gated/private metadata only when the model owner has granted access.

Source authentication does not grant cloud-inference permission. Hosted inference requires a separate endpoint-scoped key and explicit data-egress consent.

## Safety rules

- Prefer local execution where practical.
- Show source failures without inventing fallback results.
- Keep demo, fallback, tested model output, and human-reviewed evidence visually distinct.
- Require model-card, license, technical, and local validation review before research use.
- Never present a model probability as a diagnosis.
