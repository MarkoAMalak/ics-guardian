# ICS Guardian

[![DevSecOps](https://github.com/MarkoAMalak/ics-guardian/actions/workflows/devsecops.yml/badge.svg)](https://github.com/MarkoAMalak/ics-guardian/actions/workflows/devsecops.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-academic-lightgrey)

**Unsupervised process–network anomaly detection for water-chlorination industrial
control systems, delivered as a hardened, cloud-native service.**

A water-chlorination PLC trusts whatever its sensors report. An attacker who spoofs a
reading, or who floods or eavesdrops on the OT network, can push chlorine dosing out of
its safe range while the operator's screen still looks normal. ICS Guardian learns what
*normal* operation looks like, using no attack labels, and flags readings that do not
fit. The repository contains the research pipeline and the production platform that
serves it: a FastAPI scoring service, role-based access, Kubernetes/Helm deployment,
Prometheus metrics and a six-gate DevSecOps pipeline.

Author: **Marko A. Malak** · School of Computing, Queen's University

---

## Results at a glance

All detectors are trained on normal operation only. ROC-AUC and PR-AUC are
threshold-free and are the headline metrics.

| Dataset | Deployed model (Dense AE) | Best model in benchmark |
|---|---|---|
| SWaT  | ROC-AUC **0.942** · PR-AUC **0.802** | TranAD 0.976 / 0.822 |
| WADI  | ROC-AUC **0.770** · PR-AUC **0.317** | LSTM-AE 0.850 / 0.467 |

**Process–network fusion** (SWaT A6 campaign, per window, no point adjustment):

| Detector | ROC-AUC | PR-AUC | F1 | Recall exfiltration | Recall disruption |
|---|:-:|:-:|:-:|:-:|:-:|
| Process only | 0.659 | 0.386 | 0.278 | 0.143 | 0.219 |
| Network only | 0.667 | 0.315 | 0.269 | 0.313 | 0.036 |
| **Fusion (OR)** | **0.776** | **0.470** | **0.399** | **0.391** | **0.248** |

Each single-view detector is close to blind to one attack type. The fused detector has
the highest recall on both.

**Operating point.** τ = 0.063966 (SWaT) and τ = 0.308141 (WADI), calibrated for
about 1 % false alarms on normal data.
**Cost.** About 0.05 ms per reading for the model forward pass on a commodity CPU.

> **A note on F1.** The SWaT benchmark also reports point-adjusted F1, the convention
> in much of the literature. Under that protocol even USAD reaches F1 1.000 while its
> ROC-AUC is 0.540, close to random. Point-adjusted F1 is optimistic, so models here
> are ranked by PR-AUC.

---

## Repository layout

```
ics-guardian/
├── notebooks/                    research: training, evaluation, export
│   ├── SWaT_Anomaly_Detection.ipynb   7 detectors on SWaT and WADI
│   ├── SWaT_A6_Fusion.ipynb           process + network fusion experiment
│   ├── fusion_results_A6.csv          recorded output of the fusion run
│   └── cells/                         threshold recalibration and artefact export
├── platform/                     the deployable system
│   ├── detection_service/        FastAPI app, model loader, auth, web UI, tests
│   ├── k8s/                      Deployment, Service, HorizontalPodAutoscaler
│   ├── helm/ics-detector/        parameterised Helm chart
│   ├── monitoring/               Prometheus config, Grafana dashboard
│   ├── ot_demo/                  PLC simulator -> detector -> fused alarm (demo)
│   └── docker-compose.yml        detector + Prometheus in one command
├── model_artifacts/              portable JSON models (SWaT 45 features, WADI 50)
├── reproduction/                 verify the shipped models without the datasets
├── figure_scripts/               scripts for the project figures
└── .github/workflows/            DevSecOps pipeline (6 gates)
```

---

## Quick start

**Docker (detector + Prometheus):**

```bash
cd platform
docker compose up --build
```

Then open <http://localhost:8000> for the web console, <http://localhost:8000/docs>
for the interactive API and <http://localhost:9090> for Prometheus.

Development accounts are seeded on first start:

| Role | Email | Password |
|---|---|---|
| admin | `admin@icsguardian.local` | `Admin@12345` |
| operator | `operator@icsguardian.local` | `Operator@12345` |

These accounts exist for demonstration only. Remove them and set `AUTH_SECRET` to a
strong random value before any real deployment.

**Without Docker:**

```bash
cd platform/detection_service
pip install -r requirements.txt
uvicorn app:app --port 8000
```

**Score a reading:**

```bash
python - <<'PY'
import json, urllib.request
p = json.load(open("reproduction/sample_payloads_real.json"))["real_attack_1"]
req = urllib.request.Request("http://localhost:8000/score",
        data=json.dumps({"features": p["features"]}).encode(),
        headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req).read().decode())
PY
```

Each response contains `recon_error`, `threshold`, `severity` (= error / τ) and
`anomaly`.

**Kubernetes:**

```bash
kubectl create secret generic ics-detector-auth --from-literal=secret=$(openssl rand -hex 32)
kubectl apply -f platform/k8s/
# or
helm upgrade --install ics-detector platform/helm/ics-detector
```

Pods run as a non-root user on a read-only root filesystem, with all capabilities
dropped and the RuntimeDefault seccomp profile. The HorizontalPodAutoscaler keeps 2–6
replicas at a 70 % CPU target.

**OT-loop demo (Python + NumPy only):**

```bash
cd platform/ot_demo && python run_demo.py
```

---

## Reproduce the deployment claims (no dataset, no GPU)

```bash
cd reproduction
python verify_artifacts.py      # layer shapes, thresholds, alarm sanity, 50 real SWaT rows
python benchmark_inference.py   # compute-only latency and throughput
```

`verify_artifacts.py` checks that the shipped models are wired correctly. Its 50-row
set was chosen for the demo, so a perfect score on it says nothing about detection
quality. Reproducing the detection metrics requires the SWaT and WADI datasets.
They are distributed by iTrust (Singapore University of Technology and Design) under
their own access process and are not included here.

---

## DevSecOps pipeline

Every push and pull request runs `.github/workflows/devsecops.yml`:

| # | Gate | Tool | Fails the build on |
|---|---|---|---|
| 1 | Lint | ruff | any finding (whole platform) |
| 2 | Contract tests | pytest | any failure |
| 3 | SAST | bandit `-ll` | medium or higher |
| 4 | Dependency CVEs | pip-audit `--strict` | any known advisory |
| 5 | Secrets | gitleaks | any leaked credential |
| 6 | Image + IaC | Trivy | CRITICAL / HIGH with a fix available |
| + | Kubernetes E2E | kind (3 nodes) | any failed deployment, cross-replica, autoscaling or failover check |

All six gates pass in GitHub Actions on this repository (see the badge above).

### Changes in release 1.2

- **Shared store across replicas.** Set `AUTH_DB_URL` to a PostgreSQL URL and every replica
  shares the same users and the same threshold override (`store.py`). Without it the
  service falls back to a per-pod SQLite file. The override is persisted, can be reverted
  (`DELETE /admin/settings/threshold`), and replicas pick it up within `SETTINGS_TTL` seconds.
- **Drift monitor.** `drift.py` runs a block CUSUM on the alarm rate against its calibrated
  target and exposes it at `GET /drift` and as Prometheus gauges (`ics_drift_cusum`,
  `ics_drift_suspected`, `ics_recent_alarm_rate`). Its limit is set per plant from
  calibration data (at most one false signal a week on SWaT's calibration block).
- **Faster batch scoring.** `/score/batch` now scores the whole batch in one vectorised pass
  (about 8x the throughput of the old per-reading loop), with one PyTorch thread per worker.
- **Kubernetes end-to-end test in CI.** A 3-node kind cluster runs the real manifests with a
  shared PostgreSQL store; the job checks cross-replica logins and threshold overrides,
  pod hardening, autoscaling under in-cluster load, failover when a pod is killed, and a
  clean Helm install.
- **Unit tests run against both SQLite and PostgreSQL.**

### Changes in release 1.1

- Upgraded `torch` 2.3.1 → 2.14.1 and `python-multipart` 0.0.9 → 0.0.32. The old pins
  had 37 published advisories, so `pip-audit --strict` would have failed the build.
  The tests still pass and the model returns identical scores.
- `torch.load` now uses `weights_only=True`, which blocks code execution from a
  tampered weights file. This fixes a bandit Medium finding.
- The lint gate now covers the whole platform; three findings in `ot_demo` were fixed.
- **Kubernetes/Helm:** the read-only root filesystem made the user database unwritable,
  so pods failed at start-up. An empty volume was also mounted over the model
  artefacts. Pods now get writable `/app/data` and `/tmp` volumes and read the JWT key
  from a Secret, and the artefacts come from the image (or from an optional PVC in Helm).
- The CI workflow moved to the repository root so GitHub Actions picks it up.
- **CI fixes found on the first real run:** pytest now finds the service module
  (`pythonpath` in `pyproject.toml`); `pip-audit` audits the CPU-only PyTorch build
  separately, since it is not on PyPI; the Trivy action is pinned to a commit SHA.
- **Image hardening (Trivy):** the image patches Debian packages and removes the
  build-time tools (`pip`, `setuptools`, `wheel`, the `ensurepip` wheels) after
  installing dependencies. This clears five HIGH findings: `libpcre2`, plus
  `urllib3`, `msgpack` and `setuptools` vendored inside pip.

---

## Known limitations

- The live service runs the **process** model. Fusion with the network model was
  evaluated offline on the SWaT A6 campaign.
- Models are plant-specific: SWaT has 45 channels and WADI 50. A new site needs clean
  data and retraining.
- Fusion results come from one short campaign; SWaT A6 network data is needed to repeat
  them over several seeds.
- The drift monitor flags a rise in the alarm rate; a sustained attack raises it too, so a
  drift signal calls for human review, not automatic recalibration.
- The platform has not been connected to a live plant.

---

## License

Academic use; see [LICENSE](LICENSE). This is a research prototype. Do not connect it
to a live control system without an independent safety and security review.
