# Security Policy

## Supported version

Security fixes currently target the latest revision of the alpha branch. Older snapshots are not supported.

## Reporting a vulnerability

Please report security issues privately to the repository owner before creating a public issue. Include:

- the affected component and version or commit;
- a minimal reproduction using synthetic data;
- the expected and observed behavior;
- the potential impact;
- any proposed mitigation.

Do not include patient information, medical images, access tokens, passwords, API keys, or third-party confidential data. If a private reporting channel has not yet been configured on GitHub, contact the repository owner directly.

## Security boundaries

MedRay is designed for loopback-only local development. It does not provide production authentication, authorization, tenant isolation, audit logging, or internet-facing hardening. Do not expose the backend or frontend directly to an untrusted network.

Before pushing to GitHub, confirm that `.env`, local databases, cases, exports, model weights, package caches, and build outputs are not staged.
