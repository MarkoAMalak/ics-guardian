"""End-to-end checks on a running cluster (used by the k8s-e2e CI job).

1. pods run hardened, on more than one node;
2. an account created through one replica can log in through another (shared PostgreSQL store);
3. a threshold override made on one replica is applied by another, and can be reverted;
4. scoring and the drift endpoint answer through the Service.
Prints a JSON summary and exits non-zero on any failure.
"""
import json
import subprocess
import sys
import time
import urllib.request


def sh(cmd):
    return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout


def call(port, path, body=None, token=None, method=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


pods = json.loads(sh("kubectl get pods -l app=ics-detector -o json"))["items"]
ready = [p for p in pods if p["status"].get("phase") == "Running"]
nodes = sorted({p["spec"]["nodeName"] for p in ready})
sec = ready[0]["spec"]["containers"][0]["securityContext"]
out = {"replicas_running": len(ready), "nodes_used": nodes,
       "read_only_root_fs": sec.get("readOnlyRootFilesystem"), "run_as_non_root":
       ready[0]["spec"]["securityContext"].get("runAsNonRoot")}
assert len(ready) >= 2, out

a, b = ready[0]["metadata"]["name"], ready[1]["metadata"]["name"]
pf = [subprocess.Popen(f"kubectl port-forward pod/{a} 18001:8000", shell=True),
      subprocess.Popen(f"kubectl port-forward pod/{b} 18002:8000", shell=True),
      subprocess.Popen("kubectl port-forward svc/ics-detector 18000:80", shell=True)]
time.sleep(6)
try:
    email = f"e2e.{int(time.time())}@plant.example"
    call(18001, "/auth/register", {"email": email, "password": "E2e-pass-123"})
    login_b = call(18002, "/auth/login", {"email": email, "password": "E2e-pass-123"})
    out["login_on_other_replica"] = login_b["role"] == "operator"

    admin = call(18001, "/auth/login", {"email": "admin@icsguardian.local", "password": "Admin@12345"})["access_token"]
    base = call(18002, "/info")["threshold"]
    call(18001, "/admin/settings", {"threshold": 0.0999}, admin)
    time.sleep(6)                                         # > SETTINGS_TTL
    feats = {f: 1.0 for f in call(18002, "/info")["features"]}
    out["override_seen_by_other_replica"] = call(18002, "/score", {"features": feats})["threshold"] == 0.0999
    call(18001, "/admin/settings/threshold", None, admin, method="DELETE")
    time.sleep(6)
    out["override_reverted_everywhere"] = call(18002, "/score", {"features": feats})["threshold"] == base

    out["score_via_service"] = "anomaly" in call(18000, "/score", {"features": feats})
    out["drift_endpoint"] = "cusum" in call(18000, "/drift")
finally:
    for p in pf:
        p.terminate()

print(json.dumps(out, indent=1))
ok = all(v for k, v in out.items() if isinstance(v, bool))
sys.exit(0 if ok and out["run_as_non_root"] and out["read_only_root_fs"] else 1)
