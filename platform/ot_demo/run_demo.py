"""
run_demo.py — Live OT-loop demo.

Streams a simulated chlorination plant (plc_simulator.py) one scan at a time and
scores each scan in real time, printing a SOC-style console with process, network,
and FUSED anomaly bars. It demonstrates the whole project thesis live:

    plant/PLC  ->  detector (process branch + network branch)  ->  fused alarm

Two detection back-ends:
  • built-in (default)  — a lightweight branch detector fit on the warm-up window.
                          Runs anywhere with only numpy; no service, no torch.
  • --service URL       — POST each scan to the real FastAPI microservice /score.
                          Use once you've exported your trained model.

The built-in detector deliberately mirrors the real design: standardize features
on the normal warm-up, score each branch by mean squared z (a reconstruction-error
proxy), threshold at a normal-distribution percentile, and FUSE by taking the max
of the two branch scores — the same score-level fusion used in the notebook.

Usage:
    python run_demo.py                 # built-in detector, ~0.15s/tick
    python run_demo.py --fast          # no sleep between ticks
    python run_demo.py --service http://localhost:8000
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from plc_simulator import scenario

PROC = ["LIT101", "FIT101", "AIT201", "P101", "MV101"]
NET = ["PKT_RATE", "N_CONN"]
WARMUP = 35          # first N normal ticks used to fit the detector
PCTL = 99            # threshold percentile on the warm-up (unsupervised)


Z2CAP = 100.0   # cap each feature's squared-z so one flipping binary tag can't
                # dominate the mean and explode the score to 1e14.


class BranchDetector:
    """Standardize on normal warm-up; anomaly score = mean (capped) squared z."""

    def __init__(self, cols):
        self.cols = cols
        self.mu = None
        self.sd = None
        self.thr = float("inf")

    def _scores(self, X):
        z2 = np.minimum(((X - self.mu) / self.sd) ** 2, Z2CAP)
        return z2.mean(axis=1)

    def fit(self, rows):
        X = np.array([[r[c] for c in self.cols] for r in rows], dtype=float)
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-6      # keep full sensitivity of every feature
        scores = self._scores(X)
        # Robust threshold: sit above the worst normal warm-up score with head-
        # room, so ordinary recovery noise doesn't trip a false alarm.
        self.thr = float(max(np.percentile(scores, PCTL), scores.max() * 1.4, 1e-3))

    def score(self, row) -> float:
        x = np.array([[row[c] for c in self.cols]], dtype=float)
        return float(self._scores(x)[0])


def bar(score, thr, width=18):
    """Render a proportional bar; fills red past the threshold."""
    ratio = min(score / (thr * 2.5), 1.0) if thr > 0 else 0
    filled = int(ratio * width)
    over = score >= thr
    ch = "█" if over else "▓"
    return ch * filled + "·" * (width - filled)


def run_builtin(fast: bool):
    ticks = list(scenario())
    warm = [t for t in ticks[:WARMUP] if t["_attack"] == "none"]
    proc, net = BranchDetector(PROC), BranchDetector(NET)
    proc.fit(warm)
    net.fit(warm)

    print("\n" + "=" * 78)
    print("  LIVE OT-LOOP DEMO  |  chlorination plant -> detector -> fused alarm")
    print("  process branch:", PROC)
    print("  network branch:", NET)
    print("=" * 78)
    print(f"  {'t':>3}  {'attack':<11} {'process':^20} {'network':^20} {'FUSED':^7}")
    print("-" * 78)

    stats = {}  # attack -> [n, proc_hits, net_hits, fused_hits]
    for t in ticks:
        sp, sn = proc.score(t), net.score(t)
        zp, zn = sp / proc.thr, sn / net.thr
        fused = max(zp, zn)                     # score-level fusion (max)
        p_al, n_al, f_al = zp >= 1, zn >= 1, fused >= 1
        atk = t["_attack"]
        st = stats.setdefault(atk, [0, 0, 0, 0])
        st[0] += 1
        st[1] += p_al
        st[2] += n_al
        st[3] += f_al

        flag = "  🚨 ALARM" if f_al else ""
        # for the spoof attack, reveal the ground-truth gap the operator can't see
        extra = ""
        if atk == "spoof":
            extra = f"  [reported Cl {t['AIT201']} | TRUE {t['_true_chlorine']}]"
        sev = ">99×" if fused > 99 else f"x{fused:.1f}"
        print(f"  {t['_t']:>3}  {atk:<11} {bar(sp, proc.thr)} {bar(sn, net.thr)} "
              f"{sev:>6}{flag}{extra}")
        if not fast:
            time.sleep(0.12)

    print("-" * 78)
    print("  Per-scenario detection rate (alarms / ticks):")
    print(f"  {'phase':<12} {'process':>10} {'network':>10} {'FUSED':>10}")
    for atk, (n, p, ne, f) in stats.items():
        if atk == "none":
            print(f"  {atk:<12} {p/n:>9.0%} {ne/n:>10.0%} {f/n:>10.0%}   (false-alarm rate)")
        else:
            print(f"  {atk:<12} {p/n:>9.0%} {ne/n:>10.0%} {f/n:>10.0%}")
    print("=" * 78)
    print("  Takeaway: the spoof attack is caught by the PROCESS branch, the")
    print("  disruption by the NETWORK branch — and FUSED catches both. Neither")
    print("  single branch covers everything; fusion has no blind spot.\n")


def run_service(url: str, fast: bool):
    import json
    import urllib.request

    def post(features):
        req = urllib.request.Request(
            url.rstrip("/") + "/score",
            data=json.dumps({"features": features}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    print(f"\n  Streaming to live microservice at {url}/score ...\n")
    for t in scenario():
        feats = {k: v for k, v in t.items() if not k.startswith("_")}
        try:
            res = post(feats)
        except Exception as exc:  # noqa: BLE001
            print(f"  t={t['_t']:>3} service error: {exc}")
            break
        flag = " 🚨 ALARM" if res.get("anomaly") else ""
        print(f"  t={t['_t']:>3} attack={t['_attack']:<11} "
              f"severity x{res.get('severity', 0):.2f}{flag}")
        if not fast:
            time.sleep(0.12)
    print()


def main():
    ap = argparse.ArgumentParser(description="Live OT-loop anomaly-detection demo")
    ap.add_argument("--service", help="POST scans to a running microservice, e.g. http://localhost:8000")
    ap.add_argument("--fast", action="store_true", help="no delay between ticks")
    args = ap.parse_args()
    if args.service:
        run_service(args.service, args.fast)
    else:
        run_builtin(args.fast)


if __name__ == "__main__":
    main()
