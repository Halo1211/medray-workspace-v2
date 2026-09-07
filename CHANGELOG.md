# Changelog

All notable changes to MedRay v2 will be documented here.

The project is currently an alpha research prototype and does not yet follow a formal release schedule.

## Unreleased

### Added

- Advanced Reading Room annotations: ellipse ROI, calibrated length, DICOM frame identity, bounded undo/redo, lock-aware editing, and reviewed export support.
- DICOM multi-frame rendering with VOI/window-level presets, manual center/width, inversion, rotation/flip controls, and Pixel Spacing exposure.
- Adaptive segmented model downloads with range validation, pause/resume segment recovery, connection tuning, and optional SHA-256 verification.
- Advanced AI preferences for generation temperature, output budget, request timeout, retries, annotation suggestion threshold, and download concurrency.
- Unified Case Library and Validation workspace with inline case rename.

- Local-first X-ray review workspace with React/Vite frontend and FastAPI backend.
- PNG, JPEG, and DICOM ingestion with multi-image case support.
- Anatomy routing for chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, and general X-ray profiles.
- Structured findings, result cards, annotations, report drafting, audit exports, and DICOM safety utilities.
- Model Finder, local model-card gates, optional Ollama/TorchXRayVision/Ultralytics adapters, and Validation Workbench.
- GitHub CI, Dependabot configuration, issue templates, and a ready-to-publish wiki source.

### Limitations

- No clinical validation, production authentication, or DICOMweb integration has been provided yet.
- The Built-in Demo is deterministic scaffolding and is not a trained clinical model.
