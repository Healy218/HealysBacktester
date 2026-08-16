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
| Container image in Artifact Registry (~2 GB) | ~$0.20 | `teardown.sh` |
| Batch job *records* (metadata, no compute) | $0 | `teardown.sh` |

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
```

Quota note: fresh projects get modest Spot vCPU quota (often 32–72 in a
region). That already runs 8–18 tasks wide; request more via IAM → Quotas
(`Preemptible CPUs`, us-central1, ask for 500) for full width.

## Per-run flow (I can drive all of this once auth exists)

```sh
cd ~/Coding/HealysBacktester

# 4. build + push the image (Cloud Build — no local docker; ~5 min)
SHA=$(git rev-parse --short HEAD)
cp deploy/gcp/Dockerfile ./Dockerfile.gcp
gcloud builds submit --tag \
  us-central1-docker.pkg.dev/healys-batch/healys/backtester:$SHA \
  --gcs-log-dir=gs://healys-backtester/buildlogs . 2>&1 | tail -2
rm Dockerfile.gcp

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
