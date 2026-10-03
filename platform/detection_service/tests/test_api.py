"""
Smoke + contract tests for the detection service. Runs in CI (pytest).

These do not require trained artifacts: when the model is absent the service must
still start, /health must return model_loaded=false, and /score must return 503.
When artifacts ARE present the same tests assert a well-formed scoring response.
"""

from fastapi.testclient import TestClient

import app as service

client = TestClient(service.app)


def test_health_always_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exposed():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "ics_requests_total" in r.text


def test_score_contract():
    # Build a sample from the model's real feature list if loaded, else a dummy.
    if service.detector.ready:
        sample = {f: 0.0 for f in service.detector.features}
        r = client.post("/score", json={"features": sample})
        assert r.status_code == 200
        body = r.json()
        assert {"recon_error", "threshold", "severity", "anomaly"} <= set(body)
        assert isinstance(body["anomaly"], bool)
    else:
        r = client.post("/score", json={"features": {"x": 1.0}})
        assert r.status_code == 503


def test_missing_feature_is_422_when_loaded():
    if not service.detector.ready:
        return
    r = client.post("/score", json={"features": {"definitely_not_a_feature": 1.0}})
    assert r.status_code == 422
