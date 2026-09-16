# V7 preparation continues — no OTC; training is not ready

Updated September 16, 2026. Continue until the persistent readiness goal passes;
alert the user only then. No subagents. Preserve existing unrelated V6 changes.

## Latest user decisions

Stock prices/quotes remain Alpaca-only. The user explicitly refuses OTC data
and permits losing the affected stocks. Exclude the entire issuer histories of
BBBY, FRC, REV and SI by security identity, preserving original ranks/scores and
without replacing them. This is an ex-post study restriction, not historically
known eligibility. Original captures and unrestricted membership are preserved.
See `docs/specs/V7_UNIVERSE_EXCLUSIONS_20260916.json` and
[review](docs/reviews/2026-09-16-v7-no-otc-preparation.md).

## Active inputs

- `docs/specs/V7_ACTIVE_INPUTS_20220315.json` binds the revised universe, plan,
  exclusions, coverage and unchanged physical-expiry evaluation declaration.
- Universe `nn_meta/validation/v7-universe-no-otc-20260916`: 593 tickers,
  591 securities, 16,549 research membership rows. Removed 51 all-history rows
  (31 research rows), without reranking. All retained research membership
  snapshots are exchange-listed; no OTC exchange memberships were found.
- Plan `nn_meta/research_plans/v7-20220315-20260914-no-otc/plan.json`:
  11,268 variants/ticker; 6,681,924 ticker×variant combinations. Its catalog now
  matches all 593 tickers (the superseded acquisition plan had only 449).
  Plan hash fa982cc6d715d277c8d204fd8b36e0ef789ecda146111e86a070ec9396184f1f.
- Coverage `nn_meta/validation/v7-coverage-no-otc-20260916`: 339,640 eligible
  sessions; 126 original zeros, 67 aliases resolved, 59 remaining zeros.
- Lifecycle `nn_meta/validation/v7-lifecycle-no-otc-20260916`: all 59 have
  retrospective causes (41 cash-merger, 14 WBD successor, four halts).
  Execution/PIT admission and held-position resolution remain false.
- Working raw inputs `nn_meta/data_v7/start-20220315`; chain
  `nn_meta/validation/v7-chain-start-20220315`. Conservative source inventories
  include excluded issuers; every downstream active job must use the new membership.
- Readiness `nn_meta/validation/v7-readiness-20260916-no-otc.json`: first three
  input/inventory checks pass, all eight substantive stages remain missing.
  No full build/training launched. Re-run `scripts/v7_readiness.py --output NEW.json`.

## New evidence and implementation

1. Original Benzinga reports captured through Alpaca explain VERU's Nov 9,
   2022 halt and Nov 10 resumption. Review is
   `docs/specs/V7_LIFECYCLE_REVIEW_20260916_NEWS.json`. Captured news clocks are
   explicit; these are news reports, not exchange bulletins. The old 122-case
   lifecycle report is now fully explained retrospectively, then reduced to
   59 active cases after the user exclusions.
2. Completed all 1,047 bounded Alpaca news queries in
   `nn_meta/data_v7/dividend-news-20260916`, request manifest
   `nn_meta/validation/v7-dividend-news-requests-20260916.json`.
   Zero failed; raw captures include former broader scope as historical evidence.
3. `nn_meta/validation/v7-dividend-publications-20260916` audited 21,814 article
   observations against 4,967 active dividend events: 256 exact original amount
   announcements, 4,711 unmatched. Matching only proves amount publication;
   security/effective-date/combined-event evidence is still required. Never use
   declaration dates alone as original-amount evidence or split-adjusted cash.
4. Added immutable full-settlement fold selection, global disk-backed duplicate
   checks, bounded factorized reads and a multi-shard LightGBM Sequence. Dense
   prediction equivalence passed on synthetic fixtures. This is a loader, not
   full training integration or measured full binned-dataset memory evidence.
5. Readiness now checks exact plan catalog, membership and exclusion hashes;
   stale plans cannot reintroduce excluded or omit eligible tickers.
6. Prior cash-merger expiry/OCC override component remains synthetic. Real
   official references, deliverable and settlement adapters remain unfinished.

Full suite: **1,771 tests +18 subtests passed**, 18 warnings, 83.92s;
`/tmp/v7-no-otc-20260916-tests.log`. Includes preserved unrelated dirty V6 work.
No active acquisition jobs. Quota last 62,555,670,511 /250,000,000,000 bytes,
reservations empty; reread before acquisition. Do not reset quota.

## Fixed scope and remaining work

March 15, 2022–September 14, 2026 inclusive. March 8–14 absent from active
price/options; retain exchange calendar. Earlier captures support membership
only; price feature state cold-starts March 15, with visible missing warmup.
Alpaca stocks, Massive options; 20 strategy families, all registered variants,
1/5/15/30-minute signals, 222 columns, all 13 TV scopes and 10 tick features.
Actual 1–9 DTE purchases, targets 1/2/4/5/7; observed minute execution/marks;
five shared slots, 10% equity premium, one symbol across timeframes.
Funded physical delivery/observed stock liquidation: missing funding, shares or
evidence remains unresolved. No synthetic intrinsic sales or free short stock.
Four bounded workers, 100 GiB reserve, shared 250 GB acquisition cap; protect V6.

Next dependencies:
- Consume dated aliases/lifecycle effects and freeze security-bound sectors.
  Existing dated reference root contains historical SIC/type/description snapshots;
  do not backfill today's sector map or a reused ticker's new issuer.
- Complete original split/dividend/combined/spin-off evidence and connect causal
  chart prices to all features/proposals with raw tick units and cross-action stops.
- Build every security's daily/context features from cold-start causal prices;
  previous daily pilot is SPY-only and not admitted as full-universe evidence.
- Supply real physical context/stock quote adapters, official expiry references,
  historical settlement calendar and dated option hours/weeklies; replay actual
  funded shared expiry paths. Cash mergers and WBD delivery need real adapters.
- Build actual new-scope proposal/feature/roll demand, verify feasibility and
  capture quotes/trades under quota. Old quote envelope is only a superset.
- Connect full-history factorized rows/labels/marks to runnable NN/GBT trials;
  declare objectives/seeds/weights/calibration before outcomes; retain baseline,
  finite checks and multiple-testing diagnostics. Measure binned memory/recovery
  and V6 coexistence; produce all eight full-universe stage artifacts.

No deployment, V6 timer/runtime or alert settings changed; no messages sent.
First-week maturity reassessment remains due on/after September 21.
Previous details: `handoff-history/HANDOFF-2026-09-16-before-no-otc-scope.md`.
