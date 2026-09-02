# Model Finder v2

Model Finder sekarang berfungsi sebagai Runtime Setup Wizard. Tujuannya bukan katalog riset, tetapi membantu pengguna memilih kandidat model untuk slot Runtime Settings, lalu download/import artifact tanpa mengaktifkannya otomatis.

Sumber:

- All-source search: Hugging Face, GitHub, dan Ollama installed dalam satu tombol.
- Hugging Face model search/download, dengan login token opsional untuk gated/private/rate-limit cases.
- GitHub repository search dan metadata scan.
- Ollama install/service detection dan model list.
- Local folder import.
- Manual URL download `http/https`.

Metadata:

- task type
- license
- size
- quantization
- VRAM/RAM estimate
- source
- local path
- status

Download queue menyimpan status, persen, speed, ETA, error, retry/cancel-ready job id.

## Current Implementation Status

- Model Finder has a guided UI with four visible steps: backend/login status, hardware check, runtime task selection, and search/download.
- `/api/models/search` supports `source=all`, Hugging Face, GitHub, and Ollama.
- `/api/models/hardware-recommendations` detects local CPU/RAM and NVIDIA VRAM when available, then recommends a model path for each Runtime Settings task slot: classifier, vision-language, segmentation, grounding, report, and chat.
- If an external source returns no usable result or fails, the UI leaves the result area empty and shows the source error/empty state.
- If one source fails during `source=all`, the other sources still render and the failure is shown as a small note.
- Runtime Settings now opens with a safe default config and shows loading/status messages instead of staying stuck on `Loading...`.

## Fit score

Hasil search diperkaya dengan:

- `maturity_score` 0-100
- `fit_summary`
- `safety_notes`

Skor ini heuristik untuk triase awal, bukan validasi kualitas model. Model tetap perlu model card, license review, local validation, dan calibration warning sebelum dipakai sebagai inference nyata.

## Guardrail

- Local-first default.
- Cloud endpoint hanya jika `allow_cloud` di Runtime Settings aktif eksplisit.
- Output demo/fallback harus tetap terlihat berbeda dari inference model nyata.
- Probabilitas penyakit tidak boleh ditampilkan seperti diagnosis tanpa validasi dan kalibrasi.

## Implemented - Download Manager UX

Goal: make model downloads understandable and controllable so users do not wonder whether a download started, froze, or failed.

Implemented UI/backend:

- Download queue panel with one row per job.
- Progress bar per download.
- Status chips:
  - `queued`
  - `downloading`
  - `paused`
  - `completed`
  - `failed`
  - `cancelled`
- Controls:
  - start;
  - pause;
  - resume;
  - cancel;
  - retry;
  - clear completed.
- Show model/source name, URL/domain, target path, downloaded bytes, total bytes, percent, speed, ETA, and error text.
- Poll `/api/models/downloads` while downloads are active.
- Warn before queueing manual downloads.
- Hugging Face detail view can prepare direct file downloads for model artifacts such as `.safetensors`, `.gguf`, `.bin`, `.onnx`, and config/tokenizer files.
- Preserve partial downloads safely so resume can continue when supported.
- Never auto-enable a downloaded model in analysis; require model card/review first.
- Download jobs include explicit `paused`, `cancelled`, `retryable`, `bytes_read`, `total_bytes`, `created_at`, `updated_at`, and `completed_at`.
- Endpoints:
  - `POST /api/models/downloads/{job_id}/pause`
  - `POST /api/models/downloads/{job_id}/resume`
  - `POST /api/models/downloads/{job_id}/cancel`
  - `POST /api/models/downloads/{job_id}/retry`
  - `DELETE /api/models/downloads/{job_id}`
- Uses range requests for resumable downloads when the server provides `Accept-Ranges`.
- Stores partial files with a `.part` suffix until complete.
- Cleanly handles network failure without deleting partial progress unless the user cancels/cleans up.

## Implemented - Hugging Face Login

Optional Hugging Face login is acceptable if it stays explicit, local, and revocable.

Implemented behavior:

- Add token entry in Runtime Settings or Model Finder.
- Token is opt-in and hidden after save.
- Token is stored locally only.
- Token must never be exported in audit bundles, reports, validation exports, logs, or screenshots.
- Show login status without displaying the token.
- Add logout/clear-token action.
- Use token for gated/private Hugging Face metadata and downloads.
- If token is missing for gated content, external provider errors remain visible and the MedRay shortlist fallback stays available.
- Endpoints:

- `GET /api/runtime/huggingface`
- `POST /api/runtime/huggingface-token`
- `DELETE /api/runtime/huggingface-token`

Safety notes:

- Login does not make cloud inference allowed.
- Downloading a gated model does not make it clinically validated.
- A model still needs model card, license review, runtime trace, and local validation before being used as a real inference adapter.
