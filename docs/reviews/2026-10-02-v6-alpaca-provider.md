# V6 paper options provider transition — October 2, 2026

The user cancelled the Massive options plan, requested removal from V6 paper,
and selected preserving the model features and full universe. On learning that
Alpaca's standard quote-stream capacity cannot cover the current demand, the user
selected keeping full-universe entry readiness blocked pending expanded capacity.

## Deployed behavior

At **14:20:49 Central**, scanner v12 and consumer v3 replaced Massive network
access with `v6_alpaca_market_v1.py` for held-position quotes. The quote path
explicitly requests OPRA with dedicated paper credentials; positive bid/ask/size,
30-second freshness and post-decision chronology checks remain. Existing prior
catalogue captures retain their original provenance and hashes. Missing catalogue
files produce an explicit blocker, never a Massive fallback. Stock bars remain
Alpaca SIP. Historical frozen training inputs and model weights are unchanged.

The scanner monitors held positions and then records
`blocked/await_alpaca_feature_coverage`. It cannot allocate new entries in this
revision. It does not delete the ten option tick features, substitute latest
quotes for their preceding 15-minute windows, or shrink the 449-security universe.
The portfolio's historical scope identity remains unchanged; the new runtime
manifest and observations label the Alpaca quote provider separately. Broker
orders/polling retain the previously admitted Alpaca execution policy.

Manifest SHA-256:
`72dda355ea27c0e8d355949fc7185e4ce64e88bf2825d635936b7796137ff420`.
Parent: `e6d33229e249ffd4a0ba0f116cf73434b16fb97c91e834f71ad250c424f31c06`.
Installer drains existing locks, preserves the previous manifest, verifies all
bound sources, installs `99z-alpaca-options-v12.conf`, and restores both timers.
No model promotion or manual broker order was performed.

At **14:23:50 Central**, the first installed scan completed held monitoring with
zero errors in **32.687 seconds**, then explicitly blocked entry features.
The scheduled 14:30 scanner also completed held monitoring (43.287 seconds)
and preserved the entry block. At 14:30:02, broker polling completed and observed one broker position. Earlier
Alpaca polls had stale-quote errors: switching provider does not waive freshness.

## Recorder and capacity evidence

`record_v6_alpaca_options_v1.py` validates an explicit plan of at most 1,000
contracts without truncation. It verifies quote/trade subscription acknowledgments,
records raw msgpack messages and nanosecond event/receipt clocks, fsyncs the journal,
and records interruptions as separate epochs. `v6_opra_journal_v1.py` declares the
actual direct-WebSocket receipt clock rather than the SDK callback clock. Data
recording is read-only and never submits orders.

This is a **bounded transport recorder**, not an admitted full-universe feature
pipeline or continuously scheduled production capture. Its status deliberately
keeps `model_admission=false` and `coverage_complete=false`: an acknowledgement,
heartbeat or open socket does not prove full quote-window coverage. The first
30-second probe recorded 33 OPRA quotes and zero trades on three held legs, with
no normalization errors. Its initial inherited receipt-basis label was corrected
in the successor journal; the old probe remains preserved, not admitted. The
subsequent 90-second four-contract probe recorded **4,909 quotes and 83 trades**,
all 4,992 rows fsynced, zero normalization errors; see `recorder-probe-v2.json`.

Read-only census using October 1 closes and the retained prior-date catalogues
found **2,434 distinct nearest-strike contracts across 414 securities**. Another
35 securities lack a retained October 1 catalogue. This is a lower bound at one
price observation, not a sufficient live subscription plan; intraday strike
changes require additional contracts. Alpaca documents **1,000 quote stream
subscriptions** for Algo Trader Plus. At **14:55:03 Central**, one actual
2,434-contract subscription request was rejected with **405: symbol limit
exceeded**. The connection closed; no bypass or plan purchase was attempted.
See `capacity-verification.json`. No account splitting, rotating incomplete
windows, subscription purchase or universe reduction was attempted.

Alpaca's documented option API supplies historical trades and bars plus latest
quotes; no historical quote-window endpoint is listed. A live GET probe of
`/v1beta1/options/quotes` returned 404. Latest OPRA quotes worked. An initial
historical-trades probe returned 400; that is not evidence trades are unavailable.
The distinction matters: bars and snapshots cannot reconstruct the frozen NBBO
spread, quote update and signed-volume windows.

## Remaining admission work

1. Obtain confirmed Alpaca capacity for the full pre-subscribed contract demand,
   including strike movement headroom. The observed 2,434 is a floor, not the
   requested final limit. Account entitlement must be verified, not inferred.
2. Capture prospective prior-date Alpaca contract catalogues with deliverable
   checks and provenance; existing Massive catalogues remain historical evidence.
3. Connect retained raw recordings to sealed, complete preceding windows with
   gap/reconnect/late-message handling. Keep event and receipt clocks distinct.
4. Validate the existing AUTO condition mapping (Massive 209 ↔ OPRA I), all ten
   feature calculations, frozen model decision behavior and restart recovery.
   Provider equivalence is not established merely by the known condition mapping.
5. Version and admit the completed adapter before enabling full-universe entries.

47 quote/recorder/monitor/window/journal tests and 12 watcher tests passed. The
receipt-clock correction's four recorder tests were rerun successfully. No broad
training or capture campaign was repeated. Evidence root:
`nn_meta/validation/v6-alpaca-provider-20261002-r0/` (`deployment.json`,
`verification.json`, `probe.json`, `stream-census.json`, recorder probes/plans).

Primary references:
- [Alpaca option stream limits](https://docs.alpaca.markets/us/docs/about-market-data-api)
- [Raw quote/trade stream format](https://docs.alpaca.markets/us/docs/real-time-option-data)
- [Option API capabilities](https://alpaca.markets/sdks/python/api_reference/data/option/historical.html)
- [Contract catalogue endpoint](https://docs.alpaca.markets/us/reference/get-options-contracts)

V7 resource work is separate: the larger pool measured 9.448 million original
assessments/hour over 15 minutes, or 6.59 continuous remaining days at that short
rate. Capture/replay and incubation pauses are additional; see
[the concurrency review](2026-10-02-v7-discovery-concurrency.md).
