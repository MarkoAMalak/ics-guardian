"""
load_test.py - drive the deployed detector and watch the metrics move.

Sends a stream of scoring requests (a realistic mix of normal and attack
snapshots) to the running service, then reads /metrics and prints the
Prometheus counters so you can see them climb. Great for the observability demo.

Usage:
    pip install requests
    python load_test.py                       # localhost:8000, 300 requests
    python load_test.py http://localhost:8000 500
"""
import sys, json, os, time

try:
    import requests
except ImportError:
    sys.exit("Please run:  pip install requests")

BASE = (sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000")
N    = int(sys.argv[2]) if len(sys.argv) > 2 else 300

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "sample_payloads_real.json"), encoding="utf-8"))
normal  = S["realistic_normal"]["features"]
attacks = [S[k]["features"] for k in ("real_attack_1", "real_attack_2", "real_attack_3") if k in S]

# health check first
try:
    h = requests.get(f"{BASE}/health", timeout=10).json()
except Exception as e:
    sys.exit(f"Cannot reach {BASE} - is the container running?  ({e})")
if not h.get("model_loaded"):
    sys.exit("Service is up but model is not loaded (artifacts missing).")
print(f"Target {BASE}  |  model_loaded=True  |  sending {N} requests...\n")

def metrics():
    txt = requests.get(f"{BASE}/metrics", timeout=10).text
    out = {}
    for line in txt.splitlines():
        if line and not line.startswith("#"):
            parts = line.split()
            if len(parts) == 2:
                try: out[parts[0]] = float(parts[1])
                except ValueError: pass
    return out

before = metrics()
t0 = time.time()
sent = anom = 0
for i in range(N):
    # ~1 in 6 requests is an attack
    feats = attacks[i % len(attacks)] if (attacks and i % 6 == 0) else normal
    try:
        r = requests.post(f"{BASE}/score", json={"features": feats}, timeout=10).json()
        sent += 1
        if r.get("anomaly"): anom += 1
    except Exception:
        pass
    if (i + 1) % 50 == 0:
        print(f"  sent {i+1}/{N}  (anomalies so far: {anom})")
dt = time.time() - t0

after = metrics()
def d(k): return after.get(k, 0) - before.get(k, 0)

print(f"\nDone in {dt:.1f}s  ->  {sent/dt:.0f} req/s from this client\n")
print("Prometheus counters (from /metrics):")
print(f"  ics_requests_total     {after.get('ics_requests_total',0):.0f}   (+{d('ics_requests_total'):.0f} this run)")
print(f"  ics_anomalies_total    {after.get('ics_anomalies_total',0):.0f}   (+{d('ics_anomalies_total'):.0f} this run)")
print(f"  ics_errors_total       {after.get('ics_errors_total',0):.0f}")
lat = after.get('ics_latency_seconds_sum',0); req = max(after.get('ics_requests_total',1),1)
print(f"  ics_latency_seconds_sum {lat:.3f}   ->  avg {1000*lat/req:.2f} ms / request")
print(f"  ics_model_loaded       {after.get('ics_model_loaded',0):.0f}")
print(f"\nObserved anomaly rate this run: {100*anom/max(sent,1):.1f}%")
print(f"\nNow open  {BASE}/metrics  in a browser to see the raw counters,")
print("and  http://localhost:9090  (Prometheus) to graph them, e.g.:")
print("    ics_requests_total")
print("    rate(ics_requests_total[1m])")
print("    ics_anomalies_total / ics_requests_total")
print("    rate(ics_latency_seconds_sum[5m]) / rate(ics_requests_total[5m])")
