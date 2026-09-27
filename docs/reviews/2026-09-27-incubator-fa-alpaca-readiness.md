# Friday incubator, FA and Monday Alpaca readiness — September 27, 2026

Read-only operational audit; no services changed, no inference campaign rerun,
no orders submitted. Times below are Chicago unless marked UTC.

## Friday incubator: successful prediction refresh, limited V6 coverage

`incubator/runs/after-close/close-20260925/after-close-summary.json` and the
campaign/model receipts report two completed models, zero failures or blocked
runs, and `prediction_refresh_complete=true`.

| Model | Predictions | Source passes | Receipt recorded Friday |
| --- | ---: | ---: | --- |
| V5 | 6,985 | 26 | 15:31:16 |
| V6 | 974 | 3 | 15:32:47 |

Both models loaded and exited zero. Result JSONL counts match the receipts;
the staged feature parquet and every source parquet hash match their manifests
under `incubator/artifacts/daily/v5-20260925` and `v6-20260925`.
The enabled after-close timer last triggered Friday at 15:30:05 and next runs
Monday September 28 at 15:30. The journal retained no Friday entries; the dated
artifacts and timer state provide the evidence here.

V6 consumed all three available Friday source passes: signal closes 19:00,
19:30 and 19:45 UTC. The original scanner portfolio database also has only three
Friday candidate cycles. This is not proof of full-day V6 coverage. The cause
of missing earlier candidate passes remains unresolved; existing logs show
scanner activity and exit events earlier in the day, so do not claim it was
simply off until the afternoon. Do not repeat successful incubator replay as a
repair for missing upstream evidence.

Both receipts remain `executed_pending_outcome`, with null performance metrics.
Prediction refresh success is not an evaluated trading-performance result.
Exact outcome joins and scoring remain unfinished.

## FA: healthy collection, insufficient evaluation history

Operational worktree: `/home/healy/Coding/HealysAutomation`. Its latest health
report and scheduled news, fundamentals, features, evaluation, tracking,
archive-pull and StockTwits jobs report success/healthy. Reddit and EDGAR are
collected through the server/archive path; local skip configuration is not a
whole-system collection failure.

Latest snapshot:
`fa/artifacts/enrichment/20260927T014037632061Z/manifest.json` in that worktree.
It covers 300 symbols; financials cover 232, float 228, short interest 300 and
short volume 300. Price-history feature coverage is 120 symbols. The older
FA notes calling the whole fundamental overlay a scaffold are stale as an
operational description; broader causal context-bar work remains pending.

Latest evaluation:
`fa/artifacts/enrichment_reports/20260927T020036287757Z.json` in that worktree.
It has **960 labeled rows over six labeled days**, no folds, and status
`insufficient-purged-history`. Policy requires 40 training days and 10 test days,
with purging; rerunning the same six days cannot satisfy that policy.
The first clean prospective monthly run is scheduled September 30 at 20:15;
health correctly reports awaiting its first scheduled run. No clean monthly
cohort was present at inspection. August evidence remains contaminated and
historical only. FA remains experimental, outside V7/live trading.

Next FA work is the existing FA-0 data contract and quality inventory, followed
by causal context bars and accumulation of clean prospective history. This
operational check does not certify the full source/partition quality audit.

## V6 Alpaca: account ready, trading integration not ready for Monday

Fresh authenticated read-only account check at `2026-09-27T20:15:31Z`:
ACTIVE, trading not blocked, $100,000 cash/equity/options buying power, options
approval/trading level 3, zero positions and zero open orders. Safe snapshot:
`/tmp/v6-alpaca-paper-readiness-20260927.json` (temporary local evidence).

However `/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper/paper-restart.json`
still has `scanner_enabled=false` and `order_submission_enabled=false`. That
state has no portfolio or broker-order database. Its copied data index ends
September 23 while the old simulator index has advanced through September 25.

Installed `healys-v6-forward.service` still targets `v6_server`, the old simulator.
The installed Alpaca timer is the read-only account monitor, next Monday 08:00;
there is no installed order-bridge schedule. Monitoring does not enable trading.
The bridge core already exists and has prior tests; its previous zero-event
preview did not establish prospective lifecycle readiness.

Remaining activation work: connect fresh scanner/data refresh and genuine new
structured lifecycle events to the existing bridge; verify preview and broker
reconciliation for entries/exits/rolls; then explicitly activate the paper
schedule. Preserve the old simulator and do not import its positions. Existing
partial/uncertain-order and multi-roll review stops must remain effective.
Monday Alpaca execution must not be described as ready until this work lands.

## Validation boundary

Inspected existing receipts, hashes, result counts, SQLite records, installed
service/timer configuration, FA job reports and an authenticated read-only
account response. No implementation changed, so no training or test suite was
rerun. V7 capture settings and running work were untouched.
