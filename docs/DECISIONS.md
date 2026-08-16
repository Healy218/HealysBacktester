# DECISIONS — dated, append-only

One line of context, the decision, and why. Newest first. The point: don't
relitigate settled questions, and keep "considered and rejected" on the
record. Append here whenever a real choice gets made (or reversed — new
entry, never edit history).

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
