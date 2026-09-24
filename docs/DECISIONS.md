# DECISIONS — dated, append-only

### 2026-09-18 — Close 6-1 with explicit noncash boundary exclusions

The 234 remaining noncash provider records are resolved one-for-one as
source-bound `explicit_boundary_exclusion` treatments. Affected dated sessions,
and all sessions for an undated identity change, are excluded from usable
feature history; held-position paths crossing them fail closed. No successor
identity, stock/option deliverable, cash, or price factor is inferred. This
closes item 6-1 under a conservative admission policy and leaves 6-2 onward
unchanged.

One line of context, the decision, and why. Newest first. The point: don't
relitigate settled questions, and keep "considered and rejected" on the
record. Append here whenever a real choice gets made (or reversed — new
entry, never edit history).

- **2026-09-14 — Start the bounded short-DTE campaign immediately.**
  User explicitly requested proceeding now. New frozen scope
  `v6-short-dte-20260914-now` permits an early start today while retaining
  8GiB/200% CPU and the 08:30 UTC refresh cutoff. It started at 20:01:57 UTC.
  Both old queued `-launch` timers are disabled; new progress is bound to `-now`.
  Dataset audit precedes automatic model training. No model/design change.

- **2026-09-14 — Enable the local short-DTE dataset/training pipeline.**
  Following compute assessment and a successful end-to-end PIT-filtered pilot,
  install `v6-short-dte-20260914-launch` with the declared 8GiB/200% CPU budget
  and 22:30–08:30 UTC schedule. First full run is scheduled for tonight;
  training follows dataset audit automatically. Paper production stays active.
  [Launch evidence](reviews/2026-09-14-v6-short-dte-launch.md).

- **2026-09-14 — Keep paper V6 local while coding the short-DTE campaign.**
  After direct verification, the user accepted home calculation/portfolio and
  Hetzner monitoring/delivery, and deferred scanner deployment. The new
  `v6-short-dte-20260914` scope uses isolated source and generated 8-GiB,
  22:30–08:30 UTC units; none were installed or launched during implementation.
  The first coded trial fixes deployed GBT/Huber EV .05 and historical aggregate
  execution, preserves /45 feature scaling and rejects actual 0DTE/10+DTE
  purchases and replacements. These implementation choices are recorded in its
  machine-readable design. [Review](reviews/2026-09-14-v6-short-dte-campaign.md).

- **2026-09-14 — Frozen V6 experimental paper alerts use an explicit expiry
  cutoff 15 minutes before each option's final regular-session close.** User
  explicitly approved this operational convention after the historical
  completed-aggregate expiry fill limitation was explained. Weights, entry
  selection, sizing and underlying strategy exits stay frozen. Current ask/bid
  quotes and actual timestamps determine paper fills; no broker orders. The
  home producer and existing server notifier are active. Eligible late-close
  option classes and early closes use their own regular close. Exact numerical
  reuse and scheduling at bar close +5 seconds preserve the five-minute entry
  deadline and frozen outputs. [Evidence](reviews/2026-09-14-v6-forward-activation.md).
- **2026-09-14 — Next training is a separate actual-1–9-DTE V6 experiment.**
  Preserve the deployed broad-DTE model and paper portfolio. The user requested
  all notes be updated before clearing chat; no new training launched in this
  session. Enforce actual listed expiry after contract resolution, including
  rolls; short target labels alone are insufficient. Keep distinct artifacts,
  predeclare evaluation and tail treatment, and do not optimize toward a promised
  1,000% winner. [Design](specs/V6_SHORT_DTE_EXPERIMENT.md).

- **2026-08-21 — Finalize refused → do the magnitude/EV head FIRST, start
  spx0 in the overlap, never override the gate.** `v4-finalize-493af85-010321`
  declined the 40-seed ensemble on the most-recent tail (filter/0.5,
  val +22.5%, n_kept 78, eligible=False): the fold-3 weakness caught at the
  last gate. Three paths were costed: (1) train the magnitude/EV head
  (`nn_meta/ev_sizing.py` is code-ready but wired into NOTHING — the only
  reference is its own test), ~1 day of wiring + <$2 per Batch cycle on
  `n2-standard-8`; (2) loosen `MIN_KEPT_TRADES`/`MAX_DRAWDOWN_CAP`/the
  baseline rule; (3) skip to the spx0 pool, 2–4 weeks before anything can run.
  Decision: (1) first, because it is the cheapest on both axes and is the
  roadmap's own Wave-2 item 1; spx0 design/label-builder work starts while the
  v4 jobs run on Batch (compute is not the bottleneck — quota leaves 24 CPUs
  free beside an 8-CPU evaluate). (2) is REJECTED: overriding a designed
  safety to ship a bundle the data rejected three separate ways. If the EV
  head still fails the gate, v4 waits and spx0 continues — no V118 by fiat.
- **2026-08-21 — EV head definition: ONE regression head on the signed
  realized return, ONE new policy mode.** The magnitude head regresses
  `magnitude_target` (signed `net_return`, winsorized on the train tail)
  per seed, same family as the P(win) head; its prediction IS the expected
  return, so the policy's `pred_ev` is the head's output directly rather
  than `P(win) × E[win size]` (that product ignores loss magnitude, which for
  defined-risk options trades is most of the EV). Added as a third mode
  `ev` beside filter/rank — rank-and-size by predicted EV via
  `ev_weighted_portfolio`, per-name cap at `PORTFOLIO_FRACTION`, thresholds
  `EV_THRESHOLDS` in return units. One head and one mode on purpose: every
  candidate is a trial in the deflated-Sharpe count, and the gate (kept ≥ 10,
  beat baseline, maxDD ≤ 40%) is unchanged. Rejected: a 4-bucket classifier
  head (`return_bucket_labels`) — more trials, no evidence it beats the
  regression; revisit only if the regression head's deciles still invert.
- **2026-08-20 — Marks build moved from SPOT to STANDARD on-demand, 16
  shards at parallelism 8.** The spot pool turned churny: `marks-build-d64ca9b-161349`
  lost tasks 0/4/7 permanently, each having burned all four attempts, and two
  distinct exit codes were eating them — 50001 (Spot preemption) and 50005 (the
  6h `maxRunDuration`). On-demand removes the first; halving the slice size
  (16 shards, ~7 symbols each) plus a 12h cap addresses the second. Cost rises
  to roughly 3x spot per VM-hour, on the order of $10-20 for the remainder —
  trivial against the $300 trial credits and against the wall-clock already
  lost. Rejected: restarting the failed tasks (Batch taskGroups are immutable —
  there is no per-task retry API; the documented recovery is to resubmit, which
  resumes from per-symbol checkpoints), and 16-way parallelism (impossible —
  see below). The predecessor was CANCELLED rather than deleted so its failure
  record survives in `jobs list`.
- **2026-08-20 — `CPUS_ALL_REGIONS = 32` is the binding GCP quota, and it is
  global.** Free trials cannot raise it, so 8 x e2-standard-4 = 32 vCPU is a
  hard ceiling on concurrency regardless of shard count. The *regional*
  `CPUS = 200` quota is real but is NOT the constraint; checking it alone gives
  a false all-clear. Check with `gcloud compute project-info describe`, not
  `gcloud compute regions describe`.
- **2026-08-20 — 16 GB disk swapfile + earlyoom added to the home box.** A
  `claude` process hit 9.7 GB RSS and was hard OOM-killed 08-19 20:40; the box
  had 15 GB RAM and zram-only swap, whose compressed pages live in that same
  RAM and so provide no real headroom. The swapfile lives in a nested `/swap`
  btrfs subvolume so snapper can still snapshot `@` (snapshots are not
  recursive), is created via `btrfs filesystem mkswapfile` (NOCOW + no
  compression by construction), and carries no `pri=` so it sits at priority
  -2 beneath zram's 100 — zram stays the fast tier, disk is pure overflow.
  This is triage for the OOM only: it does nothing for the memory corruption,
  and the DIMM bisect remains the real fix.
- **2026-08-20 — Claude Code crashes on this box attributed to the hardware,
  not to Claude Code.** Three coredumps on 08-19 all faulted in allocator/GC
  threads (`mi-scavenger`, `HeapHelper`, `abort`) with the system under no
  memory pressure, on a machine with proven single-bit corruption. Rejected:
  filing a Claude Code bug, and the earlier "timeout" framing — herdr, its
  hook, all 15 MCP servers and the network were each verified healthy first.
- **2026-08-17 — gcloud auth: Workspace session control set to "never
  expire", no SA key.** The healylabs.io session-duration policy was
  logging local gcloud out (overnight 08-16/17, again mid-day 08-17),
  blinding the box's monitoring while cloud jobs ran. User (Workspace
  admin) set Admin console → Security → Google Cloud session control to
  never expire. The SA-key alternative (long-lived credential on disk) was
  considered and rejected as unnecessary once the policy fix exists. Cloud
  jobs themselves were never affected (VMs run on GCP's service account).
- **2026-08-16 — compute doctrine: heavy builds/training move to GCP Batch;
  the home box is for using, not training** (user goal, stated explicitly).
  Contingent only on the pilot's byte-identity diff. The box keeps: dev,
  small evals, and the API crawls (entitlement + keys never leave home).
  First migration: the in-flight marks build (stopped locally at 28/118;
  checkpoints sync to the bucket AFTER the pilot terminates — uploading
  mid-pilot would let a retry skip the pilot symbols and fake the diff).
- **2026-08-16 — v3.1 joins the panel as the [v31] paper expert.** Its
  "shelved" verdict barred it from *replacing* v3, not from running
  alongside: forward paper tracking is exactly how its outlier-fragility
  question gets settled. Legacy scorer path (`run_live` under
  `NN_META_POOL=v31`, hybrid provider via `get_provider(live=True)`),
  pool-suffixed alert state, `[v31]`-labeled alerts. `model_final_v31/`
  committed (2.7 MB).
- **2026-08-16 — the live universe refreshes weekly (`--live-horizon`),
  research windows stay frozen.** The deployed chain must never again
  inherit its horizon from `WINDOW_END` — that clip silently emptied the
  live chain when the frozen window's horizon passed. Weekly Sunday server
  cron rebuilds listings/universe through today+120d for both pools.
- **2026-08-16 — `model_final_v4/` is committed (force-add), deployed in
  paper mode.** Supersedes the 2026-07-25 out-of-git call for the deployable
  bundle only (9.7 MB — same pattern as `model_final_v3/`; reports stay
  gitignored). The [v4] expert runs on the server via `--paper` until the
  Option B re-finalize replaces the bundle in place and the flag is dropped.
- **2026-08-16 — branch merged to `main` for the alongside-deploy.** Verified
  first: only v3-critical deltas are a docstring + a default-off kwarg, so
  the live v3 scanner is behaviorally identical. Model *promotion* stays
  gated; main carries the additive v4 expert in paper mode.
- **2026-08-15 — Docs system: one ROADMAP, TODO per phase, fresh HANDOFF per
  session.** Specs demoted to `docs/specs/` reference; task tracking moved
  out of `V4_OUTLINE.md` into `TODO.md`. Old handoffs archive to
  `handoff-history/`.
- **2026-08-15 — Home-box crash investigation closed as a non-issue** (user
  call). No further diagnostic work; recovery/checkpoint infra stays because
  it's cheap insurance regardless.
- **2026-08-15 — Deployment model: experts are added ALONGSIDE the live
  scanner, never swapped in.** v4 ships as a second labeled expert next to
  v3; promotion to sole scanner requires its gates. Motivation: more
  triggering selectors (current ~1 alert/week is not enough) without ever
  risking the working v3 line.
- **2026-07-25 — `nn_meta/reports_v31/` and `model_final_v4/` stay out of
  git** (commit `64ff257`): regenerable / too large; headline tables are
  preserved in `docs/specs/V4_OUTLINE.md` and `docs/v31_run_history.md`,
  binaries in the D: backup.
- **2026-07-24 — GitHub auth is `gh` over HTTPS; the ed25519 key is
  Hetzner-only.** Do not set origin to SSH (the restore doc's contrary claim
  was verified wrong).
- **2026-07-21 — v3.1 NOT promoted to the live scanner.** ROBUST on paper
  but outlier-fragile (fold 2 ≈ one 31x TQQQ trade); live v3's edge is
  broad-based. v3.1's dataset became v4's input instead.
- **2026-07-21 — Option A / Option B split.** A: persist a deployable v4
  candidate now under the existing simulator (done). B: re-route selection
  through the mark-to-market ledger before trusting it further (the current
  phase). Order chosen so a candidate exists while the accounting hardens.
- **2026-08-19 — `v3/underlying.py` crawl end made exclusive; the 9y crawl was
  short one session per year.** `end = f"{year}-12-31"` is midnight, so every
  completed year silently dropped 31 Dec. Fixed to `{year+1}-01-01` plus a clip
  to the owning year (the wider request can return a lone 00:00 Jan-1 bar, and
  `load_1m` concatenates partitions without deduping). The CURRENT year still
  ends at today-00:00 on purpose: asking for tomorrow trips Alpaca's
  "subscription does not permit querying recent SIP data" and fails the whole
  year. Only SPY/QQQ were repaired; **re-crawling the other 287 symbols is
  deferred as a deliberate decision**, not an oversight — it is 289 symbols x
  9 years for 1 session in ~252, and it should be batched with some other
  reason to touch the crawl.
- **2026-08-19 — spx0 proxy underlying comes from the existing v3 crawl, not
  a fresh pull.** The stage-0 audit found `data_cache_spx0/underlying_1m/`
  holding SPY and QQQ at exactly 10,000 bars each (12 sessions, ending
  2024-08-16) — a truncated pull, covering 1 of the 521 sessions the option
  archive spans. `v3/data/underlying/{SPY,QQQ}/` already has 2017→2026-07-07
  at 1m in the same schema, so repoint rather than re-crawl; only the
  28-weekday tail (2026-07-08..2026-08-14) needs fetching. Rejected: a full
  2y re-pull (redundant, and burns quota on data we hold).
- **2026-08-19 — The spx0 seat must model fills, not assume them.** Audit
  measured a median of **3 contracts of volume per 1m bar** (p90 ~48) across
  the index roots. At that depth most 1m bars are untradeable, so a backtest
  that fills at every bar would be fiction. The pool concentrates on liquid
  strikes/times and stage-2 cost accounting gates the seat — consistent with
  ROADMAP already naming cost modeling the make-or-break for this expert.
- **2026-08-19 — Rebuild only the 90 symbols built 08-18, not all 118.**
  Bucket timestamps split the build cleanly: 28 shards written 08-17 against a
  complete flat-file cache, 90 on 08-18 after 44 day-frames went missing. The
  criterion is *which cache the symbol was built against*, not which happened
  to differ — SQ was built 08-18 and shows no contract change, and is rebuilt
  anyway. Saves ~25% of the wall clock without weakening the guarantee.
  Rejected: rebuilding all 118 (wasteful, and the 28 are provably identical);
  rebuilding only the 89 that visibly differ (would bake an inference into the
  artifact set).
- **2026-08-19 — Stale shards ARCHIVED, never deleted.** The pre-fix
  `meta_rows`/`meta_marks` and the assembled dataset are preserved at
  `gs://healys-backtester/out/archive-2026-08-19-stale-cache/` (118+118+2,
  verified before anything was removed). They are the evidence for the
  before/after comparison; the prefix must survive until the new dataset is
  verified.
- **2026-08-19 — Build-vs-build comparison gets a module, not a one-off
  script** (`nn_meta.dataset_diff`). A naive sort-and-walk comparison produced
  845 fabricated `dte` differences on AAPL, and keying on
  contract/strike/expiration hides exactly the rows a cache change moves. The
  module aligns on the signal, CHECKS key uniqueness rather than assuming it,
  and refuses to align rather than mis-pair. Validated by reproducing the known
  13-column result independently.
- **2026-08-19 — Reddit collector tolerates blips but still fails loudly on a
  wipe-out.** Retry 429/5xx per listing; a dead listing costs that listing
  only. `collect()` raises only when EVERY listing failed, because `fa.collect`
  counts a collector as failed only when it raises — a credentials outage must
  not pass as a quiet "+0 rows". Rejected: blanket try/except (hides outages),
  and raising on first error (the status quo, which lost the whole run).
- **2026-07-21 — CNN-on-chart-images rejected** for the classification
  track: discards exact numerical information for pixels; not serious
  industry practice.
- **2026-07-19 — Magnitude-aware labels / score-scaled sizing approved** as
  backlog: v3.1 calibration showed score ranks win *probability* cleanly but
  inverts on win *size* at the top deciles.
- **2026-07-13 — Deploy to the server by `git pull` only, never scp.** An
  untracked scp'd file silently wedged pulls for days.
- **2026-07-11 — Path A chosen for the big run** (120 symbols, ~2y options
  via flat-files) over Path B (9y underlying-only): flat-files probed
  definitively — same ~2y entitlement on every endpoint; deeper needs a paid
  upgrade.
- **2026-07-08 — X/Twitter API deferred** ($100/mo tier is a trickle, real
  access $5k/mo) until the pilot proves social velocity carries signal.
  Discord/Telegram scraping rejected outright (closed, unarchivable).
- **2026-07-08 — Hetzner CX33 over Oracle free tier** (ARM capacity
  unavailable; user declined the PAYG card hold).

## 2026-08-24 — V118 shipped on the local review; --paper dropped

**Decision (user):** merge `codex/v4-causal-validation` → `main` and deploy
V118 without waiting for a cloud ultrareview retry. The planned ultrareview
crashed (orchestrator: all agents terminated — infra, not a verdict); the
local `/code-review` had produced 10 verified findings, ALL fixed and
re-tested before the merge (`a300830`), and the bundle was regenerated on
the fixed code. Deploy chain: v3-safety diff audit → ff-merge → server
pull → on-server selftest → `--paper` dropped (crontab backup
`~/crontab.bak.2026-08-24`). The retry (2 of 3 free) remains available for
the branch at any time. Rejected: holding the live gate-eligible bundle
behind a crashed review tool with no ETA.

## 2026-08-24 — spx0 round 3: credit verticals + intraday-native seats

**Decision (user):** round 3 pursues both remaining levers at once — credit
verticals replace the condemned naked shorts, and intraday-native strategies
replace the daily-swing placeholder params. Grid: `ROUND3_VARIANTS` (long
stops {.3,.5,.7} + put/call credit spreads with wings 1/2/4 measured strike
steps OTM, codes −100x) × 11 strategy seats (5 v31 + vwap_rev 1.5σ/2.0σ,
ORB 15/30, gap-fill 30/50bp — each param setting its own seat, selected
in-fold like any strategy).

**Vertical mechanics settled by the 12-session smoke, in order:**
1. Legs fill as a PACKAGE — first bar where BOTH legs have depth, priced at
   that bar's closes. Worst-printing two legs independently compounds
   pathologically (−3.6× margin means) and double-counts the cost model.
2. Package costs — one net-premium half-spread crossing per side plus both
   contracts' fees (the complex order book trades the net, ~0.1–0.2 wide on
   a 5-wide vertical; per-leg full-premium spreads overcharged ATM ~10×).
3. The closing debit and every mark are clamped to [0, width] — a seller
   never pays more than the width to close (cash settlement bounds it), a
   negative debit is stale-print arbitrage. This makes −1×margin a HARD
   gross floor (verified in the smoke), the property round 2's naked
   shorts fatally lacked.
4. Credits above 90% of the width are rejected at entry — near-width
   credit ⇒ margin ≈ 0 ⇒ −68× net artifacts from stale closes, not a
   fillable market.

**Rejected:** margin = full width (masks leverage rather than bounding
loss; width − credit IS the worst case once the debit clamp holds); a
take-profit stop on the spread (bounded already; one fewer knob).

## 2026-09-05 — The live path never reads a day-keyed cache for the current session; streamed bars are the live source

**Decision:** `run_live._bar_loader` composes closed sessions (≤ yesterday)
from the smart loader's day-keyed CSV cache — valid, those sessions never
change — with TODAY's bars from the streamed bar store
(`nn_meta/live/feeds`, Alpaca SIP 1m → 15m, parity-identical to REST) when
its heartbeat is ≤ 3 min old, else a forced REST download. The cache is
never consulted for the current session. Feeds run on the server as
daemons under `@reboot` + 5-minute watchdog cron lines (no sudo there);
their heartbeats are in the daily digest.

**Cause:** the panel had scanned the previous session's bars all day since
2026-07-05 (EXPERIMENTS 2026-09-05) — a scanner that runs and alerts is not
a scanner that sees current data. Freshness is now judged by the newest bar
timestamp, never by pass counts.

**Rejected:** deleting the cache each pass (still one REST call per symbol
per pass; the free-tier 15-minute hole would have remained); a time-keyed
cache (the same class of bug one refactor away).

## 2026-09-05 — Scan cadence: fire one minute after the bar, stagger by pool, parallel detection

**Decision (user):** expert crons moved from `*/15` to `1,16,31,46` (v5),
`2,17,32,47` (v4, v31), `3,18,33,48` (v3) so a pass never races the bar it
wants and the 8 GB server never hosts all experts' worker pools at once;
detection runs in a spawn process pool (`nn_meta/live/parallel.py`,
`--workers` 3/2/2/1 on the server, `SCAN_WORKERS` env). Measured: v5 100
symbols 197 s → 50 s on the server; 60 symbols 66 s → 15 s on the box.
Scoring, dedupe, state and alerts stay single-process.

**Rejected:** 1-minute pass cadence (15× the work for no new information —
signals change only when a 15m bar closes; the box would saturate);
1-minute decision bars (a different seat needing retraining — REALTIME_SPEC).

## 2026-09-05 — v7 "real-time capable" means: offline twin + parity gate per intraday feature

**Decision:** decisions stay on the closed 15m bar. Any feature derived
from sub-15m data enters v7 only with an offline twin computed from history
(Alpaca SIP 1m for stocks; Massive minute aggs / trades / quotes for
options) by the same code, and a parity test live-vs-twin over ≥ 1 session.
Paper fills use streamed NBBO with the quote-verified ledger as the twin.
Spec: `docs/specs/REALTIME_SPEC.md`.

## 2026-09-04 — The v4 gate's beat-baseline term is risk-aware (return per unit drawdown)

**Decision (user):** `_passes_gate`'s beat-baseline term now compares the
candidate's validation `total_return / max(max_drawdown, GATE_DD_FLOOR)`
against the same ratio for the frozen book's ex-top3 ledger result
(`config.GATE_BAR = "risk"`, `GATE_DD_FLOOR = 0.05`). MIN_KEPT and the 40%
DD cap are unchanged; the candidate side stays raw. Supersedes the
2026-08-24 return-only ex-top3 bar.

**Cause:** the ex-top3 bar is a 5-slot first-come draw of ~200 trades from
~42k proposals; reshuffling only equal-timestamp ties moved it from −66% to
+283% on the 2026-05-21→08-21 tail (`scripts/gate_bar_sensitivity.py`), and
it carried maxDD 47–77%. A return-only comparison against that book
measures luck and ignores risk. On the same predictions, the risk-aware bar
was the only variant that discriminated: it passed filter ≤ 0.45 and the
ev/0.05 family and rejected the rest (`policy_gate_sweep.md`).

**Rejected:** (b) median ex-top3 over tie-shuffled draws and (c) ex-top-k at
5–10% of the book — both bars landed below zero here and passed a −12.6%
candidate; a bar of "don't lose more than X" is not a skill test. (c) at 2%
behaves like (a) and remains available via `GATE_BAR=ex_topk_pct`.

## 2026-08-24 — The v4 gate's baseline bar is the baseline's ex-top3

**Decision (user):** `_passes_gate`'s beat-baseline term compares the
candidate's total return against the baseline's `total_ex_top3` (the
take-everything book with its top-3 tickets removed, already computed
through the same ledger), falling back to the raw return only when ex-top3
is unavailable. Cause: the 2026-08-21 finalize refusals were carried
entirely by this term — the raw baseline showed +1854% on the validation
window, riding one 1526× outlier ticket, so the bar measured luck. The DD
cap and MIN_KEPT terms are untouched; the candidate side stays raw (a
candidate that catches an outlier deserves the credit).

**Rejected:** overriding the gate for one run (already on the record,
2026-08-21); winsorizing the baseline's returns (a second knob to justify;
ex-top3 already exists in the shared metric schema and is reported).

## 2026-08-24 — spx0 second round: sell-premium variants ride the DTE axis

Implemented per SPX0_SPEC "Second design round" items 1+2: every signal is
emitted at six `TradeVariant`s — long premium stops {0.3, 0.5, 0.7} and
sell-premium stops {1.5, 2.0, 3.0} — with the variant code riding the
dataset's `dte` column so rank/EV dedupe on (symbol, strategy, trade_idx)
makes the variant fold-selectable exactly like DTE in v4; code 0 reproduces
the round-1 long build bit-identically and stays the frozen baseline.

**Short mechanics:** a short SELLS the opposite right (bullish signal sells
the put), fills at the bar LOW on entry and buys back at the HIGH (worst
prints), posts `margin = (stop_frac − 1) × entry premium` — the max planned
loss, enforced by the premium stop above entry — and returns are per unit
margin so the ledger's units and the 25% DD cap keep their meaning. Gap
risk past the stop (and settlement) can exceed −1×margin; that is kept as
data (smoke build: stop-outs average −1.5 to −2.1× margin). Cash
settlement pays intrinsic with entry-side costs only (no exit crossing); a
market buyback pays both sides. New features: `spx0_short`,
`spx0_stop_frac`, `spx0_prem_rich` (last premium/spot vs the realized-vol
move to expiry); KEEP_THRESHOLDS gained 0.55/0.60/0.65 rungs for the short
book's ~0.7+ base rate.

## 2026-08-21 (evening) — Drawdown-aware gross brake on EV sizing

**Decision (user):** after the EV head fixed selection but the full
ensemble refused on the 40% DD cap, add a drawdown-aware gross scaler to
EV sizing and run it on Batch; the cap stays at 40%; no override.

**Definition:** at each entry, every new EV-sized position is multiplied by
`max(0.25, 1 − dd_now/dd_brake)`, `dd_now` = the EV portfolio's own
realized drawdown at that moment. Brake ∈ {None, 0.20, 0.30}, fold-selectable
beside the EV threshold through the unchanged gate. Only shrinks gross.

**Rejected:** raising the cap (already on the record); vol-targeting on the
underlying (needs a realized-vol series the selection path doesn't carry
yet — revisit if the brake isn't enough); a brake on the MARKED drawdown
inside the ledger (would make sizing depend on the accounting layer; the
realized-equity brake is simpler and tracks marked DD within ~6 pts on the
fold-2 evidence).

## 2026-08-24 (late) — PIT universe frozen: params, canaries, and two renames

**Decision:** freeze the point-in-time universe (2024-11→2026-07, 21
monthlies) with the spec defaults unchanged — enter ≤270 / exit >330,
63-trading-day median option dollar volume, ≥50 active days. The churn
report showed ~300 members and ~10 entries/exits per month; no retune
needed, so the parameters are now frozen with the artifacts.

**Canaries (empirical, from the backfill itself):** X (US Steel, last
trade 2025-06-17), SWTX (2025-06-30), WBA (2025-08-27) — each enters
membership while alive and is absent after death. MRO/CTLT/JNPR/HES/ANSS
were REJECTED as canaries: they died inside the window but their option
liquidity never cracked top-270, so they can't witness membership churn.

**Renames found by the build:** FI→FISV (2025-11-11) and BITF→DRAM
(2026-04-07), identified by next-trading-day handoffs with matching dollar
volume (the SQ→XYZ signature); added to `TICKER_ALIASES`, which stitched
both membership stints gap-free at the seam.

**members_asof semantics:** a freeze is usable during month M iff its
available_at falls within (or before) M — comparing against M's first
CALENDAR day wrongly zeroed out any month starting on a weekend (Dec 2024).

**Rejected:** freezing without named canaries (the driver refuses ≥12
months without them); seeding from the universe-filtered flatfiles_15m
cache (stage A re-pulled raw day aggregates per the spec).

## 2026-08-26 (overnight) — v5 freeze fleet: wide single-core on N2, resized from the cloud pilot

**Context:** the first cloud freeze pilot (AAPL,X,BYND on one e2 vCPU,
4h leash) was kill-looped: AAPL alone ran ~4.3h (ma 50min, macd 80min) —
the box measurement (DKNG 51min on a Zen5 core) under-predicted cloud
time ~5x, and the attempt died with zero symbols published.

**Decision (user, 2026-08-26):** go WIDE, not deep. The freeze is
single-threaded (`baseline.freeze_all` is one process, one family at a
time), so per-symbol tasks stay 1-core/12GiB and the fleet packs five of
them per n2-highmem-8 spot VM, 8h leash, 100GB boot disk (five containers
each stage their own ~10GB cache copy; the 30GB default would ENOSPC).

**Rejected:** the 8-cores-per-symbol shape (would need family-parallel
freeze + merge code written overnight, and caps at ~3x/symbol because
macd is an 80min critical path); e2 machines (regional E2 quota is only
24 CPUs; N2 has 200); e2/n2-highmem-16 packing without a bigger boot disk.

**Quota reality check:** the project-global `CPUS_ALL_REGIONS=32` (free
trial, unbumpable) is the BINDING cap despite regional reads of 200 —
max width is 4 VMs = 20 concurrent symbols, ~2 days for 453 names. Wider
needs the billing upgrade (credits carry over) + a quota request — the
fleet is submitted with parallelism 60 so a mid-run bump widens it
automatically.

**Also landed:** task.sh non-v31 pools now publish under `out/<pool>/` —
the unsuffixed out/ names are v31's live artifacts (118 meta_rows + the
assembled dataset); a v5 build would have skip-checked against v31 rows
and a v5 assemble would have overwritten v31's dataset in place. Training
modes publish pool-suffixed reports/runs dirs (v5 outputs would otherwise
have died with the VM — the P1-6 mode).

## 2026-09-01 — v5 build stage: spot survivability over spot avoidance

**Context:** the 441-symbol dataset build is ~8h of single-process work
per symbol (10 families × DTE grid). On spot VMs reclaimed every ~3h
during US business hours, whole-symbol checkpointing meant Monday
2026-08-31 netted roughly ONE symbol in five hours.

**Decision (user, 2026-09-01):** make spot survivable rather than paying
to avoid it. Three moves, in order of impact:
1. **Per-family checkpoints** (`build_symbol_rows(partial_dir=)`): each
   completed family persists rows+marks atomically and a rerun resumes at
   the first unfinished one. Preemption cost: ~8h → ~40min.
2. **Home box as a third build worker**, walking the spec BACKWARDS to
   meet the cloud fleets in the middle; the bucket skip-check is the only
   coordination. The Ryzen runs cells ~5–10× faster than a packed cloud
   core.
3. **Twin fleets on two machine families** (c2d + n2, same image, same
   checkpoints). Proven the same day: c2d's spot pool went dry for 3h
   while n2 filled all 20 slots within 10 minutes of submit. The 32-CPU
   global quota caps total concurrency, so the twin costs nothing.

**Rejected:** on-demand VMs for the remainder (~$134 — most of the
remaining credits, would squeeze the training stage that is the actual
point of the campaign); more cores per task (the build is one process —
width is the only lever); waiting on the CPU quota increase (Google
routed it to a Sales-POC dead end twice).

**Accepted caveat:** box-built rows come from the venv, not the docker
image, so BLAS-level float differences vs cloud-built rows are possible.
v5 has no identity-diff gate (that was the v31 rebuild), so heterogeneous
provenance is acceptable; recorded here rather than papered over.

**Also decided:** `boot_restart.sh`'s per-boot Telegram heartbeat now
defaults OFF — it earned its keep on the crash-prone i5, but the Ryzen
box is stable and a ping per routine boot is noise. Relaunch notices
still fire. Conversely a **reverse dead-man** (home box → Hetzner) was
ADDED after the 2026-08-27/28 outage went unnoticed for ~31h: nothing was
watching the server, only the server watching the box.

## 2026-09-03 — assemble + training move to the home box; the "never train
## on the box" doctrine is retired with the hardware it was written about

**Decision (user):** the v5 assemble and the evaluate/finalize ladder run
on the home box. Cloud stays available but is no longer required for them.

**What this overturns.** `deploy/gcp/task.sh` carried a strong rule that
training must NEVER run on the home box, because that machine had PROVEN
single-bit memory corruption (2026-08-18: a bit flipped r->v inside a .pyc
the CPU was writing; evidence retained at `docs/incidents/`). The rule was
correct for its subject — **the i5-11400/B560 build with the faulty RAM.**
That machine was retired 2026-08-23 and replaced by the Ryzen 9850X3D with
new DDR5. The premise is gone, so the rule goes with it. The comment in
task.sh has been rewritten to say so, because a future reader would
otherwise route training back to the cloud on the strength of a warning
about hardware that no longer exists.

**Why now, concretely.** Credits are nearly exhausted ($36.85 of $300 left
on 2026-09-02, see the billing post-mortem in DOCUMENTATION.md), and the
box is not a fallback — it is measurably the better machine for this work:
2.33 symbols/hour against 1.98 from a 4-VM spot fleet, ~5x per worker.
Training on it costs $0 and preserves the remaining credits.

**The risk that does NOT go away, and how it is handled.** The new RAM is
unvalidated, and these steps still produce the bundle that is committed and
deployed to production. Silent corruption does not announce itself, so
"it didn't crash" is not evidence. **Validate by determinism:** v4_evaluate
and v4_finalize already emit `SHA256SUMS.txt` over every output — run
evaluate twice with identical seeds and diff the hashes. Byte-identical
output means no flip landed in a training array or a model weight. A
memtest86+ pass is the stronger check when a reboot is convenient.

**Practical constraints noted at decision time:** (1) most row/marks shards
live only in the bucket (cloud-built), ~1 GB to pull down before assemble;
(2) the mark stream is the memory-sensitive step — v31's 88M rows peaked
~9 GB via `pd.concat` and died on the OLD box, which is why the shipped
path streams shard-by-shard through a `ParquetWriter` (~0.2 GB peak). v5
has 441 symbols against v31's 118, so expect 300M+ rows; the streaming path
should hold, and the box now has 32 GB rather than 15.5 GB, but this is the
step to watch rather than assume.

**Rejected:** paying the last ~$10 of credits to run training in the cloud
(it buys nothing the box cannot do, and leaves no margin for a re-run);
and treating the 2026-08-18 incident as a permanent property of "the home
box" rather than of the specific retired hardware.


## 2026-09-05 — Repair the adversarial audit before reusing research results

The user requested fixes for every September 5 audit finding. Correct causal
inputs, event/cost accounting, publication/state durability and research
splits in the review checkout; retain the original audit and experiment
history. The shared contract is `2026-09-05-causal-v2`. Old freezes, generated
rows/marks and verified ensembles must be rebuilt and revalidated; do not
silently resume them under corrected semantics. Target moneyness is a
decision-time feature; the executed strike is execution metadata.

A globally frozen proposal generator may only be assessed on validation/test
periods after its optimization horizon. Such evaluation is explicitly
conditional on that frozen generator; it is not a claim of fold-local
refreezing. Genuinely end-to-end nested evaluation requires fold-local
proposal rebuilds. The historical September 4 risk gate decision is retained,
with its selection history disclosed; no new untouched forward-performance
verdict is asserted by local source tests.

Implementation and validation: [remediation report](reviews/2026-09-05-remediation.md).


## 2026-09-05 — Merge to main, preserve pipeline notes, TradingView next

The user directed merging the review fixes into `main`, continuing in
`/home/healy/Coding/HealysBacktester`, and doing the TradingView work next,
before rebuilding the research artifacts. Integration validation passed: 642 tests and 18 subtests;
the 535-test count in the preserved notes is the pre-merge result. A local
merge does not deploy the server or launch a freeze/build/training campaign.

Newer operational notes and the v7 real-time contract are retained. Existing
paused/generated artifacts remain historical; old resume/reuse instructions
do not override the causal-v2 migration requirements. Shared alert-format
changes still require the user's go/no-go.


## 2026-09-05 — TradingView selection and six-workstream implementation

The user requested the ten most boosted scripts across every exposed page of
the supplied general TradingView listing and the three most boosted Editors'
Picks. The completed inventory ranked exact boost counts over 1,000 recent
general scripts (42 pages) and 758 Editors' Picks (32 pages), yielding thirteen
distinct indicators. Their detail pages label them open source; Pine source
pinning, licenses, causal rules and mathematical parity remain separate
implementation checks. The optional all-time clarification was unanswered at
this milestone, so the literal supplied-page scope governs the current work.
[Selection and source snapshot](specs/TRADINGVIEW_EXPANSION.md).

The user then authorized starting all six organized workstreams with multiple
agents: documentation reconciliation; TradingView implementation; corrected
campaign preparation; rebuild/comparison after prerequisites; operational
readiness; and execution/broader research. This is authorization to start and
advance the work, not a claim that any ports, rebuilds, provider acquisition,
server inspection or deployment have completed. Dependencies remain explicit
in [TODO](../TODO.md). The shared alert-format go/no-go applies to a concrete
preview; resolver/calculation preparation can proceed before that decision.

Keep existing v6/v5 research windows equal and preserve all pre-audit v5
outputs and 211/441 paused v6 partials as historical artifacts. The corrected
campaign needs fresh freezes, rows, marks and provenance under
`2026-09-05-causal-v2`; compatibility checks must pass before any reuse of new
artifacts. Complete the admitted TradingView source/data contracts first,
then compare corrected baseline and expanded pools on the same funded,
fully costed ledger. Current default loaders reject old bundles, so source
and verified replacement models must be coordinated for rollout.

Reconcile active documentation rather than retaining contradictory open task
lists below supersession banners. Preserve the old checklist/roadmap/reference
in dated handoff-history snapshots, keep experiment/decision history intact,
and record prospective FA evidence separately from the contaminated August
monthly. Historical gate changes and model results do not create untouched
forward evidence.

## 2026-09-05 — Scoped source ports and immutable corrected campaigns

The first batch pins all thirteen requested public Pine revisions and implements
scoped calculations for eight. Keep these outside active proposal pools until
exported TradingView fixtures and each data/signal contract pass. Emre's MSB
subset does not claim order-box parity; ICT and VWOB remain feature/event-only.
Source performance dashboards are not option-ledger evidence. Preserve original
licenses and bind source, adaptation and runtime hashes for fixture review.

Corrected research uses explicit named campaign paths, full per-symbol freezes,
exact-list merges and immutable raw/source/runtime identities. A changed input
requires a new campaign name; do not silently resume old freezes after repairing
raw history. No campaign ran during this batch. The five observed underlying
holes block launch; the downloader boundary is fixed and the restored SPY pilot
supports a wider repair, not an assertion that the archive is complete.

The contract resolver remains a captured-data preview with deliverables marked
unverified pending contract-reference data. Production alert-format approval,
offline selection parity and quote-verified accounting precede execution wiring.
[Implementation evidence](reviews/2026-09-05-readiness-milestone.md).

## 2026-09-06 — Raw strike basis, richer option history and existing sockets

The user requested a fresh v6 rebuild if possible tonight, reuse of the server's
existing live sockets in v6/v7, and historical Massive quotes/trades as features.
The initial near-live target remains decisions on completed15-minute bars.
Capture richer observations before model admission; do not infer guaranteed
predictive improvement or exact fills from added data.

Advance the build contract to `2026-09-06-raw-spot-v3`: option strike selection
and IV need raw contemporaneous stock spot, separate from adjusted technical
history. The old adjusted-spot filter demonstrably excluded relevant contracts
(IBKR's split is a concrete example). Rebuild surface daily summaries from the
existing broad option archive while preserving all observed contract identities.
All roll selections wait for a known close and fill in a later bar. Preserve
old artifacts and fully refresh both stock bases after sampled adjustment
comparisons revealed multiple historical vintages.

Historical tick capture is bounded by explicit contract/time selections, strict
pagination and input hashes. Missing trade identifiers preserve multiplicity;
unknown trade conditions remain unsigned. Historical SIP clocks and live SDK
receipt clocks are distinct. Opt-in OPRA recording reuses the existing daemon
and exposes capture failures without asserting uninterrupted coverage. No
server deployment, live subscription change or notification follows merely
from committing this work.

All thirteen requested TradingView sources now have scoped local calculations.
Keep actual numerical fixture and input-contract admission gates; chart/native
features are not fabricated from OHLCV. Existing Keltner breakout and BBW
rolling-minimum strategies retain their formulas and now have sweep/replay
regressions. A corrected data/build pilot is preparation for the expanded
comparison, not completion of quote-feature training or production readiness.

## 2026-09-06 — Keep materialized contract caches outside sealed inputs

The first SPY/IBKR raw-price pilot wrote 1,299 derived contract files into the
sealed candidate because the historical provider inherited the shared writable
cache location. Stop that scope, verify all 123,471 original payload hashes,
and quarantine only the added files. Restore the exact original inventory and
keep the existing manifest/seal unchanged. The completed IBKR shard belongs to
the aborted scope and is not reused.

Named historical campaigns now own their writable `runs/provider_cache`.
Sealed contract files remain read-only fallbacks. Use unique atomic temporary
files for concurrent writers and per-underlying lifetime indexes to avoid
repeated full-universe scans. The replacement pilot uses a fresh name,
`raw-options-20260906-r2`, and cold caches. Reusing the aborted spec or relabeling
the modified data as newly sealed would conceal the source/input mismatch.
[Recovery evidence](reviews/2026-09-06-pilot-cache-restoration.json).

## 2026-09-06 — Full v6 includes every requested addition

The user explicitly confirmed that all thirteen selected TradingView indicator
scopes and quote/trade features must be included when the full v6 freeze/build
starts. The SPY/IBKR existing-family pilot validates the repaired pipeline;
do not scale it into an existing-family-only full rebuild. Complete external
indicator verification, sufficient historical quote/trade coverage and the
combined feature integration before freezing the full expanded campaign.
Keep the controlled baseline comparisons within the final research design;
they do not replace the requested expanded build.

## 2026-09-06 — full v6 includes all thirteen scopes and option ticks

The user's latest instruction authorizes completing and starting the full
expanded freeze. Its scope is twenty proposal families, thirteen selected
indicator feature groups (96 columns), and ten historical tick columns.
Eight sources have explicit directional wrappers; five remain features.
Fixed source defaults avoid admitting unverified grid combinations. Setup
identities are typed strings and preserve source book priority.

A new opt-in research contract binds actual parity/default/proposal/context
and immutable tick inputs. Shared label/feature selection uses previous-date
observed contracts and current raw spot, with no current snapshot Greeks.
Missing windows are errors; unknown conditions stay outside eligible trades.
Actual source comparisons cover accepted proposal exits as well as indicator
fields; warmup-only NaNs cannot establish active-value parity.

The older core pilot completed its two freezes and IBKR build, then its
remaining SPY worker was deliberately stopped before source integration.
All original input bytes/scope/runtime/seal were verified unchanged first.
Its nonzero exit and artifacts are preserved, and its descriptor is retired.
It is not relabeled as the user's expanded rebuild.

The full freeze launcher was invoked and refused the absent reviewed input
manifest. Actual chart exports/context and broad tick coverage remain gates;
no synthetic or self-declared admission artifact will replace them. No extra
user launch confirmation is needed once these real inputs/checks pass.

### 2026-09-06 — Defer external comparison, retain full TV13 scope

The user explicitly requested moving past external TradingView comparison and
keeping all thirteen indicator groups in v6. Added an explicit deferred policy
with a distinct unverified research contract, full 106-column scope and all
twenty proposal families. The manifest records the reason and complete feature
settings; no parity report is synthesized. The verified path remains available.
This supersedes the external-comparison prerequisite for the research run.
Per-symbol 2D/VWAP context and historical tick inputs still must exist. Asked
whether to use explicit local research assumptions for the missing context;
that is a different choice from skipping output comparison.

### 2026-09-06 — Option 1 local context and full tick scope

The user selected Option 1, authorizing explicit local calendar/VWAP assumptions
while keeping every TV13 and option-tick feature. Two-session groups use the
retained calendar anchored on 2024-04-01; daily VWAP resets use New York dates;
minimum tick is a fixed 0.01 research assumption. No missing bars are inserted.
The local_research policy preserves observed membership transitions where
sparse history conceals ICT boundaries. Diagnostics identify one NYPM gap for
MULL and one NYAM/six NYPM gaps for SBET. Strict modes still reject these cases.

Real inventory execution exposed and fixed pandas rich-attrs propagation in
legacy strategy arithmetic and the naive-UTC/aware-UTC boundary between baseline
and expanded proposal wrappers. These fixes preserve caller data and event
timestamps; regression tests cover both. External parity is still unverified.


## 2026-09-06 — Parallel symbol capture with measured host headroom

User requested parallel tick-store processes after observing low host utilization.
Use `scripts/run_v6_parallel_freeze.py` around the unchanged pinned capture and
streaming materializer. Four symbol slots maximum, 16 network threads each;
size from measured idle logical CPUs and MemAvailable, exclude two whole
physical cores, budget 3 GiB/symbol plus 4 GiB reserve. Delay starts below 7 GiB
available and stop below 4 GiB. This is a sampled guard, not a cgroup memory cap.
Keep partial raw captures and completed stores in place; validate every store
before the original full-universe seal. Freeze independently resizes with 5 GiB
per worker and the same 4 GiB reserve. Scheduler source snapshot, process checks,
and per-symbol locks protect provenance and prevent overlapping supervisors.
Actual four-process launch preserved 181 stores. No fold design or causal input
changes; build/training remain gated. Main regression 1444 tests +18 subtests.

## 2026-09-07 — Two-hour fifth freeze worker trial, automatic return to four

User authorized trying a fifth v6 freeze worker for two hours and reverting if
throughput did not improve. `scripts/run_v6_freeze_trial.py` (PID 2541751)
drained the original launcher with SIGINT, re-ran the coverage/fingerprint/
campaign-lock gates, then queued five with a memory guard (MemAvailable < 4 GiB
or full-memory PSI avg60 > 5% for 120 s permanently lowers the target). Baseline
12.02 symbols/hour (24 completions, 11:01–13:01 UTC). Verdict recorded by the
controller: `return_to_four_memory_headroom` — trial rate 9.23/hour, memory
pressure avg60 1.2 %. Four workers stand for the rest of the campaign; a fifth
worker is not a free speed-up on this box. Rejected: leaving five running and
"seeing", which the memory guard exists to prevent.

## 2026-09-08 — Top-five cross-expert alert routing with strict probability floors

User asked for at most five highest-probability entry alerts per set of bars
during bursts, then a count of the remainder with a yes/button to see them.
Implemented on the production compatibility branch only (home research
sources untouched): a shared SQLite queue keyed by 15-minute cycle, ranking
by each expert's own P(win) (no recalibration, no new probability guarantee),
dispatch after all four completion markers or a 5-minute/12-minute deadline,
overflow notice with Telegram button and "yes" reply, summaries chunked to the
message limit. Follow-up the same day: floors v5 > 0.55 and v4 > 0.51 (strict)
applied on admission and again before dispatch; below-floor rows are kept as
`suppressed_probability` and excluded from remainder summaries; expired
callback acknowledgements no longer abort a requested summary. Evening
amendment (server review, below): one slot per symbol+side idea. Rejected:
throttling inside each expert (would not rank across experts) and a
persistent bot process (the minute cron polls replies instead).
[Review](reviews/2026-09-08-top-five-alerts.md).

## 2026-09-08 — Prepare the post-freeze v6 launchers at halfway; launch nothing

At ~227/453 freeze shards, wrap build/assemble, evaluate and finalize in
`scripts/run_{build,evaluate,finalize}_v6_local.sh` (preview by default,
`--run` to execute), each requiring its predecessor's successful receipt, the
merged freeze and the sealed input digest. Resource sizing happens at execution
(max four slots, 5 GiB each + 4 GiB reserve, two physical cores excluded), not
while the freeze owns the box. Three folds are requested; the evaluator keeps
only folds outside the proposal optimization window, so the eligible count is
not promised and zero eligible folds refuses. Build and training remain
unlaunched until the freeze returns zero. Rejected: auto-chaining build into
training (separate explicit commands keep the admission gates visible).
[Review](reviews/2026-09-08-v6-stage-launchers.md).

## 2026-09-08 — Server operations fixes: gate the option feed, tolerate quiet minutes, session-aware staleness, anchored watchdogs

A full-session review of the Hetzner scanners (first trading day after Labor
Day) found the panel operationally clean and eight things to fix; all eight
shipped the same evening on the compatibility branch
([review](reviews/2026-09-08-server-ops-fixes.md)). Decisions with
alternatives considered:

- **Option quote feed**: gate the stream until the watch list is non-empty
  and make the alert path register real contracts — rather than removing the
  daemon (it was burning a core for nothing because alpaca-py busy-waits until
  the first subscription and nothing ever wrote `option_watch.json`).
- **Streamed 15m buckets**: accept a missing minute when SPY/QQQ streamed it
  (stream provably alive), reject otherwise — rather than either keeping the
  strict all-15 rule (~190 REST fallbacks per cycle) or accepting any gap
  (would hide a real outage).
- **Staleness**: measure against the session calendar's latest closed bar,
  stale = more than one interval behind — rather than widening the wall-clock
  window (would also excuse a feed stalled mid-session).
- **Delisted names**: skip and remember per expert for a week — rather than
  editing frozen specs (they are frozen for a reason) or leaving them as
  errors (they dominated the heartbeat's count).
- **Top-five**: one slot per symbol+side; the runner-up strategy stays in the
  remainder summary.
- **Logs**: file handler WARNING+, quiet console filter that keeps tagged
  live-path lines, user-cron logrotate with copytruncate — rather than
  lowering the engine's log level globally (research runs want it).
- **Heartbeat**: warn on > 50 scanner errors, 0-contract options feed in RTH,
  surface > 8 days, failed refresh — rather than excluding loader errors from
  the count (would hide real ones).
- **Sunday refresh**: `run_refresh.sh` with 6 download workers and a recorded
  exit status — the 16-worker run was killed at 84 % on the 8 GB host and the
  `&&`-chained surface build silently never ran.
- **Feed watchdogs** (found during deploy): anchored `pgrep -f "feeds\.x$"`
  replaces the bracketed pattern, which self-matched the restart command on
  the same line. This REVERSES the "preserve bracketed pgrep patterns"
  instruction in TODO §5; DOCUMENTATION Traps explains when the bracket trick
  is and is not enough.

Not merged into `main` yet: the freeze campaign imports `nn_meta` from the
home working tree for every new freeze process, so the live-path source stays
on the ops branch until the campaign completes.


## 2026-09-10 — Year-end maturity target and v6 checkpoint

User requested GOALS.md with the September 10 assessment and a target of
≥7/10 in every area and overall by December 31, 2026. Continue the existing
ROADMAP and TODOs. Reassess after one week actually running v6 and completing
more TODOs; no immediate broad reprioritization or rewrite is authorized by
this goal alone. Scores require evidence, and durable trading edge remains
unproven until supported. The week starts with operational v6, not its build.

## 2026-09-12 — Derived-artifact training continuation and objective comparisons

User authorized practical training parallelization/vectorization, recommendations
using existing data, later-work notes and launch. Parent `v6-local-20260906`
completed all 449 eligible symbol builds; assembly was OOM-killed. Preserve its
pinned scope and failed receipt. New `v6-train-20260912` explicitly consumes
copied/hash-verified derived shards and parent-matching assembly inputs under
current source/runtime. It does not claim raw archives were reread or the
freeze repeated.

Use streamed assembly, two bounded seed processes, shared prepared arrays,
verified resume and sequential member inference. Keep baseline objectives,
seed counts and gates. Add event-balanced classification and downside-quantile
regression as separate research comparisons. Use explicit post-freeze folds
because the old schedule conflicts with generator provenance after dataset
gaps; results remain conditional. Details, tests, limits and later dependencies:
[training review](reviews/2026-09-12-v6-training.md).

The first continuation completed assembly/comparisons, then memory-high
throttling stalled evaluator preparation. Preserve that attempt/source.
Replacement `v6-train-20260912r2` imports verified completed outputs, uses
bounded-batch preparation and releases unused copies before workers start.
Real first-fold preparation: 29 seconds, 15.21 GiB peak RSS, 8.26 GiB after
release. Keep the 24 GiB hard cap; remove the overly restrictive 20 GiB soft
throttle. Latest suite: 1,468 +18 subtests passed. No objective retuning after
the comparison's held-out readout, and no change to promotion requirements.

## 2026-09-14/15 — Separate minute/multiple-timeframe research version

User expanded the short-DTE trial to all registered strategy variations over
1/5/15/30-minute stock signals and one-minute option execution using frozen
MASSIVE bid/ask quotes. Preserve the original train window (2024-08-26 to
2025-12-19) and historical window (through 2026-08-24); changing strategy
parameters is distinct from moving dates. Historical evaluation remains
previously inspected revalidation. Complete data/strategy/execution coverage
and resource pilots before launching the long build. The old 15-minute
campaign was stopped, with 21 completed symbols preserved and its main timer
disabled. Full backup/file inventory does not establish usable minute history.
See [design](specs/MULTITIMEFRAME_RESEARCH.md).

## 2026-09-14/15 — V7 uses full observed-quote history

User explicitly replaced the earlier fixed V6 dates with March 7, 2022
through today and requested a fresh V7 or V6.1. Name: V7. End resolves to
September 14, 2026, the latest completed regular session at preparation;
freeze that endpoint rather than advancing it during the build. Full feature
suite, 1/5/15/30-minute signals and observed-quote minute execution remain
required. Earlier data may support causal warmup; inferred spreads cannot
be represented as observed execution history. New chronological purged
fold dates remain to be designed/sealed before training. Audit the complete
feature dependency/PIT universe history; quote access alone is insufficient.
See [V7 scope](specs/MULTITIMEFRAME_RESEARCH.md).

## 2026-09-15 — Bound V7 acquisition and choose storage from measured workloads

The user authorized four-process acquisition and 250 GB of data downloads.
Interpret the cap as 250,000,000,000 retained bytes shared by base and quote
captures, with cross-process reservations and preserved failed attempts.
Capacity exhaustion pauses new work; it does not waive research coverage.
Keep historical observations and frozen launch sources immutable.

Implement shared MA windows, bounded quote unions and streamed storage first.
Keep Arrow IPC, Parquet, NumPy mmap and Zarr selectable: the SPY pilot favored
mmap/IPC warm reads, while Parquet saved space and Zarr was slower. No blanket
format migration, allocator/sysctl change or full-build speedup claim follows
from this component benchmark. All strategy/feature/execution and temporal
validation gates still apply. [Evidence](reviews/2026-09-15-v7-download-and-performance.md).

## 2026-09-15 — Retry delayed context without changing frozen V6 inference

The three morning refreshes exhausted their schedule while MASSIVE's prior-
session minute file was absent. Add a separate lightweight availability poll
and request the existing refresh when all needed files appear and services
are idle. Keep the strict context freshness gate, model and numerical source
unchanged. A successful availability poll is not a successful refresh or an
accepted paper pass. This avoids repeated full surface builds while the
provider file is missing. [Incident](reviews/2026-09-15-v6-paper-health.md).

## 2026-09-15 — V7 expiry remains unresolved; investigate stock entitlement

User explicitly chose to retain unresolved outcomes and block affected
V7 evaluations when an expiring position cannot obtain an eligible observed
bid. Preserve the position, null return and incomplete label; do not silently
exclude it from portfolio admission or invent exercise, abandonment or a
terminal value. This confirms the existing replay policy and frozen evaluation
requirement; it does not make the SPY call pilot evaluation-ready.
Focused replay/execution/portfolio regressions: 17 passed.

User authorized investigation of the Massive stock upgrade, not purchase or
external messages. Stocks Starter advertises $29/month, five years of minute
bars, sufficient date entitlement for March 8, 2022 as of September 15, 2026.
Actual records remain unverified behind the saved HTTP403. See
[upgrade investigation](reviews/2026-09-15-v7-massive-stock-upgrade.md).

## 2026-09-15 — Retain Alpaca stocks and Massive options

User clarified that the existing account has Alpaca Pro and the intended V7
source split is Alpaca underlying stock data plus Massive historical options.
This supersedes pursuing the Massive stock upgrade. Investigate the 26 March8
missing SIP sessions through Alpaca; successful but incomplete stock responses
are not evidence of an Alpaca subscription/history entitlement restriction.
The saved HTTP403 belongs to the alternate Massive stock endpoint only.
Preserve observed gap evidence, originals and the unsent Alpaca support draft;
no new subscription or support message is authorized by this clarification.
The selected unresolved-expiry/evaluation-blocking policy is unchanged.

## 2026-09-15 — Physical exercise supersedes unresolved-only expiry policy

Latest explicit user choice: model exercise and stock delivery, requiring
funding and observed liquidation prices. This supersedes the earlier choice
to leave all unsold expiring contracts unresolved. It does not authorize an
intrinsic-value cash settlement or borrowed funding/inventory assumptions.
Unavailable funding, deliverable evidence or executable stock prices still
leave affected outcomes unresolved and block evaluation admission.

[Implementation contract](specs/V7_PHYSICAL_EXPIRY_20260915.md) records the
cash/share checks, dated settlement, quote sources and completion criteria.
New `V7_EVALUATION_20260915_PHYSICAL.json` preserves the original declaration
and adds this policy as an amendment. Existing code/pilots are not migrated or
validated by recording this decision; implementation and real replay remain
required. Alpaca supplies underlying stocks; Massive supplies options.

## 2026-09-15 — User moves V7 start to birthday, March 15, 2022

User explicitly replaces the March 7 research start with March 15, 2022 and
asks to delete March 8–14. End remains September 14, 2026. This retires the
March 8 Alpaca repair investigation and Massive stock upgrade path for V7.
Implement as removal from the active derived dataset; original provider
captures and old pilots remain archived provenance, outside active inputs.
March 7 is also outside the label/evaluation window. Separate older captures
remain available for historical membership; feature state restarts March 15
and must warm up from retained observations without bridging the deleted week.

Create a new plan, evaluation amendment and input identity. Preserve all
11,268 variants per ticker, the fold dates, full feature requirements, Alpaca
stocks/Massive options and funded physical-exercise policy. Previously inspected
periods remain revalidation. No old pilot or outcome is relabeled current.
[Change evidence](reviews/2026-09-15-v7-march15-start.md).

## 2026-09-15 — V7 preparation implementation conventions

- Deleted March 8–14 sessions retain their positions in the 63-session PIT
  calendar lookback, contribute neither zero volume nor activity, and are not
  backfilled by older observations. Keep the 50-active-session threshold.
- V7 selected-contract rows use actual calendar DTE / 9 and log(strike/raw spot),
  with a causally available raw minute close aged at most 60 seconds. Target
  maturity remains provenance. Version factorized stores; reject old semantics.
- Missing initial daily context remains explicit NaN with recorded warmup
  status; preserve the March 15 start.
- Physical engine uses pro-rata paper quantities, funded cash/stock, separate
  commitments/settlement, and conservative availability at the next trading
  open after settlement date. Zero exercise fee and .001/.0005 stock fee/
  slippage are declared research inputs, not verified broker fee history.
  Do not change the five-slot/10%-premium policy to make funding tests pass.
- Component tests and the readiness aggregator do not admit real exercise or
  a full campaign. Captured official references, settlement dates, stock quotes,
  corporate-action deliverables and full-universe stage producers remain gates.

Evidence and limits: [preparation review](reviews/2026-09-15-v7-training-preparation.md).

## 2026-09-16 — V7 excludes the four OTC-transition issuers

The user says “Keep Alpaca-only stock data” and “no we aren't touching anything
OTC markets ... we can lose it.” Remove BBBY, FRC, REV and SI by their captured
security identities across the entire V7 research history. Preserve source
captures, original ranks/scores and remaining membership; no replacement or
reranking. Record this explicitly as an ex-post study restriction, not historical
knowledge of future delisting. Do not seek OTC data from Alpaca or another stock
provider. This supersedes the unanswered Massive/OTC access question.

Declaration: `docs/specs/V7_UNIVERSE_EXCLUSIONS_20260916.json`; active universe
593 tickers /591 identities. Physical-exercise rules remain: missing funding,
shares or verified settlement evidence stays unresolved. Removing these issuers
does not waive any remaining full-universe training-readiness gate.

## 2026-09-16 — Freeze V7 coarse dated sector taxonomy

Retain the nine existing sector columns, with classifications derived from dated
security-type/SIC/business-description captures joined by composite FIGI. This
is a declared V7 research taxonomy, not GICS or a retrospective copy of V6's
symbol map. Reference dates precede the eligible session; never backfill future
classifications across time or ticker reuse. Unknowns remain explicit all-zero
sector vectors with source and reason. A newer missing classification remains
unknown rather than being silently filled. See `nn_meta/v7/sectors.py` and the
frozen `nn_meta/validation/v7-sectors-20260916-final/policy.json`. Original
publication-vintage claims are not inferred from historical vendor reconstruction.

## 2026-09-16 — preserve V6 and predeclare initial V7 model pilots

After the observed SEDG exit was explained (BBW stock exit, not a 5% option-P&L
stop), the user directed us to leave the V6 experiment as it is and resume V7.
No proposed spread cap or midpoint fill/stop policy was adopted.

Initial V7 model comparisons are predeclared in
`docs/specs/V7_MODEL_TRIALS_20260916.json`: three objectives, constant baselines
and GBT/NN seeds 11/29/47, fixed budgets, identical purged selections and no
post-fit calibration. Weighted-win outputs are not treated as calibrated
probabilities. These are component trials with no winner/threshold selection;
full campaign scheduling, calibration/selection amendments, portfolio evidence
and multiple-testing diagnostics remain required. See the September 16 model
trial review. This does not authorize full training or change readiness gates.

## 2026-09-16 — user-selected midpoint option paper prices

The user explicitly directed both V6 and upcoming V7 to use one midpoint for
simulated option buying and selling, preferring a valid provider midpoint when
available and otherwise averaging bid/ask. Apply that convention consistently
to option entries, exits, roll legs and equity marks. Retain bid/ask, supplied
midpoint source and separate existing costs; last trade is reference, not a
substitute midpoint. These are simulated prices, not guaranteed executions.
This supersedes ask-entry/bid-exit for this paper experiment; it does not alter
underlying strategy/stop logic or the funded physical-stock liquidation policy.
Preserve completed V6 records and legacy V7 artifacts; use an audited retained-
quote transition only for outstanding V6 paper legs and rebuild V7 derived
execution artifacts under the new bound policy. Actual deployment found no open
V6 legs. Do not rewrite historical losses or reset equity.

## 2026-09-16 — original issuer resolves the DVN cash-action group

For DVN September13,2024, use the original August6 issuer release's $0.44 total
($0.22 fixed plus $0.22 variable). The captured Massive group totals $0.66 and
Alpaca lists $0.22. Preserve all four records; replace the entire group exactly
once with the reviewed total, never add it to provider components or generalize
this correction to another event. Immutable evidence:
`nn_meta/validation/v7-dvn-action-review-20260916`. This resolves one cash amount
and publication, not full-security action/identity coverage or training readiness.
[Evidence](reviews/2026-09-16-v7-action-inventory.md).

## 2026-09-16 — stop acquisition expansion and prioritize the executable build

The user explicitly corrected the preparation workflow: the 250 GB allowance is
an upper limit, not a storage target, and V7 training readiness remains the goal.
All current capture jobs have finished. Stop broad reference/news/issuer expansion
and use the captured data to complete full feature/proposal construction, actual
quote demand, execution/labels, bounded assembly and the full training runner.
Additional acquisition must correspond to a specific required missing build input;
optional reference completeness is not an independent training prerequisite.
Keep actual correctness issues visible and preserve the agreed date range,
features, Alpaca-only stocks, no OTC, midpoint option paper pricing and resource
limits. This changes the work order, not the validity of unresolved artifacts.

## 2026-09-16 — option-premium stops and confirmed ITM expiry timing

The user specified arithmetic (bid+ask)/2 simulated option entry and exit prices,
strategy-signal exits, and an option-midpoint loss stop versus entry midpoint of
7.5% for V6 and 12.5% for V7. This replaces the generic 5% underlying-stock stop.
Costs remain separate from the midpoint threshold; the existing 0.15% per-side
bookkeeping allowance is retained until changed. The user confirmed the ITM
expiry-day close occurs 15 minutes before the option's regular close, when no
earlier exit occurred. These execution changes are authorized for V6 and V7;
implementation, validation and V6 activation remain outstanding at this entry.
Preserve completed paper history. Do not call the previous midpoint-only runtime
compliant with the new stop/expiry rules.

## 2026-09-16 — option premium risk and arithmetic midpoint

The user selected arithmetic bid/ask midpoint for V6/V7 simulated entries, exits
and marks; fixed entry-premium loss stops of 7.5%/12.5%, respectively; and ITM
expiry exits 15 minutes before the option class regular close. Strategy signals
remain. Generic underlying 5% stops no longer control held exits. Existing 0.15%
per-side costs remain separate. A valid trigger quote supplies the sale midpoint
without a second quote request. Quote gaps remain explicit. Preserve completed
history, V6 frozen entry features, existing OTM rolls and physical fallback.

V6 repair deployed at d415733, followed by the September17 d252c51 expiry-roll
concurrency guard, with guarded activation, empty-book transition and
unchanged 13 closed records/equity. V7 uses the new OPTION_RISK active manifest;
raw predecessor bytes/producer bindings remain unchanged, with exact non-execution
scope verification. Affected proposals, labels and portfolios require rebuilds.
See [implementation and evidence](reviews/2026-09-16-option-premium-risk.md).

## 2026-09-17 — compact proposal storage and dated entry admission

Use typed ZSTD Parquet with a shared variant/policy dictionary for V7 proposal
batches. Reconstruct deterministic IDs/public fields on bounded reads; preserve
all variants, censored horizons and dated stock routing. The real all-variant
AAPL audit matched every field and reduced proposal bytes98.77% versus identical
JSON rows. PIT membership applies at entry only; leaving membership does not
truncate a held exit. Keep exact raw-unit parameter averages in saved causal
epochs for row reconstruction. This changes storage/consumer integration, not
strategy formulas, execution rules or full-universe admission.
See [verification](reviews/2026-09-17-v7-compact-proposals.md).

## 2026-09-17 — demand from actual proposal decisions

Use actual PIT-filtered proposals to select contracts and share identical causal
tick-feature requests. Preserve per-timeframe proposal counts and distinct target
identities; matching initial contracts do not imply matching future roll paths.
Export bounded contract/day groups for the existing shared-quota capturer. This
replaces the all-minute envelope for pre-entry feature demand only; execution,
marks, rolls and physical-delivery demands still require integration. The component
completion flag does not establish full quote coverage.
See [real-data verification](reviews/2026-09-17-v7-entry-demand.md).

## 2026-09-17 — Finish V7 one report deliverable per handoff

After reviewing the three-day progress report, the user selected its section 6
as the priority checklist at the top of TODO.md, numbered 6-1 through 6-7.
Current work is 6-1: complete usable identity/action histories under the agreed
admission policy. Completed work is indexed from ROADMAP/DOCUMENTATION and the
report; the overlapping old TODO is archived. Finish and verify each item's
closure evidence, update the docs, archive the handoff, and set the next handoff
to the next item. An unfinished item remains current; component success alone
cannot close a full-scope item. This replaces the review pause and scattered
parallel workstreams with a sequential workflow, without changing research scope
or starting background jobs as part of the documentation update.

No broader acquisition, added feature/model scope, V6 policy change, or relaxed
causal/execution gate is implied. Reuse existing work and acquire only a concrete
missing input needed by the current item. See the
[report](reviews/2026-09-17-three-day-goals-and-progress.md#6-consolidated-remaining-todos-before-the-goal-is-finished)
and [active checklist](../TODO.md).
## 2026-09-17 — matching ordinary actions as effective-session reconstruction

The user explicitly accepts matching provider terms as historical reconstruction
inputs, applied only from the effective session, retaining the assumption and
reviewing conflicts/complex actions separately. For a unique ordinary cash or
split record from each of Alpaca and Massive, exact matching effective dates and
terms, verified units and dated security continuity may support causal chart
adjustment without separately captured pre-event publication evidence.

Bind `docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json` in each new output.
An effective-open reconstruction availability clock is an explicit assumption,
not proof of publication; preserve null publication availability and
`publication_verified=false`. Preserve all original IDs, dates, units, source
receipts and missingness. Existing reviewed whole-group corrections, including
DVN, take precedence exactly once. Do not sum duplicates, admit simultaneous or
complex actions, infer option deliverables, change identities, or infer no-event
intervals from missing records. Full-security admission and 6-1 closure remain
separate. This supersedes the pending question in the source-routing handoff.

## 2026-09-17 — finite identity resolution from captured share-class witnesses

Resolve explicitly reviewed exact dates using the retained provider share-class
FIGI and an earlier captured listing of the scoped security, with identical
ticker, exchange, instrument type, market, locale, currency and issuer CIK.
This is a source-backed identity inference: [OpenFIGI's identifier definition](https://www.openfigi.com/api/documentation)
links composite FIGIs for the same instrument at share-class level. Require an
unambiguous active US listing on each reviewed day and reject a composite ID
already assigned to another scoped security. Preserve original composite IDs,
capture receipts, record hashes and the finite review separately from the
canonical identity. Apply only listed review dates; do not propagate aliases.

The first 27 reviewed dates are in `V7_SHARE_CLASS_IDENTITIES_20260917.json`.
Missing/different share classes, absent listings and future-only witnesses remain
unresolved. This does not infer merger entitlements, historical publication,
no-event completeness or any new issuer exclusion. Ordinary actions still use
the user's separately approved effective-session reconstruction policy. Rebuild
history and action consumers with new immutable outputs; do not relabel old
artifacts. See [evidence and remaining scope](reviews/2026-09-17-v7-share-class-identities.md).

## 2026-09-17 — explicit provider-union no-event reconstruction assumption

The user accepted the concrete proposal in
`V7_NO_EVENT_RECONSTRUCTION_PROPOSAL_20260917.json`: use reconciled retrospective
provider histories as a completeness assumption for resolved no-event sessions,
after resolving every applicable conflict. The active declaration is
`V7_NO_EVENT_ADMISSION_20260917.json`. This decision is settled; do not ask again.

Each consuming feature declaration must bind the coverage receipt and policy
identity, retain `completeness_verified=false` and distinguish the assumption
from historical publication. Unknown identities, unresolved dated or undated
records and missing required dates remain blocking. This adds no issuer exclusion
and does not admit stock cash entitlements, payment clocks or option deliverables.
The proposal builder must consume explicit coverage instead of interpreting an
empty action list as proof of no events.

## 2026-09-17 — targeted missing-input repairs and unrelated ticker records

Use the named GAP 2025–2026 raw history and the named 45-symbol Alpaca process-date
tail to repair specific consumer inputs. The latter requests already effective
cash records whose scheduled payment/process dates fall after the old September
15 cutoff; it does not extend the study's September 14 effective-date end. Retain
the old captures and inventory, append verified original records into a new
inventory and reject unreviewed provider revisions.

The finite 45 cash groups in `V7_UNRELATED_ACTION_IDENTITIES_20260917.json` belong
to unrelated reused-ticker instruments, established by exact captured identities
and distinct share classes. Keep their 90 source records as explicit
`reviewed_unrelated_instrument` treatments. This is record relevance, not a new
study exclusion or a shortcut for an actual corporate successor.

## 2026-09-17 — finite unchanged-common-share ticker treatments

Seven name-change records in `V7_COMMON_SHARE_RENAMES_20260917.json` have primary
notices and exact adjacent composite/share-class identities. Treat these as
unchanged common shares with an effective-time ticker transition, separately
from chart factors and cash entitlements. This is finite evidence review under
the existing policy, not a broader assumption about all renames or CUSIPs.
Barrick's changed CUSIP is retained; no different share class is merged.

Date-only notices use a conservative next-midnight New York availability bound.
The stock ledger can consume reviewed transitions without changing funding,
quantities or settlements. An open option or merger phase still needs its own
corporate-action evidence. Other unresolved records remain blocking, including
Barrick's separate AMRK-to-GOLD ticker reuse. See the
[rename evidence review](reviews/2026-09-17-v7-common-share-renames.md).

## 2026-09-17 — unrelated name-change record relevance

Finite original listing witnesses and captured primary notices distinguish
AMRK→GOLD, BNZI→PARA and SPCX→SPCK from the scoped Barrick, Paramount and SpaceX
histories. Retain these three original records as unrelated-instrument treatments,
without adding exclusions or inferring successors. Coverage combines independent
explicit treatment sets against the original inventory, preserving the exact
record partition. [Evidence and limits](reviews/2026-09-17-v7-unrelated-renames.md).

## 2026-09-17 — pre-tax funded-stock cash-flow reconstruction authorized

The user explicitly accepted `V7_STOCK_CASH_LEDGER_PROPOSAL_20260917.json`.
The active policy is `V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json`, bound to the
original proposal and its 4,337 eligible compiled cash events. This decision is
settled; do not ask again. Accrue gross distributions on entitled funded shares,
include receivables in equity while excluding them from spendable cash, and
release cash at the first captured regular open strictly after the agreed pay
date. Model zero withholding under this explicitly pre-tax research convention.
Retain source dates, security identity, policy and accrual/release ledger events.
Do not describe this as verified broker posting. Missing/conflicting dates, due
bills, unknown calendar release clocks and option deliverables remain separate
gates. The other 55 compiled cash events remain outside this policy's finite set.


Implementation evidence for the accepted September 17 stock-cash decision:
[dividend-ledger review](reviews/2026-09-17-v7-stock-cash-ledger.md). All 4,337
finite events compile; the ledger separates receivables from spendable cash,
requires exact modeled opens and settlement coverage, and consumes the captured
AAPL funded purchase with reviewed 2022 settlement dates. Broker posting remains
unverified, the 55 excluded events remain excluded, and later settlement years
are not inferred. This implements the accepted model without expanding it.


## 2026-09-17 — Finite same-share split interpretation

Ten exact `stock_dividend` provider groups are ordinary same-share forward splits
under their original primary notices; apply their ratios at the effective open
through causal chart history and funded stock bookkeeping. Preserve original
records and publication review bindings. Reject global category conversion,
ENVX/OPEN warrant-like records, combined entitlements and inferred option contract
adjustments. Cash payables/receivables do not change with stock units. This is an
implementation of reviewed terms, not an expansion of the three accepted
reconstruction assumptions. [Evidence and limits](reviews/2026-09-17-v7-reviewed-splits.md).

## 2026-09-17 — Extend the accepted pre-tax model to the finite remaining cash scope

The user explicitly accepted `V7_REMAINING_STOCK_CASH_PROPOSAL_20260917.json`:
apply the same approved pre-tax funded-stock cash model to the remaining 528
original dividend groups **as each passes amount, date and identity review**.
The exact admission is `V7_REMAINING_STOCK_CASH_ADMISSION_20260917.json`.
Keep the original 4,337 events unchanged. Retain ex-open accrual, nonspendable
receivables, release at the first regular open strictly after the reviewed pay
date, zero modeled withholding/fees and pro-rata fractions. Original provider
references define the finite scope. Provider-agreed or explicit primary-corrected
dates qualify; unreviewed currency/ADR units, due bills and mixed/lifecycle cases
remain blocked. This does not change chart admission or authorize new exclusions.
Do not request another per-issuer model approval within this accepted scope.
The first 36 FCX/SLB groups now compile and pass actual portfolio consumption.

## 2026-09-17 — Consume original reported settlement dates directly

Alpaca's already captured original calendar response contains the documented
`settlement_date` for each trade date. Use that explicit map through
`ReportedSettlementSchedule`, keeping first-regular-open-after-settlement cash
availability. Do not infer a bank calendar from exchange sessions or the union
of reported settlement dates. All 46 independent FINRA 2022 pairs agree; later
mapped dates preserve the 2023 Veterans Day, 2024 T+1 and January 2025 exchange
closure distinctions. This supplies captured scheduled settlement inputs;
it does not claim actual broker posting, historical publication or option-class
exercise rules. [Evidence](reviews/2026-09-17-v7-cash-calendar-closure.md).

## 2026-09-18 — finite cash-date reconstruction and producer preservation

Within the previously authorized 528-group extension, consume exact issuer
record/payment dates for 48 reviewed cases, retaining price actions and the
first-regular-open-strictly-after-pay model. January 2025 INTU/ORCL/MA chronology
is permitted only with the original Nasdaq ETA2025-1 notice and issuer evidence.
Reject a global record-before-ex waiver or a blanket weekend date roll.
Preserve two exact historical producer versions as hashed snapshots and bind
current producers separately in new v2 outputs; do not relabel sealed inputs.
The resulting 4,421-event verification is not full held-history admission.
[Evidence, limits and seven remaining dates](reviews/2026-09-18-v7-cash-date-recovery.md).

### 2026-09-18 — Explicit modeled FX and separate dividend security identities

The user approved: “Use this modeled FX rule” for the remaining SU, CCJ and PBR
groups. Convert retained primary native cash amounts using the last official
Bank of Canada daily observation strictly before the ex-date, rounded to 12 USD
decimals per payment, and freeze that amount for both the price factor and cash
entitlement. Preserve the native amounts, observation dates, rates and policy
identity. This is a pre-tax modeled conversion, not an actual depositary rate or
verified historical publication vintage. PBR currencyPerDr already incorporates
the ADR share ratio. Source and policy: V7_DIVIDEND_FX_POLICY_20260918.json.

Compile dividends for changed legal securities under their distinct dated FIGIs
or primary-confirmed CUSIPs, using a finite auxiliary boundary view. Do not alias
them onto the predecessor identity or add trading eligibility. The cash consumer
must see beneficial holdings under the actual dividend security ID; predecessor
holdings alone earn none. This closes dividend terms without inventing a share
conversion; the separate noncash lifecycle gate still governs transitions.
First-scope March14 observations establish March15 price factors only: retain the
existing cold-start research feature and unchanged study membership.

### 2026-09-18 — Final SILJ date correction and finite ETHE precision reconciliation

The issuer's ICI 2025 primary tax table (visually checked page 2) supersedes its
backfilled website distribution dates for SILJ: December 29 record/ex, December
30 payment, cash $0.55410448. Do not add foreign-tax reporting gross-up as cash.

Under the user's authorization to finish and make necessary implementation
edits, resolve the final ETHE September 3 pair as reported decimal precision:
Alpaca USD $0.025932 rounds to Massive USD $0.0259, with identical dates and no
foreign/special flags. A separate finite policy requires exactly these original
records, known common USD units, decimal rounding agreement, and strict absolute
and relative bounds. Retain $0.025932; do not average, manufacture digits or
relax date/currency/identity conflicts. The original primary-only policy stays
sealed; this event explicitly uses matching-provider reconstruction and declares
`primary_amount_verified=false`. The unavailable primary September notice is a
documented source limitation, not hidden corroboration. This exception does not
change the scope or the pre-tax beneficial-share cash model.

### 2026-09-23 — Incubator daily registry and EV decision semantics

Keep executable V5/V6 replay bundles in the curated
`incubator/artifacts/active/` registry; preserve earlier bundles as historical
artifacts outside that discovery root. Both active models use EV-mode policy,
so `results.jsonl.prediction` must be the ensemble magnitude-head EV, not
P(win). Keep V6 P(win) as a separately named diagnostic. A V5-compatible
matrix built from V6 candidates is not V5 paper evidence. Route V5 only to a
separately sealed V5 candidate feed; until that feed exists, report it as
input-blocked while still allowing V6 read-only validation. Production timer
activation remains gated by TODO.md item 8.

### 2026-09-24 — Backport V5 capture to the server-compatible branch

Keep the server on `ops/server-alert-readiness-20260906` while V5 is the sole
active server expert. Its production fixes and dirty retired-model deletions
make a full `main` merge or checkout switch unsafe for this deployment.
Preserve the three server-local commits, backport only the opt-in V5 candidate
capture and tested cron flag, and deploy by fast-forward Git pull. Keep capture
failure nonfatal to paper alerts. Do not infer V5 candidate evidence from the
old trade ledger or V6 rows, and do not enable the incubator after-close timer
before its separate readiness and paper-data gates.
