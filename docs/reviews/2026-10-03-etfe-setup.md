# ETFE setup and bounded Alpaca capability checks — October 3, 2026

ETFE now has an independent configuration, parameter catalog, setup manifest,
read-only provider probes and an integrity checker. This completes initial
setup, not data admission or training readiness. [Measured receipts](2026-10-03-etfe-setup.json).

## Implemented and checked

- Fixed scope: SPY/QQQ/VOO; 1/5/15-minute signals; inherited V7 timing/risk;
  Alpaca options history through October 2, 2026 inclusive. No Massive quotes,
  old model weights or V7 checkpoints enter ETFE.
- New catalog: 20 families, 2,817 parameter variants per timeframe, 8,451
  combinations per ticker, 25,353 across the three tickers. IDs include ETFE
  identity. Tests compare every grid membership against the original registry,
  confirm the restored minute scope and preserve V7's unchanged 5/15/30 catalog.
- Setup requires `NN_META_POOL=etfe`, rejects conflicting inherited campaign
  selectors, writes only a fresh `nn_meta/validation/etfe-*` root, and refuses
  overwrite. Explicit paths and source/file hashes bind the configuration and
  catalog. A source snapshot preserves exact bytes, including pre-existing dirty
  shared registry sources; no shared source was edited by this setup.
- GET probes use allowlisted Alpaca URLs, separate data and paper-metadata
  credentials, no redirects, per-request timeouts, 32-request/2-MiB-response caps,
  exact response bytes and hashes. Secrets/exception internals are not logged.
  The probes do not submit orders, record streams or assert complete pagination.
- 30 focused tests passed, covering full variant parity, new identities, scope
  rejection, inclusive-date conversion, immutable output, endpoint restrictions,
  failures/pagination, credential handling and tampered artifact/source rejection.

The selected root is `nn_meta/validation/etfe-setup-20261003-r0/`.
`PREPARED.json` and `plan.json` describe preparation only; all build/training
readiness fields remain false. Source snapshot and all probe hashes verified.
Total setup artifacts measured 2,510,709 bytes, not a full-build storage estimate.
V7 archive completion receipt remains intact.

## Live observations

The first sandbox attempt recorded seven transport failures. The successful
`probe-r1` and `probe-boundary-r0` made **43 read-only GET requests**, with no
transport failures. This is a bounded capability check, not a coverage census.

| Observation | Result and limit |
| --- | --- |
| Underlying minute data | HTTP 200 samples for SPY, QQQ, VOO via SIP; queried UTC-day examples include extended hours and do not prove complete regular-session coverage |
| Expired option references | HTTP 200 examples for each ETF; current responses about expired contracts are not historical as-of catalogues or deliverable admission |
| Historical option bars/trades | HTTP 200 and real observations for representative contracts in all three ETFs; sampled near-money contracts show January 18, 2024 data |
| Earliest observed sample | SPY minute bar at `2024-01-18T14:30:00Z`; sampled SPY trade at `2024-01-18T14:30:00.009729024Z`. QQQ/VOO also return January 18 observations. This is not proof of Alpaca's global floor or full-contract coverage |
| Historical bid/ask endpoint | `/v1beta1/options/quotes` returned HTTP 404 for all three ETF contract examples; no historical quote-window access established |
| Fixed end session | Alpaca calendar confirms October 2, 2026 stock regular hours 09:30–16:00 New York (13:30–20:00 UTC); instrument-specific option hours remain to be bound |

Alpaca's [published history overview](https://docs.alpaca.markets/us/docs/historical-option-data)
says February 2024. The recorded January observations show that this month-level
description is not a reliable exact lower boundary for every returned data type.
Keep the earliest-history requirement; do not silently freeze February 1 or
promote a sampled January 18 trade into full start-date certification.

The [historical bars](https://docs.alpaca.markets/us/reference/optionbars) and
[trades](https://docs.alpaca.markets/us/reference/optiontrades) references describe
inclusive query boundaries and pagination. A first page is not a completed
history. Feed provenance and market-data semantics must still be verified for
admission; an accepted historical request does not itself prove OPRA identity.
Returned adjusted-strike contract examples also need dated deliverable checks.

## Remaining scope

`ETFE.history-boundary` remains open for complete boundary evidence, not a user
date decision. `ETFE.provider-contract` remains open because the inherited
midpoint execution and quote-based features need historical bid/ask observations
that these Alpaca checks did not establish. No Massive fallback is allowed.
An explicit methodology decision is required if Alpaca cannot supply those
observations; bars/latest snapshots cannot silently substitute.

Dataset admission still needs dated contracts, underlying/features, causal
strategy-timeframe validation, execution/labels, ETFE schema/folds/trials and
measured resource/recovery evidence. No acquisition campaign, training run,
model evaluation, deployment or provider subscription change occurred.
