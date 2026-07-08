# fa/scores.py — Stage 2: per-source attention/sentiment scores.
"""Velocity, not level: z-score of attention vs each ticker's OWN trailing
config.BASELINE_DAYS baseline (SPY is always trending; a spike for $KODK is
signal). Output rows: (ticker, date, source, score, evidence_ref) — evidence
links back to raw archive rows so every ranking is auditable."""
