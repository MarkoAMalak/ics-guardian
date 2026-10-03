"""Run the live demo headless and dump per-tick records to JSON for the HTML view.
Reuses the exact simulator + branch detector so the HTML shows validated numbers."""
import json

from plc_simulator import scenario
from run_demo import NET, PROC, WARMUP, BranchDetector

ticks = list(scenario())
warm = [t for t in ticks[:WARMUP] if t["_attack"] == "none"]
proc, net = BranchDetector(PROC), BranchDetector(NET)
proc.fit(warm)
net.fit(warm)

records = []
for t in ticks:
    sp, sn = proc.score(t), net.score(t)
    zp, zn = sp / proc.thr, sn / net.thr
    fused = max(zp, zn)
    records.append({
        "t": t["_t"],
        "attack": t["_attack"],
        "LIT101": t["LIT101"], "FIT101": t["FIT101"], "AIT201": t["AIT201"],
        "P101": t["P101"], "MV101": t["MV101"],
        "PKT_RATE": t["PKT_RATE"], "N_CONN": t["N_CONN"],
        "true_cl": t["_true_chlorine"],
        "zp": round(zp, 3), "zn": round(zn, 3), "fused": round(fused, 3),
        "pa": int(zp >= 1), "na": int(zn >= 1), "fa": int(fused >= 1),
    })

out = {"proc_thr": proc.thr, "net_thr": net.thr, "records": records,
       "proc_feats": PROC, "net_feats": NET}
print(json.dumps(out))
