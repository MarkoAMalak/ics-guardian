"""
test_client.py - hit the deployed ICS detection service and see it work.

Usage:
    python test_client.py                      # tests http://localhost:8000
    python test_client.py http://YOUR_URL      # tests a deployed URL

It calls /health, then POSTs the curated normal reading and the real SWaT attack
rows from sample_payloads_real.json to /score and prints the verdicts.
Only needs the `requests` library:  pip install requests
"""
import sys, json, os

try:
    import requests
except ImportError:
    sys.exit("Please run:  pip install requests")

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
HERE = os.path.dirname(os.path.abspath(__file__))
samples = json.load(open(os.path.join(HERE, "sample_payloads_real.json"), encoding="utf-8"))

print(f"Target: {BASE}\n")

# 1) health
h = requests.get(f"{BASE}/health", timeout=10).json()
print("GET /health ->", h)
if not h.get("model_loaded"):
    print("\n! model_loaded is false: the artifacts are not in detection_service/artifacts/.")
    sys.exit(1)

# 2) info
info = requests.get(f"{BASE}/info", timeout=10).json()
print(f"GET /info   -> {info['n_features']} features, threshold={info['threshold']:.5f}\n")

# 3) score the curated samples
for name in [k for k in samples if isinstance(samples[k], dict) and "features" in samples[k]]:
    feats = samples[name]["features"]
    exp = samples[name]["expected"]
    r = requests.post(f"{BASE}/score", json={"features": feats}, timeout=10).json()
    flag = "ANOMALY" if r["anomaly"] else "normal"
    print(f"POST /score  [{name:14}] -> {flag:8} "
          f"severity={r['severity']:.2f}  recon_error={r['recon_error']:.5f}  "
          f"(expected anomaly={exp['anomaly']})")

print("\nDone. Open", BASE + "/docs", "for the interactive Swagger UI.")
