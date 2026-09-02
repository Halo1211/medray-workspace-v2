# Safety and Privacy

## Intended use

MedRay v2 is for research, education, software development, prototyping, and controlled evaluation. It is not a certified medical device or clinical diagnostic system.

Never use it for emergency triage, autonomous decisions, or unsupervised patient care. Every finding, annotation, differential, and report must be independently reviewed by a qualified clinician.

## Local-first behavior

The default runtime stores cases and generated artifacts locally. The Built-in Demo does not require an external model. Ollama and local adapters can run on the same machine. Compatible API endpoints are optional and must be configured explicitly.

Keep the server bound to `127.0.0.1` or `localhost`. The project does not provide production authentication, authorization, tenant isolation, or internet-facing hardening.

## DICOM handling

The DICOM safety page can inspect tags, flag private or burned-in risks, and export a prototype de-identified metadata or DICOM copy. This is not a guarantee of de-identification or DICOM PS3.15 compliance. Text burned into pixels can remain identifying. Review every export manually.

## Data policy for issues and pull requests

Never include:

- patient identifiers or clinical records;
- identifiable DICOM files or radiographs;
- API keys, access tokens, or credentials;
- private model weights or confidential datasets.

Use synthetic or properly de-identified data and sanitized logs only.

## Security reports

Follow the repository's `SECURITY.md` policy for vulnerability reports. Do not disclose security issues in public issues before maintainers have had an opportunity to assess them.
