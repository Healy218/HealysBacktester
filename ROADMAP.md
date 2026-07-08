# Roadmap — the plan for the plans

One page. Each phase gates the next; specs hold the detail.

```
NOW ──► v2.2 verdict ──► live alert server ──► Pop!_OS rebuild ──► v3 build ──► FA build ──► v4
                              │                                        ▲            ▲
                              └── FA Stage 0 collectors deploy here ───┘────────────┘
                                  (archive-first: history can't be bought later)
```

## Phase 0 — v2.2 walk-forward (RUNNING)
Windows/WSL2 box grinding 3 folds; checkpointed; monitor armed.
**Exit:** verdict row in `nn_meta/reports/meta_report.md` (ROBUST / NOT robust).

## Phase 1 — Live alert server
Deploy the v2 live scanner (`nn_meta/live/`, alert-only, research mode).
Needs: Pushover account (or Twilio if SMS preferred) — keys not yet in `.env`.
**Also deploy here: FA Stage 0 collectors** (Reddit/StockTwits/news/EDGAR raw
archive, see `FA_SPEC.md`) — trivial to run, and every month archived is a
month of backtestable history the FA phase gains for free.
**Exit:** alerts arriving on phone; collectors cron-ing; both surviving reboots.

## Phase 2 — Pop!_OS rebuild of the Windows box
After Phase 0 completes (wipe kills WSL and the run).
Pre-wipe backup: `artifacts/wf/`, `runs/`, reports, `wf.log`, `.env` → external
drive; everything committable → GitHub. Rebuild is ~20 min (all env gotchas
already solved and committed).
**Exit:** native-Linux box, env rebuilt, tests green, data cache restored.

## Phase 3 — v3: big-universe TA (`V3_SPEC.md`)
200+ point-in-time tickers, 2017→present, 1m-resampled underlying data,
on-demand option fills, TV-validated indicator library, GBT-vs-NN bake-off,
spot-CPU dataset builds. Gated stages 0–8 in the spec.
**Exit:** v3 walk-forward verdict + regime report.

## Phase 4 — FA: ticker discovery (`FA_SPEC.md`)
Coded while v3's long runs train. Sentiment + filings NLP + options flow →
frozen monthly Top-10 → forward-return tracker → graduation into the training
universe.
**Exit:** ≥3 monthly top-10 artifacts frozen and tracking forward returns.

## Phase 5 — v4: the loop closes
FA graduation feeds v3's universe reconstitution; retrain on the expanded
universe; discovery quality is judged by realized forward returns, not vibes.

---
**Standing rules across phases**
- Point-in-time everything; frozen artifacts; no retroactive edits.
- Checkpoint every long stage (spot-safe by construction).
- Evaluate portfolio-level, out-of-fold, with costs, ex-outliers.
- New complexity must beat the boring baseline (GBT, buy-and-hold basket)
  before it ships.
