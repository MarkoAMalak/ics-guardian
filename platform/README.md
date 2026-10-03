# Cloud-Native DevSecOps Platform - ICS Detection Serving Tier

[![DevSecOps](https://github.com/MarkoAMalak/ics-guardian/actions/workflows/devsecops.yml/badge.svg)](https://github.com/MarkoAMalak/ics-guardian/actions/workflows/devsecops.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Container](https://img.shields.io/badge/container-non--root%20%7C%20read--only%20FS-3fb27f)
![Security gates](https://img.shields.io/badge/security-Bandit%20%7C%20pip--audit%20%7C%20Gitleaks%20%7C%20Trivy-f5c451)
![License](https://img.shields.io/badge/license-academic-lightgrey)

This repository is the **deployable platform** around the anomaly-detection
research: it turns the trained SWaT detector into a containerized, continuously
secured, observable service, and documents how the detector fits into a layered
ICS defense.

```
platform/
├── detection_service/        # FastAPI real-time scoring service (+ Docker, tests)
│   ├── app.py                #   HTTP API: /score, /score/batch, /health, /metrics
│   ├── model.py              #   inference-only detector (loads exported artifacts)
│   ├── export_model.py       #   run in the training notebook to dump artifacts
│   ├── Dockerfile            #   non-root, slim, healthchecked image
│   └── tests/                #   pytest contract tests (run in CI)
├── ot_demo/                  # LIVE demo: PLC simulator -> detector -> fused alarm
│   ├── plc_simulator.py      #   chlorination-process / PLC simulator
│   └── run_demo.py           #   live scorer (built-in or --service mode)
├── k8s/                      # plain Kubernetes manifests (Deployment, Service, HPA)
├── helm/ics-detector/        # parameterized Helm chart
├── monitoring/
│   ├── prometheus.yml        #   scrapes the service /metrics
│   └── grafana_dashboard.json#   importable Grafana observability dashboard
├── docker-compose.yml        # detector + Prometheus, one command
└── SECURITY.md               # security policy & hardening

Companion documents (delivered separately):
  - MITRE ATT&CK for ICS - SWaT attack mapping & detection coverage
  - Incident Response / PLC playbook - what happens when the detector fires
```

## The end-to-end story (for the defense)

1. **Train** offline on the GPU (`SWaT_Anomaly_Detection.ipynb`), export artifacts.
2. **Serve** the model here as a small container - real-time `/score` API.
3. **Secure** it: every commit passes SAST, dependency, secret, and container CVE
   scans before it can ship (`devsecops.yml`).
4. **Observe** it: Prometheus scrapes `/metrics`; import `monitoring/grafana_dashboard.json`
   into Grafana for live request / anomaly / latency panels.
5. **Respond**: an alarm triggers the Incident Response / PLC playbook; the MITRE
   mapping shows exactly which ICS techniques each detection covers.

## Detection approach

The deployed service runs a single dense autoencoder trained only on normal SWaT
operation (ROC-AUC 0.942, PR-AUC 0.802, threshold-free). Process-network fusion
was evaluated offline on the SWaT A6 campaign (per window, no point adjustment):

| Detector     | ROC-AUC | PR-AUC | F1    | Recall exfiltration | Recall disruption |
|--------------|:-------:|:------:|:-----:|:-------------------:|:-----------------:|
| Process only | 0.659   | 0.386  | 0.278 | 0.143               | 0.219             |
| Network only | 0.667   | 0.315  | 0.269 | 0.313               | 0.036             |
| **Fusion**   | **0.776** | **0.470** | **0.399** | **0.391**     | **0.248**         |

The `ot_demo/` simulator shows the same fusion idea on synthetic PLC data; its
output is a demonstration, not an evaluation.

## Quick start

```bash
docker compose up --build          # detector on :8000, Prometheus on :9090
curl localhost:8000/health
open http://localhost:8000/docs    # interactive API
```

Live OT-loop demo (no Docker needed, Python + numpy):

```bash
cd ot_demo
python run_demo.py
```

## Continuous security (DevSecOps)

Every push and pull request runs the full gate in `.github/workflows/devsecops.yml`:

| Stage        | Tool       | Fails the build on                    |
|--------------|------------|---------------------------------------|
| Lint         | ruff       | style / error-prone code              |
| Unit tests   | pytest     | broken API contract                   |
| SAST         | Bandit     | insecure Python patterns              |
| Dependencies | pip-audit  | known CVEs in packages                |
| Secrets      | Gitleaks   | committed credentials / tokens        |
| Container    | Trivy      | OS / library CVEs, Dockerfile misconfig |

A build **fails on any CRITICAL/HIGH finding** - insecure code cannot ship.

See `detection_service/README.md` for the full API and model-export instructions.
