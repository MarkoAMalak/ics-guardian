#!/usr/bin/env python3
"""
benchmark_inference.py — reproduce the scoring-latency figures quoted in the report.

What is measured
----------------
The compute cost of one forward pass through the deployed dense autoencoder plus
the threshold comparison, i.e. exactly the work the detector does per reading.
HTTP parsing, JSON serialisation, network transit and Kubernetes ingress are all
excluded, so these numbers are a floor on end-to-end latency, not a substitute
for it. The report labels them "compute-only" for the same reason.

The forward pass here is a plain NumPy re-implementation driven by the exported
weight files, which means the benchmark does not depend on PyTorch being present
and cannot silently drift away from what actually ships.

Usage
-----
    python benchmark_inference.py                    # both plants, default sizes
    python benchmark_inference.py --repeats 5000     # tighter estimate
    python benchmark_inference.py --batch 500
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ART = HERE.parent / "03_model_artifacts"
MODELS = {"swat": "model_web.json", "wadi": "model_web_wadi.json"}


def load(name: str) -> dict:
    with (ART / MODELS[name]).open("r", encoding="utf-8") as fh:
        model = json.load(fh)
    model["_mean"] = np.asarray(model["mean"], dtype=np.float64)
    model["_scale"] = np.asarray(model["scale"], dtype=np.float64)
    model["_layers"] = [
        (np.asarray(layer["W"], dtype=np.float64),
         np.asarray(layer["b"], dtype=np.float64),
         (layer.get("act") or "").lower())
        for layer in model["layers"]
    ]
    return model


def score(model: dict, x: np.ndarray) -> np.ndarray:
    """Per-row reconstruction error for a (n, n_features) batch of raw readings."""
    z = (x - model["_mean"]) / model["_scale"]
    h = z
    for w, b, act in model["_layers"]:
        h = h @ (w.T if w.shape[1] == h.shape[-1] else w) + b
        if act == "relu":
            h = np.maximum(h, 0.0)
    return np.mean((h - z) ** 2, axis=-1)


def make_inputs(model: dict, batch: int) -> tuple[np.ndarray, str]:
    """Build a benchmark batch, preferring real plant rows over synthetic ones.

    Synthetic rows drawn independently per channel are *not* representative of
    plant data: normal operation is a low-dimensional manifold, so perturbing
    every channel at once produces a reading the plant could never occupy. That
    does not change the arithmetic cost of a forward pass, which is what this
    script measures, but using real rows where they exist keeps the ReLU branch
    pattern realistic.
    """
    feats = model["features"]
    csv_path = HERE / "swat_test_mixed.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if rows and all(f in rows[0] for f in feats):
            real = np.asarray([[float(r[f]) for f in feats] for r in rows], dtype=np.float64)
            reps = int(np.ceil(batch / len(real)))
            return np.tile(real, (reps, 1))[:batch], f"real rows from {csv_path.name}"

    rng = np.random.default_rng(20260729)
    synth = model["_mean"] + rng.normal(0, 1, size=(batch, len(feats))) * model["_scale"]
    return synth, "synthetic rows (no real sample available for this plant)"


def bench(name: str, repeats: int, batch: int) -> None:
    model = load(name)
    n_feat = len(model["features"])
    tau = float(model["threshold"])

    shapes = [tuple(w.shape) for w, _, _ in model["_layers"]]
    acts = [a or "linear" for _, _, a in model["_layers"]]
    print(f"\n=== {name.upper()} ===")
    print(f"  features {n_feat}   threshold {tau}")
    print(f"  layer shapes {shapes}")
    print(f"  activations  {acts}")

    many, source = make_inputs(model, batch)
    one = many[:1]
    print(f"  input          : {source}")

    for _ in range(200):                      # warm-up: let NumPy settle
        score(model, one)

    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        s = score(model, one)
        _ = bool(s[0] >= tau)
        samples.append((time.perf_counter() - t0) * 1000.0)

    samples.sort()
    mean_ms = statistics.fmean(samples)
    p50 = samples[len(samples) // 2]
    p95 = samples[int(len(samples) * 0.95)]

    # Time the batch several times and report the median, so a single allocation
    # stall does not decide the headline throughput number.
    score(model, many)                        # warm the allocation path
    batch_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        errs = score(model, many)
        batch_times.append((time.perf_counter() - t0) * 1000.0)
    batch_ms = statistics.median(batch_times)
    flagged = int(np.sum(errs >= tau))

    print(f"  single reading : mean {mean_ms:.3f} ms   p50 {p50:.3f} ms   p95 {p95:.3f} ms"
          f"   ({repeats} repeats)")
    print(f"  batch of {batch:<4d}  : {batch_ms:.2f} ms median of 20"
          f"  ->  {batch / (batch_ms / 1000.0):,.0f} readings/s")
    print(f"  flagged        : {flagged}/{batch} rows above threshold "
          "(depends on the input mix, not on timing)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repeats", type=int, default=2000)
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--model", choices=sorted(MODELS) + ["all"], default="all")
    args = ap.parse_args()

    print("Compute-only detector benchmark (excludes HTTP, serialisation, network).")
    targets = sorted(MODELS) if args.model == "all" else [args.model]
    for name in targets:
        bench(name, args.repeats, args.batch)
    print("\nNote: absolute timings depend on the host CPU. The report quotes the")
    print("range observed on the project's own build machine, not a guarantee.")


if __name__ == "__main__":
    main()
