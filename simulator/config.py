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
TICK_RATE: float = 1.0   # seconds between simulation steps (1 Hz)
DWELL_TIME: int  = 3     # seconds a bus waits at each named station
