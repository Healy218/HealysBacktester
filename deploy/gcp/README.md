# GCP Batch runbook — setup, run, and verified shutdown

Feasibility + cost analysis: `docs/GCP_BATCH_FEASIBILITY.md`. This is the
do-it runbook. Files here: `Dockerfile`, `task.sh` (what each cloud task
runs), `submit.sh`, `teardown.sh`, `constraints-linux.txt` (the exact
package pins of the local venv that produced every committed result —
cloud runs are comparable by construction).

## The "does it stay on?" answer, up front

Batch allocates task VMs and releases them after job termination. Confirm
terminal job states and inspect remaining instances; a submitted cancellation
request or a failed describe call is not evidence that billing has stopped.
Buckets, registry images and build staging storage remain until removed.

`submit.sh` chooses resource limits by mode: build/freeze and training have
different time caps and retry counts. A time cap applies per task attempt,
not to total campaign spend. Review `MAX_RUN`, `RETRIES`, packing and fleet
width before submission. Billing budget alerts are delayed notifications,
not spending caps.

`scripts/cloud_budget_guard.sh` is a time/rate estimate that monitors explicit
job IDs. Set `PROJECT`, `REGION`, `BUDGET_USD`, `USD_PER_HOUR` and any
`SPENT_USD` already incurred. It treats describe errors as unknown/active,
retries cancellation after the deadline, and stays running until every job is
confirmed terminal. It still depends on the guard host and cloud API remaining
available; review its log and the cloud resources independently after shutdown.

## One-time setup (~15 min, needs your Google account)

Run these yourself (step 1 is interactive auth — in a Claude Code session,
`! gcloud auth login` runs it inline):

```sh
# 0. install the CLI (once per machine)
curl https://sdk.cloud.google.com | bash && exec -l $SHELL

# 1. auth + project
gcloud auth login
gcloud projects create healys-batch --name="HealysBacktester Batch"
gcloud config set project healys-batch
# link billing (shows your billing account id, then links it):
gcloud billing accounts list
gcloud billing projects link healys-batch --billing-account=XXXXXX-XXXXXX-XXXXXX

# 2. BUDGET ALERT — notification only ($25); does not stop spending
#    (single line — pasting multi-line backslash commands eats the flags)
gcloud billing budgets create --billing-account=XXXXXX-XXXXXX-XXXXXX --display-name=healys-batch-cap --budget-amount=25USD --threshold-rule=percent=0.5 --threshold-rule=percent=0.9

# 3. APIs + artifact repo + bucket (each a single line)
gcloud services enable batch.googleapis.com compute.googleapis.com storage.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories create healys --repository-format=docker --location=us-central1
gsutil mb -l us-central1 gs://healys-backtester

# 3.5 IAM for the Compute Engine default SA (REQUIRED on modern projects —
#     since ~2024 new projects grant this SA nothing, so Cloud Build can't
#     read its own source and Batch VMs can't touch the bucket; hit live
#     2026-08-16). Find the SA: gcloud iam service-accounts list
SA=<project-number>-compute@developer.gserviceaccount.com
for role in roles/storage.objectAdmin roles/artifactregistry.writer roles/logging.logWriter roles/batch.agentReporter; do gcloud projects add-iam-policy-binding healys-batch --member="serviceAccount:$SA" --role="$role" --condition=None --quiet; done

# 3.6 Private Google Access (REQUIRED under a Workspace org — hit live
#     2026-08-16: the org policy compute.vmExternalIpAccess blocks VMs with
#     external IPs, so jobs run IP-less; PGA routes their GCS + Artifact
#     Registry traffic. submit.sh already sets noExternalIpAddress.)
gcloud compute networks subnets update default --region=us-central1 --enable-private-ip-google-access
```

Quota note: fresh projects get modest Spot vCPU quota (often 32–72 in a
region). That already runs 8–18 tasks wide; request more via IAM → Quotas
(`Preemptible CPUs`, us-central1, ask for 500) for full width.

## Per-run flow (I can drive all of this once auth exists)

```sh
cd ~/Coding/HealysBacktester

# 4. build + push the image (Cloud Build — no local docker; ~5 min).
#    Build from a STATIC `git archive` tree, never the live working dir:
#    gcloud's tarball snapshotter crashes ("lost gzip_file") if files churn
#    mid-archive — e.g. a running dataset build's checkpoints (hit live
#    2026-08-16). Also gives exact-commit provenance for the tag.
bash deploy/gcp/build_image.sh

# 5. one-time data sync (ingress is free; ~10 min on home upstream)
gsutil -m rsync -r nn_meta/data_cache_v3 gs://healys-backtester/data_cache_v3
gsutil -m cp nn_meta/artifacts_v31/baseline_spec.json \
  gs://healys-backtester/artifacts_v31_in/

# 6a. PILOT first: two symbols, one task — then diff outputs vs local
PROJECT=healys-batch BUCKET=gs://healys-backtester \
  bash deploy/gcp/submit.sh 1 "AAPL,SPY"

# 6b. full build: review duration/rate estimates for this pool before launching
PROJECT=healys-batch BUCKET=gs://healys-backtester bash deploy/gcp/submit.sh 30
#     ...then the single assemble task (TASK_MODE=assemble via submit tweak)

# 6c. THE VERIFICATION GATE — after assemble, before any training run.
#     Batch or the current home box can run this check. Validate reproducibility
#     with identical seeds and comparable artifact hashes.
#     Exits non-zero if any shared column still differs (--expect-identical).
TASK_MODE=diff PROJECT=healys-batch BUCKET=gs://healys-backtester \
  IMAGE_TAG=<tag> bash deploy/gcp/submit.sh 1
#     Override the inputs with BASELINE_URI / CANDIDATE_URI; report + hashes
#     land in out/diff-<UTC stamp>/.

# 6d. spx0 pool (SPX/NDX 0DTE, docs/specs/SPX0_SPEC.md): one task builds the
#     dataset from data_cache_spx0 (synced once, ~850 MB) and runs the nested
#     walk-forward; outputs land in out/spx0-<stamp>/artifacts_spx0/.
gsutil -m rsync -r nn_meta/data_cache_spx0 gs://healys-backtester/data_cache_spx0   # once
TASK_MODE=spx0 EXTRA_ARGS="--folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600" \
  PROJECT=healys-batch BUCKET=gs://healys-backtester IMAGE_TAG=<tag> bash deploy/gcp/submit.sh 1

# 7. pull results home
gsutil -m rsync -r gs://healys-backtester/out/ nn_meta/artifacts_v31/

# 8. SHUTDOWN — inspect the final job states and remaining compute afterward
PROJECT=healys-batch BUCKET=gs://healys-backtester bash deploy/gcp/teardown.sh
```

## What must never move to the cloud

API crawls (listings, flat files, live bars): entitlement-gated, rate-
limited, and they'd put `.env` keys in the cloud. Cache-only compute jobs
need **no secrets at all** — that's deliberate. And cloud compute does not
extend the ~2-year options-history entitlement; that's a provider plan
limit.

## Training modes: `evaluate` and `finalize` (added 2026-08-18)

    TASK_MODE=evaluate PROJECT=... BUCKET=gs://... \
      EXTRA_ARGS='--ablation --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D' \
      bash deploy/gcp/submit.sh 1

    TASK_MODE=finalize PROJECT=... BUCKET=gs://... \
      EXTRA_ARGS='--epochs 60 --gbt-estimators 600' bash deploy/gcp/submit.sh 1

Training may run on Batch or the current home box. The faulty i5/RAM machine
was retired on 2026-08-23; its incident is not a prohibition on the replacement
hardware. Compare deterministic runs and artifact hashes when establishing
trust in a new environment.

The 2026-09-05 causal-feature correction invalidates older research specs,
row checkpoints and model contracts for current validation. Re-freeze, rebuild,
evaluate and finalize matching artifacts before promoting a bundle. Existing
frozen bundles are historical artifacts; default verification rejects stale
contracts. Research-only overrides do not make an old bundle deployable.

Notes:

- Inputs are pulled from `out/meta_dataset.parquet` and
  `out/meta_dataset.marks.parquet`, so **assemble must have run first**. The
  multi-GB `data_cache_v3` rsync is skipped: nothing here reads raw option bars.
- Outputs go to `out/<mode>-<UTC stamp>/` — `reports/`, `runs/`, and for
  finalize `model_final_v4/` — plus **`SHA256SUMS.txt`**, so a second run can be
  compared file for file rather than assumed identical.
- **Reports are published even when the task exits non-zero.** `v4_finalize`
  exits 1 when nothing clears the eligibility gate; that is a result, not a
  crash, and the evidence must survive it.
- Defaults: `n2-standard-8`, 8 vCPU, 32 GiB, 12h cap, **STANDARD not SPOT**
  (preemption restarts training from zero — no checkpointing to resume from),
  1 retry. Override via `MACHINE` / `CPU_MILLI` / `MEMORY_MIB` / `MAX_RUN` /
  `PROVISIONING` / `RETRIES`.
- `EXTRA_ARGS` is interpolated into the job JSON and must not contain double
  quotes; submit.sh refuses rather than emitting invalid JSON.

## Checkpoint publication and failure semantics

Cloud and local builders pull rows, marks and the matching
`<symbol>.provenance.json`. The Python builder validates the current feature
contract, full input signature and mark coverage before it skips a symbol.
Remote row existence alone never proves completion. Publication is per symbol:
marks first, rows second, matching provenance last. All required uploads must
succeed; partial publication is repaired on the next validated build.
Family partial checkpoints include their provenance sidecars in synchronization.
The local worker and v6 freeze launcher return nonzero when any worker fails;
`LOCAL-*-DONE` is emitted only after successful completion.

Freeze retries download an existing per-symbol spec and validate its current
feature contract and pool configuration hash before skipping. Missing, stale,
or invalid specs are rebuilt and published; old bucket existence alone is
not evidence of a completed freeze under the corrected recipe.
