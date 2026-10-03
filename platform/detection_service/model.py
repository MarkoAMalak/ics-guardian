"""
model.py — Inference-only detector for the ICS anomaly-detection microservice.

The service is intentionally decoupled from the training notebook. Training happens
offline on the GPU (SWaT_Anomaly_Detection.ipynb); this module only *loads* the
exported artifacts and scores incoming samples. Keeping inference separate from
training is what lets the same model ship as a small, dependency-light container.

Expected artifacts (produced by export_model.py), all under ./artifacts:
    model.pt            - state_dict of the Dense autoencoder
    scaler.joblib       - fitted StandardScaler (from the training data)
    threshold.json      - {"threshold": float, "percentile": int, "metric": "recon_error"}
    feature_names.json  - ordered list of feature column names the model expects
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

# One intra-op thread per worker process: the model is tiny, and several threads per request
# only contend with FastAPI's thread pool. Scale out with more workers or replicas instead.
torch.set_num_threads(int(os.getenv("TORCH_THREADS", "1")))

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", Path(__file__).parent / "artifacts"))


class DenseAE(nn.Module):
    """Symmetric dense autoencoder. Must match the architecture used at train time."""

    def __init__(self, n_features: int, hidden: Sequence[int] = (64, 32, 16)):
        super().__init__()
        dims = [n_features, *hidden]
        enc: list[nn.Module] = []
        for a, b in zip(dims[:-1], dims[1:], strict=False):
            enc += [nn.Linear(a, b), nn.ReLU()]
        dec: list[nn.Module] = []
        rev = list(reversed(dims))
        for a, b in zip(rev[:-1], rev[1:], strict=False):
            dec += [nn.Linear(a, b), nn.ReLU()]
        dec = dec[:-1]  # no activation on the reconstruction layer
        self.encoder = nn.Sequential(*enc)
        self.decoder = nn.Sequential(*dec)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


class Detector:
    """Loads exported artifacts once and scores samples on demand."""

    def __init__(self, artifact_dir: Path = ARTIFACT_DIR):
        self.artifact_dir = Path(artifact_dir)
        self.ready = False
        self.features: list[str] = []
        self.threshold: float = float("inf")
        self.meta: dict = {}
        self._scaler = None
        self._model: DenseAE | None = None
        self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        try:
            import joblib

            self.features = json.loads((self.artifact_dir / "feature_names.json").read_text())
            thr = json.loads((self.artifact_dir / "threshold.json").read_text())
            self.threshold = float(thr["threshold"])
            self.meta = thr
            self._scaler = joblib.load(self.artifact_dir / "scaler.joblib")

            model = DenseAE(n_features=len(self.features))
            state = torch.load(self.artifact_dir / "model.pt", map_location="cpu", weights_only=True)
            # Accept weights exported from the research notebook, where the layers
            # are named enc./dec. instead of this class's encoder./decoder.
            state = {
                k.replace("enc.", "encoder.").replace("dec.", "decoder."): v
                for k, v in state.items()
            }
            model.load_state_dict(state)
            model.eval()
            self._model = model
            self.ready = True
        except FileNotFoundError:
            # Service still starts (health endpoint works) but /score returns 503.
            self.ready = False

    # ------------------------------------------------------------------ #
    def _vectorize(self, sample: dict[str, float]) -> np.ndarray:
        """Order a {feature: value} dict into the model's expected vector."""
        missing = [f for f in self.features if f not in sample]
        if missing:
            raise KeyError(f"missing features: {missing[:8]}{'...' if len(missing) > 8 else ''}")
        return np.array([[float(sample[f]) for f in self.features]], dtype=np.float32)

    def _errors(self, x: np.ndarray) -> np.ndarray:
        xs = self._scaler.transform(x)
        with torch.no_grad():
            recon = self._model(torch.from_numpy(xs.astype(np.float32))).numpy()
        return np.mean((xs - recon) ** 2, axis=1)

    def _result(self, err: float) -> dict:
        z = err / self.threshold if self.threshold > 0 else 0.0
        return {
            "recon_error": round(err, 6),
            "threshold": round(self.threshold, 6),
            "severity": round(z, 3),          # >=1.0 means over threshold
            "anomaly": bool(err >= self.threshold),
        }

    def score_one(self, sample: dict[str, float]) -> dict:
        if not self.ready:
            raise RuntimeError("model artifacts not loaded")
        return self._result(float(self._errors(self._vectorize(sample))[0]))

    def score_batch(self, samples: list[dict[str, float]]) -> list[dict]:
        """Score many readings in one vectorised pass (same decisions as one by one, errors equal to float32 precision)."""
        if not self.ready:
            raise RuntimeError("model artifacts not loaded")
        if not samples:
            return []
        x = np.vstack([self._vectorize(s) for s in samples])
        return [self._result(float(e)) for e in self._errors(x)]
