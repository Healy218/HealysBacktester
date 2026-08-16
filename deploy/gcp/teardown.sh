#!/usr/bin/env bash
# Leave-nothing-billing teardown. Batch VMs already self-delete when a job
# ends; this removes every residual line item: finished job records, the
# bucket (optional — it holds your results!), and the container images.
#
#   PROJECT=... REGION=us-central1 BUCKET=gs://... [DELETE_BUCKET=1] \
#     bash deploy/gcp/teardown.sh
set -euo pipefail
PROJECT=${PROJECT:?}; REGION=${REGION:-us-central1}

echo "== batch jobs (deleting all in $REGION) =="
for j in $(gcloud batch jobs list --project "$PROJECT" --location "$REGION" \
             --format="value(name)"); do
  gcloud batch jobs delete "$j" --project "$PROJECT" --location "$REGION" --quiet || true
done

echo "== container images (repo itself is one-time setup — keep it) =="
for img in $(gcloud artifacts docker images list \
    "${REGION}-docker.pkg.dev/${PROJECT}/healys" --format="value(package)" \
    2>/dev/null | sort -u); do
  gcloud artifacts docker images delete "$img" --delete-tags --quiet || true
done

echo "== Cloud Build staging bucket (auto-created per build) =="
gcloud storage rm -r "gs://${PROJECT}_cloudbuild" --project "$PROJECT" 2>/dev/null || true

echo "== stray VMs (there should be NONE — Batch self-deletes; listing to prove it) =="
gcloud compute instances list --project "$PROJECT" --format="table(name,status)" || true

if [ "${DELETE_BUCKET:-0}" = "1" ]; then
  echo "== deleting bucket ${BUCKET:?} (results included!) =="
  gsutil -m rm -r "$BUCKET" || true
else
  echo "bucket kept (${BUCKET:-unset}) — ~\$0.02/GB-mo; DELETE_BUCKET=1 to remove"
fi
echo "teardown complete — remaining monthly cost: \$0 (or bucket storage only)"
