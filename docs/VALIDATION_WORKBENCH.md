# Validation Workbench

MedRay v2 Validation Workbench is a local research tool for comparing AI outputs against curated labels. It is intentionally framed as agreement checking, not clinical performance measurement.

## Scope

- Stores labels under `data/validation/labels/{case_id}.json`.
- Runs without network access.
- Compares saved labels with locally stored cases and analysis results.
- Exports a JSON report with dataset summary, protocol notes, runtime/model references, failure cases, limitations, and per-case results.
- Deleting a case from Case Library also removes its linked validation label; clearing the case database removes all local case labels and case exports.

Do not describe these outputs as diagnostic accuracy, sensitivity, specificity, or clinical performance unless a validated dataset and protocol have been documented outside this prototype.

## Label Schema

Each label can include:

- `case_id`, `title`, `dataset_name`, and `split`.
- `expected_body_region`.
- `expected_image_quality` with `diagnostic_quality`, `limitations`, and optional note.
- `expected_findings` with label, expected status, and note.
- `expected_annotations` with label, coordinate type, required flag, and note.
- `reference_standard`, `reviewer`, and `protocol_notes`.
- `skip_reason` for unsupported or intentionally excluded cases.

Older labels that only include body region and findings still load.

## Fixture

A small offline fixture is included at:

`data/validation/fixtures/curated_sample_labels.json`

It is synthetic and exists only to exercise workbench plumbing. It should not be used as evidence of model quality.

The frontend also exposes a `Sample Fixture` action that writes the same fixture through:

`GET /api/validation/fixtures/curated-sample`

## API

- `GET /api/validation/labels`
- `POST /api/validation/labels`
- `DELETE /api/validation/labels/{case_id}`
- `POST /api/validation/run`
- `POST /api/validation/export`
- `GET /api/validation/fixtures/curated-sample`

## Metrics

The report uses agreement-style metrics:

- label counts and evaluated/skipped cases;
- finding agreements and mismatch flags;
- result-card agreements and human review status;
- body-region agreements;
- required annotation agreements;
- skipped missing/no-analysis/skipped-by-label cases.

Mismatch flags are prototype review cues. They are not clinical false-positive or false-negative rates.

## Review Flow

1. Open or upload a case.
2. Run the AI workflow if no analysis exists.
3. Open `Validation Workbench`.
4. Save a research label for the active case.
5. Run validation.
6. Review grouped per-case result rows: mismatch/failure, uncertain/high-disagreement, skipped/no-analysis, and agreement.
7. Use `Open case for review` on a result row to jump to the case and referenced study image in the Reading Room.
8. Export JSON for protocol review.
