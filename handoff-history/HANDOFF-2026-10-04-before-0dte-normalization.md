# Handoff — October 4, 2026 — Fresh Alpaca ETFE and five-DTE cap

## User direction and completed scope

ETFE starts fresh with Alpaca stock/options data; no old project metadata,
market data, feature arrays, labels, checkpoints or models are inputs. The user
also caps traded options at five DTE. Preserve the prior one-day minimum:
**1–5 calendar DTE at every entry/roll attempt**, targets 1/5 plus eligible 2/4.
Target 7 removed; context-only 1–45 DTE surface demand remains separate.
[Current scope](docs/specs/ETFE_SCOPE_ALPACA_20261004.json),
[DTE successor](docs/specs/ETFE_DTE_20261004.md),
[fresh collection successor](docs/specs/ETFE_FRESH_ACQUISITION_20261003.md).

## Changes and evidence

- Independent resumable Alpaca downloader: source-bound manifest, checksummed
  immutable responses/page commits, rate/budget guards, raw reader and audits.
- Fresh bootstrap complete: 30 partitions, 36 live GETs, all HTTP 200.
  50,106 stock bars; 2,284 option bars; 39,975 trades; 2,084 discovery records.
- Stock windows: January 2024 and October 1–2, 2026. Option transport samples:
  January 18, 2024 and October 2, 2026, calls and puts for each ETF; full-day
  bars/opening-30m trades. October same-day samples are not eligible purchases.
- Live stop/resume preserved the three previously committed file hashes.
  About 9.55 MiB raw roots; peak reported RSS 835,710,976 bytes. This does not
  forecast full dataset/training resources or close the integrated pilot.
- New immutable v3 setup and DTE guard. dte_frac's new-schema denominator is 5.
  All twenty families and 25,353 ticker variants remain; no full execution claim.
- 73 focused tests passed; current and predecessor integrity checks pass.
[Review](docs/reviews/2026-10-04-etfe-fresh-acquisition.md),
[portable receipt](docs/reviews/2026-10-04-etfe-fresh-acquisition.json).

## Stopping point and next actions

1. Normalize fresh page chains into typed bounded partitions; reconcile sessions,
   timestamps, conditions, missingness, duplicates and source lineage.
2. Build complete scoped stock/context/option demand. Enforce the new 1–5 DTE
   guard in candidate selection and roll execution; keep context scope distinct.
3. Expand capture with measured budgets and establish earliest scoped coverage.
   January 18 is an observed lead; January stock padding is not an options floor.
4. Integrate feature/execution/dataset/training smoke measurements and recovery
   under ETFE-4.pilot; then full acquisition/freeze in ROADMAP order.

Do not block raw collection on provider-global history proof or old metadata
repairs. Source/dated-term/eligibility questions remain for scientific admission,
not permission to download. ETFE-0 admission, ETFE-1 full coverage, integrated
pilot, full builds/freezes and training are still open. No deployment/model verdict.

## Exact pointers and constraints

Selected setup: `nn_meta/validation/etfe-setup-20261004-alpaca-r0/`; plan SHA256
`212b52b034190ea3dd5c5bf5b0f097897a09bcce241004afaa9db6220e94a136`.
Verify: `./venv/bin/python scripts/prepare_etfe_current.py verify --root nn_meta/validation/etfe-setup-20261004-alpaca-r0`.
Fresh data: `nn_meta/data_cache_etfe/alpaca-fresh-20261003-bootstrap-r0/` and
`nn_meta/data_cache_etfe/alpaca-fresh-20261004-options-r0/`. The capture CLI is
`scripts/acquire_etfe_alpaca.py`; it does not import the old runtime configuration.
[Current pointers](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[sequence](ROADMAP.md#etfe-first-run-sequence). Preserve prior setups/contracts,
unrelated dirty/untracked work and V7's completed archive. Other campaigns paused.
[Previous handoff](handoff-history/HANDOFF-2026-10-04-before-fresh-acquisition.md).
