#!/usr/bin/env bash
# Submit the sharded rows+marks build to Google Cloud Batch on spot VMs.
#
#   PROJECT=healys-batch REGION=us-central1 BUCKET=gs://healys-backtester \
#     bash deploy/gcp/submit.sh [SHARDS] [SYMBOLS]
#
# SHARDS defaults to 30. Passing SYMBOLS (comma list) runs the 2-symbol-style
# pilot on a single task. Every job carries maxRunDuration so a hung task
# can never bill past the cap — Batch deletes its VMs the moment tasks end.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/../.."

PROJECT=${PROJECT:?set PROJECT}
REGION=${REGION:-us-central1}
BUCKET=${BUCKET:?set BUCKET (gs://...)}
SHARDS=${1:-30}
SYMBOLS=${2:-}
# IMAGE_TAG overrides the tag when the image was built at an earlier commit
# (docs-only commits move HEAD without changing task code).
SHA=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/healys/backtester:${SHA}"

# FAIL CLOSED if the tag was never pushed. On 2026-09-01 a 441-task fleet
# launched against a tag whose Cloud Build had silently failed (and a
# watcher blessed a STALE build from `builds list`) — 148 tasks died on
# "manifest unknown" before anyone looked. Verify the manifest exists
# before spending a job on it.
gcloud artifacts docker images describe "$IMAGE" >/dev/null 2>&1 || {
  echo "FATAL: image tag ${SHA} not found in Artifact Registry — build it" \
       "first (deploy/gcp/build_image.sh) or pass IMAGE_TAG=<existing>" >&2
  exit 1
}

MODE=${TASK_MODE:-build}
POOL=${NN_META_POOL:-v31}
case "$MODE" in
  evaluate) JOB_PREFIX=v4-evaluate ;;
  finalize) JOB_PREFIX=v4-finalize ;;
  spx0)     JOB_PREFIX=spx0-run ;;
  vol)      JOB_PREFIX=vol-build ;;
  assemble) JOB_PREFIX=marks-assemble ;;
  diff)     JOB_PREFIX=v4-diff ;;
  freeze)       JOB_PREFIX=${POOL}-freeze ;;
  freeze-merge) JOB_PREFIX=${POOL}-freeze-merge ;;
  *)        JOB_PREFIX=marks-build ;;
esac
JOB="${JOB_PREFIX}-${SHA}-$(date +%H%M%S)"

if [ -n "$SYMBOLS" ]; then TASKS=1; else TASKS=$SHARDS; fi

# Training modes are a single task and want a bigger box and a longer leash than
# a per-symbol build shard: 5 seeds x 60 epochs plus a 600-estimator GBT, and for
# finalize a 40-seed persisted ensemble. Defaults below are overridable.
case "$MODE" in
  spx0)
    # build (~5 min) + nested walk-forward with 2 heads × seeds; one VM.
    TASKS=1
    MACHINE=${MACHINE:-e2-standard-8}
    CPU_MILLI=${CPU_MILLI:-8000}
    MEMORY_MIB=${MEMORY_MIB:-32768}
    MAX_RUN=${MAX_RUN:-43200s}
    PROVISIONING=${PROVISIONING:-STANDARD}
    RETRIES=${RETRIES:-1}
    ;;
  evaluate|finalize)
    TASKS=1
    MACHINE=${MACHINE:-n2-standard-8}
    CPU_MILLI=${CPU_MILLI:-8000}
    MEMORY_MIB=${MEMORY_MIB:-32768}
    MAX_RUN=${MAX_RUN:-43200s}          # 12h — training must not be killed mid-run
    # SPOT preemption would restart training from zero and these modes have no
    # per-symbol checkpointing to resume from, so pay for a STANDARD VM.
    PROVISIONING=${PROVISIONING:-STANDARD}
    RETRIES=${RETRIES:-1}
    ;;
  diff)
    # One short task. Sized generously on purpose: it loads TWO ~490k-row
    # frames into pandas and aligns them, and OOM-failing the correctness gate
    # for the sake of a few cents would be a poor trade. e2 over n2 — n2 hit
    # CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED on 2026-08-19.
    TASKS=1
    MACHINE=${MACHINE:-e2-standard-8}
    CPU_MILLI=${CPU_MILLI:-8000}
    MEMORY_MIB=${MEMORY_MIB:-24576}
    MAX_RUN=${MAX_RUN:-3600s}
    PROVISIONING=${PROVISIONING:-STANDARD}
    RETRIES=${RETRIES:-1}
    ;;
  freeze)
    # Per-ticker tasks (user decision 2026-08-25): SHARDS = the universe size,
    # one symbol per task. RESIZED from the CLOUD pilot 2026-08-25/26: AAPL on
    # one e2 vCPU ran ~4.3 h (ma 50 min, macd 80 min) — the box measurement
    # (DKNG 51 min on a Zen5 core) under-predicted cloud time ~5x, and the
    # 3 h leash kill-looped the first pilot with zero symbols published. The
    # freeze is single-threaded (baseline.freeze_all is one process), so the
    # fix is leash + WIDTH, not cores per task: 8 h bounds a hung task at
    # pennies, and n2-highmem-8 packs five 12 GiB tasks per VM (user decision
    # 2026-08-26: wide single-core fleet) — 24 instances x 5 = 120 concurrent
    # under the live quotas (CPUS/N2 200, INSTANCES 24; E2 is capped at 24,
    # which is why this is N2). BOOT_GB=100: five packed containers each
    # rsync their own ~10 GB cache copy onto the shared boot disk, and the
    # 30 GB default would ENOSPC the whole VM.
    # Spot is safe: per-symbol bucket checkpoints.
    CPU_MILLI=${CPU_MILLI:-1000}
    MEMORY_MIB=${MEMORY_MIB:-12288}
    MAX_RUN=${MAX_RUN:-28800s}
    PROVISIONING=${PROVISIONING:-SPOT}
    RETRIES=${RETRIES:-3}
    MACHINE=${MACHINE:-n2-highmem-8}
    BOOT_GB=${BOOT_GB:-100}
    # pd-standard, not pd-balanced: 100GB boot disks per VM eat the regional
    # SSD quota (500GB — pd-balanced counts as SSD; the 2026-08-28 freeze
    # fleet's 4x100GB sat at 400/500, capping any CPU-quota widening at 5
    # VMs). pd-standard draws from DISKS_TOTAL_GB (4TB, ~empty). Slower VM
    # startup only; the workload is CPU-bound after staging.
    BOOT_TYPE=${BOOT_TYPE:-pd-standard}
    ;;
  freeze-merge)
    TASKS=1
    CPU_MILLI=${CPU_MILLI:-2000}
    MEMORY_MIB=${MEMORY_MIB:-8192}
    MAX_RUN=${MAX_RUN:-3600s}
    PROVISIONING=${PROVISIONING:-STANDARD}
    RETRIES=${RETRIES:-1}
    ;;
  *)
    if [ "$MODE" = "build" ] && [ "$POOL" != "v31" ]; then
      # v5 builds: n2 SPOT (e2 spot was preempted 3x in 5h on 2026-08-29;
      # n2 ran the 75h freeze with zero preemptions), single-process tasks.
      # CPU_MILLI=1500, NOT 1000: Batch packs by cpuMilli and overcommits
      # memoryMib (observed on both fleets — 8x12GiB tasks landed on 64GiB
      # VMs). At 8-packed, 8x ~10GB cache copies overflow the page cache
      # and every flatfile read hits the boot disk; on pd-standard's
      # ~12MB/s that I/O-starved the 2026-08-29 fleet to ONE completion in
      # 11 hours. 1500 milli packs 5/VM (50GB of caches fit in RAM) and
      # pd-balanced (~140MB/s) absorbs what misses. BOOT_GB=70 keeps even
      # a 7-VM fleet inside the 500GB regional SSD quota (7x70=490).
      CPU_MILLI=${CPU_MILLI:-1500}
      MEMORY_MIB=${MEMORY_MIB:-12288}
      MAX_RUN=${MAX_RUN:-28800s}
      PROVISIONING=${PROVISIONING:-SPOT}
      RETRIES=${RETRIES:-3}
      MACHINE=${MACHINE:-n2-highmem-8}
      # Local-SSD scratch (fleet v3): tasks share ONE cache copy per VM at
      # NVMe speed (task.sh /mnt/ssd path) — kills both the per-task 10GB
      # restage and the small-pd-disk throughput wall (70GB pd-balanced is
      # ~20MB/s; staging 5 copies through it cost ~1.4h per slot cycle on
      # the 2026-08-30 fleet). Boot disk shrinks back to overlay-only size.
      LOCAL_SSD=${LOCAL_SSD:-1}
      BOOT_GB=${BOOT_GB:-40}
      BOOT_TYPE=${BOOT_TYPE:-pd-balanced}
    else
      CPU_MILLI=${CPU_MILLI:-4000}
      MEMORY_MIB=${MEMORY_MIB:-12288}
      MAX_RUN=${MAX_RUN:-14400s}
      PROVISIONING=${PROVISIONING:-SPOT}
      RETRIES=${RETRIES:-3}
    fi
    ;;
esac

# EXTRA_ARGS is interpolated into JSON; a double quote in it would break the
# document. Flag lists never need one, so refuse rather than emit invalid JSON.
case "${EXTRA_ARGS:-}" in
  *'"'*) echo "EXTRA_ARGS must not contain double quotes" >&2; exit 1 ;;
esac

# Optional local-SSD scratch volume shared by all tasks on a VM (task.sh
# looks for /mnt/ssd). 375GB is the fixed local-SSD unit size; the quota
# (LOCAL_SSD_TOTAL_GB) is effectively unlimited.
DISKS_JSON=""; VOLUMES_JSON=""; CONTAINER_VOLS=""
if [ "${LOCAL_SSD:-0}" = "1" ]; then
  DISKS_JSON=', "disks": [{"deviceName": "localssd", "newDisk": {"type": "local-ssd", "sizeGb": 375}}]'
  # Host mount MUST live under /mnt/disks/ — COS root is read-only (pilot
  # 2026-08-30 died exit 125: "mkdir /mnt/ssd: read-only file system").
  # The container bind-mounts it at /mnt/ssd, the path task.sh probes.
  VOLUMES_JSON='"volumes": [{"deviceName": "localssd", "mountPath": "/mnt/disks/ssd"}],'
  CONTAINER_VOLS=', "volumes": ["/mnt/disks/ssd:/mnt/ssd"]'
fi

cat > /tmp/healys_batch_job.json <<JSON
{
  "taskGroups": [{
    "taskCount": ${TASKS},
    "parallelism": ${PARALLEL:-${TASKS}},
    "taskSpec": {
      ${VOLUMES_JSON}
      "runnables": [{"container": {"imageUri": "${IMAGE}"${CONTAINER_VOLS}}}],
      "computeResource": {"cpuMilli": ${CPU_MILLI}, "memoryMib": ${MEMORY_MIB}},
      "maxRetryCount": ${RETRIES},
      "maxRunDuration": "${MAX_RUN}",
      "environment": {"variables": {
        "NN_META_POOL": "${POOL}",
        "BUCKET": "${BUCKET}",
        "SHARDS": "${SHARDS}",
        "SYMBOLS": "${SYMBOLS}",
        "TASK_MODE": "${MODE}",
        "EXTRA_ARGS": "${EXTRA_ARGS:-}",
        "BASELINE_URI": "${BASELINE_URI:-}",
        "CANDIDATE_URI": "${CANDIDATE_URI:-}"
      }}
    }
  }],
  "allocationPolicy": {
    "instances": [{"policy": {
      "machineType": "${MACHINE:-e2-standard-4}",
      "provisioningModel": "${PROVISIONING}",
      "bootDisk": {"sizeGb": ${BOOT_GB:-30}, "type": "${BOOT_TYPE:-pd-balanced}"}${DISKS_JSON}
    }}],
    "network": {"networkInterfaces": [{
      "network": "projects/${PROJECT}/global/networks/default",
      "subnetwork": "regions/${REGION}/subnetworks/default",
      "noExternalIpAddress": true
    }]}
  },
  "logsPolicy": {"destination": "CLOUD_LOGGING"}
}
JSON

# Clear the handle BEFORE submitting: under `set -e` a failed submit aborts
# here, and a stale .last_job would leave watch_job.sh bound to the previous
# (SUCCEEDED) job — reporting a confident, wrong, terminal state. Exactly the
# stale-watcher trap this file exists to prevent.
LAST_JOB_F="$(dirname "$(readlink -f "$0")")/.last_job"
: > "$LAST_JOB_F"

gcloud batch jobs submit "$JOB" --project "$PROJECT" --location "$REGION" \
  --config /tmp/healys_batch_job.json
# Machine-readable handle for watchers: bind to THIS, never re-derive the
# job by listing (a stale list entry watched the wrong job on 2026-08-25).
echo "$JOB" > "$(dirname "$(readlink -f "$0")")/.last_job"
echo "submitted: $JOB  (mode=$MODE machine=${MACHINE:-e2-standard-4} $PROVISIONING)"
echo "watch:     bash deploy/gcp/watch_job.sh   # follows .last_job"
echo "watch:     gcloud batch jobs describe $JOB --project $PROJECT --location $REGION"
case "$MODE" in
  freeze)
    echo "when all freeze tasks SUCCEED, merge the per-symbol specs:"
    echo "  TASK_MODE=freeze-merge NN_META_POOL=${POOL} PROJECT=$PROJECT BUCKET=$BUCKET bash deploy/gcp/submit.sh 1" ;;
  build)
    echo "when all build tasks SUCCEED, run the single assemble task:"
    echo "  TASK_MODE=assemble PROJECT=... BUCKET=... bash deploy/gcp/submit.sh 1" ;;
  assemble)
    echo "then run ledger validation on Batch or the current home box:"
    echo "  TASK_MODE=evaluate EXTRA_ARGS='--ablation --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D' \\"
    echo "    PROJECT=$PROJECT BUCKET=$BUCKET bash deploy/gcp/submit.sh 1" ;;
  evaluate)
    echo "outputs land under ${BUCKET}/out/evaluate-<UTC stamp>/ with SHA256SUMS.txt" ;;
  finalize)
    echo "outputs land under ${BUCKET}/out/finalize-<UTC stamp>/ with SHA256SUMS.txt"
    echo "rc=1 from the task means NOTHING CLEARED THE GATE — a result, not a crash;"
    echo "the reports are published either way." ;;
esac
