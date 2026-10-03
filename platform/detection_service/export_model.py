"""
export_model.py — Run this at the END of your training notebook (on the GPU box)
to dump the artifacts the microservice needs. It bridges the research notebook and
the deployed service.

Paste the body of `export_artifacts(...)` into a notebook cell after you've trained
the Dense autoencoder, or import this file and call it. It writes four files into
detection_service/artifacts/ which the container then mounts / copies.

Requirements at export time: torch, scikit-learn, joblib, numpy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def export_artifacts(
    model,                       # trained DenseAE (nn.Module), on any device
    scaler,                      # fitted sklearn StandardScaler
    feature_names: list[str],    # ordered training columns
    train_errors: np.ndarray,    # per-sample recon error on NORMAL training data
    percentile: int = 99,        # threshold percentile (match your notebook)
    out_dir: str = "detection_service/artifacts",
) -> None:
    import joblib
    import torch

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1) model weights (move to CPU so the container needs no GPU)
    torch.save(model.to("cpu").state_dict(), out / "model.pt")

    # 2) scaler
    joblib.dump(scaler, out / "scaler.joblib")

    # 3) feature order
    (out / "feature_names.json").write_text(json.dumps(list(feature_names), indent=2))

    # 4) threshold from the NORMAL training distribution (unsupervised!)
    thr = float(np.percentile(train_errors, percentile))
    (out / "threshold.json").write_text(
        json.dumps(
            {"threshold": thr, "percentile": percentile, "metric": "recon_error"},
            indent=2,
        )
    )
    print(f"[export] wrote artifacts to {out.resolve()}")
    print(f"[export] threshold (p{percentile}) = {thr:.6f}  |  {len(feature_names)} features")


if __name__ == "__main__":
    print("Import export_artifacts() into your training notebook and call it "
          "with your trained model, scaler, feature list, and training recon errors.")
