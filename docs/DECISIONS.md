# DECISIONS — dated, append-only

One line of context, the decision, and why. Newest first. The point: don't
relitigate settled questions, and keep "considered and rejected" on the
record. Append here whenever a real choice gets made (or reversed — new
entry, never edit history).

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
