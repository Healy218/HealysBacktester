# HANDOFF — state for the next session

Written 2026-08-21 (evening CDT). Protocol: `CLAUDE.md`.
Previous handoff (EV-head verdicts, finalize refused on the DD cap, spx0
first design rejected):
`handoff-history/HANDOFF-2026-08-21-ev-verdict-spx0-no-edge.md`.

## Where we are

- **User decision 2026-08-21 (evening):** drawdown-aware gross scaling on
  EV sizing, run on Batch. No gate override (still on the record as
  rejected).
- **Landed in `0c74274`** (suite 443 green, pushed): `ev_sizing.gross_scale`
  = `max(EV_DD_FLOOR=0.25, 1 − dd_now/dd_brake)` applied to each new
  EV-sized position, `dd_now` = the EV portfolio's own realized drawdown at
  that entry (causal). `config.EV_DD_BRAKES = [None, 0.20, 0.30]` join the
  `ev` grid beside every EV threshold; `None` is bit-identical to the
  unbraked path (tested). The scaled `size_fraction` flows into the ledger
  unchanged; `choose_policy` winners carry `dd_brake`; finalize persists it
  in `ensemble_config.json` (+ `ev_dd_brakes`, `ev_dd_floor`); the loader
  exposes `bundle.dd_brake`; the live alert prints "DD brake NN%".
  **Live sizing does NOT yet apply the brake** — the paper ledger would
  need to feed its current drawdown into `gross_scale`; it's shown, not
  enforced. Do that before dropping `--paper` if a braked bundle ships.

## LAUNCHED 2026-08-21 17:13 CDT — braked EV jobs on Batch (image `0c74274`)

Both verified SCHEDULED on the pinned image, `e2-standard-8`, STANDARD:

| job | what | expected |
|---|---|---|
| `v4-evaluate-0c74274-171306` | `--folds 3 --marks` (seeds 0-4, 60 ep, gbt 600, embargo 1D) | ~4h on e2 |
| `v4-finalize-0c74274-171307` | `--marks` full 40-seed ensemble, gate decides | ~40 min |

Outputs: `gs://healys-backtester/out/{evaluate,finalize}-<stamp>-<uid>/`.
(Superseded by the verdict below.) Read first: the finalize task log's `ensemble winner:` line — it now prints
`ev/0.05 brake=0.2`-style labels; `eligible=True` → bundle in
`.../model_final_v4/` → `gsutil rsync`, force-add commit, server `git pull`,
`v4_scan --selftest` (TODO block 3). `eligible=False` → v4 waits; log it in
EXPERIMENTS either way. In the walk-forward report the mode column shows
`brake X.XX` when a fold picked one; compare fold-2 test DD against the
unbraked 75% — that is the number this run exists to move.
Check live: `gcloud batch jobs list --project=healys-batch`.

## VERDICT 18:40 CDT — both jobs done; the gate diagnosis was WRONG

Walk-forward (`out/evaluate-20260821T221528Z-4ae40/`): identical to the
unbraked run, every fold `brake=None` (unbraked was already eligible on
val, rank rule prefers return). Finalize refused twice more; the candidate
grid (`2e6c434`, now printed on every finalize) shows **`ev/0.05` at maxDD
21.9% — the cap was never binding. Every candidate fails BEAT-BASELINE:
the take-everything ledger baseline is +1854% on the finalize validation
window, carried by a single outlier ticket (raw max 1526×).** Full grid in
EXPERIMENTS. Next action is a USER DECISION on the gate's baseline term
(recommended: compare against the baseline's `total_ex_top3`). Do not
touch `_passes_gate` before that decision; it is logged as open in
EXPERIMENTS and TODO. Nothing running on GCP.

## spx0 — second design round PLANNED, not started

Plan written to `docs/specs/SPX0_SPEC.md` "Second design round" and TODO
block 1c. Key finding while reading the builder: **sell-premium is not a
sign flip** — the ledger has long semantics (cash debited, value marked)
and a short's loss is unbounded, so the short path needs margin-as-size
and a hard loss cap via `stop_frac > 1` selected in-fold. Sequence: short
path + `stop_frac` grid → run → intraday strategies (VWAP/ORB/gap) swept
in-fold → run → extend data to 2022.

## The box — REPLACED 2026-08-23

The RAM-fault saga is over: instead of the planned DDR4 kit, the user built
a NEW machine — Ryzen 7 9850X3D (8C/16T), 32 GB DDR5, RTX 3060 Ti carried
over, same 1 TB NVMe moved intact (OS/paths/user unchanged). The old box
segfaulted `fa.collect` hourly on its final morning (05:38–09:03 CDT);
zero coredumps since the swap, StockTwits service running clean, full
444-test suite green in 23 s. Compute doctrine unchanged: training/finalize
still run on GCP Batch, not here.

## Standing warnings (unchanged)

- **Do NOT run training/finalize on this box** — run on GCP Batch.
- Docker image BAKES the repo → rebuild + pin `IMAGE_TAG` after every code
  change; build from a `git archive` tree.
- Never report cloud state from memory — job state + task logs + bucket
  listing, live.
- `NN_META_POOL=v31` for everything v4. Deploy by `git pull`, never scp.
- Agent shell is zsh (bare `=====` separators fail; no word-splitting of
  unquoted vars); `!` prefix is bash; chain privileged steps in one
  `sudo bash -c "..."`.
- Do NOT delete `gs://healys-backtester/out/archive-2026-08-19-stale-cache/`;
  do NOT pass `DELETE_BUCKET=1` to teardown.
- `prem_spot` leakage question still OPEN (needs its own feature-drop run).
- earlyoom runs the stock `--avoid`; tuned config staged, not installed.
- CLAUDE.md says 425 tests; actual 443.
