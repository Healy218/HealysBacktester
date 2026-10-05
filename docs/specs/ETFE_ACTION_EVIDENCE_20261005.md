# Fresh ETFE corporate-action evidence — October 5, 2026

**ETFE.provider-actions** is a bounded component of ETFE.provider-contract.
Capture fresh Alpaca observations needed to investigate causal underlying
adjustments. It does not admit prices, prove all dated inputs, or alter completed
feature roots. Existing source-bound consumers remain immutable.

## Requests and scope

Three paginated GET inventories, one each for SPY/QQQ/VOO, use
`https://data.alpaca.markets/v1/corporate-actions`, inclusive dates January 1,
2024–October 2, 2026, all types, `data_quality=all`, ascending order, limit 5.
The small page size deliberately exercises continuation. Dates filter the
provider's process-date interval, not a complete ex-date interval. Preserve all
returned types, incomplete fields and raw numeric representations. Retain empty
terminal responses as observations, not proof of no actions.

Two finite GET probes use the documented corporate-action event stream with
`since`, `until` and US region: January 18–19, 2024 and October 1–2, 2026 UTC.
The route has no documented symbol filter. Any unrelated-symbol events are
reference probe payloads only, never ETFE feature inputs. Probe receipt completion
means the request was observed; an HTTP rejection, timeout, byte cap or EOF does
not prove historical replay coverage. Preserve status, headers, error and body.
No background subscription, provider message, order or account mutation.

[REST documentation](https://docs.alpaca.markets/us/reference/corporateactions-1)
defines process-date filtering, continuation and incomplete-record selection.
It warns that provider ingestion/processing can delay availability.
[Event documentation](https://docs.alpaca.markets/us/reference/subscribetocorporateactionseventssse)
describes mutation replay and finite end filters. These current specifications
are route leads, not evidence that the account can replay the required past.

## Immutable capture and limits

Isolated root `nn_meta/data_cache_etfe/alpaca-fresh-actions-20261005-r0`.
PLAN binds source files and every exact request. One serial request stream,
at least one second between GETs; 64 attempts and 15 minutes per invocation,
128 MiB root and 8 MiB response ceilings. Stream probes have a 20-second read
budget checked between blocks and 5-second socket read timeout; timeout overrun
can extend to the next socket timeout. Preserve existing disk/RAM reserves.

Write sanitized body and receipt before exclusive page commit. Resume validates
contiguous page indices, parameters, plan/source hashes, body hashes and tokens;
reject token cycles. Five-attempt transient retries, persisted provider cooldown,
and no waiting over 60 seconds. Failed raw attempts remain evidence. A retry
never becomes a successful page. Credential echoes are discarded. Actual one-page
stop/resume must preserve prior files. No secrets in logs or evidence bundles.

## Normalization and acceptance

One Parquet row per raw occurrence, including duplicates: query symbol, action
group, native ID, process/effective date, observation receipt time and exact raw
JSON. Effective date uses ex-date or a supplied effective date, never process-date
as an invented fallback. Keep occurrence/page/group ordinals and source hashes.
Do not derive dividend/split factors or apply current-vintage changes to prices.

`historical_available_at_ns=-1` and `model_feature_admitted=false` on every row.
A declaration/ex/process date or today's receipt alone is insufficient to establish
original availability or revision history. An independent audit reconciles every
normalized field to raw pages, checks tokens, logical occurrences, duplicate IDs,
conflicts and retained timing fields. Missing data stays missing.

Exit: all three REST query chains terminal, both bounded probe receipts retained,
normalization/raw audit and actual resume pass, measured requests/storage recorded.
If the provider rejects a required route, record the exact failure and remaining
work; do not silently switch providers, data-quality filters or historical rules.
Dated action admission, option terms/sector/sessions, source provenance, usable
history, full acquisition demand and integrated pilot remain separate.
