# WADI — 5 seeds (3, 2, 1, 0, 42), all 6 detectors + ensemble
Run: Kaggle notebook, GPU Tesla T4 (one run, 18 759 s for all 30 trainings).
Data check: attack.csv 172802 rows, normal.csv 784572 rows (same as Colab/CPU).
Metrics: bench_metrics.py (notebook's own _prf / best_f1_threshold), mean ± s.d. over 5 seeds.

| Dataset | Model | n | ROC_AUC | PR_AUC | F1_val_PA | F1_best_PA | F1_val_noPA | F1_best_noPA |
|---|---|---|---|---|---|---|---|---|
| WADI | IsolationForest | 5 | 0.763 ± 0.005 | 0.132 ± 0.020 | 0.444 ± 0.055 | 0.516 ± 0.022 | 0.151 ± 0.010 | 0.187 ± 0.015 |
| WADI | DenseAE | 5 | 0.788 ± 0.015 | 0.312 ± 0.012 | 0.633 ± 0.032 | 0.715 ± 0.031 | 0.315 ± 0.011 | 0.368 ± 0.030 |
| WADI | LSTM_AE | 5 | 0.850 ± 0.002 | 0.484 ± 0.006 | 0.668 ± 0.065 | 0.700 ± 0.034 | 0.493 ± 0.007 | 0.494 ± 0.006 |
| WADI | USAD | 5 | 0.482 ± 0.146 | 0.043 ± 0.044 | 0.209 ± 0.215 | 0.256 ± 0.221 | 0.064 ± 0.076 | 0.075 ± 0.071 |
| WADI | TranAD | 5 | 0.774 ± 0.019 | 0.354 ± 0.010 | 0.744 ± 0.034 | 0.877 ± 0.023 | 0.358 ± 0.015 | 0.412 ± 0.013 |
| WADI | GDN | 5 | 0.855 ± 0.022 | 0.252 ± 0.011 | 0.690 ± 0.026 | 0.773 ± 0.018 | 0.231 ± 0.013 | 0.270 ± 0.013 |
| WADI | Ensemble | 5 | 0.833 ± 0.010 | 0.423 ± 0.007 | 0.630 ± 0.000 | 0.886 ± 0.031 | 0.275 ± 0.002 | 0.487 ± 0.009 |

Training time per seed on T4 (s): IF ~2, DenseAE ~40, LSTM_AE ~105, GDN ~88, TranAD ~1640, USAD ~1750.
