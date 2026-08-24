# HANDOFF — state for the next session

Written 2026-08-24 (~01:10 CDT). Protocol: `CLAUDE.md`.
Previous handoff (braked-EV verdict, DD cap never binding, old box's last
days): `handoff-history/HANDOFF-2026-08-21-dd-cap-never-binding-new-box.md`.

## The box is NEW (2026-08-23) — the RAM-fault era is over

Ryzen 7 9850X3D (8C/16T), 32 GB DDR5, RTX 3060 Ti carried over, same 1 TB
NVMe moved intact (OS/paths/user `healy` unchanged; CLAUDE.md +
DOCUMENTATION.md updated). Old box's final morning segfaulted `fa.collect`
hourly; zero coredumps since the swap, StockTwits service clean, suite
green in ~14 s. Training still runs on Batch — the checksummed-artifact
and provenance arguments stand even though the corruption rationale is
now historical.

## Two decisions landed 2026-08-24 (commit `6ab5120`, suite 451, pushed)

1. **v4 gate baseline term = ex-top3 (user decision).** `_passes_gate`
   bars candidates at the baseline's `total_ex_top3` (raw fallback when
   unavailable); candidate side stays raw. The +1854% outlier-carried bar
   is gone. Grid print shows `gate bar = ex-top3`; `ensemble_config.json`
   persists `baseline_ex_top3`. DECISIONS 2026-08-24.
2. **spx0 second round built** (SPX0_SPEC items 1+2): six `TradeVariant`s
   per signal — long stops {.3,.5,.7}, sell-premium stops {1.5,2,3} — the
   variant code rides the `dte` column so rank/EV dedupe on (symbol,
   strategy, trade_idx) fold-selects it exactly like DTE in v4; code 0 is
   bit-identical to round 1 and stays the frozen baseline. Shorts: sell the
   opposite right, fill Low/buy back High, margin = (stop−1)×entry (max
   planned loss; gap-past-stop kept as data — smoke stop-outs avg −1.5 to
   −2.1× margin), cash settlement pays intrinsic with entry-side costs
   only. New features `spx0_short`/`spx0_stop_frac`/`spx0_prem_rich`;
   KEEP_THRESHOLDS gained .55/.60/.65. 12-session smoke + `--smoke`
   evaluate ran clean end-to-end through the ledger.

## LAUNCHED 2026-08-24 ~01:01 CDT — two jobs on Batch (image `6ab5120`)

Both verified SCHEDULED on the pinned image, STANDARD provisioning:

| job | what | expected |
|---|---|---|
| `spx0-run-6ab5120-010113` | round-2 build (6 variants, 500 sessions) + `--folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600` | build ~30 min + walk-forward several h (dataset is 6× round 1) on e2-standard-8 |
| `v4-finalize-6ab5120-010121` | 40-seed finalize against the NEW ex-top3 gate (same verified dataset+marks as 08-21) | ~40 min on n2-standard-8 |

Outputs: `gs://healys-backtester/out/{spx0,finalize}-<stamp>-<uid>/`.
Check live: `gcloud batch jobs list --project=healys-batch`.

**Read first, finalize:** the task log's `ensemble winner:` +
`candidate grid` lines — the grid now prints `gate bar = ex-top3`.
`eligible=True` → bundle in `.../model_final_v4/` → `gsutil rsync`,
force-add commit, server `git pull`, `v4_scan --selftest`, re-validate
candidate parity, then drop `--paper` (TODO blocks 1b/3). Note: **live
sizing does NOT yet enforce the DD brake** (shown, not enforced) — only
matters if the shipped bundle carries `dd_brake != None`.
`eligible=False` → v4 waits for the next label idea; log either way in
EXPERIMENTS.

**Read first, spx0:** `spx0_walkforward_report.md` — the mode column and
per-fold winners; against round 1 the question is whether any fold's
winner is a short variant (dte < 0) with a positive ledger test return
under the 25% DD cap. The build log's `(dte, exit_reason)` table shows the
raw variant economics. Verdict → EXPERIMENTS; if shorts show life, next
levers are SPX0_SPEC round-2 items 3 (intraday-native strategies swept
in-fold) then 5 (extend data to 2022).

## Standing warnings

- **Training/finalize run on GCP Batch**, not locally (provenance +
  checksums; the old-box corruption rationale is historical).
- Docker image BAKES the repo → rebuild + pin `IMAGE_TAG` after every code
  change; build from a `git archive` tree.
- Never report cloud state from memory — job state + task logs + bucket
  listing, live.
- `NN_META_POOL=v31` for everything v4/spx0. Deploy by `git pull`, never scp.
- Agent shell is zsh (bare `===` separators get eaten — quote them; no
  word-splitting of unquoted vars); `!` prefix is bash.
- Do NOT delete `gs://healys-backtester/out/archive-2026-08-19-stale-cache/`;
  do NOT pass `DELETE_BUCKET=1` to teardown.
- `prem_spot` leakage question still OPEN (needs its own feature-drop run).
- earlyoom runs the stock `--avoid`; tuned config staged, not installed.
- CLAUDE.md says 425 tests; actual 451.
- `/ultrareview` window still open (TODO): run from the DESKTOP session
  once the branch is quiet, then merge to main.
