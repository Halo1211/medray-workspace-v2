# User Guide

## Main workflow

### 1. Import

Use **Reading Room** to upload one or more PNG, JPEG, or DICOM images. Multiple images can belong to one local study. Add a case label that does not expose patient identity.

### 2. Route and review

MedRay derives an anatomy profile from DICOM body-part metadata, study/series descriptions, filename context, or a reviewer override. It can route to chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, or general/unknown templates.

The review surface provides image controls, metadata, quality estimates, systematic checklists, warnings, and model trace information. Unknown anatomy and unknown projection remain visible as limitations. DICOM studies additionally expose frame selection, stored Window Center/Width presets, manual window/level, MONOCHROME inversion, Pixel Spacing, and source-preserving display controls. MedRay does not claim to serialize DICOM GSPS, SEG, or SR yet; current reviewed artifacts remain PNG/JSON.

### 3. Findings and annotations

Findings and result cards separate observations, candidate diagnoses, confidence, source, and reviewer state. Manual box, point, polygon, ellipse ROI, length, and three-point angle annotations can be created and edited. Drag selected measurement endpoints to adjust their geometry. Use **Ctrl+Z** to undo and **Ctrl+Shift+Z** to redo annotation changes, including their evidence links. Lock reviewed geometry to avoid accidental edits. DICOM length and ellipse measurements use Pixel Spacing when available; otherwise they are explicitly reported in `px`/`px²`, never millimetres. Annotation links preserve the source image/frame, finding, report statement, and revision context.

Fallback regions are general review guides. They are not pathology localization.

### 4. Report and export

Review draft reports and export them as Markdown, PDF, or JSON. The workspace also supports reviewed PNG output, annotation review packages, and audit JSON bundles. DICOM AI analysis and PNG exports use frame 1; annotations on other frames remain in review JSON. Saves complete before export, and a failed save requires loading the latest saved case before exporting. Review every export for identifiers and unsupported claims before sharing.

## Case Library and Validation

Cases are stored in local SQLite and local case folders. Search, rename, reopen, or explicitly delete cases in **Case Library**. Open its **Validation workspace** to create reference labels, run agreement checks, inspect failures, and export protocol reports. **General Settings** can move the database to another folder; the application refuses to overwrite an existing database and requires a restart for a newly selected location.

## Model downloads

The download queue supports pause, resume, retry, cancellation, adaptive parallel HTTP byte ranges, and optional SHA-256 verification. Parallel connections are used only when a server returns valid range responses; otherwise MedRay falls back to one stream. For Hugging Face repository snapshots, prefer the official Hub client with Xet because it adds content-addressed chunking and cache reuse.

## Language and appearance

New users start in English. Indonesian is available through the language control. Theme and language preferences are stored in browser local storage.

## Advanced tools

- **Model Finder:** discover, inspect, import, and queue optional model artifacts.
- **AI Setup:** choose the Built-in Demo, Ollama, or a compatible endpoint; advanced controls include temperature, output-token cap, timeout, retry count, localization/review thresholds, and model-download connections.
- **Case Library → Validation:** save labels, run agreement checks, inspect failure summaries, and export a validation report.
- **About:** product identity, local-first status, intended use, and safety disclaimer only.

## Implementation references

- DICOM display/annotation object roles: [Grayscale Softcopy Presentation State](https://dicom.nema.org/medical/Dicom/2016a/output/chtml/part03/sect_A.33.html), [Segmentation IOD](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_a.51.html), and [Structured Report IODs](https://dicom.nema.org/medical/dicom/2024e/output/chtml/part03/sect_A.35.html).
- Annotation state and measurement-service design references: [Cornerstone annotation state](https://www.cornerstonejs.org/docs/concepts/cornerstone-tools/annotation/state/) and [OHIF Measurement Service](https://docs.ohif.org/platform/services/data/measurementservice/).
- Resumable/parallel transfer references: [HTTP Range Requests (RFC 9110)](https://www.rfc-editor.org/rfc/rfc9110.pdf), [aria2 manual](https://aria2.github.io/manual/en/html/aria2c.html), and [Hugging Face Hub downloads/Xet](https://huggingface.co/docs/huggingface_hub/main/guides/download).
