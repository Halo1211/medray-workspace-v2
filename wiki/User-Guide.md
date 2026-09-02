# User Guide

## Main workflow

### 1. Import

Use **Reading Room** to upload one or more PNG, JPEG, or DICOM images. Multiple images can belong to one local study. Add a case label that does not expose patient identity.

### 2. Route and review

MedRay derives an anatomy profile from DICOM body-part metadata, study/series descriptions, filename context, or a reviewer override. It can route to chest, MSK/trauma, abdomen/KUB, spine, skull/facial/sinus, or general/unknown templates.

The review surface provides image controls, metadata, quality estimates, systematic checklists, warnings, and model trace information. Unknown anatomy and unknown projection remain visible as limitations.

### 3. Findings and annotations

Findings and result cards separate observations, candidate diagnoses, confidence, source, and reviewer state. Manual annotations can be created, moved, resized, or deleted. Annotation links preserve the source image, finding, report statement, and revision context where available.

Fallback regions are general review guides. They are not pathology localization.

### 4. Report and export

Reports can be edited and exported as Markdown, PDF, or JSON. The workspace also supports reviewed PNG output, annotation review packages, and audit JSON bundles. Review every export for identifiers and unsupported claims before sharing.

## Case Library

Cases are stored in local SQLite and local case folders. Use **Case Library** to search, reopen, or explicitly delete cases. **General Settings** can move the database to another folder; the application refuses to overwrite an existing database and requires a restart for a newly selected location.

## Language and appearance

New users start in English. Indonesian is available through the language control. Theme and language preferences are stored in browser local storage.

## Research pages

- **Model Finder:** discover, inspect, import, and queue optional model artifacts.
- **Runtime Settings:** choose the Built-in Demo, Ollama, or a compatible endpoint and review model assignments.
- **Validation Workbench:** save labels, run agreement checks, inspect failure summaries, and export a validation report.
- **About:** view references, maturity gaps, and project safety notes.
