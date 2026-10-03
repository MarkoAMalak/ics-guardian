#!/usr/bin/env python3
# Generates the ICS Guardian project + pipeline figure as an SVG.
import html

W, H = 1560, 1020

# palette (semantic)
C = {
    "data":  ("#E8F0FE", "#1D4ED8", "#0B2E63"),
    "prep":  ("#EAF6FF", "#0E7FBF", "#08476B"),
    "proc":  ("#E8F0FE", "#2563EB", "#0B2E63"),
    "net":   ("#FFF3E2", "#EA8A0E", "#7A4708"),
    "fuse":  ("#E4F6F2", "#0D9488", "#0A4F49"),
    "serve": ("#EEF0FF", "#4F46E5", "#2A247A"),
    "infra": ("#EEF2F7", "#334155", "#1C2733"),
    "sec":   ("#FDECEC", "#DC2626", "#7F1D1D"),
    "mon":   ("#F4ECFB", "#7C3AED", "#43217A"),
    "user":  ("#ECFDF5", "#059669", "#064E3B"),
}

svg = []
def add(s): svg.append(s)

def esc(t): return html.escape(str(t))

def box(x, y, w, h, title, sub, key, rx=12, title_sz=17, sub_sz=12.0):
    fill, stroke, tcol = C[key]
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    # accent bar on the left
    add(f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{stroke}"/>')
    cx = x + w/2
    if sub:
        add(f'<text x="{cx}" y="{y+h/2-4}" text-anchor="middle" font-family="Segoe UI, Arial" '
            f'font-size="{title_sz}" font-weight="700" fill="{tcol}">{esc(title)}</text>')
        # subtitle may contain \n
        lines = sub.split("\n")
        ly = y + h/2 + 14
        for ln in lines:
            add(f'<text x="{cx}" y="{ly}" text-anchor="middle" font-family="Segoe UI, Arial" '
                f'font-size="{sub_sz}" fill="#475569">{esc(ln)}</text>')
            ly += 15
    else:
        add(f'<text x="{cx}" y="{y+h/2+6}" text-anchor="middle" font-family="Segoe UI, Arial" '
            f'font-size="{title_sz}" font-weight="700" fill="{tcol}">{esc(title)}</text>')

def arrow(x1, y1, x2, y2, color="#64748B", w_=2.4, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w_}" '
        f'marker-end="url(#ah)"{d}/>')

def band(x, y, w, h, label, color="#94A3B8"):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="none" '
        f'stroke="{color}" stroke-width="1.4" stroke-dasharray="3 5" opacity="0.7"/>')
    add(f'<text x="{x+18}" y="{y-8}" font-family="Segoe UI, Arial" font-size="14.5" '
        f'font-weight="800" letter-spacing="0.5" fill="#334155">{esc(label)}</text>')

# ---- header ----
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>')
add(f'<defs><marker id="ah" markerWidth="11" markerHeight="11" refX="8" refY="4" orient="auto">'
    f'<path d="M0,0 L9,4 L0,8 Z" fill="#475569"/></marker></defs>')
add(f'<text x="{W/2}" y="46" text-anchor="middle" font-family="Segoe UI, Arial" font-size="27" '
    f'font-weight="800" fill="#0B2E63">ICS Guardian — Cloud-Native DevSecOps Pipeline for Water-Chlorination ICS Protection</text>')
add(f'<text x="{W/2}" y="72" text-anchor="middle" font-family="Segoe UI, Arial" font-size="14.5" '
    f'fill="#64748B">Unsupervised process + network anomaly detection, fused and served as a secured, auto-scaling, observable cloud service</text>')

# =================== BAND 1: OFFLINE TRAIN & CALIBRATE ===================
band(30, 118, W-60, 150, "1 · OFFLINE  —  TRAIN & CALIBRATE   (unsupervised · trained on NORMAL operation only)")
y1 = 150
box(50,  y1, 215, 88, "SWaT / WADI Data", "Process sensors +\nOT-network · normal-only", "data")
arrow(265, y1+44, 300, y1+44)
box(300, y1, 205, 88, "Preprocessing", "45 features · z-score\nsubsample", "prep")
arrow(505, y1+44, 540, y1+44)
# dual branch
box(540, y1-6, 250, 46, "Process Autoencoder", "Dense  45-64-32-16", "proc", rx=10, title_sz=14.5, sub_sz=11.5)
box(540, y1+48, 250, 46, "Network Autoencoder", "OT-traffic counters", "net", rx=10, title_sz=14.5, sub_sz=11.5)
arrow(790, y1+44, 825, y1+44)
box(825, y1, 210, 88, "Threshold Calibration", "0.063966\n(~1% false alarm)", "fuse")
arrow(1035, y1+44, 1070, y1+44)
box(1070, y1, 220, 88, "Model Artifacts", "model.pt · scaler\nthreshold.json", "infra")

# feed artifacts down into the service
arrow(1180, y1+88, 1180, 330, color="#334155", dash="5 5")
add(f'<text x="1192" y="310" font-family="Segoe UI, Arial" font-size="11.5" fill="#475569">load at start-up</text>')

# =================== BAND 2: ONLINE DETECTION SERVICE ===================
band(30, 348, W-60, 150, "2 · ONLINE  —  REAL-TIME DETECTION SERVICE")
# container
add(f'<rect x="50" y="372" width="{W-100}" height="112" rx="14" fill="#F8FAFF" stroke="#4F46E5" stroke-width="2"/>')
add(f'<text x="70" y="396" font-family="Segoe UI, Arial" font-size="15" font-weight="800" fill="#2A247A">'
    f'FastAPI Microservice</text>')
add(f'<text x="250" y="396" font-family="Segoe UI, Arial" font-size="12.5" fill="#4F46E5">'
    f'endpoints:  /score · /health · /metrics</text>')
yb = 410
box(70,  yb, 220, 44, "Process recon-error", "", "proc", rx=9, title_sz=13.5)
box(70,  yb+52, 220, 0+44, "Network recon-error", "", "net", rx=9, title_sz=13.5)
arrow(290, yb+22, 330, yb+40); arrow(290, yb+74, 330, yb+56)
box(330, yb+18, 200, 58, "OR / max Fusion", "no blind spot", "fuse", rx=10, title_sz=15)
arrow(530, yb+47, 570, yb+47)
box(570, yb+18, 230, 58, "Anomaly Decision", "verdict · severity", "serve", rx=10, title_sz=15)
arrow(800, yb+47, 840, yb+47)
box(840, yb+18, 250, 58, "JSON response", "per-reading result", "infra", rx=10, title_sz=14.5)
# service deploys downward
arrow(300, 484, 300, 560, color="#334155")
add(f'<text x="312" y="528" font-family="Segoe UI, Arial" font-size="11.5" fill="#475569">containerise &amp; deploy</text>')

# =================== BAND 3: CLOUD / DEVSECOPS / OBSERVABILITY / USERS ===================
band(30, 578, W-60, 380, "3 · CLOUD DEPLOYMENT · DEVSECOPS · OBSERVABILITY · USERS")
y3 = 610
box(50,  y3, 220, 92, "Docker (hardened)", "non-root · read-only FS\nslim image", "infra")
arrow(270, y3+46, 305, y3+46)
box(305, y3, 235, 92, "Kubernetes + Helm", "rolling deploy\nauto-scale", "infra")
arrow(540, y3+46, 575, y3+46)
box(575, y3, 250, 92, "Prometheus + Grafana", "requests · anomalies\nlatency dashboards", "mon")
arrow(825, y3+46, 860, y3+46)
box(860, y3, 300, 92, "SOC Dashboard · Web Console", "role-based access\nadmin  /  operator", "user")

# DevSecOps gate band (below, gating the deploy)
yg = 760
add(f'<rect x="50" y="{yg}" width="1110" height="92" rx="14" fill="#FDECEC" stroke="#DC2626" stroke-width="2"/>')
add(f'<rect x="50" y="{yg}" width="6" height="92" rx="3" fill="#DC2626"/>')
add(f'<text x="605" y="{yg+30}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="16" '
    f'font-weight="800" fill="#7F1D1D">DevSecOps CI/CD — every push must pass 6 security gates</text>')
gates = ["ruff (lint)", "pytest", "pip-audit", "bandit (SAST)", "gitleaks (secrets)", "Trivy (image scan)"]
gx = 95
for g in gates:
    add(f'<rect x="{gx}" y="{yg+46}" width="168" height="30" rx="15" fill="#FFFFFF" stroke="#DC2626" stroke-width="1.4"/>')
    add(f'<text x="{gx+84}" y="{yg+65}" text-anchor="middle" font-family="Segoe UI, Arial" '
        f'font-size="12" font-weight="600" fill="#B91C1C">{esc(g)}</text>')
    gx += 178
# gate arrow up to Docker/K8s
arrow(300, yg, 300, y3+92, color="#DC2626", dash="4 4")
add(f'<text x="312" y="{yg-6}" font-family="Segoe UI, Arial" font-size="11.5" fill="#B91C1C">gates the build &amp; deploy</text>')
# k8s -> monitoring arrow already left-to-right; add metrics scrape note
add(f'<text x="600" y="{y3-6}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="11.5" fill="#7C3AED">scrapes /metrics</text>')

# ---- legend (clean single column, right side) ----
lx = 1200
add(f'<text x="{lx}" y="{yg+24}" font-family="Segoe UI, Arial" font-size="14" font-weight="800" fill="#334155">Legend</text>')
leg = [("proc","Process branch"),("net","Network branch"),("fuse","Fusion / threshold"),
       ("serve","Serving API"),("infra","Infra / deploy"),("sec","Security gates"),
       ("mon","Monitoring"),("user","Users / SOC")]
lyy = yg+46
for k,lab in leg:
    col = C[k][1]
    add(f'<rect x="{lx}" y="{lyy-12}" width="16" height="16" rx="4" fill="{col}"/>')
    add(f'<text x="{lx+24}" y="{lyy+1}" font-family="Segoe UI, Arial" font-size="12.5" fill="#475569">{esc(lab)}</text>')
    lyy += 25
# ---- end legend ----
svg_body = "\n".join(svg)
# fix legend: rebuild cleanly below
out = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n{svg_body}\n</svg>'
open("/home/user/ICS_Guardian_Pipeline_Figure.svg","w").write(out)
open("/home/user/_figure.html","w").write(
    f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;background:#fff}}</style></head>'
    f'<body>{out}</body></html>')
print("SVG written", len(out), "bytes")
