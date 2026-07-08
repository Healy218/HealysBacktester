# fa/tracker.py — Stage 5: forward-return tracking + graduation.
"""THE metric: forward returns of past top-10s vs the existing-universe
baseline. Every pick tracked monthly from its ranking date. Graduation:
after config.PROBATION_MONTHS, qualifying picks enter the training universe
POINT-IN-TIME (as of their ranking date, not today). If discovery picks don't
outperform after 6+ months of tracking, the ranker is redecorating, not
discovering — kill or fix it."""
