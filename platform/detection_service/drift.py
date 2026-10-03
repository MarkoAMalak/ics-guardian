"""
drift.py - online monitor that tells an operator when the detector's operating point has moved.

The threshold tau is calibrated so that a fraction p0 of normal readings (1% by default) raise an
alarm. If the plant drifts (sensor ageing, a recalibrated instrument, a new operating regime), the
alarm rate on normal operation rises above p0 and tau should be reviewed.

Alarms on real plant data come in bursts, so a test that treats every reading as independent
fires far too often. The monitor therefore works on blocks: it counts the alarm rate r_b in each
block of B readings (60 by default, one minute at 1 Hz) and runs a one-sided CUSUM (Page, 1954)

    S_b = max(0, S_{b-1} + r_b - (p0 + k))

reporting drift when S_b exceeds h. k is the allowance (default p0, so a doubling of the alarm
rate is the change of interest) and h is the decision limit. h is set per plant from its own
calibration data so that normal operation triggers at most one signal a week (see the paper);
the defaults below are the values derived for SWaT.

A sustained attack also raises the alarm rate, so a drift signal is a prompt for human review
(is the plant under attack, or has it changed?), never an automatic recalibration: recalibration
stays a gated step through the CI pipeline.

Settings (environment): DRIFT_P0, DRIFT_K, DRIFT_H, DRIFT_BLOCK, DRIFT_WINDOW.
"""
from __future__ import annotations

import os
import threading
from collections import deque


class DriftMonitor:
    def __init__(self, p0: float | None = None, k: float | None = None, h: float | None = None,
                 block: int | None = None, window: int | None = None):
        self.p0 = float(p0 if p0 is not None else os.getenv("DRIFT_P0", 0.01))
        self.k = float(k if k is not None else os.getenv("DRIFT_K", self.p0))
        self.h = float(h if h is not None else os.getenv("DRIFT_H", 19.5))
        self.block = int(block if block is not None else os.getenv("DRIFT_BLOCK", 60))
        self.window = int(window if window is not None else os.getenv("DRIFT_WINDOW", 3600))
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.s = 0.0
            self.n = 0
            self.drift = False
            self.first_signal_at: int | None = None
            self._in_block = 0
            self._block_alarms = 0
            self._recent: deque[int] = deque(maxlen=self.window)

    def update(self, alarm: bool) -> bool:
        x = 1 if alarm else 0
        with self._lock:
            self.n += 1
            self._recent.append(x)
            self._in_block += 1
            self._block_alarms += x
            if self._in_block == self.block:
                rate = self._block_alarms / self.block
                self.s = max(0.0, self.s + rate - (self.p0 + self.k))
                self._in_block = self._block_alarms = 0
                if self.s > self.h and not self.drift:
                    self.drift = True
                    self.first_signal_at = self.n
            return self.drift

    def status(self) -> dict:
        with self._lock:
            recent = sum(self._recent) / len(self._recent) if self._recent else 0.0
            return {
                "drift_suspected": self.drift,
                "cusum": round(self.s, 4),
                "cusum_limit": self.h,
                "target_alarm_rate": self.p0,
                "allowance": self.k,
                "block_readings": self.block,
                "recent_alarm_rate": round(recent, 5),
                "recent_window": len(self._recent),
                "readings_seen": self.n,
                "first_signal_at_reading": self.first_signal_at,
            }


def calibrate_h(alarms, p0: float = 0.01, k: float | None = None, block: int = 60,
                max_signals_per_day: float = 1 / 7, readings_per_day: int = 86400) -> float:
    """Smallest decision limit h that keeps drift signals on normal calibration data at or below
    `max_signals_per_day` (the monitor restarts after each signal, as an operator would)."""
    import numpy as np

    k = p0 if k is None else k
    a = np.asarray(alarms, dtype=float)
    nb = len(a) // block
    rates = a[: nb * block].reshape(nb, block).mean(axis=1) - (p0 + k)
    allowed = max_signals_per_day * len(a) / readings_per_day

    def count(h):
        s, n = 0.0, 0
        for r in rates:
            s = max(0.0, s + r)
            if s > h:
                n, s = n + 1, 0.0
        return n

    lo, hi = 0.0, 1.0
    while count(hi) > allowed:
        hi *= 2
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if count(mid) > allowed else (lo, mid)
    return round(hi, 4)
