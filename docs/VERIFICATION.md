# Verification and operating limits

This summary applies to **0.2.0-alpha.1**, checked on October 14, 2026. Passing
software tests establishes the behavior of the tested workflows, not clinical
validity or universal model compatibility.

## Automated checks

| Check | Result |
| --- | --- |
| Backend tests on Python 3.12 / Windows | 476 passed, 1 skipped |
| Frontend tests | 146 passed across 14 files |
| TypeScript and production Vite build | Passed |
| Python compilation and critical runtime lint | Passed |
| npm dependency audit | No known vulnerabilities |

Backend tests use isolated data directories and database-location configuration.
Coverage includes case persistence and concurrency, raster/DICOM rendering,
geometry, anatomy routing, pipeline/provider contracts, reports and audit exports,
model setup/downloads, validation references, and launcher behavior. Frontend
tests cover editor state, evidence links, delayed responses, save queues, setup,
validation, request cancellation, and browser-storage failures.

The Windows suite skips one symlink test. Existing TestClient dependencies emit
two deprecation warnings. Full Ruff still reports exception-handling/style
findings; this release does not claim a clean full-lint or percentage-coverage
baseline.

## Browser checks

A real browser with synthetic images and a temporary database verified import of
16-bit PNG and two-frame DICOM studies, demo analysis, anatomy overrides, manual
annotations, accepted review state, undo/redo, image switching, case reopening,
chat, report JSON, and multi-image review packages. AI Setup system checks
completed successfully. No application console errors were observed in those
workflows.

## Image and export boundaries

- High-bit-depth PNG sources remain unchanged. A documented linear min–max 8-bit
  rendering is used for preview and analysis; this is not modality calibration.
- DICOM frames can be viewed and manually annotated. AI analysis and PNG exports
  currently use **frame 1**. Other-frame annotations remain in review JSON.
- Measurements use valid DICOM Pixel Spacing when available; otherwise they use
  pixel units. Display transforms preserve source coordinates.
- Atomic writes protect individual completed files from interrupted replacement.
  A review package is not a single transaction across all its files, and writes
  do not guarantee durability after a power failure.
- Conditional case saves protect clients that send the case revision through
  `If-Match`. Older clients without that header retain unconditional upsert
  behavior.

## External models and platforms

Real inference has not been tested for every provider/model combination, GPU, or
vendor DICOM variant. Use the task-specific connection test before activation.
Downloaded weights or installed packages alone do not establish readiness.
Arbitrary repository code is not executed as an automatic model runtime.

Clean setup/upgrade testing across all supported operating systems remains
separate from unit and integration tests. DICOM de-identification is a prototype,
not a DICOM PS3.15 certification, and cannot remove identifiers burned into pixels.

See [Safety](SAFETY.md), [AI Setup](AI_SETUP.md), [Troubleshooting](TROUBLESHOOTING.md),
and [the roadmap](ROADMAP.md) for operational guidance and planned validation.
