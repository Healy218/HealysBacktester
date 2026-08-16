# Adversarial review — full project, 2026-08-16

Requested by the user ahead of the weekly usage reset. Method: hostile
re-read of the highest-blast-radius surfaces (everything deployed to
production this weekend, then the causal-evaluation chain, then ops/secrets),
with every finding **verified against the code or the live systems** — line
refs below were read, and empirical claims (git history, server logs, cron
state) were probed, not assumed. The complementary multi-agent pass
(`/code-review ultra`) is user-triggered and was not run here.

Scope note: the FA collectors and the layer-1 vectorbt/legacy-NN code got a
light pass only. Layer-1's known defects (June 2026 review in
`.claude/agent-memory/`) stand and are quarantined from everything live.

## Fixed during the review (commit `9b8b473`, deployed to the server)

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | **P0** | `data/vbt_data_loader.py:_cache_df` wrote the bar cache with a plain `to_csv`. Three scanner processes now fire on the same cron minute and share cache paths for overlapping symbols; interleaved writes could produce a torn-but-parseable CSV → **silently short bar history** → wrong/missed detections with no error anywhere. | Atomic tmp+`os.replace` write (+ regression test). |
| 2 | **P0** | The SQ→XYZ ticker alias existed only in `v4_scan`; the `[v31]` legacy scanner would hit `closed_bars(None)` → AttributeError for SQ **every pass** — a dead seat plus ~26 heartbeat-visible scan errors/day (crying wolf in the daily digest). | `TICKER_ALIASES`/`aliased_bar_loader` moved to `live/scanner.py`, wired into `run_live` (inert for v2/v3 — their specs contain no renamed tickers). |
| 3 | P1 | `v4_scan` imported the TF-heavy loader chain (`v4_loader → v4_evaluate → model → tensorflow`) at module level; the cron fires 96×/day and most firings exit at the RTH gate — pure wasted load on the CX33. | Lazy import inside `load_trusted_bundle()`/`selftest()`. |
| 4 | P1 | The weekly universe refresh atomically **replaces** the file the live scanners select contracts from; a pathological-but-exit-0 crawl could shrink the tradable chain silently. | `_guard_universe_shrink`: refuse replacement below 50% of the existing universe, exit non-zero (+ test). |
| 5 | P1 | `build_meta_dataset.assemble()` wrote `meta_dataset.parquet` (a committed artifact) non-atomically — a crash mid-write leaves a truncated tracked file. | Atomic tmp+replace. |
| 6 | **P0** | Discovered *during* the review: the v31 surface rebuild was **silently OOM-killed on the 8 GB server** — `load_daily_bars` concatenated the whole raw bar cache (12M rows post-refresh) before filtering, the kill left no traceback, and the refresh chain's `; echo DONE` masked it. The v31 surface would have quietly stayed frozen at 07-07 while every weekly "refresh" reported success. | Per-part column-pruned streaming reads + meta/dte/premium filters (identical output rows, test-proven); re-ran on the server — v31 surface now current through 08-14, 100% IV coverage on the last week. |

## Open queue (ordered; none block Monday)

1. **P1 — `bars_daily` grows without bound.** The weekly surface refresh
   re-appends each alive contract's full life-to-date; dedupe happens only at
   read (`build_surface.load_daily_bars`). Disk and surface-build time creep
   ~weekly. Add a post-refresh compaction (rewrite parts deduped) or dedupe
   at append. `nn_meta/download_universe.py` step 4.
2. **P1 — heartbeat is blind to the new experts.** `nn_meta/live/heartbeat.py`
   counts passes/errors from `live_cron.log` + `backtester.log` only; a
   crashlooping `[v4]`/`[v31]` cron would be invisible to the daily digest.
   Extend it to the three logs (per-expert pass/alert/error counts).
3. **P2 — paper-ledger drift window** (`v4_scan.scan_pass`): a crash between
   `alert_state.mark` and `ledger.open` delivers the alert (outbox replay)
   but never opens the paper position. Rare, self-limiting, worth a comment
   or an open-before-mark reorder with a caught duplicate-id.
4. **P2 — alias doesn't extend to context refreshes**: SQ's beta/IV context
   stays NaN/stale because the daily/surface crawls fetch "SQ". Fold
   `TICKER_ALIASES` into `download_universe`/`build_surface` symbol handling.
5. **P2 — `.claude/settings.local.json` is tracked.** Verified clean: commit
   `5474335` stripped the Telegram token *before* commit and a
   token-pattern grep across **all history** returns zero. Still unusual to
   track a local settings file; untrack at leisure.
6. **P2 — v3's tracked `.alert_state.json` landmine** (already in TODO): a
   future commit touching it conflicts with the server's live-mutated copy.
   Defuse deliberately on a quiet weekend.
7. **P2 — three scanners, one Alpaca key, same minute**: no rate-limit
   errors observed yet (weekend); if Monday's logs show 429s, stagger the
   expert crons by 2–3 min (dedupe keys make double-alerts impossible).

## Verified clean (positive findings worth recording)

- **Purge/embargo** (`temporal_validation.py`): assignment requires both
  entry and exit inside the split's information set; embargo applied at both
  boundaries; NaT exits fall to "purged". One accepted conservatism: trades
  still open at `test_end` are dropped rather than marked-to-market — which
  is precisely what Option B's ledger supersedes.
- **Eligibility-aware selection** (`v4_evaluate._policy_rank/_select_winner`):
  gate-passing dominates raw return in both the within-family and
  cross-family picks, exactly as documented after the 07-22 review.
- **Mark stream**: deterministic `stable_trade_id`; per-symbol validation at
  build time; the 88M-row sidecar streams shard-by-shard through a
  `ParquetWriter` into a **tmp file with an atomic rename** (verified —
  crash-safe); the ledger's no-synthetic-marks rule intact.
- **Finalize persistence**: staging + atomic swap + gate-refusal paths as
  documented (re-verified at the call sites, not re-tested).
- **Secrets**: `.env` mode 600, never tracked; Telegram token never in git
  history (probed); Hetzner key is Hetzner-only; deploy key read-only.
- **Live parity construction**: the v4 candidate batch is built by the same
  functions as the offline dataset; `prem_spot` structurally absent; schema
  drift fails closed (`assert_candidate_parity` + fail-closed missing-column
  check in `build_candidate_batch`).
- **State machinery** (`live/state.py`): all writes atomic; outbox
  at-least-once with key dedupe verified against crash-replay tests.
- **Build health**: 3 shards, 0 retry-loop events, marks landing per symbol.

## The day's structural lesson

Both of this weekend's near-misses — the frozen-window chain expiry and the
torn-cache race — are the same species: **research-time assumptions leaking
into the live path** (a frozen window used as a live horizon; a
single-process cache used by three processes). When adding a live consumer,
audit every input for "who else writes/derives this, and under what clock?"
