# Fresh ETFE corporate-action evidence

Completed **ETFE.provider-actions** in its bounded capture scope. Fresh Alpaca
requests retained **35 dividend records**, including two September SPY/QQQ
actions omitted when the initial process-date query stopped at the fixed price
cutoff. All records, raw occurrences and stream links passed independent audits.
[Machine receipt](2026-10-05-etfe-action-evidence.json),
[capture contract](../specs/ETFE_ACTION_EVIDENCE_20261005.md),
[tail contract](../specs/ETFE_ACTION_TAIL_20261005.md).

## The date-boundary finding

Alpaca's REST action endpoint filters on process dates and warns that ingestion
and processing can delay availability. Its incomplete-record option does not
provide an original publication timestamp.
[Provider reference](https://docs.alpaca.markets/us/reference/corporateactions-1).

The first three all-type/all-quality queries, process dates January 1, 2024–
October 2, 2026, returned eleven cash dividends per ETF across nine pages. They
included two December 2023 ex-dates but omitted these in-window actions:

| ETF | Ex-date | Process date | Tail result |
| --- | --- | --- | --- |
| SPY | 2026-09-18 | 2026-10-30 | Fresh REST record recovered |
| QQQ | 2026-09-21 | 2026-10-08 | Fresh REST record recovered |

A bounded October 3–December 31 process-date tail returned those two records;
VOO returned an empty terminal page. The combined inventory has **33 effective
dates inside the fixed price window**, plus two earlier occurrences kept with
their source lineage. All 35 records remain current observations. No duplicate
or conflicting native IDs occurred in the original capture. A finite tail is
not a proof that no other late-processed or omitted action exists.

The market-price cutoff remains **October 2, 2026**. No later stock or option
prices were requested. No current action was applied to a historical feature.

## Mutation-route observations

The documented action-event stream supports finite historical filters, making it
a possible source of revision evidence. Its documented filters do not include
an ETF symbol selector.
[Provider reference](https://docs.alpaca.markets/us/reference/subscribetocorporateactionseventssse).

Both probes returned HTTP 200. January 18–19, 2024 returned only a welcome
comment. This does not establish no actions, retention scope or usable history.
The October 1–2, 2026 probe reached the 8 MiB byte cap after **19,132 complete US
mutation events**, from 00:03:10 through 11:30:10 UTC on October 1. The retained
8,385,513 bytes end with a **292-byte incomplete block**, which was not parsed.

Among the complete events are **15 ETF updates for two action IDs**, matching
the two tail records above. These October update timestamps are later than their
September ex-dates; they do not establish the original announcement time. The
event stream is a useful follow-up route, but this capped observation cannot be
called a complete replay or used to fill historical availability clocks.

## Verification, resources and retained evidence

- **196 focused ETFE tests pass**, including 23 action/replay tests. Guards cover
  source identity, process bounds, incomplete fields, exact raw occurrences,
  pagination, token cycles, failed HTTP responses, retries, provider cooldown,
  credential echoes, source drift, partial/multiline SSE and duplicate events.
- Actual one-page interruption/resume preserved **three files** byte-for-byte.
  Independent normalization audit reconciled all 33 original action rows; a
  separate audit checked both tail rows and all 19,132 complete stream events,
  including every retained ETF mutation field and source link.
- **14 GETs:** twelve REST pages and two finite stream probes. All returned HTTP
  200; the October stream was intentionally incomplete at the byte limit.
  Capture elapsed **12.26 seconds**, excluding normalization/audits. Local roots
  occupy **8,470,004** and **83,277 bytes**. No bulk campaign or background process.
- [Evidence ZIP](2026-10-05-etfe-action-evidence.zip): 54 metadata/source/audit
  members with hashes for 15 raw/Parquet payloads. Raw probe bodies stay local.
  All archived members were reconciled to their source bytes. SHA256:
  `12ee5795be86f3a3caf43aafda2d01b1d54707ee837fd19b677b723ec407b7b0`.

Selected roots:
`nn_meta/data_cache_etfe/alpaca-fresh-actions-20261005-r0/` and
`nn_meta/data_cache_etfe/alpaca-fresh-actions-tail-20261005-r0/`.
Plan SHAs respectively:
`688be0b5d23f66c02ee437caabc82542a4a206ce905dfb0b0b0a069f8d70680c`,
`daaa5b54f1fa1e5d3a5ebe8dc6ef6a41e6cb51c09e23c53d5ff8225775dbb78d`.

## Remaining admission work

Historical action availability and complete effective-date coverage remain
unverified; normalized availability stays -1 and model admission false. No
price adjustment factors, model-ready inputs, labels or training were produced.
The existing joined schema and all predecessor hashes still verify unchanged.

Next establish action-event retention and original/revision availability with a
separately budgeted study, while continuing remaining contract/sector/session/
trade-source evidence and full phase-B/C acquisition demand. Final-vintage
assumptions, usable history and integrated ETFE-4 execution/dataset/training
validation remain separate gates.
