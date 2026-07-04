"""
Options backtesting subsystem.

A self-contained package that mirrors the project's layered hierarchy:

    options/
      data/        vendor-agnostic data interface + adapters (Alpaca, Polygon…)
      selection/   contract selection (by DTE + delta/moneyness)
      backtests/   strategy runners (single-leg directional to start)
      analysis/    options-specific plotting (payoff, greeks over time)

Design note: single-leg P&L is computed by trading each option contract's OWN
historical price series through the existing equity engine
(portfolio/simulator.py) — the market price already embeds theta/gamma/IV as
realized, so no options-pricing model is needed when real contract bars exist.
See options/README.md for the data-availability caveats.
"""
