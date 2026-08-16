# Google Cloud Batch for the training pipeline — feasibility (2026-08-16)

**Verdict: highly feasible, cheap, and the codebase is unusually well-shaped
for it — every heavy stage is an embarrassingly-parallel, per-symbol/per-seed
CPU job that already checkpoints (spot-safe by construction, the standing
rule). The one thing cloud does NOT fix is data depth: the ~2y options
entitlement is a provider limit, not a compute limit.**

## What maps to Batch, stage by stage

| Stage | Shape | Batch fit | Local cost today |
|---|---|---|---|
| Dataset build (`build_meta_dataset --marks`) | 118 independent symbol tasks, ~2–4 GB RAM each, cache-only (no API) | **Task array, perfect** | ~2 days at 3 shards (running now) |
| Training grid (`train_meta`, 320 runs) | 320 independent CPU jobs, ~3.4 min each | Task array, perfect | ~20 h |
| Walk-forward prewarm (freeze+rows × folds) | per-symbol × per-fold tasks | Task array | days |
| Selection / finalize | single-node, minutes | one task (or local) | fine locally |
| Data crawls (listings, flat-files, bars) | API-bound, entitlement-gated | **keep on home box/server** — rate limits + keys, no compute win | — |

Estimated wall-clock for a full generation on Batch: **~1–2 hours** (vs ~a
week local end-to-end), because width is bounded only by quota.

## Architecture sketch

1. **Image**: `python:3.12-slim` + `requirements.txt` installed with the
   WSL-era `wsl_pip_freeze.txt` as a pip **constraints** file (the exact env
   that produced the v3.1/v4 numbers — NOT `requirements.lock.txt`, which is
   Mac-poisoned; see DOCUMENTATION.md). Repo baked in at build (code rev
   pinned in the image tag → lands in every artifact manifest).
2. **Data**: one-time `gsutil rsync` of `nn_meta/data_cache_v3/` (3.4 GB) to
   a GCS bucket; ingress is free. Tasks stage it to local SSD at start
   (~1 min) or mount via gcsfuse.
3. **Job spec**: Batch task array, `taskCount=118` (or 320), each task maps
   `BATCH_TASK_INDEX` → its symbol/seed slice (the round-robin sharding in
   `run_build_parallel.sh` is already exactly this), `NN_META_POOL=v31` in
   the env, machine `e2-standard-4` **spot**, `maxRetryCount=3`.
4. **Checkpoints/outputs**: per-symbol parquets sync to GCS on completion;
   preemption = retry = the same resume logic the crash-prone home box
   already forced us to build. Assemble runs as a final dependent task.
5. **Secrets: none needed** for cache-only jobs — API keys stay home. (This
   is the security posture win: the cloud never sees `.env`.)

## Cost estimate (spot, us-central1-class pricing)

- Build: 118 tasks × ~0.75 h × 4 vCPU ≈ 350 vCPU-h → **~$3–5**
- Training grid: 320 × 3.4 min ≈ 18 vCPU-h → **<$0.50**
- Walk-forward (3 folds × build-like) → **~$8–12**
- Storage 5 GB + result egress (~100 MB) → **pennies**

**A full research generation ≈ $10–20.** No GPUs/TPUs (standing doctrine:
tiny MLPs and GBTs leave accelerators idle; TF-CPU wheels in the image).

## Risks / prerequisites

- **Determinism check**: one symbol built locally vs on Batch must produce
  byte-identical rows (same constraints file → should; verify once).
- **Quota**: fresh projects start with modest spot vCPU quota (often 32–72);
  request ~500 preemptible vCPUs for full width, or run narrower.
- **numba/vectorbt in slim images**: needs `gcc`/`libgomp` in the image —
  known-solved, just don't use alpine.
- The manifest system (`v4_artifacts`) already records code rev + config
  hash per artifact, so cloud-built artifacts stay audit-equal to local.

## Recommendation

Pilot (≈ half a day): Dockerfile + a 2-symbol task-array job that builds
rows+marks into a bucket, then diff against the local build for those
symbols. If identical, the **first real customer is the next full retrain**
(post-Option-B re-run, or the magnitude-head training) — and the expert
panel's cadence stops being gated on the home box entirely.
