# Live OT-Loop Demo

A zero-setup, runnable demonstration of the whole project thesis in real time:

```
 chlorination plant / PLC  ──▶  detector (process branch + network branch)  ──▶  FUSED alarm
```

It streams a simulated water-chlorination control loop one PLC scan at a time,
scores each scan live, and shows the process branch, the network branch, and the
**fused** decision reacting as two SWaT-style attacks are injected.

## Why this exists

The notebook proves fusion works on the recorded SWaT A6 data. This demo lets you
*show it happening live* in the defense — the single most convincing thing you can
put in front of a committee, because it turns the static results into a working system.

## Run it

```bash
cd ot_demo
python run_demo.py            # built-in detector, ~0.12s per scan (watchable)
python run_demo.py --fast     # no delay, runs instantly
```

Only `numpy` is required — no service, no GPU, no trained model needed.

### Against the real microservice

Once you've exported your trained model into `detection_service/artifacts/`, start
the service (`docker compose up`) and point the demo at it:

```bash
python run_demo.py --service http://localhost:8000
```

Each simulated scan is POSTed to the real `/score` endpoint.

## What you'll see

- **Warm-up (normal):** the detector fits its two branches on the first ~35 normal scans.
- **Spoof attack (T0856):** the analyser tag reports a safe ~0.8 mg/L while the *true*
  chlorine collapses to ~0.35 and the pump is forced off. The **process branch** lights
  up; the network branch sees nothing. The console prints the reported-vs-true gap the
  operator would be blind to.
- **Disruption attack (T0814):** a network flood spikes packet rate and connections and
  knocks the readings out of band. The **network branch** lights up.
- **Summary:** per-phase detection rate showing the spoof caught by process, the
  disruption by network, and **fusion catching both** — the project's core claim, live.

## Files

- `plc_simulator.py` — the chlorination-process / PLC simulator (stands in for the
  OpenPLC / EtherNet-IP field layer; no hardware needed).
- `run_demo.py` — the live scorer + SOC-style console, with built-in and `--service` modes.

## Talking point for the defense

> "This isn't a recording — the plant is being simulated and scored live. Watch: the
> spoof attack is invisible to the network detector but the process model catches it,
> the flood is invisible to the process model but the network detector catches it, and
> the fused detector catches both. That's the whole thesis in thirty seconds."
