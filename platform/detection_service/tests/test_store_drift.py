"""Tests for the shared settings store, the cross-replica threshold and the drift monitor.

Run against SQLite by default. When AUTH_DB_URL points at PostgreSQL (as in CI), the same tests
exercise the shared PostgreSQL backend.
"""
import random

from fastapi.testclient import TestClient

import app as service
import store
from drift import DriftMonitor, calibrate_h

client = TestClient(service.app)


def _admin_headers():
    service.seed_users()
    r = client.post("/auth/login", json={"email": "admin@icsguardian.local", "password": "Admin@12345"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_settings_roundtrip():
    store.init_schema()
    store.set_setting("unit_test_key", "1.5", "tester")
    assert store.get_setting("unit_test_key") == "1.5"
    store.set_setting("unit_test_key", "2.5", "tester")          # upsert
    assert store.get_setting("unit_test_key") == "2.5"
    store.delete_setting("unit_test_key")
    assert store.get_setting("unit_test_key") is None


def test_threshold_override_is_shared_and_reversible():
    if not service.detector.ready:
        return
    h = _admin_headers()
    original = service.detector.threshold
    r = client.post("/admin/settings", json={"threshold": 0.5}, headers=h)
    assert r.status_code == 200 and r.json()["threshold"] == 0.5
    # a second replica only sees the shared store: simulate it by resetting local state
    service.detector.threshold = original
    service._sync_threshold(force=True)
    assert service.detector.threshold == 0.5
    r = client.delete("/admin/settings/threshold", headers=h)
    assert r.status_code == 200 and r.json()["source"] == "artefact"
    assert service.detector.threshold == service._ARTEFACT_THRESHOLD


def test_operator_cannot_change_threshold():
    service.seed_users()
    r = client.post("/auth/login", json={"email": "operator@icsguardian.local", "password": "Operator@12345"})
    tok = r.json()["access_token"]
    r = client.post("/admin/settings", json={"threshold": 0.5}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_drift_monitor_quiet_at_target_rate():
    rng = random.Random(0)
    m = DriftMonitor(p0=0.01, k=0.01, h=2.0, block=60)
    for _ in range(300_000):
        m.update(rng.random() < 0.01)
    assert not m.status()["drift_suspected"]


def test_drift_monitor_signals_when_rate_rises():
    rng = random.Random(1)
    m = DriftMonitor(p0=0.01, k=0.01, h=2.0, block=60)
    for _ in range(6_000):
        m.update(rng.random() < 0.01)
    for _ in range(20_000):
        m.update(rng.random() < 0.10)
    st = m.status()
    assert st["drift_suspected"] and st["first_signal_at_reading"] > 6_000


def test_calibrate_h_limits_false_signals():
    rng = random.Random(2)
    alarms = []
    for _ in range(400):                       # bursty normal data: 1% of readings in bursts
        burst = rng.random() < 0.05
        alarms += [1 if (burst and rng.random() < 0.2) else 0 for _ in range(600)]
    h = calibrate_h(alarms, p0=0.01, block=60, max_signals_per_day=1.0, readings_per_day=86400)
    m, n = DriftMonitor(p0=0.01, k=0.01, h=h, block=60), 0
    for a in alarms:
        if m.update(bool(a)):
            n += 1
            m.reset()
    assert n <= max(1, len(alarms) / 86400)


def test_drift_endpoint_and_metrics():
    r = client.get("/drift")
    assert r.status_code == 200 and "cusum" in r.json()
    assert "ics_drift_cusum" in client.get("/metrics").text
