# Handoff — October 7, 2026 — ETFE envelope captured; label kernel next

## Focus and result

Continued ETFE-1 after dated-input policy v1. User decisions (all in
[DECISIONS](docs/DECISIONS.md), October 6–7):

- **Existence census:** daily option bars for 439,606 admitted contracts
  (5,162 GETs, 738 MB). A contract is selectable from the session after its first
  traded day. **Selection v2** picks a contract for 95.1% of 6,993,352 decision
  clocks (was 5.3% from capture-dependent evidence); VOO is about 21% (thin listing).
  Weekly targets 2/4 admitted for SPY/QQQ.
- **Envelope capture (bars-only):** 40,646,087 option minute bars (44,765
  contracts, 13,580 roll legs) and 45,954,878 SIP quotes (expiry ITM windows at
  15:45 ET, liquidation opens). Both normalized (671 MB / 428 MB) with
  independent occurrence audits. Option trades skipped: 673M trades feed only
  about 5 trade-only fields (masked); bar-countable fields come from bars.
- **Row unit amended:** variant rows (233M, ~412 GB) don't fit, so rows are
  decision clocks (6.65M) with per-family firing-summary features. Exit = earliest
  exit among firing variants, plus stop and expiry cutoff; rolls into later
  expiries only. [Amendment](docs/specs/ETFE_ROW_UNIT_AMENDMENT_20261007.md).
- New engines follow the pinned-source pattern: `option_daily_capture`,
  `option_minute_capture`, `stock_quote_capture_v2`. 346 ETFE tests pass.
  Captures ran one process each, network-bound; quotes and bars ran in parallel
  within Alpaca's 200/min limit.

## Next actions

1. **ETFE-3.label-kernel:** vectorized isolated-path kernel over decision-clock
   rows. Earliest firing-variant exit from packed signal channels (0/1 call
   entry/exit, 2/3 put), entry/exit VWAP references from envelope bars, 10% /
   1% participation sizing, 12.5% stop, 15:45 cutoff ITM from quotes, rolls,
   exercise at closing-auction references, liquidation from open quotes,
   settlement dates, right-censoring. Parity against the synthetic `Scheduler`
   tapes and hand-worked real paths; the existing per-second `Scheduler` is
   too slow for 6.65M paths.
2. Size the option-context (1–45 DTE) capture. Build its engine with a cached
   root-size counter: the current per-request rglob guard slowed 128-GET runs
   from ~130 s to ~540 s on large roots.
3. Feature build (bars-only amendment, VOO re-warm, variant-summary features),
   then the ETFE-4 pilot to set the worker count via `scripts/lib/autosize.sh`.

## Selected artifacts

See [CURRENT_STATE](docs/CURRENT_STATE.md) rows for the existence census,
selection v2, envelope demand/capture, exercise references and dated policy.
Preserve unrelated dirty V6/V7 work, including uncommitted DECISIONS hunks.
Never edit a file a capture root pins (memory note; grep PLAN `sources`).

[Previous handoff](handoff-history/HANDOFF-2026-10-07-before-label-kernel.md).
