# ==================================================================
#  ONE-SHOT CONSISTENT EXPORT  -  models + metrics, single timestamp
#  تصدير موحّد: الموديل بصيغة الخدمة + جدول المقاييس + الأوزان، بتاريخ واحد
#  ------------------------------------------------------------------
#  Paste this as the LAST cell of SWaT_Anomaly_Detection and run it
#  AFTER cells 19 and 23 (so swat_models / swat_df / compare_df exist).
#  ضعها كآخر خلية وشغّلها بعد ما تكون شغّلت خلايا التدريب.
# ==================================================================
import os, json, datetime, numpy as np, pandas as pd, torch, joblib

# --- one folder, one timestamp: nothing gets mixed with old runs ---
STAMP  = datetime.datetime.now().strftime("%Y%m%d_%H%M")
EXPORT = os.path.join(CONFIG["OUT_DIR"], f"export_{STAMP}")
os.makedirs(EXPORT, exist_ok=True)
print("Export folder:", EXPORT)

# ------------------------------------------------------------------ #
# 1) METRICS TABLE  (all models, incl. IsolationForest & Ensemble)
#    نفس أرقام هذه التشغيلة بالضبط - لا خلط مع القديم
# ------------------------------------------------------------------ #
swat_df.to_csv(os.path.join(EXPORT, "metrics_swat.csv"), index=False)
try:
    compare_df.to_csv(os.path.join(EXPORT, "metrics_swat_wadi.csv"), index=False)
except NameError:
    pass
print("Metrics saved for:", list(swat_df["Model"]))

# ------------------------------------------------------------------ #
# 2) SERVICE ARTIFACTS for the deployable model (DenseAE)
#    الموديل الوحيد اللي بتخدمه الـ microservice - بصيغتها الأربع ملفات
# ------------------------------------------------------------------ #
FEATURES = swat_meta["features"]
PCTL     = 99

# recompute the NORMAL split to get an honest threshold on per-row recon error
X, y = load_dataset(CONFIG["DATASETS"]["SWaT"], {**CONFIG, "_dataset_name": "SWaT"})
Xtr, Xval, Xte, yte, _sc = make_splits(X, y, {**CONFIG, "_dataset_name": "SWaT"})

ae = swat_models["DenseAE"]                       # still on its training device
train_err = recon_error(ae, Xtr, seq=False)       # per-row MSE on NORMAL only
thr = float(np.percentile(train_err, PCTL))

svc = os.path.join(EXPORT, "service_DenseAE")
os.makedirs(svc, exist_ok=True)

# model.pt with encoder/decoder key names so ANY version of the service loads it
sd = ae.to("cpu").eval().state_dict()
sd = {k.replace("enc.", "encoder.").replace("dec.", "decoder."): v for k, v in sd.items()}
torch.save(sd, os.path.join(svc, "model.pt"))
joblib.dump(swat_scaler, os.path.join(svc, "scaler.joblib"))
json.dump(list(FEATURES), open(os.path.join(svc, "feature_names.json"), "w"), indent=2)
json.dump({"threshold": thr, "percentile": PCTL, "metric": "recon_error"},
          open(os.path.join(svc, "threshold.json"), "w"), indent=2)
print(f"Service DenseAE -> {svc}  | features={len(FEATURES)}  threshold(p{PCTL})={thr:.6f}")

# ------------------------------------------------------------------ #
# 3) raw weights of every other torch model (same folder + stamp)
#    أوزان باقي الموديلات في نفس الفولدر للتوثيق
# ------------------------------------------------------------------ #
for name, m in swat_models.items():
    torch.save(m.to("cpu").state_dict(), os.path.join(EXPORT, f"weights_swat_{name}.pt"))
print("Raw weights saved for:", list(swat_models.keys()))

# ------------------------------------------------------------------ #
# 4) MANIFEST - so you always know exactly what this run produced
# ------------------------------------------------------------------ #
best = swat_df.iloc[0].to_dict()
manifest = {
    "stamp": STAMP,
    "service_model": "DenseAE",
    "n_features": len(FEATURES),
    "threshold_p99": thr,
    "models_in_metrics": list(swat_df["Model"]),
    "best_by_PR_AUC": {"model": best.get("Model"), "PR_AUC": best.get("PR_AUC"),
                       "ROC_AUC": best.get("ROC_AUC")},
    "note": "metrics table and DenseAE service artifacts come from the SAME run",
}
json.dump(manifest, open(os.path.join(EXPORT, "MANIFEST.json"), "w"), indent=2)

print("\nDONE - everything for this run is under:", EXPORT)
print("For the microservice: copy  service_DenseAE/*  into  detection_service/artifacts/")
print("Metrics for the report are in metrics_swat.csv (same run as the deployed model).")
