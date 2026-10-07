# ETFE envelope path capture — October 6, 2026

User-selected October 6: capture everything an isolated label path could need,
then run ledgers offline (no iterative frontier). First run is **bars-only**:
option trades are not captured; trade-only feature fields are masked unavailable
and bar-countable fields are recomputed from bars under a separate declared
feature amendment.

Demand (`nn_meta/etfe/envelope_demand.py`, frozen as
`nn_meta/validation/etfe-envelope-demand-20261006-r0/DEMAND.json` and bound by
hash in each plan) derives from selection v2 (census-dated existence, targets
0/1/5 plus 2/4 for SPY/QQQ):

- Held-contract 1-minute option bars from the contract's earliest feature or
  entry window through its expiry close.
- Roll legs selected at every expiry-session cutoff — dated close minus
  15 minutes (15:45 ET; 12:45 on early closes) — per underlying, right and
  target, restricted to a **later** expiry (actual DTE >= 1 at the roll), spot
  from the newest completed regular SIP minute bar. Bars run from the cutoff
  through the roll leg's expiry close; chains are followed to closure.
- SIP stock quotes in the 30 s before each expiry cutoff (ITM classification)
  and in the first minute of each exercise settlement session (stock liquidation).

Bars group contracts sharing one expiry, at most 100 symbols per request, over
the group's widest window (harmless over-fetch). Engines are route-specific
successors of the frozen capture engines (`option_minute_capture.py`,
`stock_quote_capture_v2.py`) with identical page lineage, resume, 1 s pacing,
128-GET runs and free-space guards, and 24 GiB root limits. Observations after
the October 2, 2026 fixed end are never requested.
