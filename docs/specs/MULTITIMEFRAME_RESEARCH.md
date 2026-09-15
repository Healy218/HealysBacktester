# New research version: minute data, multiple signal timeframes, frozen option quotes

Status: preparation only, September 14 Central / September 15 UTC, 2026.
This supersedes resuming the 15-minute short-DTE experiment. It does not
change the deployed broad-DTE V6 paper release.

## Accepted scope and dates

The user requested the entire strategy variation universe before the long
build, with signals selectable at 1/5/15/30 minutes and option execution at
one-minute resolution using frozen MASSIVE quotes. Keep the historical dates:

| Purpose | Dates |
|---|---|
| Underlying warmup | From 2024-04-01 |
| Original strategy training | 2024-08-26 through 2025-12-19 |
| Full historical model window | 2024-08-26 through 2026-08-24 |

Changing lookbacks or selecting parameter variants does not require changing
these dates. Any selection/normalization/threshold tuning must use training
data only. Previously inspected evaluation periods remain revalidation;
calling this a new version does not make those outcomes an untouched holdout.
Retain the existing purged fold dates as the comparison reference. Where a
fold requires fitting a proposal selector, fit it only on that fold's past;
do not reuse a selector fitted through December 2025 to claim earlier
end-to-end out-of-sample results. Future prospective evaluation needs its own
declaration before viewing outcomes.

Use the existing 449-symbol scope, with point-in-time membership and alias
history. Preserve actual 1–9 calendar DTE at selection and purchase, target
grid 1/5 plus 2/4/7 for the frozen weekly subset. Zero DTE stays excluded.
Create new code/data/feature/execution manifests and separate outputs; the
old rows, labels and weights cannot be relabeled as this experiment.

## What the inventory establishes

`scripts/prepare_multitimeframe_catalog.py` creates an outcome-independent
catalog from the registered grids and verifies the old baseline's hash before
copying its training dates. `nn_meta/multitimeframe_catalog.py` assigns stable
strategy/timeframe/parameter identities, preserves all variants and refuses
unknown legacy grid shapes. This is inventory code, not the new signal engine.

The current 12 legacy and eight source strategy wrappers declare 2,817
parameter combinations per timeframe, 11,268 per ticker, and **5,059,332**
ticker/timeframe/parameter combinations for 449 tickers. This excludes
direction, DTE targets, actual contracts, events and model trials. MA supplies
2,485 of the 2,817 combinations. Seven TradingView strategy grids remain
single source defaults; setup scanner has six identities. This does not
invent additional numeric parameter searches for those publications. The
other five of thirteen TradingView publications remain feature-only.

Generated draft and data inventory:
`nn_meta/validation/multitimeframe-preparation-20260915/`.
The draft's `ready_for_build` is always false; it is not a launch approval
or a replacement for the eventual executable readiness gate.

## Data audit as of this preparation

- Local `v3/data/underlying` contains only SPY. The repaired full-universe
  panel is 15-minute data, which cannot reconstruct original minute bars.
- Read-only GCS inventory found 2,761 symbol/year objects (5.33 GiB) over
  2017–2026 under `backup/homebox/v3/data/underlying`. In 2024/2025/2026,
  respectively 220/221/221 of the 449 scope tickers have exact-name objects.
  Those are file-presence counts, not verified usable minute coverage.
  Resolve aliases, listing dates and eligible sessions before identifying
  actual missing history. Do not fabricate pre-IPO history.
- Existing historical MASSIVE tick captures cover selected feature windows.
  They do not establish quote coverage for every proposed entry, holding
  minute, exit or roll in the expanded universe.
- MASSIVE option minute aggregates are trade OHLCV. Existing code combines
  them into 15-minute bars. They cannot substitute for historical bid/ask
  execution quotes.

## Implementation and admission requirements

### 1. Stock minute base and causal signal bars

Inventory/copy reusable raw minute files, verify source receipts and repair
eligible-session gaps. Freeze raw prices for contract selection/execution and
the explicitly defined adjusted series for indicators; bind corporate actions,
timestamp conventions, alias mappings and calendar bytes.

Derive each timeframe from the same minute base, aligned to the exchange's
actual session open/close, including DST and early closes. Distinguish a
verified no-trade minute from an incomplete download. A missing minute is
not automatically corruption; do not silently forward-fill it as an observed
trade. Freeze the handling of incomplete end-of-session bars and missingness.
Signals/features become available only at the completed bar's close.

### 2. All registered strategy variants, bounded vectorization

Existing vectorbt MA/MACD implementations can be reused after semantic and
parity checks. Evaluate all catalog variants in bounded column batches and
persist stable identities. Do not retain only the old per-family TRAIN winner,
apply the old 2,000-signal cap, or silently discard inconvenient variants.
Record unsupported variants and reasons; unresolved support blocks claiming
the entire requested universe. Event deduplication may share raw computation
and quote requests, but must preserve all variant memberships and weights.

Audit bar-count lookbacks, time-of-day features, session flags, source inputs,
stop/timeout rules and warmup at every timeframe. HTF profile auto-selection
changes with chart timeframe (1m -> 240m, 5m -> 720m, 15/30m -> 2D); existing
two-day flags cannot simply be reused. A 15-minute opening range cannot be
recovered from a completed 30-minute OHLC bar: supply causal minute context.
Resolve killzone/session boundary compatibility. Add sweep-versus-single,
prefix-invariance and batch-size-invariance tests before admission.

Keep all thirteen feature scopes. External Pine comparison was previously
deferred and remains explicitly unverified; local tests do not establish
external parity.

### 3. Frozen historical option execution and marks

Use the point-in-time chain and raw underlying price available at decision
time. Freeze the union of quote requests needed by all proposals, holding
paths and rolls without filtering by realized profitability. Deduplicate raw
contract/time windows; verify complete pagination, boundaries, raw hashes and
capture receipts. Split high-volume requests into bounded windows rather than
treating a page cap as complete history.

The [MASSIVE historical quotes API](https://massive.com/docs/rest/options/trades-quotes/quotes)
provides bid/ask prices and sizes, SIP timestamps and paginated results.
Use SIP timestamps for historical availability; capture/download time is
provenance, not historical arrival time. One-minute execution cadence still
needs quote event timestamps to establish ordering after the signal close.

Before freezing, specify entry/exit latency, quote maximum age, positive
bid/ask and size rules, crossed-market handling, size units, entry deadlines,
mark freshness, missing-quote policy and option-class session cutoffs. Buy at
observed ask and sell at observed bid with explicit fees/slippage. Existing
0.15% per side is the comparison assumption, not proof of real execution
cost; document whether additional slippage is intentional alongside spread.
Quote-based fills do not establish queue position or guaranteed executable
size. Track unknown/unavailable data separately from valid unfilled attempts.

Marks must be causal as-of observations, never future quotes. Audit cash,
contract multiplier, realized/unrealized P&L, exits and roll proceeds. Apply
actual 1–9 DTE to each purchase; explicitly resolve expiry liquidation and
exercise/assignment treatment before final seal. No aggregate-price fallback
may silently stand in for missing execution quotes.

### 4. Dataset, selection and validation

Include timeframe and parameter identity in row/proposal keys and freeze
model-facing representations. Recompute features and labels at their actual
availability times. Retain PIT eligibility and explicit rejected proposals.
Define how simultaneous cross-timeframe proposals share the existing portfolio
slots, symbol limits and capital; they are correlated candidates, not extra
independent capital. Purge splits by complete exit/roll label horizons and
retain the embargo. Keep all model/parameter trials in the search accounting.

### 5. Gate before the long build

Require verified full-universe minute/quote coverage, strategy/timeframe
support, frozen source/runtime/data manifests, causal feature/label tests and
a representative end-to-end pilot including sparse quotes, high activity,
early closes, aliases and rolls. Measure worker peak memory, capture volume,
disk growth, requests and event counts; estimate duration from those results.
Four worker processes are the user's target, with bounded internal threads
and memory/disk guards while the paper producer runs. Do not promise a
weeks-long ETA from the old 15-minute build's throughput.

Only after this gate passes: final seal -> full dataset construction ->
audits -> training/evaluation. A completed inventory alone does not pass it.
