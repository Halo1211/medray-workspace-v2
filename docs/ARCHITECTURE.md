# Architecture

MedRay v2 memakai FastAPI backend dan React/Vite frontend.

- `backend/app/api`: REST API.
- `backend/app/models`: schema Pydantic untuk Case, AnalysisResult, Annotation, Report, ModelMetadata, RuntimeConfig.
- `backend/app/storage`: SQLite local-first.
- `backend/app/pipelines`: MedRAX-inspired pipeline runner.
- `backend/app/medrax_adapter`: tool interface, orchestrator, registry-ready normalizer.
- `backend/app/model_finder`: Hugging Face, GitHub, Ollama, local import, download queue.
- `backend/app/runtime`: Demo/Ollama/OpenAI-compatible adapter.
- `backend/app/reference_catalog.py`: katalog referensi, gap maturitas, dan rekomendasi build berikutnya.
- `frontend/src`: GUI halaman Dashboard, Reading Room, Chat, Report, Model Finder, Runtime, Case Library, About.

Data lokal ada di `data/`. Tidak ada upload cloud default.

Roadmap maturitas ada di `docs/ROADMAP.md`.
