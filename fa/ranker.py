# fa/ranker.py — Stage 4: composite ranking → frozen monthly Top-10.
"""Heuristic weights first (documented), learned weights only after tracker
history exists. Anti-footgun gates (FA_SPEC.md): corroboration across
>= config.CORROBORATION_MIN independent source families; per-source weight
cap; liquidity floor (MIN_ADV_USD, MIN_OPTION_OI); manipulation flags.
Output: artifacts/top10_<yyyy-mm>.json + .md — frozen, timestamped, never
edited retroactively. Pushed via the live-alert channel."""
