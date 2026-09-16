# September 16 V7 causal feature and real dividend pilot

## Result and validation

Implemented causal action epochs in `nn_meta/v7/causal_features.py`, sharing
Polars aggregation through `bars.aggregate_frame`, selecting required TV source
aliases through `features.source_frames`, and routing bounded causal signal
batches through the existing vectorbt proposal simulation in `proposals.py`.
Completed an actual AAPL March 15–May 10, 2022 dividend pilot across all 20
families, 2,817 variants per timeframe and all 13 TV feature groups.

This is a feature/proposal component milestone. It does not establish all 222
columns, quote labels, physical execution, model training or full readiness.
The pilot reports explicitly retain `research_ready: false`.

Full suite: **1,786 passed +18 subtests**, 18 warnings, 91.01 seconds.
Log: `/tmp/v7-causal-features-20260916-full-tests.log`. Focused tests: 10 passed
(including the existing proposal test), `/tmp/v7-causal-features-tests.log`.
Tests include all four timeframes, cold start, future-price/action invariance,
exact direct-epoch signals for every family, exact minute clocks, rejection of
mid-session actions and a split crossing without a false proposal stop.
These runs include the pre-existing unrelated dirty V6 work, not a clean checkout.

## Causal contract

`CausalFeatures` cold-starts at the active research boundary and requires exact
completed-minute clocks. Reviewed actions must coincide with captured session
opens. Each epoch recomputes its available prefix in contemporaneous units and
retains only that epoch's observations. Later actions never rewrite prior
outputs. Raw minimum tick remains 0.01. Epoch rows retain full prefix lookbacks
and accept dated sectors. A continuous fixed-origin proposal basis preserves
cross-action stops; this is not an execution price. Raw execution stays separate.

Signal batches verify registered variants, exact clocks and the four boolean
channels. This correctness implementation recomputes epoch views per variant
batch: whole-history throughput and cache optimization remain unverified.

## Actual AAPL evidence and output

Output: `nn_meta/validation/v7-causal-aapl-pilot-20260916`; root `report.json`
and all four timeframe artifacts completed and passed receipt verification.
Source/runtime/input bindings passed. Changing bound code later makes these
historical bindings stale; preserve them and never relabel old artifacts.

| Minutes | Variants | Proposals | Censored | Seconds | Peak RSS KiB |
|---|---:|---:|---:|---:|---:|
| 1 | 2,817 | 598,944 | 2,099 | 252.21 | 842,016 |
| 5 | 2,817 | 108,354 | 1,826 | 160.41 | 610,704 |
| 15 | 2,817 | 34,156 | 2,291 | 147.63 | 577,648 |
| 30 | 2,817 | 16,011 | 2,218 | 144.24 | 576,052 |

Total: **757,465 proposals, 11,268 variants, 40 sessions**. Epoch feature files
contain 111 columns (96 TV plus 15 technical). Diagnostic artifact size is
702,285,368 bytes; full assembly should use compact factorized/columnar storage.
Sampled memory availability was 24.9 then 24.4 GB; swap stayed 2,355 MiB.
These samples are not a full resource or V6 coexistence gate.

The original Apple April 28 announcement supplies $0.23/share, with conservative
availability at the following New York midnight. Both captured action providers
agree on May 6 ex-date, May 9 record and May 12 payment. Prior raw Alpaca close
is $156.81, available May 5 at 20:00 UTC. The factor is 0.9985332568076015,
available May 5 at 20:00 UTC and effective May 6 at 13:30 UTC. Do not use the
current cumulative adjustment factor. Apple dividend-history board declaration
April 27 is distinct from the original April 28 publication date.

- Original release: https://www.apple.com/newsroom/2022/04/apple-reports-second-quarter-results/
- Capture: `nn_meta/data_v7/public-actions-20260916/aapl-20220428-issuer` (143,029 bytes).
- Request: `nn_meta/validation/v7-aapl-action-evidence-requests-20260916.json`.
- Dated identity: `nn_meta/data_v7/action-reference-20260916/AAPL/2022-05-05`;
  FIGI BBG000B9XRY4, CIK 0000320193.
- Identity requests: `nn_meta/validation/v7-aapl-action-identity-requests-20260916.json`.
- Source identity: `48486a24d9ace0ddd731de6f95704eaa5da446b87f275f39fe5d817c1ce302be`.
- Pilot log: `/tmp/v7-causal-aapl-pilot-20260916.log` (exit 0).

Exact completed invocation (use a new immutable output for any future rerun):

```bash
./venv/bin/python scripts/pilot_v7_causal_features.py \
  --source nn_meta/data_v7/start-20220315 \
  --dividends nn_meta/data_v7/corporate-actions-20260915/dividends \
  --splits nn_meta/data_v7/corporate-actions-20260915/splits \
  --alpaca nn_meta/data_v7/alpaca-actions-20260915 \
  --issuer nn_meta/data_v7/public-actions-20260916/aapl-20220428-issuer \
  --reference nn_meta/data_v7/action-reference-20260916/AAPL/2022-05-05 \
  --output nn_meta/validation/v7-causal-aapl-pilot-20260916 \
  --workers 4
```

## Settlement research checkpoint — unfinished

Request manifest: `nn_meta/validation/v7-settlement-evidence-requests-20260916.json`.
Output: `nn_meta/data_v7/public-settlement-20260916`.
Log: `/tmp/v7-public-settlement-20260916.log`; process ended with exit 1 because
four DTCC URLs returned HTTP 404. No acquisition job or reservation remains.

Captured FINRA 2022 notice (88,674 bytes), 2023 notice (120,564 bytes) and
2026 margin-extension schedule HTML (108,484 bytes). These have not yet been
visually reviewed as PDF tables or admitted into a settlement adapter.

- https://www.finra.org/sites/default/files/2021-10/information-notice-101521.pdf
- https://www.finra.org/sites/default/files/2022-11/Information-Notice-111822.pdf
- https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-extension-holiday-schedule

Failed raw PDF paths on `www.dtcc.com` (no captured evidence):
`/-/media/Files/pdf/2023/12/12/19404-23.pdf`,
`/-/media/Files/pdf/2024/10/30/20972-24.pdf`,
`/-/media/Files/pdf/2024/12/30/0275.pdf`,
`/-/media/Files/pdf/2023/10/11/19155-23.pdf`.
Search-indexed texts suggested the following issues; verify original sources
before implementation: trading and settlement calendars differ; bank holidays
need separate treatment; November 10, 2023 cannot be inferred from a generic
federal holiday calendar; January 9, 2025 mourning closed exchanges while
DTC/NSCC settlement continued; DTC Good Friday limited settlement must not be
mistaken for ordinary stock settlement. Physical exercise T+1 transition also
needs official effective-date handling.

Potential canonical source pages to revisit:
https://www.dtcc.com/Globals/PDFs/2024/October/30/20972-24,
https://www.dtcc.com/Globals/PDFs/2023/October/11/19155-23,
https://www.dtcc.com/Globals/PDFs/2024/September/11/20703-24,
https://www.theocc.com/getcontentasset/a151a9ae-d784-4a15-bdeb-23a029f50b70/dfc3d011-8f63-43f6-9ed8-4b444333a1d0/riskstoc.pd.

## User-reported V6 incident

At session end the user reported V6 starts the morning successfully then keeps
showing an error. They requested a handoff before clearing the session.
**This September 16 incident has not been diagnosed.** Capture the actual error,
cycle timestamps and producer/refresh/relay/server/dashboard evidence first.
Do not assume the September 15 missing-provider-file incident has recurred.
No V6 runtime, timer, deployment or alert settings changed during this work.
The unrelated dirty V6 files are preserved and must not be reset or swept into
this V7 commit. V6 diagnosis is the next session's first task.
