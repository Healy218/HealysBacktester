# Handoff — September 27, 2026 — faster V7 entry capture

Read TODO first. The user explicitly asked to speed up the live download as much
as possible. The versioned parallel downloader is deployed; completed preparation
and capture packs were preserved. Do not restart demand/catalog work or repeat
the completed concurrency trials. Work on main; protect V6 and unrelated changes.

## Authoritative running download

- Service: `healys-v7-capture-v3-20260927.service`.
- Meter: `nn_meta/validation/v7-entry-campaign-v3-20260927/progress.json`.
- Frozen declaration, invocations, runs and attempts: same state root.
- Packs still in `nn_meta/data_v7/entry-campaign-20260927/`.
- Launcher: `bash scripts/start_v7_capture_campaign_v3.sh 16`.
- Four autosized process workers, 16 bounded I/O threads each (64 requests max),
  persistent per-thread sessions; numerical libraries remain one thread each.
- MemoryHigh 10 GiB / Max 14 GiB, no swap, 400% CPU, Nice 10, TasksMax 256.
- Graceful systemd stop signals only the controller; it drains workers and records
  a pause. Original/v2/v3 locks prevent overlapping controllers on this queue.

[Implementation, measurements and qualifications](docs/reviews/2026-09-27-v7-parallel-capture.md)
and its companion JSON. Check the current meter, not old state directories, for
live progress. Original and v2 services have drained; their frozen declarations,
producer files and completed packs must remain unchanged. Version 3 binds them
and accepts their original pack identities without relabeling or charging twice.
First resume verified 6,605 original packs; v2 added 858 packs, all retained.

51 focused checks passed for v2 plus seven for the final pagination adjustment
and v2 receipt reuse. Real resumes, quota drain and Bash syntax passed. No broad
unchanged suite or completed data campaign was rerun. Code commits: e14a690 and
3f7ac39, pushed to main. The new producers are now frozen too; version future
behavior changes rather than editing bound files under a running campaign.

## Why final pagination differs from the first setting

The first concurrent implementation used 5,000-row pages. The next dense ticker
exposed redundant round trips and splits. Version 3 uses one full 50,000-row page
per leaf, then the existing exact recursive split, with at most one prefetched
leaf per active generator. All tick rows/precision/manifests and lossless v2 packs
remain. Existing pack limits still fail closed. HTTP 429/permanent failures pause;
transient transport/5xx retries are bounded. No secret URLs/bodies are logged.
Rates depend heavily on ticker/window density; early quiet ranges reached about
55–97 ranges/s but the first dense implementation was only about 22/s. Do not
claim a constant multiplier or retain the old six-day estimate as a promise.
The final version's sample reached 77.85 ranges/s with 1.60 GB RAM and
zero API throttles/failures. At the evidence snapshot it had completed 301
new v3 batches after verifying 7,463 retained packs. See the companion JSON.

## Storage and scope

The 100 GB campaign allocation, 250 GB shared acquisition cap, 640 GB project cap
and 20 GiB free reserve remain. Faster acquisition does not establish that the
remaining data fits these limits. MRHA storage use is authorized. The earlier
142–174 GB sample forecast was not a bound; the user's 3 GB / 1% arithmetic was
valid, but range sizes vary and the final total remains uncertain. Existing option
flat files contain OHLCV aggregates, not event-level bid/ask ticks. This download
uses Massive (formerly Polygon) REST quotes/trades, not Alpaca.

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
