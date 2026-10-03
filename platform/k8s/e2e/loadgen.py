"""Closed-loop load generator (standard library only) used inside the e2e cluster."""
import json
import os
import threading
import time
import urllib.request

TARGET = os.environ["TARGET"]
THREADS, DURATION = int(os.environ["THREADS"]), float(os.environ["DURATION"])
feats = json.load(urllib.request.urlopen(TARGET.rsplit("/", 1)[0] + "/info", timeout=10))["features"]
body = json.dumps({"features": {f: 1.0 for f in feats}}).encode()
lat, errors, lock = [], [0], threading.Lock()
stop = time.time() + DURATION


def worker():
    while time.time() < stop:
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(TARGET, data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
            with lock:
                lat.append(time.perf_counter() - t0)
        except Exception:  # count every failed request
            with lock:
                errors[0] += 1


ts = [threading.Thread(target=worker) for _ in range(THREADS)]
[t.start() for t in ts]
[t.join() for t in ts]
lat.sort()
q = lambda p: round(1000 * lat[min(len(lat) - 1, int(p * len(lat)))], 2) if lat else None  # noqa: E731
print(json.dumps({"requests": len(lat), "errors": errors[0], "rps": round(len(lat) / DURATION, 1),
                  "p50_ms": q(0.50), "p95_ms": q(0.95), "p99_ms": q(0.99)}))
