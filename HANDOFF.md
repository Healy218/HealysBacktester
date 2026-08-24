# HANDOFF — state for the next session

Written 2026-08-24 ~13:00 CDT. Protocol: `CLAUDE.md`.
Previous handoff (the day's blow-by-blow: gate decision, review cycle,
deploy): `handoff-history/HANDOFF-2026-08-24-v118-live-phase-exit.md`.

## The one-paragraph state

**[v4] is LIVE with real alerts** (V118: gbt×40, ev/0.05, no brake — first
gate-eligible bundle, ex-top3 gate) on the Hetzner server since 2026-08-24,
alongside untouched v3 and the v31 paper expert; the daily watchlist digest
(wave-2 item 5, v4 seat) is cron'd for 20:10 UTC weekdays. The v4-ship
phase EXITED; **TODO.md is refilled for the wave-2 phase**. The prem_spot
question is CLOSED (leaks in both families). spx0 rounds 1–2 are rejected;
**round 3 (credit verticals + intraday seats) is RUNNING on Batch**. The
box is the new Ryzen build; suite ~474 green in ~11 s.

## Nothing running on GCP — all seven+ jobs landed 2026-08-24

Verdicts (all in EXPERIMENTS, all pushed): v4 finalize ELIGIBLE ×2 →
V118 LIVE; prem_spot CLOSED (both families); spx0 rounds 2/3/4 (round 4:
fold 2 +48.5% but fold-3 refusal + cap breach — no seat; USER DECISION
lever-5 data vs park, tied to the Massive upgrade the user is weighing);
vol track stages 1–2 DONE (289 symbols' RV features published to
`out/vol_features/`; HAR-RV QLIKE 0.117 uniform across regimes = the
stage-3 seat bar).

## Monday watch (first trading day with everything live)

- First REAL `[v4]` alert(s): threshold is EV ≥ 0.05 through the EV head —
  cadence unknown; the paper history averaged ~a few/week at filter/0.5.
- First populated watchlist digest lands 20:10 UTC; hit-rates start
  resolving ~Wednesday (min(dte,7d) horizons).
- Heartbeat (17:00 UTC) now covers three experts + new crash deltas.

## Today's landings (all pushed; main == branch == `45ab67a`+)

1. Gate baseline = ex-top3 (user decision; small-baseline raw fallback
   after review) → finalize ELIGIBLE → **V118 deployed, --paper dropped**
   (crontab backup `~/crontab.bak.2026-08-24`; rollback = restore it).
2. 10 local-review findings fixed (spx0 1-minute decision lookahead, diff
   gate row-set hole, busted-book EV floor, finalize magnitude-head
   population + bundle regenerated, ops hardening).
3. prem_spot CLOSED: purged legacy −23%/−44% (gbt/nn) vs causal
   +69%/+82% — leak confirmed in both families (EXPERIMENTS).
4. spx0 round 2 REJECTED (naked-short tail blows through stop-margin;
   structural lesson logged); round 3 BUILT (verticals: package fills,
   package costs, [0,width] clamps → hard −1×margin floor; 6 intraday
   seats) and launched.
5. Watchlist digest shipped end-to-end (code, 7 tests, server cron).
6. Docs: ROADMAP phase promoted (wave 2 is ▶ NOW; item 1 folded into
   V118), TODO refilled, CLAUDE.md test count fixed (~474, floor not pin).

## Standing warnings

- Docker image BAKES the repo → rebuild + pin `IMAGE_TAG` after every code
  change; build from a `git archive` tree. Training/finalize on Batch.
- Never report cloud state from memory — job state + task logs + bucket
  listing, live.
- `NN_META_POOL=v31` for everything v4/spx0. Deploy by `git pull`, never
  scp. Server crontab edits: stage to a file, show the diff, `crontab
  <file>` (a piped `crontab -` was classifier-blocked once).
- Agent shell is zsh (quote `===` separators; no word-splitting); `!`
  prefix is bash and runs on the HOME box (Remote Control caveat: the
  user's own terminal may be elsewhere and lacks the Hetzner key).
- Do NOT delete `gs://healys-backtester/out/archive-2026-08-19-stale-cache/`;
  no `DELETE_BUCKET=1`.
- The server `_st.py` v3 selftest is GONE — v3 health = clean passes in
  `logs/live_cron.log` (DOCUMENTATION updated).
- earlyoom: stock config; the tuned one was staged for the OLD box — 32 GB
  now, revisit only if OOM ever shows up.
- Live DD-brake enforcement still missing in v4_scan sizing (moot for
  V118's `dd_brake=None`; TODO block 5 before any braked bundle ships).
- Ultrareview retry: 2 of 3 free remain; the branch has only had the
  local review (DECISIONS 2026-08-24).
