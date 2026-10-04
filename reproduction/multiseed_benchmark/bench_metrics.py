"""Metrics for the multi-seed benchmark, computed from the saved scores with the notebook's own
evaluation code. Adds the same F1 values without point adjustment (PA).

Outputs bench/metrics_per_seed.csv, bench/metrics_summary.csv and bench/metrics_summary.md.
"""
import glob
import json
import os
import re

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
NOTEBOOK = os.getenv("BENCH_NOTEBOOK", os.path.join(HERE, "..", "..", "notebooks", "SWaT_Anomaly_Detection.ipynb"))
nb = json.load(open(NOTEBOOK))
code = {i: "".join(c["source"]) for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"}
ns = {"__name__": "nb", "display": print}
# config, loading/preprocessing and evaluation cells
for i in (3, 5, 13):
    exec(compile(code[i], f"cell{i}", "exec"), ns)
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

CFG = ns["CONFIG"]
POINT = {"IsolationForest", "DenseAE"}
ENSEMBLE = ["LSTM_AE", "TranAD", "GDN"]
ORDER = ["IsolationForest", "DenseAE", "LSTM_AE", "USAD", "TranAD", "GDN", "Ensemble"]


def f1s(sv, st, y, pa):
    cfg = {**CFG, "POINT_ADJUST": pa}
    thr = np.percentile(sv, cfg["THRESHOLD_PERCENTILE"])
    _, _, f1_val = ns["_prf"](y, (st > thr).astype(int), cfg)
    best = ns["best_f1_threshold"](st, y, cfg)
    return f1_val, best["f1"]


def z(a):
    return (a - a.mean()) / (a.std() + 1e-8)


rows = []
for ds in ("SWaT", "WADI"):
    d = os.path.join(os.getenv("BENCH_OUT", os.path.join(HERE, "bench")), ds)
    if not os.path.exists(os.path.join(d, "labels.npz")):
        continue
    lab = np.load(os.path.join(d, "labels.npz"))
    scores = {}
    for f in glob.glob(os.path.join(d, "*_seed*.npz")):
        m, s = re.match(r"(.+)_seed(-?\d+)\.npz", os.path.basename(f)).groups()
        z_ = np.load(f)
        scores[(m, int(s))] = (z_["sv"], z_["st"], float(z_["seconds"]))
    seeds = sorted({s for _, s in scores})
    for s in seeds:
        if all((m, s) in scores for m in ENSEMBLE):
            sv = np.mean([z(scores[(m, s)][0]) for m in ENSEMBLE], axis=0)
            st = np.mean([z(scores[(m, s)][1]) for m in ENSEMBLE], axis=0)
            scores[("Ensemble", s)] = (sv, st, np.nan)
    for (m, s), (sv, st, sec) in sorted(scores.items()):
        y = lab["y_point"] if m in POINT else lab["y_win"]
        f1v_pa, f1b_pa = f1s(sv, st, y, True)
        f1v_np, f1b_np = f1s(sv, st, y, False)
        rows.append({"dataset": ds, "model": m, "seed": s,
                     "ROC_AUC": roc_auc_score(y, st), "PR_AUC": average_precision_score(y, st),
                     "F1_val_PA": f1v_pa, "F1_best_PA": f1b_pa,
                     "F1_val_noPA": f1v_np, "F1_best_noPA": f1b_np, "train_seconds": sec})
        print(ds, m, s, f"ROC={rows[-1]['ROC_AUC']:.3f} PR={rows[-1]['PR_AUC']:.3f}", flush=True)

df = pd.DataFrame(rows)
OUT = os.getenv("BENCH_OUT", os.path.join(HERE, "bench"))
df.to_csv(os.path.join(OUT, "metrics_per_seed.csv"), index=False)
mets = ["ROC_AUC", "PR_AUC", "F1_val_PA", "F1_best_PA", "F1_val_noPA", "F1_best_noPA"]
summ, lines = [], ["| Dataset | Model | n | " + " | ".join(mets) + " |", "|" + "---|" * (3 + len(mets))]
for ds in ("SWaT", "WADI"):
    for m in ORDER:
        g = df[(df.dataset == ds) & (df.model == m)]
        if g.empty:
            continue
        r = {"dataset": ds, "model": m, "n_seeds": len(g)}
        cells = []
        for c in mets:
            mu, sd = g[c].mean(), (g[c].std(ddof=1) if len(g) > 1 else 0.0)
            r[c + "_mean"], r[c + "_std"] = mu, sd
            cells.append(f"{mu:.3f} ± {sd:.3f}")
        summ.append(r)
        lines.append(f"| {ds} | {m} | {len(g)} | " + " | ".join(cells) + " |")
pd.DataFrame(summ).to_csv(os.path.join(OUT, "metrics_summary.csv"), index=False)
open(os.path.join(OUT, "metrics_summary.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
