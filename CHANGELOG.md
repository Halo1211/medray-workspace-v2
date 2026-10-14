# Changelog

MedRay v2 is an alpha research prototype. Artifact schema versions are independent
of the application release version.

## 0.2.0-alpha.1 — October 14, 2026

### Added

- Three-point angle measurements and editable length/angle endpoints, with DICOM
  Pixel Spacing support and geometry locks.
- Server-managed case revisions, conditional saves, a shared editor save queue,
  and explicit conflict recovery.
- Independent tested vision, chat, and report connections; guided specialist
  classifier setup; model-card and validation-evidence activation gates.
- Adaptive segmented downloads with pause/resume recovery and SHA-256 checking.
- Release checks for matching versions, React dependency compatibility, Markdown
  formatting, and local documentation links.

### Fixed

- Update the transitive `source-map-js` dependency to the patched 1.2.2 release
  for [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).
- Preserve original high-bit-depth PNG sources and render their intensity range
  consistently for preview and analysis.
- Correct DICOM palette colors, calibration values, paired window presets, and
  color-image display controls; make the frame-1 analysis/export boundary clear.
- Keep analysis, annotations, review decisions, and evidence links attached to
  the correct image through editing, undo/redo, and concurrent operations.
- Prevent stale case, chat, setup, and validation responses from replacing newer
  state or changing the selected page.
- Preserve chat history and current-image context; wait for pending saves and
  propagate server revisions before subsequent editor saves.
- Retain request deadlines and cancellation while reading response bodies and
  after backend discovery.
- Preserve completed export files, model cards, and validation references after
  interrupted writes; reject unsupported options and nonfinite input/output.
- Validate detector scores, range responses, model paths, and explicit download
  checksums; recover interrupted and missing model artifacts.
- Keep the application usable when browser preference storage is unavailable.

### Documentation

- Publish English documentation with a single verification summary and updated
  user and classifier guides.
- Remove temporary audit reports, redundant design history, and debug screenshots
  from the public repository.

## 0.1.0-alpha

- Initial local-first X-ray review workspace with raster/DICOM import, anatomy
  routing, structured findings, annotations, draft reports, and audit exports.
- Local case storage, model discovery, runtime adapters, validation tools,
  platform launchers, and GitHub Actions CI.

## Known limitations

The demo is deterministic scaffolding. Clinical validation, production
authentication, DICOMweb, and universal provider/GPU compatibility are not
established. See [verification and operating limits](docs/VERIFICATION.md).
