# v3/audit_data.py — Stage 0: data-availability audit (gates the window).
"""Empirically answer, before anything else is built:

1. How far back does Massive option-bar history actually reach, by year and
   liquidity tier? (Sample a few contracts per year for SPY, a mid-cap, and a
   high-IV name; record bar coverage per sample.)
2. How deep/clean is Alpaca 1m history for illiquid and delisted names?

Output: artifacts/audit_report.md + audit_results.parquet. The report's
conclusion sets config.WINDOW_START for real (2017-01-20 is the goal, not
the guarantee).

Run: python -m v3.audit_data [--symbols SPY,DKNG,MARA] [--years 2017-2026]
"""


def audit_option_history(symbol: str, year: int) -> dict:
    """Sample option contracts for `symbol` in `year`; return coverage stats
    (contracts found, bars per contract, first/last bar ts)."""
    raise NotImplementedError("Stage 0 — see V3_SPEC.md")


def audit_underlying_history(symbol: str) -> dict:
    """1m bar depth/gap stats for `symbol` from Alpaca."""
    raise NotImplementedError("Stage 0 — see V3_SPEC.md")


if __name__ == "__main__":
    raise SystemExit("Stage 0 not implemented yet — see V3_SPEC.md")
