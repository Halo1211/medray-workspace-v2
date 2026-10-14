# Contributing to MedRay v2

Thank you for helping improve MedRay v2.

## Ground rules

- Use synthetic or properly de-identified test images only.
- Never commit patient data, credentials, model weights, local databases, or generated exports.
- Preserve the human-review gates and research-only labeling.
- Do not present unvalidated model output as clinical diagnosis or verified localization.
- Keep user-facing English concise; update Indonesian translations when changing existing translated copy.

## Development

Follow the manual setup in [README.md](README.md), then run:

```bash
python -m pytest backend/tests
python scripts/check_release.py
cd frontend
npm test -- --run
npm run build
```

Keep application versions aligned in the backend, frontend package, and lockfile.
Pin React and React DOM to the same version. Public Markdown documentation is
written in English; the application continues to support English and Indonesian.

## Pull requests

Keep each pull request focused. Explain the user problem, the chosen approach, safety implications, tests performed, and screenshots for visible interface changes. Add or update tests for changed behavior.

## Licensing

MedRay v2 is distributed under the MIT License. By contributing, you agree that your contribution may be distributed under the same terms. See [LICENSE](LICENSE).
