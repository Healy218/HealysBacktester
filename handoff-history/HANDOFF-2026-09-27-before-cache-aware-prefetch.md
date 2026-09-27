# Handoff — September 27, 2026 — live disk allocation, MRHA and 14 GiB capture

Read TODO first. The user explicitly replaced the earlier allocation: leave
10 GB free locally and use MRHA for whatever does not fit. They also requested
as much download speed as possible with the training-size 14 GB RAM allocation.
Both changes are deployed. Do not restart completed preparation or repeat the
finished concurrency/overflow checks. Protect V6 and unrelated working changes.

## Current running entry capture

- Service: `healys-v7-capture-v4-20260927.service`.
- Meter: `nn_meta/validation/v7-entry-campaign-v4-20260927/progress.json`.
- Declaration/invocations/attempts/runs: same state root.
- Launcher: `bash scripts/start_v7_capture_campaign_v4.sh 32`.
- Logical packs remain `nn_meta/data_v7/entry-campaign-20260927/<security>/<key>`.
- MRHA payload root: `HealysBacktester/v7-entry-campaign-20260927` on UUID
  `62C9-C390`, currently mounted at `/run/media/healy/MRHA`.
- Four autosized process workers, up to 32 I/O threads each (128 requests max).
  Numerical libraries stay one thread per worker. Prefetch backs off at 6/8/10 GiB
  service memory usage to drain buffers before reaching the hard limit.
- MemoryHigh and MemoryMax are both 14 GiB; no swap. CPU burst quota 800%,
  CPUWeight 50 and Nice 10. This removes the former 400% burst restriction.
- SIGINT/SIGTERM drains current batches. All four campaign state locks are held,
  preventing an older controller from overlapping the live queue.

All prior producers/declarations remain frozen and must not be edited. Version 4
reuses their exact original pack bindings. It verified 8,704 completed packs /
278,284 ranges at startup. Code commit a545b31 is pushed. Version 4 code, helper,
and policy are now frozen too: version any subsequent behavior change.

## Storage authorization — supersedes prior fixed caps

Policy: `docs/specs/V7_CAPTURE_STORAGE_20260927.json`. The earlier 100 GB campaign,
250 GB acquisition, 640 GB project caps and 20 GiB local reserve are superseded
by the user's newer allocation. Keep **10,000,000,000 bytes free**, accounting
for all pending payloads and local metadata before dispatch. Prefer local disk;
route new payloads to verified MRHA when the local reserve would be breached.
The external drive also retains 10 GB of headroom. Other MRHA files are untouched.
At launch: approximately 279 GB local free and 744 GB external free, giving about
269 GB local plus 734 GB external headroom. These are live, changing values.
The shared quota limit was expanded to roughly 1.079 TB including already charged
data, based on available space; it is not a dataset-size requirement.

Keep the logical pack directories and binding/completion receipts local. Only
`captures.sqlite3` is a file symlink to the immutable external payload. This
preserves rglob discovery, hashes and existing packed/index readers; do not replace
whole pack directories with symlinks. MRHA must stay connected for those payloads.
The quota includes external physical data and local locator metadata, charged
once. Do not blindly rerun the old quota initializer: a local-only tree scan
would miss external partials or reset the newly authorized limit.

## Verification and measurements — complete, do not repeat

[Review and live evidence](docs/reviews/2026-09-27-v7-storage-and-memory.md), plus
its companion JSON. Sixteen focused checks passed: routing at the reserve,
in-flight accounting, wrong-drive rejection, locator/index reads, failed
publication recovery without another API fetch/charge, prior binding rejection,
and existing pagination/index checks. Bash syntax passed.

Four real pending batches were captured on MRHA, then 40,886 records were read
back through unchanged local packed/index readers. The proof index is
`nn_meta/validation/v7-overflow-readback-20260927`; its sibling `-proof.json`
records matching hashes. These are real completed inputs, not throwaway samples.
The launch used `32 0 4` to validate four external batches; ordinary resumes use
`32` and prefer local storage. Original v3 drained with no outstanding quota
reservations before v4 started.

The dense-data before/after 30-second observations were 10.66 and 22.39 ranges/s,
respectively. New sample memory peaked at 10.40 GB, with no memory-limit/OOM
counter increments, provider throttles or failed batches. CPU burst throttling
fell to zero in that sample. Inputs differ, so do not promise a constant 2x gain.
Earlier quiet-data 78 ranges/s and 38–48-hour estimates are not a reliable current
full-campaign ETA; larger windows vary sharply in records and splitting cost.
Keep measuring actual sustained work instead of multiplying concurrency counts.

Entry acquisition alone does not complete 7-3. Dated-reference plan and five exact
blackouts are done, but the retained reference stores cover only 720 of 2,223,844
planned entry pairs. Acquire remaining references from that existing plan, and
only actual additional held/exit/roll/stock gaps from existing replay frontiers.
Reconcile actual coverage/storage before declaring completion. No new blanket
first-leg envelope download or component reimplementation is required.

## Preserve the latest 7-4 work

Shared ledger: `nn_meta/validation/v7-integrated-execution-20260927-r2`.
Quote index: `v7-integrated-quote-index-20260927-r2`; source discovery:
`v7-execution-discovery-20260927-r13` (all validation roots). DIS and ABBV complete;
NVDA remains open, cash $87,596.26474814238. All 1,466 prior ledger events, three
decisions and 164 marks survived the last resume, which added one mark. Next
NVDA240322C00910000 quote window is [1711038150000000000,1711038180000000001).
VKTX/FUTU source gaps remain. No real physical exercise/stock liquidation occurred
in that five-path run. Reuse the integration and its 58 focused checks; full 7-4
is open. Later steps: 7-5 assembly/folds, 7-6 resource/recovery, 7-7 readiness/launch.

V7 model training has not started. The October 2 Massive decision, Alpaca bridge
and incubator tasks remain separate TODO items. Broad pre-existing dirty V6,
assembly.py/dataset_inputs.py and other unrelated changes remain untouched.
