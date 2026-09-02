# GitHub Release Checklist

Run this checklist before the first push and before each public release.

## Repository hygiene

- [ ] No `.env`, credentials, tokens, or private endpoints are tracked.
- [ ] No patient images, DICOM files, local databases, exports, or logs are tracked.
- [ ] No model weights, package caches, virtual environments, `node_modules`, or frontend builds are tracked.
- [ ] No personal absolute filesystem paths remain.
- [ ] Every file larger than 10 MB is intentional and reviewed.

## Quality

- [ ] `python -m pytest backend/tests` passes.
- [ ] `npm test -- --run` passes in `frontend`.
- [ ] `npm run build` passes in `frontend`.
- [ ] A fresh browser session opens in English and all primary pages load.
- [ ] Setup instructions were tested on the target operating system.

## Project governance

- [ ] A project license has been selected and added.
- [ ] GitHub private vulnerability reporting or a private security contact is configured.
- [ ] Repository description, topics, and social preview are configured.
- [ ] Clinical and research-only limitations are visible in the README.
- [ ] Release notes list known limitations and validation status.
