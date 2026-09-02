# Changelog

All notable changes to MedRay v2 will be documented here.

The project is currently an alpha research prototype and does not yet follow a formal release schedule.

## Unreleased

### Added

- Local-first X-ray review workspace with React/Vite frontend and FastAPI backend.
- PNG, JPEG, and DICOM ingestion with multi-image case support.
- Anatomy routing for chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, and general X-ray profiles.
- Structured findings, result cards, annotations, report drafting, audit exports, and DICOM safety utilities.
- Model Finder, local model-card gates, optional Ollama/TorchXRayVision/Ultralytics adapters, and Validation Workbench.
- GitHub CI, Dependabot configuration, issue templates, and a ready-to-publish wiki source.

### Limitations

- No clinical validation, production authentication, or DICOMweb integration has been provided yet.
- The Built-in Demo is deterministic scaffolding and is not a trained clinical model.
