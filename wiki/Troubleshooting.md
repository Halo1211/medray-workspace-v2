# Troubleshooting

## Backend is offline

1. Start the application with `start_medray_v2.bat` on Windows or `./start_medray_v2.sh` on Linux/macOS.
2. Check `http://127.0.0.1:8765/api/health` or the backend URL printed by the launcher.
3. If a previous process owns a port on Windows, run `stop_medray_v2.bat` and start again.
4. Check that Python 3.10+ and Node.js 20/22 LTS are installed.

## Setup fails

Run the setup script directly and read the first dependency error:

```powershell
.\scripts\setup_windows.ps1
```

```bash
./scripts/setup_unix.sh
```

Do not install optional model packages unless you need them. They can be large and may require a hardware-specific PyTorch build.

## Frontend cannot reach the backend

The frontend defaults to `http://127.0.0.1:8765/api` and can discover nearby backend ports. For manual development, set `VITE_API_BASE` to the actual API base before running Vite.

## Ollama model is not detected

Confirm that Ollama is running and that the exact model name appears in:

```bash
ollama list
```

For image review, use a vision-capable model. A text-only model cannot perform image review.

## DICOM export is blocked

Read the burned-in risk and private-tag warnings. Acknowledgement may be required before exporting a de-identified DICOM copy. Even after export, manually verify that identifiers are removed from metadata and pixels.

## Tests

From the repository root:

```bash
python -m pytest backend/tests
cd frontend
npm ci
npm test -- --run
npm run build
```

The main repository's `docs/TROUBLESHOOTING.md` contains the longer operating note.
