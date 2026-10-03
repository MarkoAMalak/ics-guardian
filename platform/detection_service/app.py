"""
app.py — FastAPI microservice that serves the ICS anomaly detector in real time.

Endpoints
    GET  /health   liveness + whether the model is loaded (for k8s / compose probes)
    GET  /info     model metadata: features, threshold, training percentile
    POST /score    score a single sensor snapshot -> anomaly decision
    POST /score/batch  score many snapshots at once
    GET  /metrics  Prometheus exposition (request counts, anomaly counts, latency)

This is the "serving" tier of the platform. Data from the historian / OPC-UA bridge
is POSTed here; the response feeds the SOC dashboard and the incident-response
playbook. Kept deliberately small so it ships as a lean container.
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from auth import _require_admin, seed_users
from auth import router as auth_router
from model import Detector

app = FastAPI(
    title="ICS Anomaly Detection Service",
    description="Real-time anomaly scoring for water-chlorination ICS (SWaT-trained detector).",
    version="1.0.0",
)

detector = Detector()

# authentication + role-based access (register / login / me / users)
app.include_router(auth_router)


@app.on_event("startup")
def _seed() -> None:
    seed_users()

# --- lightweight Prometheus-style counters (no external dep required) --------- #
_METRICS = {"requests_total": 0, "anomalies_total": 0, "errors_total": 0, "latency_sum_s": 0.0}


class Sample(BaseModel):
    """A single time-step of sensor/actuator readings, keyed by feature name."""

    features: dict[str, float] = Field(..., description="feature_name -> value")


class BatchRequest(BaseModel):
    samples: list[Sample]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": detector.ready}


@app.get("/info")
def info() -> dict:
    if not detector.ready:
        raise HTTPException(status_code=503, detail="model artifacts not loaded")
    return {
        "n_features": len(detector.features),
        "features": detector.features,
        "threshold": detector.threshold,
        "threshold_percentile": detector.meta.get("percentile"),
        "metric": detector.meta.get("metric", "recon_error"),
    }


@app.post("/score")
def score(sample: Sample) -> dict:
    t0 = time.perf_counter()
    _METRICS["requests_total"] += 1
    try:
        result = detector.score_one(sample.features)
    except RuntimeError as exc:
        _METRICS["errors_total"] += 1
        raise HTTPException(status_code=503, detail="model artifacts not loaded") from exc
    except KeyError as exc:
        _METRICS["errors_total"] += 1
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result["anomaly"]:
        _METRICS["anomalies_total"] += 1
    _METRICS["latency_sum_s"] += time.perf_counter() - t0
    return result


@app.post("/score/batch")
def score_batch(req: BatchRequest) -> dict:
    t0 = time.perf_counter()
    _METRICS["requests_total"] += len(req.samples)
    try:
        results = detector.score_batch([s.features for s in req.samples])
    except RuntimeError as exc:
        _METRICS["errors_total"] += 1
        raise HTTPException(status_code=503, detail="model artifacts not loaded") from exc
    except KeyError as exc:
        _METRICS["errors_total"] += 1
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _METRICS["anomalies_total"] += sum(1 for r in results if r["anomaly"])
    _METRICS["latency_sum_s"] += time.perf_counter() - t0
    return {"count": len(results), "results": results}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    lines = [
        "# HELP ics_requests_total Total scoring requests.",
        "# TYPE ics_requests_total counter",
        f"ics_requests_total {_METRICS['requests_total']}",
        "# HELP ics_anomalies_total Total samples flagged anomalous.",
        "# TYPE ics_anomalies_total counter",
        f"ics_anomalies_total {_METRICS['anomalies_total']}",
        "# HELP ics_errors_total Total failed requests.",
        "# TYPE ics_errors_total counter",
        f"ics_errors_total {_METRICS['errors_total']}",
        "# HELP ics_latency_seconds_sum Cumulative scoring latency.",
        "# TYPE ics_latency_seconds_sum counter",
        f"ics_latency_seconds_sum {_METRICS['latency_sum_s']:.6f}",
        "# HELP ics_model_loaded Whether model artifacts are loaded (1/0).",
        "# TYPE ics_model_loaded gauge",
        f"ics_model_loaded {1 if detector.ready else 0}",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Role-gated endpoints. These make the operator/admin split concrete:
#   * any signed-in user (operator OR admin) may score data via /score.
#   * only an admin may view activity or change the live detection threshold.
# --------------------------------------------------------------------------- #
class ThresholdUpdate(BaseModel):
    threshold: float = Field(..., gt=0, description="new reconstruction-error cut-off")


@app.get("/admin/activity")
def admin_activity(authorization: str | None = Header(default=None)) -> dict:
    """Admin-only: live system activity (scoring volume, anomalies, latency)."""
    _require_admin(authorization)
    reqs = _METRICS["requests_total"]
    return {
        "requests_total": reqs,
        "anomalies_total": _METRICS["anomalies_total"],
        "errors_total": _METRICS["errors_total"],
        "avg_latency_ms": round(1000 * _METRICS["latency_sum_s"] / reqs, 3) if reqs else 0.0,
        "model_loaded": detector.ready,
    }


@app.get("/admin/settings")
def get_settings(authorization: str | None = Header(default=None)) -> dict:
    """Admin-only: view the live detection settings."""
    _require_admin(authorization)
    return {"threshold": detector.threshold,
            "percentile": detector.meta.get("percentile"),
            "metric": detector.meta.get("metric", "recon_error")}


@app.post("/admin/settings")
def update_settings(body: ThresholdUpdate, authorization: str | None = Header(default=None)) -> dict:
    """Admin-only: change the live detection threshold (operators cannot)."""
    _require_admin(authorization)
    old = detector.threshold
    detector.threshold = float(body.threshold)
    detector.meta["threshold"] = float(body.threshold)
    detector.meta["calibration"] = "adjusted live by admin"
    return {"threshold": detector.threshold, "previous": old, "updated": True}


# --- serve the ICS Guardian website (mounted last so API routes win) -------- #
import os as _os  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_WEB = _Path(_os.getenv("WEB_DIR", _Path(__file__).parent / "web"))
if _WEB.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="site")
