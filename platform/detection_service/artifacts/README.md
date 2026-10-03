# artifacts/

This folder holds the exported model artifacts the service loads at startup:

- `model.pt` — Dense autoencoder weights (state_dict)
- `scaler.joblib` — fitted StandardScaler
- `threshold.json` — anomaly threshold from the normal-training distribution
- `feature_names.json` — ordered feature columns

Generate them at the end of your training notebook with `export_model.py`:

```python
from export_model import export_artifacts
export_artifacts(model, scaler, feature_names, train_errors, percentile=99)
```

The service starts even if this folder is empty (health stays green, `/score`
returns 503 until artifacts are present), so the container image always builds.
