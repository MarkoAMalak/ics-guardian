"""
plc_simulator.py — A tiny chlorination-process / PLC simulator.

It models a single control loop (raw-water tank + dosing pump + chlorine analyser)
the way a real PLC would drive it, emitting one "scan" per tick as a dict of
tag readings. It can inject the two attack types from the SWaT campaign so the
live demo shows the detector reacting in real time.

No hardware and no network stack required — this stands in for the OpenPLC /
Modbus-EtherNet/IP field layer for a laptop demo. The exported detector consumes
these readings exactly as it would consume a real historian feed.

Tags (kept deliberately small and self-explanatory):
    LIT101  raw-water tank level (mm)
    FIT101  inflow rate (m^3/h)
    AIT201  chlorine residual (mg/L)      <- the safety-critical variable
    P101    dosing pump state (0/1)
    MV101   inlet motorised valve (0/1)
    PKT_RATE  network packet rate on the OT segment (pkts/s)  <- network modality
    N_CONN    active connections on the OT segment
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlantState:
    level: float = 500.0        # LIT101 mm, target band 480-520
    inflow: float = 2.5         # FIT101 m^3/h
    chlorine: float = 0.8       # AIT201 mg/L, target 0.5-1.0
    pump: int = 1               # P101
    valve: int = 1              # MV101
    pkt_rate: float = 180.0     # nominal OT-segment packet rate
    n_conn: int = 6
    t: int = 0
    _seed: int = 12345
    _log: list = field(default_factory=list)

    # deterministic pseudo-noise (no Math.random / os.urandom needed for repeatable demo)
    def _noise(self, scale: float) -> float:
        self._seed = (1103515245 * self._seed + 12345) & 0x7FFFFFFF
        return ((self._seed / 0x7FFFFFFF) - 0.5) * 2 * scale


def step(s: PlantState, attack: str | None = None) -> dict:
    """Advance the plant one control scan and return the tag readings.

    attack:
        None            normal operation (closed-loop control holds setpoints)
        "spoof"         sensor spoofing — AIT201 reads normal while true dosing drifts
                        (MITRE T0856 Spoof Reporting Message)
        "disruption"    network flood degrading the loop (MITRE T0814 Denial of Service)
    """
    s.t += 1

    # --- normal closed-loop physics ---------------------------------------
    # The PLC holds the plant at setpoint: dosing pump ON, inlet valve OPEN.
    # (Attacks below may override these for the duration of the attack only;
    #  because we reset them here every scan, the plant recovers cleanly once
    #  the attack ends — the "none" phases are genuinely normal again.)
    s.pump = 1
    s.valve = 1
    # level oscillates gently around 500 as inflow vs draw balances
    # Kept STATIONARY (no slow drift terms) so the short warm-up window is a
    # representative sample of normal — otherwise a slow cycle unseen in warm-up
    # would later read as anomalous and inflate the false-alarm rate.
    s.level += (500 - s.level) * 0.15 + s._noise(1.2)
    s.inflow = 2.5 + s._noise(0.09)
    # PLC dosing control keeps chlorine near 0.8 mg/L when pump is on.
    # A fairly strong gain means that once an attack ends the loop returns to
    # setpoint within a few scans, so the post-attack "none" phase is normal.
    target_cl = 0.8 if s.pump else 0.3
    s.chlorine += (target_cl - s.chlorine) * 0.4 + s._noise(0.02)
    s.pkt_rate = 180 + s._noise(9)
    s.n_conn = 6

    # Reported readings start from the (clean) persistent state; attacks below
    # perturb these OUTPUT values, so the persistent plant state is never
    # corrupted and the plant is genuinely normal again the moment an attack ends.
    lit_out, fit_out = s.level, s.inflow
    cl_out = s.chlorine
    pkt_out, conn_out, pump_out = s.pkt_rate, s.n_conn, s.pump

    # --- attack overlays ---------------------------------------------------
    if attack == "spoof":
        # Attacker drives true dosing down (under-chlorination — unsafe water)
        # but SPOOFS the analyser tag so operators still see ~0.8 mg/L.
        s.chlorine += (0.15 - s.chlorine) * 0.25   # true value collapses toward 0.15
        cl_out = 0.8 + s._noise(0.02)               # spoofed reading looks normal
        pump_out = 0                                # pump forced off out of sequence

    elif attack == "disruption":
        # Network flood: packet rate and connection count spike; the loop misses
        # updates so the reported level/chlorine wander out of band (transient —
        # applied to the OUTPUT only, so state recovers cleanly afterwards).
        pkt_out = 950 + s._noise(80)
        conn_out = 42
        lit_out = s.level + s._noise(22)
        cl_out = s.chlorine + s._noise(0.28)

    return {
        "LIT101": round(lit_out, 2),
        "FIT101": round(fit_out, 3),
        "AIT201": round(max(cl_out, 0.0), 3),
        "P101": int(pump_out),
        "MV101": int(s.valve),
        "PKT_RATE": round(max(pkt_out, 0.0), 1),
        "N_CONN": int(conn_out),
        "_true_chlorine": round(max(s.chlorine, 0.0), 3),  # ground truth (demo only)
        "_attack": attack or "none",
        "_t": s.t,
    }


def scenario():
    """Yield a full demo timeline: normal -> spoof -> normal -> disruption -> normal."""
    plan = (
        [(None, 40)]          # warm-up normal
        + [("spoof", 25)]     # sensor-spoofing attack
        + [(None, 20)]        # recover
        + [("disruption", 25)]  # network disruption attack
        + [(None, 25)]        # recover
    )
    s = PlantState()
    for atk, n in plan:
        for _ in range(n):
            yield step(s, atk)
