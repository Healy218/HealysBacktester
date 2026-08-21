# HANDOFF — state for the next session

Written 2026-08-21 (morning CDT). Protocol: `CLAUDE.md`.
Previous handoff (rebuild chain, evaluate re-runs, fold-3 dig, finalize
refusal, the box's swap/earlyoom work):
`handoff-history/HANDOFF-2026-08-21-rebuild-verified-finalize-refused.md`.

## Where we are

- Dataset: rebuilt 118/118 on STANDARD, assembled, **diff gate IDENTICAL**
  to stage-0 (candidate sha256 `155bae9e…`, `out/diff-20260821T040444Z-43e30/`).
- Evaluate re-runs on it: stage-0 reproduced; fold 3 is real (March shock +
  payoff-size inversion, not decay). `docs/EXPERIMENTS.md`.
- **Finalize REFUSED** (`v4-finalize-493af85-010321`): filter/0.5,
  val +22.5%, n_kept 78, eligible=False on the most-recent tail. **No V118
  bundle.** Server untouched; `[v4]` paper expert from Option A still runs.

## The decision (user, 2026-08-21 — `docs/DECISIONS.md`)

Cheapest path on both time and money: **wire the magnitude/EV head, run it
on Batch; start spx0 design/label-builder while it runs.** No gate override.
Full design + task list: `TODO.md` blocks 1b and 1c. Sequence:

1. Code 1b to a pushed, green state (suite was 410; must stay self-contained).
2. Build the image from the pinned commit → `v4-evaluate --folds 3 --marks`,
   `--ablation --marks`, then `v4-finalize --marks` on Batch
   (`deploy/gcp/submit.sh`, STANDARD `n2-standard-8`, ~3h evaluate, ~25 min
   finalize, <$2 per cycle against ~$290 of remaining credits).
3. While they run: spx0 label builder → fill model → cost accounting (1c).
4. Read the verdict. Bundle → V118 deploy-alongside (TODO block 3 remaining
   items). Refusal → v4 waits, spx0 continues; log either way in EXPERIMENTS.

## Standing warnings (unchanged)

- **Do NOT run training/finalize on this box** — proven single-bit RAM
  corruption; run on GCP Batch. DIMM bisect still the real fix (unaddressed).
- Docker image BAKES the repo (`COPY . /app`) → rebuild + pin `IMAGE_TAG`
  after every code change; build from a `git archive` tree.
- Verification doctrine: never report cloud state from memory — job state +
  task logs + bucket listing, live.
- `NN_META_POOL=v31` for everything v4. Deploy by `git pull`, never scp.
- Agent shell is zsh (no word-splitting of unquoted vars); `!` prefix is bash;
  chain privileged steps in one `sudo bash -c "..."`.
- Do NOT delete `gs://healys-backtester/out/archive-2026-08-19-stale-cache/`
  yet; do NOT pass `DELETE_BUCKET=1` to teardown.
- `prem_spot` leakage question still OPEN (needs its own feature-drop run).
- earlyoom runs the stock `--avoid`; tuned config staged, not installed.
- CLAUDE.md says 390 tests; actual 410 before this session's additions.
