# v3/pilot.py — Stages 4–5: SPY end-to-end pilot, then diverse-basket calibration.
"""Stage 4 (SPY): full pipeline on one symbol — signals → proposals →
on-demand option fills → labels → GBT + small NN → mini walk-forward.
Validates plumbing and label economics. NO tuning decisions here.

Stage 5 (~10-name basket: index ETF, mega-caps, high-IV retail,
rate-sensitive): where design decisions actually get made."""
