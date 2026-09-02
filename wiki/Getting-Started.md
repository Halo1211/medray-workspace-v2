# Getting Started

## Requirements

- Python 3.10 or newer.
- Node.js 20 LTS or 22 LTS and npm.
- Windows 10/11, Linux, or macOS.
- Optional: Ollama for local chat or vision-language models.

## Windows launcher

From the repository root, run:

```powershell
.\start_medray_v2.bat
```

The launcher creates the local Python environment, installs core dependencies, starts the backend and frontend, and prints the URLs. Open the frontend at `http://127.0.0.1:5173` unless another free port is reported.

Stop the services with `Ctrl+C`. If an older process owns a port, run:

```powershell
.\stop_medray_v2.bat
```

## Linux or macOS launcher

```bash
chmod +x start_medray_v2.sh
./start_medray_v2.sh
```

Open `http://127.0.0.1:5173` and stop the services with `Ctrl+C`.

## Backend API

The backend normally serves:

- Health check: `http://127.0.0.1:8765/api/health`
- Interactive API docs: `http://127.0.0.1:8765/docs`

The launcher may choose another backend port if the preferred port is busy; use the URL it prints.

## First run

1. Open **User Guide** to understand the four-step workflow.
2. Go to **Reading Room** and upload a synthetic or properly de-identified PNG, JPEG, or DICOM image.
3. Confirm the active image and anatomy route.
4. Run the Built-in Demo analysis.
5. Review findings, annotations, warnings, and provenance before drafting or exporting a report.

The Built-in Demo is deterministic scaffolding. It does not provide clinical interpretation.
