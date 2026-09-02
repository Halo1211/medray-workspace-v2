# Contributing

Thank you for helping improve MedRay v2. Read the repository's `CONTRIBUTING.md` for the contribution policy and `CODE_OF_CONDUCT.md` for community expectations.

## Before opening an issue or pull request

- Reproduce the problem with synthetic or properly de-identified data.
- Remove patient identifiers, credentials, tokens, private model weights, and confidential logs.
- Describe the operating system, project version/commit, and exact reproduction steps.
- Consider safety, provenance, DICOM, storage, networking, and model-output implications.

## Local verification

```bash
python -m pytest backend/tests
cd frontend
npm ci
npm test -- --run
npm run build
```

## Pull request expectations

- Keep the change focused and explain the user or research problem.
- Add or update tests for behavior changes.
- Preserve research-only labeling and human-review gates.
- Update the README, `docs/`, or this wiki source when behavior or setup changes.
- Do not commit generated runtime data, `.env`, databases, medical images, or model weights.

## Security issues

Do not open a public issue for a suspected vulnerability. Follow the repository's `SECURITY.md` policy.
