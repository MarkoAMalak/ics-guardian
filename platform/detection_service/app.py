"""
app.py — FastAPI microservice that serves the ICS anomaly detector in real time.

Endpoints
    GET  /health   liveness + whether the model is loaded (for k8s / compose probes)
    GET  /info     model metadata: features, threshold, training percentile
    POST /score    score a single sensor snapshot -> anomaly decision
    POST /score/batch  score many snapshots at once
    GET  /metrics  Prometheus exposition (request counts, anomaly counts, latency, drift)
    GET  /drift    drift monitor: is the alarm rate on recent readings above its calibrated target?

This is the "serving" tier of the platform. Data from the historian / OPC-UA bridge
is POSTed here; the response feeds the SOC dashboard and the incident-response
playbook. Kept deliberately small so it ships as a lean container.
"""

from __future__ import annotations

import os
import threading
import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

import store
from auth import _require_admin, seed_users
from auth import router as auth_router
from drift import DriftMonitor
from model import Detector

app = FastAPI(
    title="ICS Anomaly Detection Service",
    description="Real-time anomaly scoring for water-chlorination ICS (SWaT-trained detector).",
    version="1.2.0",
)

detector = Detector()
drift = DriftMonitor()

# --- threshold shared by all replicas ---------------------------------------- #
# The artefact's threshold is the default. An administrator's override is stored in the shared
# settings table (store.py), so with a PostgreSQL store every replica applies the same value and
# the override survives restarts. Each replica re-reads it at most every SETTINGS_TTL seconds.
_ARTEFACT_THRESHOLD = detector.threshold
_SETTINGS_TTL = float(os.getenv("SETTINGS_TTL", "5"))
_settings_lock = threading.Lock()
_settings_checked = 0.0


def _sync_threshold(force: bool = False) -> None:
    global _settings_checked
    now = time.monotonic()
    if not force and now - _settings_checked < _SETTINGS_TTL:
        return
    with _settings_lock:
        _settings_checked = now
        try:
            value = store.get_setting("threshold")
        except Exception:  # store unavailable: keep serving with the current threshold
            return
        new = float(value) if value is not None else _ARTEFACT_THRESHOLD
        if detector.ready and new != detector.threshold:
            detector.threshold = new
            detector.meta["threshold"] = new

# authentication + role-based access (register / login / me / users)
app.include_router(auth_router)


@app.on_event("startup")
def _seed() -> None:
    seed_users()
    _sync_threshold(force=True)

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
    _sync_threshold()
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
    drift.update(result["anomaly"])
    _METRICS["latency_sum_s"] += time.perf_counter() - t0
    return result


@app.post("/score/batch")
def score_batch(req: BatchRequest) -> dict:
    t0 = time.perf_counter()
    _METRICS["requests_total"] += len(req.samples)
    _sync_threshold()
    try:
        results = detector.score_batch([s.features for s in req.samples])
    except RuntimeError as exc:
        _METRICS["errors_total"] += 1
        raise HTTPException(status_code=503, detail="model artifacts not loaded") from exc
    except KeyError as exc:
        _METRICS["errors_total"] += 1
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _METRICS["anomalies_total"] += sum(1 for r in results if r["anomaly"])
    for r in results:
        drift.update(r["anomaly"])
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
        "# HELP ics_threshold Detection threshold currently applied.",
        "# TYPE ics_threshold gauge",
        f"ics_threshold {detector.threshold if detector.ready else 0}",
    ]
    d = drift.status()
    lines += [
        "# HELP ics_drift_cusum Bernoulli CUSUM statistic of the alarm rate.",
        "# TYPE ics_drift_cusum gauge",
        f"ics_drift_cusum {d['cusum']}",
        "# HELP ics_drift_suspected 1 when the alarm rate has drifted above its target.",
        "# TYPE ics_drift_suspected gauge",
        f"ics_drift_suspected {1 if d['drift_suspected'] else 0}",
        "# HELP ics_recent_alarm_rate Alarm rate over the recent window.",
        "# TYPE ics_recent_alarm_rate gauge",
        f"ics_recent_alarm_rate {d['recent_alarm_rate']}",
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
    _sync_threshold(force=True)
    return {"threshold": detector.threshold,
            "artefact_threshold": _ARTEFACT_THRESHOLD,
            "percentile": detector.meta.get("percentile"),
            "metric": detector.meta.get("metric", "recon_error"),
            "store": store.backend()}


@app.post("/admin/settings")
def update_settings(body: ThresholdUpdate, authorization: str | None = Header(default=None)) -> dict:
    """Admin-only: change the live detection threshold (operators cannot)."""
    admin = _require_admin(authorization)
    old = detector.threshold
    store.set_setting("threshold", repr(float(body.threshold)), admin["sub"])
    _sync_threshold(force=True)
    detector.meta["calibration"] = "adjusted live by admin"
    drift.reset()  # a new operating point starts a new monitoring period
    return {"threshold": detector.threshold, "previous": old, "updated": True,
            "shared_with_all_replicas": store.IS_POSTGRES}


@app.delete("/admin/settings/threshold")
def reset_threshold(authorization: str | None = Header(default=None)) -> dict:
    """Admin-only: drop the override and return to the threshold in the model artefact."""
    _require_admin(authorization)
    store.delete_setting("threshold")
    _sync_threshold(force=True)
    drift.reset()
    return {"threshold": detector.threshold, "source": "artefact"}


@app.get("/drift")
def drift_status() -> dict:
    """Drift monitor for this replica: CUSUM on the alarm rate against its calibrated target."""
    return drift.status()


@app.post("/admin/drift/reset")
def drift_reset(authorization: str | None = Header(default=None)) -> dict:
    """Admin-only: acknowledge a drift signal and restart monitoring."""
    _require_admin(authorization)
    drift.reset()
    return drift.status()


# --- serve the ICS Guardian website (mounted last so API routes win) -------- #
import os as _os  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_WEB = _Path(_os.getenv("WEB_DIR", _Path(__file__).parent / "web"))
if _WEB.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="site")
