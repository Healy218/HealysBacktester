# DECISIONS — dated, append-only

One line of context, the decision, and why. Newest first. The point: don't
relitigate settled questions, and keep "considered and rejected" on the
record. Append here whenever a real choice gets made (or reversed — new
entry, never edit history).

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
