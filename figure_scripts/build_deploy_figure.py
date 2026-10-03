#!/usr/bin/env python3
"""Figure 4 — Cloud-native deployment & DevSecOps supply chain (Phase 2)."""
import html

W, H = 1620, 790
C = {
    "dev":   ("#E8F0FE", "#1D4ED8", "#0B2E63"),
    "sec":   ("#FDECEC", "#DC2626", "#7F1D1D"),
    "reg":   ("#EEF0FF", "#4F46E5", "#2A247A"),
    "k8s":   ("#EAF6FF", "#0E7FBF", "#08476B"),
    "pod":   ("#E4F6F2", "#0D9488", "#0A4F49"),
    "mon":   ("#F4ECFB", "#7C3AED", "#43217A"),
    "user":  ("#ECFDF5", "#059669", "#064E3B"),
    "infra": ("#EEF2F7", "#334155", "#1C2733"),
}
svg = []
def add(s): svg.append(s)
def esc(t): return html.escape(str(t))

def box(x, y, w, h, title, sub, key, rx=12, ts=16, ss=11.5):
    fill, stroke, tcol = C[key]
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    add(f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{stroke}"/>')
    cx = x + w / 2
    if sub:
        add(f'<text x="{cx}" y="{y+h/2-3}" text-anchor="middle" font-family="Segoe UI, Arial" '
            f'font-size="{ts}" font-weight="700" fill="{tcol}">{esc(title)}</text>')
        ly = y + h / 2 + 15
        for ln in sub.split("\n"):
            add(f'<text x="{cx}" y="{ly}" text-anchor="middle" font-family="Segoe UI, Arial" '
                f'font-size="{ss}" fill="#475569">{esc(ln)}</text>')
            ly += 14
    else:
        add(f'<text x="{cx}" y="{y+h/2+6}" text-anchor="middle" font-family="Segoe UI, Arial" '
            f'font-size="{ts}" font-weight="700" fill="{tcol}">{esc(title)}</text>')

def arrow(x1, y1, x2, y2, col="#64748B", w=2.2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{w}" '
        f'marker-end="url(#ah)"{d}/>')

def label(x, y, t, size=12, col="#475569", weight=400, anchor="middle"):
    add(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Segoe UI, Arial" '
        f'font-size="{size}" font-weight="{weight}" fill="{col}">{esc(t)}</text>')

add('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#64748B"/></marker>'
    '<marker id="ahr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#DC2626"/></marker></defs>')
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>')

label(W / 2, 40, "Cloud-Native Deployment & DevSecOps Supply Chain", 24, "#0B2A4A", 800)
label(W / 2, 64, "every commit is gated before it can become a running pod", 13.5, "#64748B")

# ---------------- row 1 : source -> gates -> registry
y1 = 100
box(50, y1, 210, 84, "Source", "Git repository\nservice · web · IaC · charts", "dev")

gx, gy, gw, gh = 300, y1 - 8, 950, 100
add(f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" rx="14" fill="#FFF8F8" stroke="#DC2626" '
    'stroke-width="2" stroke-dasharray="7 5"/>')
label(gx + 14, gy + 22, "DevSecOps gates — build fails on any CRITICAL / HIGH finding", 13, "#B91C1C", 700, "start")
gates = [("1 · ruff", "lint"), ("2 · pytest", "unit tests"), ("3 · bandit", "SAST"),
         ("4 · pip-audit", "dep CVEs"), ("5 · gitleaks", "secrets"), ("6 · Trivy", "image CVEs")]
bw = 145
for i, (n, s) in enumerate(gates):
    bx = gx + 16 + i * (bw + 8)
    box(bx, gy + 34, bw, 52, n, s, "sec", rx=9, ts=13.5, ss=11)

box(1290, y1, 270, 84, "Container registry", "signed, hardened image\nnon-root · read-only FS", "reg")

arrow(262, y1 + 42, 296, y1 + 42)
arrow(1252, y1 + 42, 1286, y1 + 42)

# ---------------- row 2 : kubernetes
y2 = 250
kx, kw = 300, 960
add(f'<rect x="{kx}" y="{y2}" width="{kw}" height="240" rx="16" fill="#F6FBFF" stroke="#0E7FBF" stroke-width="2"/>')
label(kx + 16, y2 + 26, "Kubernetes cluster  ·  Helm chart  ·  namespace ics-guardian", 14.5, "#08476B", 700, "start")

box(kx + 24, y2 + 42, 250, 74, "Deployment", "replicas 2 · rolling update\nliveness + readiness /health", "k8s", ts=14.5, ss=11)
box(kx + 24, y2 + 130, 250, 84, "HorizontalPodAutoscaler",
    "min 2 → max 6 replicas\ntarget 70 % CPU utilisation", "k8s", ts=13.5, ss=11)

# pods
px = kx + 300
for i in range(4):
    box(px + i * 118, y2 + 60, 104, 96,
        f"pod {i+1}", "detector\nFastAPI\n:8000", "pod", rx=10, ts=13.5, ss=10.5)
label(px + 236, y2 + 176, "scaled out by the HPA under ingestion load", 11.5, "#0A4F49")
label(px + 470, y2 + 108, "…", 26, "#0D9488")

box(kx + 800, y2 + 60, 140, 96, "Service", "ClusterIP\n+ Ingress\nTLS", "k8s", rx=10, ts=13.5, ss=10.5)

add(f'<rect x="{kx+24}" y="{y2+42}" width="0" height="0"/>')
arrow(kx + 274, y2 + 80, px - 6, y2 + 100)
arrow(kx + 274, y2 + 172, px - 6, y2 + 130, "#0D9488", 2.0, "6 4")
arrow(px + 460, y2 + 108, kx + 796, y2 + 108)

# registry -> cluster
add(f'<path d="M1425,{y1+84} L1425,{y2-24} L{kx+kw+24},{y2-24} L{kx+kw+24},{y2+108} L{kx+kw+4},{y2+108}" '
    'fill="none" stroke="#4F46E5" stroke-width="2.4" marker-end="url(#ah)"/>')
label(1300, y2 - 32, "helm upgrade --install", 12, "#4F46E5")

# security gate arrow down
add(f'<path d="M{gx+gw/2},{gy+gh} L{gx+gw/2},{y2-6}" fill="none" stroke="#DC2626" stroke-width="2" '
    'stroke-dasharray="6 5" marker-end="url(#ahr)"/>')

# ---------------- row 3 : plant, observability, users
y3 = 530
box(20, y2 + 46, 200, 150, "OT plant / ICS",
    "45 sensor + network\nfeatures per reading\n\nposted to /score", "infra", ts=15, ss=11.5)
arrow(224, y2 + 121, kx - 6, y2 + 121, "#334155")
label(259, y2 + 107, "telemetry", 11.5, "#334155", 600)

box(kx, y3, 300, 100, "Prometheus", "scrapes /metrics from\nevery pod · 15 s interval", "mon", ts=15, ss=11.5)
box(kx + 340, y3, 300, 100, "Grafana", "requests · anomalies\nlatency · model loaded", "mon", ts=15, ss=11.5)
box(kx + 680, y3, 280, 100, "SOC operators", "role-aware web platform\nadmin · operator", "user", ts=15, ss=11.5)

add(f'<path d="M{kx+150},{y2+240} L{kx+150},{y3-6}" fill="none" stroke="#7C3AED" stroke-width="2.2" marker-end="url(#ah)"/>')
label(kx + 162, y3 - 30, "scrape /metrics", 12, "#7C3AED", 400, "start")
arrow(kx + 300, y3 + 50, kx + 336, y3 + 50, "#7C3AED")
arrow(kx + 640, y3 + 50, kx + 676, y3 + 50, "#059669")
add(f'<path d="M{kx+960},{y3+50} L{kx+1000},{y3+50} L{kx+1000},{y2+150} L{kx+kw+4},{y2+150}" '
    'fill="none" stroke="#059669" stroke-width="2.2" marker-end="url(#ah)"/>')
label(kx + 1010, y3 - 4, "authenticated", 11.5, "#059669", 400, "start")
label(kx + 1010, y3 + 12, "HTTPS", 11.5, "#059669", 400, "start")

# ---------------- legend
lx, ly = 1400, y2 + 300
label(lx, ly, "Legend", 14, "#334155", 800, "start")
leg = [("dev", "Source control"), ("sec", "Security gate"), ("reg", "Image registry"),
       ("k8s", "Kubernetes object"), ("pod", "Running detector"), ("mon", "Observability"),
       ("user", "Human operators"), ("infra", "Plant / OT side")]
yy = ly + 24
for k, lab in leg:
    add(f'<rect x="{lx}" y="{yy-11}" width="14" height="14" rx="4" fill="{C[k][1]}"/>')
    label(lx + 21, yy + 1, lab, 12, "#475569", 400, "start")
    yy += 22

out = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n' + "\n".join(svg) + "\n</svg>"
open("/home/user/ICS_Guardian_Deploy_Figure.svg", "w").write(out)
open("/home/user/_deployfig.html", "w").write(
    '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:#fff}</style>'
    f'</head><body>{out}</body></html>')
print("SVG written")
