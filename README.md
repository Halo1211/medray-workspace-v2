# MedRay v2

<p align="center">
  <img src="frontend/public/medray-v2-logo.png" width="190" alt="MedRay v2 logo">
</p>

<p align="center"><strong>A local-first workspace for structured X-ray review, AI-assisted reporting, annotations, and model evaluation.</strong></p>

<p align="center">
  <img alt="Status: alpha" src="https://img.shields.io/badge/status-alpha-f59e0b">
  <img alt="Version: 0.2.0-alpha.1" src="https://img.shields.io/badge/version-0.2.0--alpha.1-2dd4bf">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
  <img alt="React 19" src="https://img.shields.io/badge/React-19-149eca">
  <img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688">
  <img alt="Data: local-first" src="https://img.shields.io/badge/data-local--first-2dd4bf">
</p>

> [!CAUTION]
> MedRay v2 is research, education, and prototyping software. It is not a medical device, diagnostic system, PACS, RIS, or emergency-triage tool. AI output may be incomplete, incorrect, or misleading and must be independently reviewed by a qualified clinician. Never use it for autonomous clinical decisions or real patient care without the required institutional approvals and validation.

## Overview

MedRay v2 is a local application for reviewing plain radiographs and experimenting with traceable AI-assisted workflows. It combines an X-ray viewer, structured reading templates, anatomy routing, editable annotations, report drafting, case management, model discovery, and validation utilities in one workspace.

The default **Built-in Demo** works without downloading a clinical model. Optional local runtimes can be connected when you want to test a model on your own machine. Data is stored locally by default; cloud access is disabled unless explicitly configured and permitted by the runtime safety checks.

The interface starts in English for new users and Indonesian is available throughout the workspace, including the guided AI Setup and annotation-review flows.

## Screenshot

![MedRay v2 dashboard](docs/screenshots/medray-dashboard.png)

## What is implemented

| Area | Current capability |
| --- | --- |
| Reading Room | Import PNG, JPEG, and multi-frame DICOM studies; calibrated window/level presets, frame navigation, inversion, rotation/flips, zoom, metadata, and overlays |
| Anatomy routing | Chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, and general/unknown profiles; DICOM metadata, study description, filename, and reviewer override are supported inputs |
| Structured review | Image-quality estimate, anatomy-specific checklists, laterality/view warnings, findings, differentials, result cards, provenance, and human-review state |
| Annotations | Bounding boxes, points, polygons, ellipse ROIs, and calibrated lengths; frame-aware provenance, lock/show controls, undo/redo, editable geometry, links, revision history, and reviewed PNG/JSON packages |
| Reporting | English or Indonesian draft reports with Markdown, PDF, JSON, annotated PNG, and audit-bundle export |
| Case Library | Local SQLite-backed case storage, title editing, multiple images per study, search, configurable database folder, explicit deletion controls, and an integrated Validation tab |
| DICOM safety | Local tag inspection, private/burned-in risk warnings, prototype de-identification, readback verification, and de-identified metadata/DICOM export |
| Model Finder | Search and inspect Hugging Face, GitHub, and installed Ollama models; resumable segmented downloads with adaptive connection count and optional SHA-256 verification; local imports and model cards |
| Validation Workbench | Integrated into Case Library with curated fixtures, reviewer labels, dataset/protocol metadata, agreement metrics, missed-reference review, and validation-report export |
| Runtime connections | Independent vision, chat, and report assignments across Ollama, LM Studio, Jan, llama.cpp, vLLM, LocalAI, TGI, LiteLLM, OpenAI, OpenRouter, Groq, Together AI, and custom compatible endpoints |

## Typical workflow

```mermaid
flowchart LR
    A[Import PNG/JPEG/DICOM] --> B[Quality and anatomy checks]
    B --> C[Systematic review]
    C --> D[Optional model tools]
    D --> E[Editable findings and annotations]
    E --> F[Human verification]
    F --> G[Draft report, audit, and export]
```

MedRay keeps the reviewer in control. A fallback visual guide is explicitly labeled as a general review region, not as pathology localization. Model-generated boxes, labels, probabilities, and text remain candidate research outputs until they have appropriate local evidence and human review.

## Architecture

```mermaid
flowchart TB
    UI[React + TypeScript + Vite] --> API[FastAPI local API]
    API --> DB[(SQLite runtime database)]
    API --> Files[Local cases, models, cache, and exports]
    API --> Pipeline[Analysis and provenance pipeline]
    Pipeline --> Demo[Built-in deterministic tools]
    Pipeline --> Ollama[Ollama]
    Pipeline --> Compatible[OpenAI-compatible API]
    Pipeline --> Vision[Optional local vision adapters]
```

- **Frontend:** React 19, TypeScript, Vite, Vitest, and Lucide icons.
- **Backend:** Python, FastAPI, Pydantic Settings, Pillow, pydicom, ReportLab, and pytest.
- **Storage:** local filesystem plus SQLite; runtime data is intentionally excluded from Git.
- **Model boundary:** optional model packages and weights are installed separately. A model is not enabled for analysis merely because it was downloaded; local model-card review and validation gates still apply.

## Model and runtime support

| Runtime or adapter | Supported use | Status and boundary |
| --- | --- | --- |
| Built-in Demo | Explore the complete UI and deterministic review flow | Available by default; not a clinical AI model |
| Ollama | Local chat, image review with a VLM, and selected report drafting paths | Available when Ollama and a compatible model are installed; outputs are unvalidated candidate observations |
| OpenAI-compatible APIs | Image review with compatible VLMs, chat, and English or Indonesian report drafting | Independent per-task testing, endpoint-scoped keys, HTTPS for remote providers, and explicit cloud opt-in |
| TorchXRayVision classifier recipes | All-dataset, NIH, CheXpert, and RSNA chest X-ray classifiers | Guided CPU setup, SHA-256-verified official weights, synthetic model-load test, and explicit activation; research-only |
| MedRAX-inspired tool interface | Composable tool contracts and provenance-oriented orchestration boundary | The repository does not bundle the external MedRAX model stack or weights |
| LocateAnything parser | Parse bounded box/point/`none` outputs into MedRay annotation objects | Research parser only; model download, remote-code execution, and automatic inference are intentionally not enabled |

## AI Setup

Start with **AI Setup** and follow the numbered flow: **1 Choose a goal → 2 Connect or find → 3 Technical test → 4 Use model**. Vision, chat, and report drafting can each use a different tested provider. **X-ray Classifiers** provides a separate guided path for specialist pathology classifiers. Optional discovery, download, and preference controls stay under **Show advanced tools**.

Read the [AI Setup and provider guide](docs/AI_SETUP.md) and [verification and limitations](docs/VERIFICATION.md).

## Quick start

### Requirements

- Python 3.10 or newer (Python 3.12 is tested in this workspace).
- Node.js 22.12+ or 24 LTS. Node.js 20/21 are not supported by this setup.
- npm.
- Windows 10/11, Linux, or macOS.
- Optional: any supported local or hosted compatible provider; a suitable PyTorch installation for embedded classifiers.

### Windows

Double-click **setup_medray_v2.bat**, then **start_medray_v2.bat**. The launcher installs core components when needed, waits for backend and frontend readiness, opens the browser and shows status. Choose **AI Setup** in the app. Python and Node must already be installed; missing prerequisites get guided error messages.

Default frontend: `http://127.0.0.1:5173`. Backend health: `http://127.0.0.1:8765/api/health`. Busy ports are handled by selecting available local ports. Starting twice reuses the running instance. Stop with Ctrl+C or **stop_medray_v2.bat**; the supervisor stops only its own services.

### Linux or macOS

```bash
chmod +x start_medray_v2.sh
./start_medray_v2.sh
```

The browser opens when both services are ready. Stop with `Ctrl+C`.

## Optional model dependencies

The core app needs no AI weights. Use **AI Setup → X-ray Classifiers** for reviewed specialist classifier recipes and **Local AI** for general models served by external applications. GPU and unsupported environments use official guided setup. The following broad optional-stack commands are for advanced development and do not add generic Hugging Face inference support:

```powershell
.\scripts\setup_windows.ps1 -WithOptional
```

```bash
MEDRAY_INSTALL_OPTIONAL=1 ./scripts/setup_unix.sh
```

For local Ollama chat, install and start Ollama separately, then pull a model available on your machine. For example:

```bash
ollama pull qwen2.5:3b
```

For local image review, use **AI Setup → Local AI**, select a detected vision model, test it, then click **Use model**. Model names and hardware requirements vary by Ollama version and model package; the example is not a clinical recommendation.

## Manual development setup

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

cd frontend
npm ci
npm run dev
```

In a second terminal, from the repository root with the virtual environment active:

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

cd frontend
npm ci
npm run dev
```

In a second terminal, from the repository root with the virtual environment active:

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765
```

The frontend falls back to `http://127.0.0.1:8765/api` when `VITE_API_BASE` is not set. If the backend uses another port, set `VITE_API_BASE` before starting Vite.

## Configuration

Copy `.env.example` to `.env` only when custom settings are needed. Never commit `.env`, API keys, tokens, patient identifiers, DICOM files, or model weights.

| Variable | Purpose | Default |
| --- | --- | --- |
| `MEDRAY_HOST` | Backend bind address; keep loopback unless authentication and hardening are added | `127.0.0.1` |
| `MEDRAY_PORT` | Preferred backend port | `8765` |
| `MEDRAY_DATA_DIR` | Root folder for cases, models, cache, exports, and the default SQLite database | `./data` |
| `MEDRAY_DEFAULT_BACKEND` | Initial primary runtime | `demo` |
| `MEDRAY_OLLAMA_BASE_URL` | Ollama endpoint | `http://127.0.0.1:11434` |
| `MEDRAY_OPENAI_BASE_URL` | OpenAI-compatible endpoint | `http://127.0.0.1:8000/v1` |
| `MEDRAY_OPENAI_API_KEY` | Optional compatible API credential | empty |
| `VITE_API_BASE` | Frontend API base for manual Vite development | `http://127.0.0.1:8765/api` |

The UI can also move the SQLite database to a user-selected folder. It refuses to overwrite an existing database and requires a restart to activate a newly selected path.

## Testing and build

Run the backend tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Run the frontend tests and production build:

```bash
cd frontend
npm test -- --run
npm run build
```

The current verified baseline in this workspace is:

- Backend: **476 passed, 1 skipped**.
- Frontend: **146 passed**.
- Production frontend build: **passed**.

See [verification and operating limits](docs/VERIFICATION.md) for test coverage, image handling, supported DICOM frames, and external-runtime limitations.

Case edits use server revisions to detect concurrent updates. The Reading Room queues annotation, finding-review, and case-detail saves before export. If a save fails, the draft stays visible and saving/exporting pause until the reviewer explicitly loads the latest saved case. Chat and image additions update the latest case inside short SQLite transactions. Older API clients must send `If-Match` with the case revision to receive the same stale-edit protection.

## Data, privacy, and security

Runtime data is excluded from Git, including:

- uploaded cases, images, and DICOM files;
- SQLite databases and generated reports/exports;
- downloaded model files and local model registries;
- caches, virtual environments, build output, logs, and credentials.

Use synthetic or properly de-identified images for development and issue reports. The DICOM helpers are a local prototype, not a certification of DICOM PS3.15 compliance. They do not remove identifying information burned into pixels, and every export must be reviewed before sharing.

By default the server is loopback-only. Do not expose it to an untrusted network. Read [SECURITY.md](SECURITY.md), [DISCLAIMER.md](DISCLAIMER.md), and [the safety guide](docs/SAFETY.md) before connecting external services or real clinical data.

## Repository layout

```text
backend/app/             FastAPI app, analysis pipeline, storage, adapters, and schemas
backend/tests/           Backend unit and API tests
frontend/src/            React UI, API client, types, annotation geometry, and styles
frontend/public/         Logo and static assets
data/                    Empty runtime directories retained with .gitkeep
docs/                    Architecture, safety, model, validation, screenshots, and roadmap documentation
wiki/                    Ready-to-publish GitHub Wiki pages
scripts/                 Cross-platform setup and Windows process helpers
.github/                 CI, Dependabot, issue, and pull-request configuration
CHANGELOG.md             Release history and current alpha status
CODE_OF_CONDUCT.md       Community participation guidelines
```

## Documentation

- [Documentation index](docs/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Verification and operating limits](docs/VERIFICATION.md)
- [AI Setup and providers](docs/AI_SETUP.md)
- [Safety and operating limits](docs/SAFETY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Model Finder](docs/MODEL_FINDER.md)
- [Validation Workbench](docs/VALIDATION_WORKBENCH.md)
- [DICOM and annotation direction](docs/XRAY_ANNOTATION_DIRECTION.md)
- [First real vision model](docs/FIRST_REAL_VISION_MODEL.md)
- [MSK localization pilot](docs/MSK_LOCALIZATION_PILOT.md)
- [LocateAnything evaluation](docs/LOCATE_ANYTHING_EVALUATION.md)
- [MedRAX adapter boundary](docs/MEDRAX_ADAPTER.md)
- [Roadmap](docs/ROADMAP.md)
- [Wiki source and publishing guide](wiki/README.md)

## Project status and known limits

MedRay v2 is an **alpha research prototype**. The review UI, case library, reporting/export paths, model discovery, runtime settings, provenance structures, anatomy routing, and validation workbench are implemented and covered by automated tests.

The following boundaries are intentional:

- the Built-in Demo is deterministic scaffolding, not a trained clinical model;
- external model outputs are not automatically treated as diagnoses;
- generic or unknown anatomy is not sent to an anatomy-specific model until confirmed;
- downloaded or imported models stay inactive until the local model-card gate is satisfied;
- segmentation and general-purpose grounding are not enabled as clinically validated capabilities;
- DICOMweb is not implemented; DICOM handling is local file ingestion and export;
- no production authentication, authorization, multi-tenant isolation, or internet-facing hardening is provided.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a pull request. Contributions should include focused tests and must not include patient data, credentials, model weights, or generated runtime files.

## References and credits

MedRay v2 is an original local-first implementation. Its workflow and integration boundaries were informed by:

- [MedRAX](https://github.com/bowang-lab/MedRAX) — a tool-oriented medical reasoning agent for chest X-ray workflows.
- [TorchXRayVision](https://github.com/mlmed/torchxrayvision) — open-source chest X-ray datasets and pretrained model interfaces.
- [FastAPI documentation](https://fastapi.tiangolo.com/) — backend API framework reference.
- [Vite documentation](https://vite.dev/guide/) — frontend development and build reference.
- [MedRay Workspace v1](https://github.com/Halo1211/medray-workspace) — archived predecessor and conceptual reference.
- [Odysseus](https://github.com/pewdiepie-archdaemon/odysseus) — project reference.

See [docs/CREDITS.md](docs/CREDITS.md) for the project-level attribution note. MedRay v2's logo is a new geometric design and does not reuse the v1 artwork.

## License

MedRay v2 is released under the [MIT License](LICENSE). The license applies to the project source code and documentation. Medical datasets, model weights, third-party libraries, and external services may have separate terms; review their licenses before redistribution or deployment.
