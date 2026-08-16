# HealysBacktester batch-compute image.
# Built by Cloud Build (deploy/gcp/README.md) — no local docker needed:
#   gcloud builds submit --tag $IMAGE .
# from the REPO ROOT (this file is passed via --config or copied there).
#
# python:3.12-slim + toolchain for numba/vectorbt; the PYTHON stack is pinned
# exactly by constraints-linux.txt (== the local venv that produced every
# committed result). Base image + apt packages float — pin a digest if a
# pilot diff ever shows OS-level drift; the numeric stack is what matters.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgomp1 git curl gnupg \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
        | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
        > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update && apt-get install -y --no-install-recommends google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt deploy/gcp/constraints-linux.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints-linux.txt

# Bake the repo at a pinned revision (image tag should carry the git SHA so
# every artifact manifest traces to exact code).
COPY . /app

ENV NN_META_POOL=v31 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["bash", "deploy/gcp/task.sh"]
