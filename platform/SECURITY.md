# Security Policy — ICS Detection Platform

Security is enforced continuously through the DevSecOps pipeline
(`.github/workflows/devsecops.yml`). This document states what is checked, why,
and how to report issues.

## Automated security gates (every push / PR)

| Stage | Tool | What it protects against |
|------|------|--------------------------|
| SAST | **Bandit** | Insecure Python patterns (eval, subprocess, weak crypto, hardcoded secrets) |
| Dependency scan | **pip-audit** | Known CVEs in third-party packages |
| Secret scan | **Gitleaks** | Committed credentials / API keys / tokens |
| Container scan | **Trivy (image)** | OS + library CVEs in the built image |
| IaC / config scan | **Trivy (config)** | Dockerfile misconfigurations (root user, missing healthcheck, etc.) |
| Lint & tests | **ruff + pytest** | Correctness regressions before deploy |

A build **fails** if any gate finds CRITICAL/HIGH issues. This is the "shift-left"
principle: vulnerabilities are caught in CI, not in production.

## Hardening applied

- Container runs as a **non-root** user (`appuser`, uid 10001).
- **Slim** base image (`python:3.11-slim`) to reduce attack surface.
- **CPU-only** torch — no unnecessary GPU/driver surface in the serving image.
- Least-privilege GitHub Actions token (`permissions: contents: read`).
- Model artifacts mounted **read-only** at runtime.
- No secrets in code or image; configuration via environment variables.

## Defense-in-depth (OT context)

The service is the detection layer of a layered ICS defense (see the MITRE
ATT&CK for ICS mapping and Incident Response playbook). It assumes network
segmentation between IT and OT (Purdue model), a one-way historian feed, and
that PLC write-back is gated behind human approval — the detector *recommends*,
the operator *acts*.

## Reporting a vulnerability

Open a private security advisory or email the maintainer. Do not file public
issues for undisclosed vulnerabilities. Expected acknowledgement: 72 hours.
