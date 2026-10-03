#!/usr/bin/env python3
# Figure 3 - ICS Guardian detection results (REAL numbers from the results report).
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.edgecolor": "#94A3B8", "axes.linewidth": 0.9,
    "axes.grid": True, "grid.color": "#E2E8F0", "grid.linewidth": 0.9,
    "axes.axisbelow": True,
})
BLUE, TEAL, AMBER, RED, SLATE = "#2563EB", "#0D9488", "#EA8A0E", "#DC2626", "#334155"

# ---------- REAL data (from SWaT_WADI_Results_Report + fusion_results.csv) ----------
swat = [  # model, ROC-AUC, PR-AUC
    ("IsolationForest", 0.8929, 0.5367),
    ("DenseAE*",        0.9416, 0.8020),   # deployed
    ("LSTM-AE",         0.9418, 0.8055),
    ("USAD",            0.5401, 0.0721),
    ("TranAD",          0.9759, 0.8216),
    ("GDN",             0.9401, 0.6825),
    ("Ensemble",        0.9565, 0.8004),
]
wadi = [
    ("IsolationForest", 0.7678, 0.1270),
    ("DenseAE*",        0.7695, 0.3169),
    ("LSTM-AE",         0.8496, 0.4665),
    ("USAD",            0.4462, 0.0263),
    ("TranAD",          0.7695, 0.3533),
    ("GDN",             0.8393, 0.2421),
    ("Ensemble",        0.8239, 0.4304),
]
fusion = [  # branch, ROC-AUC, PR-AUC
    ("Process-only", 0.659, 0.386),
    ("Network-only", 0.667, 0.315),
    ("Fusion (OR)",  0.776, 0.470),
]

fig = plt.figure(figsize=(15.5, 9.4))
fig.patch.set_facecolor("white")
gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.42, wspace=0.22,
                      left=0.06, right=0.985, top=0.87, bottom=0.08)

fig.suptitle("ICS Guardian — Detection Results  (threshold-free ROC-AUC / PR-AUC · point-adjust protocol)",
             fontsize=17, fontweight="bold", color="#0B2E63", x=0.06, ha="left", y=0.965)
fig.text(0.06, 0.915,
         "Deployed model: Dense Autoencoder (marked *). Higher is better; PR-AUC is the stricter metric on this imbalanced data. "
         "Operating threshold recalibrated to 0.063966 (~1% false alarm).",
         fontsize=11, color="#475569", ha="left")

def grouped(ax, data, title, star_idx=1, star_label="deployed"):
    labels = [d[0] for d in data]
    roc = [d[1] for d in data]; pr = [d[2] for d in data]
    x = np.arange(len(labels)); w = 0.38
    b1 = ax.bar(x-w/2, roc, w, color=BLUE, label="ROC-AUC", zorder=3)
    b2 = ax.bar(x+w/2, pr,  w, color=TEAL, label="PR-AUC", zorder=3)
    # highlight deployed model
    b1[star_idx].set_edgecolor(RED); b1[star_idx].set_linewidth(2.2)
    b2[star_idx].set_edgecolor(RED); b2[star_idx].set_linewidth(2.2)
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x()+r.get_width()/2, r.get_height()+0.012, f"{r.get_height():.2f}",
                    ha="center", va="bottom", fontsize=8.3, color="#334155")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=18, ha="right", fontsize=9.5)
    ax.set_ylim(0, 1.06); ax.set_ylabel("score")
    ax.set_title(title, fontsize=13, fontweight="bold", color=SLATE, loc="left", pad=8)
    ax.annotate(star_label, xy=(star_idx, 1.0), xytext=(star_idx, 1.045),
                ha="center", fontsize=8.5, color=RED, fontweight="bold")

# Panel A: SWaT (full width top)
axA = fig.add_subplot(gs[0, :])
grouped(axA, swat, "SWaT testbed — model comparison  (primary benchmark)")
axA.legend(loc="upper right", frameon=True, framealpha=0.95, fontsize=10)

# Panel B: Fusion ablation
axB = fig.add_subplot(gs[1, 0])
grouped(axB, fusion, "Fusion ablation (A6 scenario: exfiltration + disruption)", star_idx=2, star_label="adopted")

# Panel C: WADI generalization
axC = fig.add_subplot(gs[1, 1])
grouped(axC, wadi, "WADI testbed — generalization to a larger network")

# footer note
fig.text(0.06, 0.015,
         "Source: project results report (full labelled test stream). ROC-AUC/PR-AUC are threshold-free; "
         "the deployed DenseAE reaches ROC-AUC 0.94 / PR-AUC 0.80 on SWaT and detects both attack families.",
         fontsize=9, color="#64748B", ha="left")

fig.savefig("/home/user/ICS_Guardian_Results_Figure.png", dpi=200, facecolor="white")
fig.savefig("/home/user/ICS_Guardian_Results_Figure.pdf", facecolor="white")
print("results figure written")
