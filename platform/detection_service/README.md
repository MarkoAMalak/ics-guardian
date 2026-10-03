# ICS Anomaly Detection Service

Real-time anomaly scoring for the water-chlorination ICS, exposed as a small
containerized HTTP service. This is the **serving tier** of the platform: the
model is trained offline on the GPU (`SWaT_Anomaly_Detection.ipynb`), exported,
and loaded here for low-latency inference.

```
 historian / OPC-UA bridge ──POST /score──▶  [ this service ]  ──▶ SOC dashboard
                                                    │
                                                    └──▶ alarm ▶ IR playbook
```

## Endpoints

| Method | Path           | Purpose                                            |
|-------|----------------|----------------------------------------------------|
| GET   | `/health`      | Liveness + `model_loaded` (probes)                 |
| GET   | `/info`        | Feature list, threshold, training percentile        |
| POST  | `/score`       | Score one sensor snapshot → anomaly decision        |
| POST  | `/score/batch` | Score many snapshots at once                        |
| GET   | `/metrics`     | Prometheus metrics (requests, anomalies, latency)   |

### Example

```bash
curl -X POST localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{"features": {"FIT101": 2.55, "LIT101": 520.1, "MV101": 1, "P101": 2}}'
# -> {"recon_error": 0.0142, "threshold": 0.0098, "severity": 1.45, "anomaly": true}
```

`severity` is `recon_error / threshold`; ≥ 1.0 means an alarm. The threshold is
derived unsupervised from the **normal** training distribution (a percentile),
never from attack labels.

## Run it

**Local (Python):**
```bash
pip install -r requirements.txt
uvicorn app:app --reload           # http://localhost:8000/docs
```

**Container:**
```bash
docker build -t ics-detector .
docker run -p 8000:8000 -v $(pwd)/artifacts:/app/artifacts:ro ics-detector
```

**Full stack (detector + Prometheus):**
```bash
cd ..            # platform/
docker compose up --build
```

## Exporting a model

At the end of your training notebook:
```python
from export_model import export_artifacts
export_artifacts(model, scaler, feature_names, train_errors, percentile=99)
```
This writes `model.pt`, `scaler.joblib`, `threshold.json`, `feature_names.json`
into `artifacts/`. The service starts even before artifacts exist (health stays
green; `/score` returns 503 until they are present).

## Design notes

- **Non-root, slim, healthchecked** container — see `Dockerfile`.
- **CPU-only torch** so the serving image is small and needs no GPU.
- **Inference decoupled from training** — the service never imports the notebook.
- Scanned on every push by the DevSecOps pipeline (Bandit, pip-audit, Trivy).
