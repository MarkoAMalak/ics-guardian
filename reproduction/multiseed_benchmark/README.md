# Multi-seed benchmark (SWaT and WADI)

Every detector of `notebooks/SWaT_Anomaly_Detection.ipynb` (Isolation Forest, dense AE,
LSTM-AE, USAD, TranAD, GDN and the LSTM-AE + TranAD + GDN ensemble), trained with
seeds 42, 0, 1, 2 and 3 and nothing else changed. These are the numbers in Table I of
the paper.

The scripts execute the notebook's own cells (configuration, preprocessing, models,
training loops, scoring and evaluation) unchanged; only memory handling differs, which
does not change any value. Raw validation and test scores are saved per
(dataset, model, seed), so every metric is computed afterwards from the same scores.

## Run

```bash
# data: <BENCH_DATA>/SWaT/{attack,normal}.csv and <BENCH_DATA>/WADI/{attack,normal}.csv
export BENCH_DATA=/path/to/data BENCH_OUT=./bench
python run_bench.py SWaT 42 0 1 2 3            # resumable: finished runs are skipped
python run_bench.py WADI 42 0 1 2 3 --models=IsolationForest,DenseAE,LSTM_AE
python bench_metrics.py                        # -> bench/metrics_summary.md, metrics_per_seed.csv
```

A GPU is needed for USAD and TranAD in reasonable time (about 10-30 min per seed each on a
T4). Isolation Forest, the dense AE and the LSTM-AE also run on a CPU.

## Results

* [`results_SWaT.md`](results_SWaT.md) - Google Colab, NVIDIA T4
* [`results_WADI.md`](results_WADI.md) - Kaggle, NVIDIA T4

| | Model | ROC-AUC | PR-AUC | F1 best, PA | F1 best, no PA |
|---|---|:-:|:-:|:-:|:-:|
| SWaT | Dense AE (deployed) | 0.942 ± 0.004 | 0.799 ± 0.006 | 0.999 | 0.832 |
| SWaT | LSTM-AE | 0.946 ± 0.003 | 0.817 ± 0.010 | 1.000 | 0.840 |
| SWaT | TranAD | 0.973 ± 0.006 | **0.840 ± 0.003** | 1.000 | 0.812 |
| SWaT | USAD | 0.452 ± 0.345 | 0.306 ± 0.342 | 0.981 | 0.349 |
| WADI | Dense AE | 0.788 ± 0.015 | 0.312 ± 0.012 | 0.715 | 0.368 |
| WADI | LSTM-AE | 0.850 ± 0.002 | **0.484 ± 0.006** | 0.700 | 0.494 |
| WADI | USAD | 0.482 ± 0.146 | 0.043 ± 0.044 | 0.256 | 0.075 |

USAD shows why point adjustment (PA) is not used for model selection: across seeds its
SWaT ROC-AUC ranges from 0.12 to 0.88, yet its PA F1 stays at or above 0.90.
