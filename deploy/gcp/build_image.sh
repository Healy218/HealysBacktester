#!/usr/bin/env bash
# Cloud Build the Batch image from a STATIC git archive tree (runbook step 4).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
SHA=$(git rev-parse --short HEAD)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive --format=tar HEAD | tar -x -C "$TMP"
cp deploy/gcp/Dockerfile "$TMP/Dockerfile"
cd "$TMP"
gcloud builds submit --tag "us-central1-docker.pkg.dev/healys-batch/healys/backtester:${SHA}" . 2>&1 | tail -3
echo "IMAGE-BUILT: ${SHA}"
