# V7: full-history minute signals and frozen option quotes

Status: base acquisition and bounded component pilots complete; March 15 working inputs prepared; full freeze/build/training blocked, September 15, 2026.
Full-universe build/training remains gated.
The user explicitly moved the start to March 15, 2022 (birthday) and removed
March 8–14 from active inputs. The end remains September 14, 2026. This
supersedes the original March 7 start and the earlier V6 dates.
The name is **V7**, reflecting new history, signal, feature and execution
contracts. Existing V6 paper operation remains separate.

## Accepted scope and dates

| Purpose | Scope |
|---|---|
| Historical research window | **2022-03-15 through 2026-09-14**, inclusive |
| End-date meaning | Latest completed regular market session when the plan was prepared |
| Earlier history | Separate verified history may support PIT membership; March 8–14 are excluded, no pre-start labels, and feature state restarts March 15 after the deleted interval |
| Signal timeframes | All registered strategy variants across 1/5/15/30 minutes |
| Option execution | One-minute cadence, frozen observed MASSIVE bid/ask quotes |
| Features | Full existing suite, all thirteen TradingView scopes, option quote/trade features |
| Training/evaluation boundaries | Redesign and freeze chronological purged folds before model selection; V6 dates are not inherited |

"Today" is fixed at **September 14, 2026**, resolved from the captured exchange
calendar at 2026-09-15T04:34:36Z. It does not advance while a long build runs.
The original cutoff calendar started in April 2024. Acquisition now has a
separate captured calendar for 2021-01-01–2026-09-14, including warmup. Bind
and validate those calendar bytes with every input before sealing data.

The prior 2024–2026 proposal is superseded, not silently edited in its old
artifacts. Create new source/runtime/data/feature manifests, labels, models
and outputs. Existing verified raw observations can be reused after coverage
and provenance checks. No old row or checkpoint is relabeled V7.

Observed bid/ask histories cannot be uniquely reconstructed from trade OHLCV.
Synthetic spread models would produce a different, explicitly modeled study
and do not meet this campaign's observed-quote execution contract. Earlier
stock/trade data can support indicator warmup without creating pre-2022
option-execution labels. Feature windows needing quotes before March 15 may
be unavailable at the beginning; determine their actual first eligible
observations instead of inventing warmup values.

Audit every feature's dependencies, history, vintage and publication time
across the whole window: prior-date option chains/surfaces, IV, market context,
corporate actions, calendars, ticks and source indicator inputs. The ability
to obtain quotes back to 2022 does not prove the full feature suite is available
on every earlier day. Missing feature history blocks full-suite admission;
record and repair it rather than silently dropping features or shortening dates.

Use the 449-symbol inventory as the starting reference; rebuild historical
PIT membership, aliases and listing/delisting coverage. A present-day stock
list is not proof of a survivorship-free 2022 universe. Preserve actual 1–9
calendar DTE at selection/purchase, target grid 1/5 and the declared weekly
2/4/7 subset, with historical eligibility validated. Zero DTE stays excluded.

Freeze chronological walk-forward splits, label-horizon purging and embargo
before training. All normalization, parameter and threshold selection uses
only each fold's past. Previously inspected evaluation dates remain
revalidation; a new version does not turn known outcomes into untouched
holdout. Prospective evaluation must be declared before outcomes are seen.

## What the inventory establishes

`scripts/prepare_multitimeframe_catalog.py` creates an outcome-independent
catalog from the registered grids. Its `--research-version v7` path uses
`nn_meta/v7_plan.py` to resolve a completed-session cutoff and explicitly
avoids inheriting the old training dates. The legacy draft mode is retained
only for reproducibility of the superseded plan. `nn_meta/multitimeframe_catalog.py` assigns stable
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
`nn_meta/validation/multitimeframe-preparation-20260915/` (earlier inventory).
Current V7 plan: `nn_meta/research_plans/v7-20220315-20260914/plan.json`.
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

## Performance preparation

Prioritize shared indicator/quote reuse, bounded streaming assembly and
read-only mapped training arrays. Benchmark Arrow IPC and Polars on actual
shards before adopting them. Durable checkpoints remain on NVMe; no global
allocator/THP changes are part of this plan. See the
[performance assessment and benchmark plan](../reviews/2026-09-15-v7-performance-options.md).

## September 15 implementation checkpoint

Base acquisition completed all 8,284 captures. The March 15 working-input
migration retains 7,430 stock shards and 1,425 option daily captures, excluding
March 8–14. Provider originals remain historical provenance. A fresh observed
contract catalog contains 22,130,242 contracts. Option trade aggregates are
not observed execution quotes.

All 20 strategy adapters, 13 TradingView scopes and 10 option-tick fields are
implemented in the 222-column model-row schema. The old-window integrated
pilot enumerated all 11,268 variants and assembled 72 sampled rows; bounded
factorization and fold-indexed LightGBM Sequence passed equivalence checks.
These results must be revalidated on the new window and completed inputs.

**Freeze/build/training remains blocked.** Complete PIT membership after date
exclusion, causal action prices, every-security daily/context and dated sector
features, selected-contract DTE/moneyness semantics, physical exercise/stock
accounting, dated option rules, actual quote capture, full-history assembly
and training/trial integration. Then pass measured resource pilots and one
executable complete-universe launch gate. Four workers and 250 GB decimal
remain the acquisition limits.

The [feature and freeze audit](../reviews/2026-09-15-v7-feature-and-freeze-audit.md)
contains the full feature inventory and ordered gates. The
[date-migration review](../reviews/2026-09-15-v7-march15-start.md) records the
verified input exclusion. Earlier [storage measurements](../reviews/2026-09-15-v7-download-and-performance.md)
remain historical benchmarks, not full-pipeline admission.
