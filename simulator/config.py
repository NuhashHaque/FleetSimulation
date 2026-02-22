"""
config.py
─────────
Central place for all environment-driven constants.
Import from here so every other module stays free of os.environ calls.
"""

import os

# ── Broker ────────────────────────────────────────────────────────────────────
BROKER_HOST: str = os.environ.get("BROKER_HOST", "localhost")
BROKER_PORT: int = int(os.environ.get("BROKER_PORT", 1883))

# ── Simulation timing ─────────────────────────────────────────────────────────
TICK_RATE: float  = 1.0   # seconds between simulation steps (1 Hz)
DWELL_TIME: int   = 5     # seconds a bus waits at each named station

# Simulation speed multiplier — how many simulated seconds pass per real second.
# Keep TICK_RATE=1.0 and realistic speeds (30–60 km/h), just warp simulated time.
#   1   → real-time  (a 2 km segment at 40 km/h takes ~3 min)
#   60  → 1 real-sec = 1 sim-min  (same segment takes ~3 sec)   ← recommended
#   120 → 2× faster than that
TIME_SCALE: float = 10.0
