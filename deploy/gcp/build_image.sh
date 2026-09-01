#!/usr/bin/env bash
# Cloud Build the Batch image from a STATIC git archive tree (runbook step 4).
set -euo pipefail
# Repo root, not this script's dir: the original lived at the root; the
# promoted copy forgot to climb out of deploy/gcp/ and its `cp` of the
# Dockerfile failed silently in a detached shell (2026-09-01: a fleet then
# launched on a tag that was never built).
cd "$(dirname "$(readlink -f "$0")")/../.."
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
SHA=$(git rev-parse --short HEAD)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive --format=tar HEAD | tar -x -C "$TMP"
cp deploy/gcp/Dockerfile "$TMP/Dockerfile"
cd "$TMP"
gcloud builds submit --tag "us-central1-docker.pkg.dev/healys-batch/healys/backtester:${SHA}" . 2>&1 | tail -3
echo "IMAGE-BUILT: ${SHA}"
