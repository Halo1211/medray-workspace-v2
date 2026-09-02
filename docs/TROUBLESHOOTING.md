# Troubleshooting

## The backend is offline

- Start the application with `start_medray_v2.bat` on Windows or `./start_medray_v2.sh` on Linux/macOS.
- Check the health URL printed by the launcher, such as `http://127.0.0.1:8765/api/health`.
- If port `8765` is occupied, the launcher tries the next available port and supplies the matching API URL to the frontend.
- Close the launcher or press `Ctrl+C` for a clean stop. On Windows, run `stop_medray_v2.bat` if an older launcher still owns a port.

## Python or Node.js is missing

- Install Python 3.10 or newer from python.org.
- Install a current Node.js LTS release with npm.
- Open a new terminal after installation so the updated `PATH` is available.

## Ollama is unavailable

- Install Ollama and start its service.
- Confirm that `http://127.0.0.1:11434` is reachable.
- Run `ollama list` and select an installed model in AI Settings.

The core application still works without Ollama.

## A DICOM image fails to open

- Confirm that the core `pydicom` dependency is installed.
- Some compressed transfer syntaxes require additional pixel-data codecs.
- The file may be incomplete or may not contain a supported image frame.
- Use only synthetic or properly de-identified samples when debugging.

## A model download fails

- Check the URL, network connection, available disk space, license, and access restrictions.
- Some gated Hugging Face repositories require authentication and license acceptance.
- Do not commit downloaded model files to Git.

## Resetting a development installation

Delete only the local `.venv` and `frontend/node_modules` directories, then run the launcher again. Runtime cases and databases are separate and are not removed by this reset.
