"""Full multi-seed benchmark: every detector of notebooks/SWaT_Anomaly_Detection.ipynb, several seeds.

The notebook's own cells (preprocessing, models, training loops, scoring) are executed verbatim;
only memory handling is changed (windows are built as views and scaled lazily), which does not
change any value. For each (dataset, model, seed) the raw validation and test scores are saved,
so every metric (with and without point adjustment) is computed afterwards from the same scores.
The run is resumable: finished (dataset, model, seed) files are skipped.

usage: python run_bench.py <SWaT|WADI> <seed> [<seed> ...] [--models A,B,...]
"""
import gc
import json
import os
import random
import sys
import time
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NOTEBOOK = os.getenv("BENCH_NOTEBOOK", os.path.join(HERE, "..", "..", "notebooks", "SWaT_Anomaly_Detection.ipynb"))
nb = json.load(open(NOTEBOOK))
code = {i: "".join(c["source"]) for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"}
ns = {"__name__": "nb", "display": print}
# config, loading/preprocessing, windowing, models, training loops and scoring cells
for i in (3, 5, 7, 11, 13, 15):
    exec(compile(code[i], f"cell{i}", "exec"), ns)

import torch  # noqa: E402

torch.set_num_threads(2)

# --- memory: let torch share numpy buffers instead of copying whole window arrays ---
_torch_proxy = types.ModuleType("torch_proxy")
_torch_proxy.__dict__.update({k: getattr(torch, k) for k in dir(torch) if not k.startswith("__")})


def _tensor(data, dtype=None, device=None, **kw):
    if (isinstance(data, np.ndarray) and data.dtype == np.float32 and dtype in (None, torch.float32)
            and (device is None or str(device) == "cpu") and not kw):
        return torch.from_numpy(np.ascontiguousarray(data))
    return torch.tensor(data, dtype=dtype, device=device, **kw)


_torch_proxy.tensor = _tensor
ns["torch"] = _torch_proxy


class Windows:
    """Read-only (N, W, F) window view over a (T, F) array; optional per-position MinMax scaling."""

    def __init__(self, arr, window, lo=None, scale=None):
        self.v = np.lib.stride_tricks.sliding_window_view(arr, window, axis=0).transpose(0, 2, 1)
        self.lo, self.scale = lo, scale
        self.shape = self.v.shape

    def __len__(self):
        return self.shape[0]

    def __getitem__(self, idx):
        b = np.array(self.v[idx], dtype=np.float32)
        if self.lo is not None:
            b = ((b - self.lo) * self.scale).astype(np.float32)
        return b

    def materialize(self):
        out = np.empty(self.shape, dtype=np.float32)
        for i in range(0, len(self), 20000):
            out[i:i + 20000] = self[i:i + 20000]
        return out


def minmax_params(arr, window):
    """Per-(time-position, feature) min/max over all training windows, as MinMaxScaler computes it."""
    n = len(arr) - window + 1
    lo = np.stack([arr[t:t + n].min(axis=0) for t in range(window)]).astype(np.float64)
    hi = np.stack([arr[t:t + n].max(axis=0) for t in range(window)]).astype(np.float64)
    rng = hi - lo
    rng[rng == 0] = 1.0                       # sklearn MinMaxScaler handles constant columns this way
    return lo.astype(np.float32), (1.0 / rng).astype(np.float32)


def load_lowmem(data_dir, cfg):
    import glob
    import pandas as pd
    parts, labels = [], []
    for f in sorted(glob.glob(os.path.join(data_dir, cfg["FILE_GLOB"]))):
        for df in pd.read_csv(f, low_memory=False, chunksize=100_000):
            df.columns = [str(c).strip() for c in df.columns]
            raw = df["Normal/Attack"].astype(str).str.strip().str.lower().str.replace(" ", "")
            labels.append(raw.apply(lambda v: 1 if "attack" in v else (1 if v in {"1", "1.0"} else 0)).astype(int))
            parts.append(df.drop(columns=["Normal/Attack"]).apply(pd.to_numeric, errors="coerce"))
    X = pd.concat(parts, ignore_index=True)
    del parts
    y = pd.concat(labels, ignore_index=True)
    X = X.dropna(axis=1, how="all").ffill().fillna(0.0)
    std = X.std()
    X = X[std[std > cfg.get("VAR_THRESHOLD", 0.0)].index.tolist()]
    k = cfg.get("MAX_FEATURES")
    if k and X.shape[1] > k:
        X = X[X.var().sort_values(ascending=False).head(k).index.tolist()]
    return X.reset_index(drop=True), y.reset_index(drop=True)


args = [a for a in sys.argv[1:] if not a.startswith("--")]
dataset, seeds = args[0], [int(s) for s in args[1:]]
models = ["IsolationForest", "DenseAE", "LSTM_AE", "USAD", "TranAD", "GDN"]
for a in sys.argv[1:]:
    if a.startswith("--models="):
        models = a.split("=", 1)[1].split(",")

CFG = ns["CONFIG"]
cfg = {**CFG, **CFG["DATASET_OVERRIDES"].get(dataset, {}), "_dataset_name": dataset}
OUT = os.path.join(os.getenv("BENCH_OUT", os.path.join(HERE, "bench")), dataset)
os.makedirs(OUT, exist_ok=True)

todo = [(m, s) for s in seeds for m in models if not os.path.exists(os.path.join(OUT, f"{m}_seed{s}.npz"))]
if not todo:
    print("nothing to do")
    sys.exit(0)

t0 = time.time()
loader = load_lowmem if dataset == "WADI" else ns["load_dataset"]
X, y = loader(os.path.join(os.getenv("BENCH_DATA", os.path.join(HERE, "data")), dataset), cfg)
Xtr, Xval, Xte, yte, scaler = ns["make_splits"](X, y, cfg)
del X, y
gc.collect()
Xtr, Xval, Xte = (a.astype(np.float32) for a in (Xtr, Xval, Xte))
W, S = cfg["WINDOW"], cfg["STRIDE"]
assert S == 1
nf = Xtr.shape[1]
yte_win = ns["window_labels"](yte, W, S)
np.savez_compressed(os.path.join(OUT, "labels.npz"), y_point=yte.astype(np.int8), y_win=yte_win.astype(np.int8))
Wtr, Wval, Wte = Windows(Xtr, W), Windows(Xval, W), Windows(Xte, W)
lo, sc = minmax_params(Xtr, W)
Wtr_s, Wval_s, Wte_s = Windows(Xtr, W, lo, sc), Windows(Xval, W, lo, sc), Windows(Xte, W, lo, sc)
print(f"{dataset}: loaded in {time.time() - t0:.0f}s  nf={nf}  train={len(Xtr)}  test={len(Xte)}", flush=True)


def seed_all(s):
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)
    ns["SEED"] = s


for m, s in todo:
    seed_all(s)
    t1 = time.time()
    print(f"=== {dataset} {m} seed {s}", flush=True)
    if m == "IsolationForest":
        from sklearn.ensemble import IsolationForest
        iso = IsolationForest(n_estimators=200, random_state=s, n_jobs=-1).fit(Xtr)
        sv, st = -iso.score_samples(Xval), -iso.score_samples(Xte)
    elif m == "DenseAE":
        mod = ns["train_ae"](ns["DenseAE"](nf), Xtr, cfg)
        sv, st = ns["recon_error"](mod, Xval, seq=False), ns["recon_error"](mod, Xte, seq=False)
    elif m == "LSTM_AE":
        Wm = Wtr.materialize()
        mod = ns["train_ae"](ns["LSTMAE"](nf), Wm, cfg)
        del Wm
        sv, st = ns["recon_error"](mod, Wval, seq=True), ns["recon_error"](mod, Wte, seq=True)
    elif m == "USAD":
        Wm = Wtr_s.materialize()
        mod = ns["train_usad"](ns["USAD"](W * nf), Wm, cfg)
        del Wm
        sv, st = ns["usad_score"](mod, Wval_s), ns["usad_score"](mod, Wte_s)
    elif m == "TranAD":
        Wm = Wtr_s.materialize()
        mod = ns["train_tranad"](ns["TranAD"](nf, W), Wm, cfg)
        del Wm
        sv, st = ns["tranad_score"](mod, Wval_s), ns["tranad_score"](mod, Wte_s)
    elif m == "GDN":
        Wm = Wtr.materialize()
        mod = ns["train_gdn"](ns["GDN"](nf, W - 1, topk=cfg.get("GDN_TOPK", 15)), Wm, cfg)
        del Wm
        sv, st = ns["gdn_score"](ns["gdn_errors"](mod, Wval), ns["gdn_errors"](mod, Wte))
    gc.collect()
    np.savez_compressed(os.path.join(OUT, f"{m}_seed{s}.npz"), sv=np.asarray(sv, np.float32),
                        st=np.asarray(st, np.float32), seconds=time.time() - t1)
    print(f"--- done {dataset} {m} seed {s} in {time.time() - t1:.0f}s", flush=True)
