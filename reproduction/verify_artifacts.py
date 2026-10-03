#!/usr/bin/env python3
"""
verify_artifacts.py — independent verification of the shipped detector artefacts.

Why this script exists
----------------------
The report makes concrete claims about the deployed model: how many features it
consumes, what the encoder/decoder shapes are, which activations are used, and
what the calibrated decision threshold is. This script re-derives every one of
those claims directly from the artefacts that ship with the submission, using
nothing but the Python standard library and NumPy. No PyTorch, no training data
and no notebook run are required, so a marker can check the claims on a bare
machine in a few seconds.

It also re-implements the forward pass independently of the service code and
replays a small set of real, labelled SWaT rows through it. That is a smoke test
of the serving path, not an evaluation: the fifty rows in swat_test_mixed.csv
were selected to exercise the demo, so a perfect score on them says the plumbing
is correct and says nothing about detection quality. The honest headline numbers
(ROC-AUC 0.9416, PR-AUC 0.8020, point-adjusted F1 0.81) come from the full held-out test
set in the training notebook, not from this file.

Usage
-----
    python verify_artifacts.py                     # verify both plants
    python verify_artifacts.py --model swat        # verify one plant only

Exit code is 0 when every structural check passes, 1 otherwise, so the script can
also be dropped into CI as a regression guard on the artefacts.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ART = HERE.parent / "03_model_artifacts"

MODELS = {
    "swat": ("model_web.json", 45, 0.063966),
    "wadi": ("model_web_wadi.json", 50, 0.30814058),
}


def load(path: pathlib.Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def forward(model: dict, x: np.ndarray) -> np.ndarray:
    """Per-row reconstruction error for a (n, n_features) batch of raw readings."""
    mean = np.asarray(model["mean"], dtype=np.float64)
    scale = np.asarray(model["scale"], dtype=np.float64)
    h = z = (x - mean) / scale
    for layer in model["layers"]:
        w = np.asarray(layer["W"], dtype=np.float64)
        b = np.asarray(layer["b"], dtype=np.float64)
        # exported weights are stored as (out, in); transpose when needed
        h = h @ (w.T if w.shape[1] == h.shape[-1] else w) + b
        if (layer.get("act") or "").lower() == "relu":
            h = np.maximum(h, 0.0)
    return np.mean((h - z) ** 2, axis=-1)


# The service flags a reading when err >= threshold (see model.py). This module
# uses the same comparison so that a row sitting exactly on the threshold is
# classified identically here and in production.


def structural_checks(name: str, model: dict, want_features: int, want_tau: float) -> bool:
    ok = True
    feats = model["features"]
    tau = float(model["threshold"])

    print(f"  features           : {len(feats)}  (first three: {feats[:3]})")
    print(f"  decision threshold : {tau}")
    print("  network:")
    for i, layer in enumerate(model["layers"]):
        w = np.asarray(layer["W"])
        b = np.asarray(layer["b"])
        print(f"    layer {i}: W{tuple(w.shape)}  b{tuple(b.shape)}  "
              f"act={layer.get('act') or 'linear'}")

    if len(feats) != want_features:
        print(f"  [FAIL] expected {want_features} features, found {len(feats)}")
        ok = False
    if not np.isclose(tau, want_tau, rtol=0, atol=1e-8):
        print(f"  [FAIL] expected threshold {want_tau}, found {tau}")
        ok = False
    if len(model["mean"]) != len(feats) or len(model["scale"]) != len(feats):
        print("  [FAIL] standardisation vectors do not match the feature list")
        ok = False
    if np.any(np.asarray(model["scale"]) <= 0):
        print("  [FAIL] non-positive scale entry would make standardisation undefined")
        ok = False

    # A grossly out-of-distribution reading (ten standard deviations away on every
    # channel) must land above the threshold, or the detector is inert.
    mean = np.asarray(model["mean"], dtype=np.float64)
    scale = np.asarray(model["scale"], dtype=np.float64)
    far = forward(model, (mean + 10.0 * scale)[None, :])[0]
    print(f"  error at mean + 10 sd : {far:.4f}   (threshold {tau})")
    if far < tau:
        print("  [FAIL] a 10-sigma excursion would not raise an alarm")
        ok = False

    # Diagnostic, deliberately NOT a pass/fail criterion. Several SWaT channels are
    # discrete actuator states (a valve is open or shut, never half-way), so the
    # per-feature mean is a vector the plant can never actually occupy. It is
    # therefore unsurprising, and worth stating plainly, that the mean vector can
    # score above the threshold on SWaT. Normality here is a manifold, not a point.
    at_mean = forward(model, mean[None, :])[0]
    verdict = "at or above" if at_mean >= tau else "below"
    print(f"  error at feature-wise mean : {at_mean:.6f}  ({verdict} threshold; "
          "informational only, see note in the code)")
    return ok


def smoke_test_swat(model: dict) -> bool:
    """Replay real labelled rows and the curated payloads through the forward pass."""
    ok = True
    feats = model["features"]
    tau = float(model["threshold"])

    csv_path = HERE / "swat_test_mixed.csv"
    if csv_path.exists():
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        x = np.asarray([[float(r[f]) for f in feats] for r in rows], dtype=np.float64)
        y = np.asarray([0 if r["Normal/Attack"].strip().lower() == "normal" else 1
                        for r in rows])
        pred = (forward(model, x) >= tau).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        print(f"\n  smoke set ({len(y)} labelled rows, {int(y.sum())} attacks):")
        print(f"    TP {tp}   FP {fp}   FN {fn}   TN {tn}")
        print("    NOTE: this set is curated for the demo. It confirms the serving")
        print("    path is wired correctly; it is not a measure of detection quality.")
        if tp == 0:
            print("  [FAIL] no attack row was flagged — the serving path is broken")
            ok = False

    payload_path = HERE / "sample_payloads_real.json"
    if payload_path.exists():
        payloads = load(payload_path)
        print("\n  curated payloads:")
        for key, body in payloads.items():
            if not isinstance(body, dict) or "features" not in body:
                continue
            x = np.asarray([body["features"][f] for f in feats], dtype=np.float64)[None, :]
            err = float(forward(model, x)[0])
            got = err >= tau
            want = body.get("expected", {}).get("anomaly")
            mark = "ok" if want is None or bool(want) == got else "MISMATCH"
            print(f"    {key:<18} error {err:>10.5f}   anomaly={str(got):<5}  {mark}")
            if want is not None and bool(want) != got:
                ok = False
    return ok


def check(name: str, filename: str, want_features: int, want_tau: float) -> bool:
    path = ART / filename
    print(f"\n=== {name.upper()} ===")
    print(f"  artefact           : {filename}")
    if not path.exists():
        print(f"  [FAIL] artefact missing at {path}")
        return False

    model = load(path)
    ok = structural_checks(name, model, want_features, want_tau)
    if name == "swat":
        ok = smoke_test_swat(model) and ok

    print(f"  result             : {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", choices=sorted(MODELS) + ["all"], default="all")
    args = ap.parse_args()

    targets = sorted(MODELS) if args.model == "all" else [args.model]
    results = [check(name, *MODELS[name]) for name in targets]

    print("\n" + "-" * 62)
    print("VERIFICATION " + ("PASSED" if all(results) else "FAILED")
          + f"  ({sum(results)}/{len(results)} artefacts clean)")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
