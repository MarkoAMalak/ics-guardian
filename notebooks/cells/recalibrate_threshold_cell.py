# ============================================================
#  Recalibrate the DEPLOYMENT threshold to a target false-alarm
#  rate on REAL full-resolution normal data (Option B / C).
#  Run in SWaT_Anomaly_Detection after the SWaT models exist
#  (swat_models, swat_scaler, swat_meta in memory).
#
#  Why: the old threshold was the 99th percentile of the SUBSAMPLED
#  training errors, which flags ~33% of full-resolution normal data.
#  This picks a threshold with ~1% false alarms on real normal.
#  It does NOT change ROC-AUC / PR-AUC (those are threshold-free).
# ============================================================
import json, numpy as np

feat = swat_meta["features"]
ae   = swat_models["DenseAE"]

# full-resolution SWaT rows (NOT subsampled), with labels
X, y = load_dataset(CONFIG["DATASETS"]["SWaT"], {**CONFIG, "_dataset_name": "SWaT"})
Xn = X.loc[y == 0, feat].values          # normal rows only, model feature order
Xa = X.loc[y == 1, feat].values          # attack rows only

err_n = recon_error(ae, swat_scaler.transform(Xn), seq=False)   # per-row error, normal
err_a = recon_error(ae, swat_scaler.transform(Xa), seq=False)   # per-row error, attack

print(f"normal rows: {len(err_n):,}   attack rows: {len(err_a):,}\n")
print(f"{'FP target':>10} {'threshold':>11} {'normal FP':>10} {'attack recall (per-row)':>24}")
options = {}
for fp in (0.01, 0.02, 0.05):
    thr = float(np.quantile(err_n, 1 - fp))
    fpr = float((err_n >= thr).mean()) * 100
    rec = float((err_a >= thr).mean()) * 100
    options[fp] = thr
    print(f"{fp*100:>9.0f}% {thr:>11.5f} {fpr:>9.2f}% {rec:>23.1f}%")

# ---- pick the 1% target (change to options[0.02] or options[0.05] if you prefer) ----
NEW_THR = options[0.01]

meta = {"threshold": round(float(NEW_THR), 8), "percentile": 99,
        "metric": "recon_error", "calibration": "1% false-alarm on full-resolution normal"}
json.dump(meta, open("detection_service/artifacts/threshold.json", "w"), indent=2)
print("\nRe-exported detection_service/artifacts/threshold.json ->", meta)
print(f"\n>>> NEW DEPLOYED THRESHOLD = {round(float(NEW_THR),6)}")
print(">>> Send this number so the browser Console can be updated to match.")
