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

## BOTH VERDICTS LANDED 2026-08-24 (~03:30 and ~04:15 CDT)

**v4 finalize: ELIGIBLE — the first V118 bundle exists and is committed.**
`v4-finalize-6ab5120-023421` (the 010121 n2 job stocked out ~90 min
cycling QUEUED↔SCHEDULED; deleted, resubmitted on e2 — precedent 08-19):
winner **gbt × 40 seeds, `ev/0.05`, dd_brake=None** — val +604.8%, n_kept
219, maxDD 21.9%, ledger-selected, magnitude head persisted. Gate bar
(ex-top3) +31.4% vs candidate +605%; raw baseline +1854% recorded, no
longer the bar. Bundle rsynced from
`out/finalize-20260824T073639Z-44b60/`, local `v4_scan --selftest` OK
(40/40, verified+eligible, median 0.433), force-added in `75ef456`.
dd_brake is None so the not-yet-enforced live brake doesn't matter.

**Deploy is gated on TWO things, in order (user decides the timing):**
1. `/ultrareview` from the DESKTOP session (user-launched; main is
   deliberately held behind the branch) → merge to main.
2. Candidate-parity re-validation against THIS bundle (Option B step 4) —
   then server `git pull`, selftest, drop `--paper`.

**spx0 round 2: REJECTED — test blowup, no seat** (EXPERIMENTS
2026-08-24). Fold 1's winner passed the val gate then returned −1863% on
test (maxDD 1126%, equity through zero): stop-based margin does not bound
a naked 0DTE short's tail. Structural lesson logged: a future short seat
needs loss bounded by construction (verticals/margin = strike distance),
not by a stop. USER DECISION on the next lever (SPX0_SPEC item 3 for the
long book, and/or defined-risk short redesign). Nothing running on GCP.

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
