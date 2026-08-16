# HANDOFF — state for the next session

Written 2026-08-16 late night, at a deliberate reboot of the home box.
Protocol: `CLAUDE.md` → "Session protocol". **Launch the next session FROM
this repo directory** (`cd ~/Coding/HealysBacktester && claude`) — sessions
launched from `~` can't run repo slash commands (/ultrareview burned an hour
on this).

## State at reboot (everything durable is committed + pushed)

- `main` == branch == server (`eec45e9`). Suite **386 green**. The
  2026-08-16 pre-merge review (1 P0 + 7 P1) is fully fixed, merged, and
  DEPLOYED — server heartbeat smoke shows all three experts. Review report:
  `docs/reviews/2026-08-16-premerge-review.md` (an appendix from the
  reviewing session may still be owed — triage if it appears).
- Three experts live on Hetzner (v3 real; [v4], [v31] paper). Context
  caches current; weekly refresh + surface + compaction crons armed.
  **Monday open watch**: `logs/{live,v4,v31}_cron.log` for Alpaca 429s from
  three same-minute scanners → stagger crons if seen.
- **Marks build was at 26/118 when the box rebooted.** Fully resumable.

## Resume checklist for the next session (in order)

1. **Relaunch the marks build** (unless boot-recovery did it — check
   `pgrep -f build_meta_dataset` first):
   `setsid nohup bash scripts/run_build_parallel.sh > v31_marks_build.log 2>&1 < /dev/null &`
   (autosizes shards; fresh desktop should give 4). Descriptor now exists at
   `scripts/jobs.d/v31_marks_build.sh`; if the user installed
   `healys-boot-restart.service` pre-reboot, this happened automatically.
2. **GCP pilot** (cache upload DONE; image build was in Cloud Build —
   completes server-side regardless of the reboot):
   - `export PATH="$PATH:$HOME/google-cloud-sdk/bin"`
   - `gcloud builds list --limit 2` → image
     `us-central1-docker.pkg.dev/healys-batch/healys/backtester:030e909`
     should be SUCCESS (if FAILED, resubmit per `deploy/gcp/README.md` step
     4 — remember `cp deploy/gcp/Dockerfile ./Dockerfile` first).
   - Submit the pilot with two locally-DONE symbols (`ls
     nn_meta/artifacts_v31/meta_rows/`): `PROJECT=healys-batch
     BUCKET=gs://healys-backtester bash deploy/gcp/submit.sh 1 "AAPL,ADBE"`
   - On SUCCEEDED: pull `gs://healys-backtester/out/{meta_rows,meta_marks}`
     for those symbols and **diff against the local parquets** — the
     byte-identity verdict gates all future cloud runs. Report it.
   - Pilot image is pre-review-fix SHA 030e909 — fine for the pilot;
     REBUILD the image at merged SHA before the first full cloud run.
3. **Apply `docs/WAVE2_DRAFT.md`** into ROADMAP ⏭ NEXT + TODO (user-set
   wave-2 goals incl. the NEW SPX/NDX daily-options expert, priority #2,
   with its stage-0 data audit). Delete the draft file after applying.
4. When the marks build finishes (`scripts/.jobstate/v31_marks_build.exit`
   == `0`): assemble sanity → TODO block 1 items 2–4 (selection-side ledger
   → re-runs vs the stage-0 tables → re-finalize) → push new
   `model_final_v4/` → server pull → **drop `--paper` from the v4 cron**.

## Standing goal (unchanged)

v4's re-finalized bundle deploys the moment it lands. Then wave 2
(`docs/WAVE2_DRAFT.md`): EV head → SPX/NDX expert → vol-regime on GCP →
FA seat → dual-mode cadence.

## Leftover P2s (leisure tier, from the review)

Heartbeat chained-traceback overcount; pin a base-image digest if a pilot
diff shows OS drift; remaining GCP README polish.
