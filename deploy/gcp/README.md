# GCP Batch runbook — setup, run, and guaranteed shutdown

Feasibility + cost analysis: `docs/GCP_BATCH_FEASIBILITY.md`. This is the
do-it runbook. Files here: `Dockerfile`, `task.sh` (what each cloud task
runs), `submit.sh`, `teardown.sh`, `constraints-linux.txt` (the exact
package pins of the local venv that produced every committed result —
cloud runs are comparable by construction).

## The "does it stay on?" answer, up front

**Google Cloud Batch has no always-on component.** VMs are created when a
job starts and **deleted automatically the moment its tasks finish or
fail** — there is nothing to remember to switch off. Cost is strictly
per-job. The only things that persist between runs, with their worst-case
monthly cost:

| Residual | Monthly cost | Removed by |
|---|---|---|
| GCS bucket (data cache 3.4 GB + results) | ~$0.10 | `teardown.sh` with `DELETE_BUCKET=1` |
| Container images in Artifact Registry (~2 GB) | ~$0.20 | `teardown.sh` (deletes images, keeps the one-time repo) |
| Cloud Build staging bucket (`gs://<project>_cloudbuild`, one source tarball per build) | pennies | `teardown.sh` |
| Batch job *records* (metadata, no compute) | $0 | `teardown.sh` |

Spot note: preemptions count against each task's `maxRetryCount: 3`. In a
churny spot pool a shard can FAIL after three preemptions — that's fine by
design: resubmitting the job resumes from the per-symbol checkpoints in the
bucket and only redoes in-flight symbols.

Belt-and-braces on top of the architecture:
1. Every job template sets `maxRunDuration: 14400s` — a hung task is killed
   (and its VM deleted) after 4 h no matter what.
2. `teardown.sh` deletes jobs + images, and *lists compute instances* so you
   can see with your own eyes that none exist.
3. Step 2 below creates a **billing budget alert at $25** — if anything ever
   surprises us, you get an email long before it matters.

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

# 2. BUDGET ALERT — the "never a surprise bill" guard ($25, emails you)
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
SHA=$(git rev-parse --short HEAD)
TMP=$(mktemp -d) && git archive --format=tar HEAD | tar -x -C "$TMP" && cp deploy/gcp/Dockerfile "$TMP/Dockerfile"
(cd "$TMP" && gcloud builds submit --tag us-central1-docker.pkg.dev/healys-batch/healys/backtester:$SHA . 2>&1 | tail -2)
rm -rf "$TMP"

# 5. one-time data sync (ingress is free; ~10 min on home upstream)
gsutil -m rsync -r nn_meta/data_cache_v3 gs://healys-backtester/data_cache_v3
gsutil -m cp nn_meta/artifacts_v31/baseline_spec.json \
  gs://healys-backtester/artifacts_v31_in/

# 6a. PILOT first: two symbols, one task — then diff outputs vs local
PROJECT=healys-batch BUCKET=gs://healys-backtester \
  bash deploy/gcp/submit.sh 1 "AAPL,SPY"

# 6b. full build: 30 shards wide (≈1–2 h, ≈$3–5 spot)
PROJECT=healys-batch BUCKET=gs://healys-backtester bash deploy/gcp/submit.sh 30
#     ...then the single assemble task (TASK_MODE=assemble via submit tweak)

# 6c. THE VERIFICATION GATE — after assemble, before any training run.
#     Runs on Batch, not the home box: a flipped bit would give a confident
#     WRONG verdict, and this gate is what decides if the dataset is trusted.
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

# 8. SHUTDOWN — even though compute already self-deleted
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

**Why these exist.** The home box has proven single-bit memory corruption
(2026-08-18; evidence in `docs/incidents/`). That corruption is silent unless it
lands somewhere that fails loudly, and these two steps produce the bundle that
is committed and deployed to production — a flip in a training array or a model
weight would ship a wrong model with no error at all. Full reasoning in
`HANDOFF.md`.

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
