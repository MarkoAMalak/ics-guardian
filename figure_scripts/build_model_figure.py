#!/usr/bin/env python3
# ICS Guardian - deep-learning model figure (Dense Autoencoder training + scoring)
import html
W, Hc = 1560, 1080

C = {
    "slate": ("#EEF2F7", "#334155", "#1C2733"),
    "blue":  ("#E8F0FE", "#2563EB", "#0B2E63"),
    "teal":  ("#E4F6F2", "#0D9488", "#0A4F49"),
    "indigo":("#EEF0FF", "#4F46E5", "#2A247A"),
    "amber": ("#FFF3E2", "#EA8A0E", "#7A4708"),
    "green": ("#ECFDF5", "#059669", "#064E3B"),
    "red":   ("#FDECEC", "#DC2626", "#7F1D1D"),
}
svg = []
def add(s): svg.append(s)
def esc(t): return html.escape(str(t))

def box(x,y,w,h,title,sub,key,rx=12,ts=16,ss=12):
    fill,stroke,tcol = C[key]
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    add(f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{stroke}"/>')
    cx=x+w/2
    if sub:
        add(f'<text x="{cx}" y="{y+h/2-3}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="{ts}" font-weight="700" fill="{tcol}">{esc(title)}</text>')
        yy=y+h/2+15
        for ln in sub.split("\n"):
            add(f'<text x="{cx}" y="{yy}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="{ss}" fill="#475569">{esc(ln)}</text>'); yy+=15
    else:
        add(f'<text x="{cx}" y="{y+h/2+6}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="{ts}" font-weight="700" fill="{tcol}">{esc(title)}</text>')

def arrow(x1,y1,x2,y2,color="#475569",wd=2.4,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{wd}" marker-end="url(#ah)"{d}/>')

def band(x,y,w,h,label):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="none" stroke="#94A3B8" stroke-width="1.4" stroke-dasharray="3 5" opacity="0.7"/>')
    add(f'<text x="{x+18}" y="{y-8}" font-family="Segoe UI, Arial" font-size="14.5" font-weight="800" letter-spacing="0.5" fill="#334155">{esc(label)}</text>')

# ---- canvas + header ----
add(f'<rect width="{W}" height="{Hc}" fill="#FFFFFF"/>')
add('<defs><marker id="ah" markerWidth="11" markerHeight="11" refX="8" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#475569"/></marker>'
    '<marker id="ahr" markerWidth="11" markerHeight="11" refX="8" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#DC2626"/></marker>'
    '<marker id="ahg" markerWidth="11" markerHeight="11" refX="8" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#059669"/></marker></defs>')
add(f'<text x="{W/2}" y="46" text-anchor="middle" font-family="Segoe UI, Arial" font-size="27" font-weight="800" fill="#0B2E63">Deep-Learning Model — Dense Autoencoder for Unsupervised Anomaly Detection</text>')
add(f'<text x="{W/2}" y="73" text-anchor="middle" font-family="Segoe UI, Arial" font-size="14.5" fill="#64748B">Trained on NORMAL operation only · the per-reading reconstruction error is the anomaly score (same recipe for the process and network branches)</text>')

# =============== BAND A: ARCHITECTURE ===============
band(30,110,W-60,340,"1 · MODEL ARCHITECTURE — DENSE AUTOENCODER (encoder → 16-D latent code → decoder)")
midY=280
counts=[45,64,32,16,32,64,45]
roles =["Input","h1","h2","code","h3","h4","Output"]
keys  =["slate","blue","blue","teal","indigo","indigo","slate"]
maxc=64; maxH=190; bw=44
xs=[110,270,430,590,750,910,1070]
# recompute even spacing
gap=150; x0=150
xs=[x0+i*gap for i in range(7)]
bars=[]
for i,(c,x) in enumerate(zip(counts,xs)):
    h=c/maxc*maxH
    top=midY-h/2; bot=midY+h/2
    bars.append((x,top,bot,h))
# envelope connectors (light) between adjacent layers
for i in range(6):
    x1,t1,b1,_=bars[i]; x2,t2,b2,_=bars[i+1]
    add(f'<line x1="{x1+bw}" y1="{t1}" x2="{x2}" y2="{t2}" stroke="#CBD5E1" stroke-width="1.4"/>')
    add(f'<line x1="{x1+bw}" y1="{b1}" x2="{x2}" y2="{b2}" stroke="#CBD5E1" stroke-width="1.4"/>')
# bars
for i,(c,x) in enumerate(zip(counts,xs)):
    _,top,bot,h=bars[i]
    fill,stroke,tcol=C[keys[i]]
    add(f'<rect x="{x}" y="{top}" width="{bw}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    add(f'<text x="{x+bw/2}" y="{top-10}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="15" font-weight="800" fill="{tcol}">{c}</text>')
# group brackets / labels
add(f'<text x="{(xs[0]+xs[3])/2+bw/2}" y="{midY+150}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="14" font-weight="700" fill="#2563EB">Encoder  (45 → 64 → 32 → 16)</text>')
add(f'<text x="{xs[3]+bw/2}" y="{midY+130}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="12" font-weight="700" fill="#0D9488">latent code (16-D)</text>')
add(f'<text x="{(xs[4]+xs[6])/2+bw/2}" y="{midY+150}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="14" font-weight="700" fill="#4F46E5">Decoder  (16 → 32 → 64 → 45)</text>')
# input / output captions
add(f'<text x="{xs[0]+bw/2}" y="{midY-125}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="12.5" font-weight="700" fill="#334155">x</text>')
add(f'<text x="{xs[0]+bw/2}" y="{midY-108}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="11" fill="#64748B">45 features (z-scored)</text>')
add(f'<text x="{xs[6]+bw/2}" y="{midY-125}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="12.5" font-weight="700" fill="#334155">x&#770;</text>')
add(f'<text x="{xs[6]+bw/2}" y="{midY-108}" text-anchor="middle" font-family="Segoe UI, Arial" font-size="11" fill="#64748B">reconstruction</text>')
# side note box (right) with hyperparams
box(1180,175,330,210,"", "", "slate", rx=12)
add(f'<text x="1200" y="205" font-family="Segoe UI, Arial" font-size="14.5" font-weight="800" fill="#1C2733">Training set-up</text>')
hp=["Type:  unsupervised (normal only)","Activation:  ReLU (hidden)","Loss:  MSE reconstruction","Optimizer:  Adam","Regularise:  early stopping","Frameworks:  PyTorch + scikit-learn"]
yy=230
for line in hp:
    add(f'<circle cx="1206" cy="{yy-4}" r="3" fill="#334155"/>')
    add(f'<text x="1218" y="{yy}" font-family="Segoe UI, Arial" font-size="12.5" fill="#334155">{esc(line)}</text>'); yy+=26

# =============== BAND B: TRAINING ===============
band(30,500,740,540,"2 · TRAINING  (learn to rebuild NORMAL precisely)")
# clean left-to-right pipeline with a feedback loop
box(70,  558,150,64,"Normal data","no attack labels","green", rx=10, ts=14, ss=11)
arrow(220,590,250,590)
box(250, 558,150,64,"Standardize","z-score (normal)","blue", rx=10, ts=14, ss=11)
arrow(400,590,430,590)
box(430, 558,150,64,"Autoencoder","x → x̂","indigo", rx=10, ts=14, ss=11)
arrow(580,590,610,590)
box(610, 558,150,64,"Loss = MSE","(x, x̂)","teal", rx=10, ts=14, ss=11)
# feedback loop: Loss -> down -> left -> up into Autoencoder
add('<path d="M 685 622 L 685 664 L 505 664 L 505 626" fill="none" stroke="#4F46E5" stroke-width="2.2" stroke-dasharray="5 4" marker-end="url(#ah)"/>')
add(f'<text x="595" y="682" text-anchor="middle" font-family="Segoe UI, Arial" font-size="11.5" fill="#4F46E5">Adam · backprop — update weights (repeat each epoch)</text>')
# outcome
box(70,712,650,64,"Result: reconstructs NORMAL patterns with tiny error","anything it CANNOT rebuild well stands out as anomalous","green", ts=14.5, ss=12)
# threshold calibration
box(70,802,650,64,"Calibrate threshold τ","99th percentile of normal error → recalibrated to 0.063966 (~1% false alarm)","amber", ts=14.5, ss=12)
# both branches note
box(70,892,650,66,"Same recipe trains BOTH detectors","Process AE (plant signals)  +  Network AE (OT traffic)  →  fused by OR","indigo", ts=14.5, ss=12)

# =============== BAND C: INFERENCE / SCORING ===============
band(790,500,740,540,"3 · INFERENCE  —  ANOMALY SCORING (per reading)")
box(820,545,360,64,"Reconstruction error","e = mean( (x − x̂)² )","teal", ts=15, ss=12.5)
arrow(1000,609,1000,646)
box(820,646,360,60,"Compare with threshold τ = 0.063966","severity = e / τ","amber", ts=14.5, ss=12)
# branch: normal
arrow(1000,706,900,745, color="#059669")
box(800,748,300,74,"NORMAL","x̂ ≈ x  →  e < τ  →  no alarm","green", ts=16, ss=12.5)
# branch: attack
arrow(1000,706,1250,745, color="#DC2626")
box(1150,748,300,74,"ANOMALY / ALERT","x̂ far from x  →  e ≥ τ","red", ts=16, ss=12.5)
# mini illustration: normal vs attack reconstruction
add(f'<text x="1160" y="880" font-family="Segoe UI, Arial" font-size="13" font-weight="800" fill="#334155">Why it works</text>')
# normal panel
add(f'<rect x="800" y="895" width="330" height="120" rx="10" fill="#F6FBF8" stroke="#059669" stroke-width="1.6"/>')
add(f'<text x="815" y="915" font-family="Segoe UI, Arial" font-size="12.5" font-weight="700" fill="#064E3B">Normal reading</text>')
# draw two overlapping lines (x and x-hat close)
import math
pts_x="".join([f"{815+i*30},{985-18*math.sin(i/1.4)} " for i in range(10)])
pts_h="".join([f"{815+i*30},{987-17*math.sin(i/1.4)} " for i in range(10)])
add(f'<polyline points="{pts_x}" fill="none" stroke="#334155" stroke-width="2"/>')
add(f'<polyline points="{pts_h}" fill="none" stroke="#059669" stroke-width="2" stroke-dasharray="4 3"/>')
add(f'<text x="1120" y="1008" text-anchor="end" font-family="Segoe UI, Arial" font-size="11" fill="#059669">small error</text>')
# attack panel
add(f'<rect x="1150" y="895" width="330" height="120" rx="10" fill="#FEF6F6" stroke="#DC2626" stroke-width="1.6"/>')
add(f'<text x="1165" y="915" font-family="Segoe UI, Arial" font-size="12.5" font-weight="700" fill="#7F1D1D">Attack reading</text>')
pts_x2="".join([f"{1165+i*30},{985-18*math.sin(i/1.4)} " for i in range(10)])
pts_h2="".join([f"{1165+i*30},{965-6*math.sin(i/0.7)} " for i in range(10)])
add(f'<polyline points="{pts_x2}" fill="none" stroke="#334155" stroke-width="2"/>')
add(f'<polyline points="{pts_h2}" fill="none" stroke="#DC2626" stroke-width="2" stroke-dasharray="4 3"/>')
add(f'<text x="1470" y="1008" text-anchor="end" font-family="Segoe UI, Arial" font-size="11" fill="#DC2626">large error → alarm</text>')
# legend for mini lines
add(f'<line x1="820" y1="1030" x2="850" y2="1030" stroke="#334155" stroke-width="2"/><text x="856" y="1034" font-family="Segoe UI, Arial" font-size="11" fill="#475569">actual x</text>')
add(f'<line x1="940" y1="1030" x2="970" y2="1030" stroke="#4F46E5" stroke-width="2" stroke-dasharray="4 3"/><text x="976" y="1034" font-family="Segoe UI, Arial" font-size="11" fill="#475569">reconstruction x&#770;</text>')

out=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{Hc}" viewBox="0 0 {W} {Hc}">\n'+"\n".join(svg)+"\n</svg>"
open("/home/user/ICS_Guardian_Model_Figure.svg","w").write(out)
open("/home/user/_model.html","w").write(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#fff}}</style></head><body>{out}</body></html>')
print("model SVG written", len(out))
