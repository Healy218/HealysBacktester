# v3/dataset.py — Stage 6: parallel full-universe dataset build.
"""v2's per-symbol loop is sequential; this one is parallel (per-symbol jobs,
checkpoint per symbol — the #1 code change for scale). Target runtime env:
rented many-core spot VM; preemption is a non-event by construction."""
