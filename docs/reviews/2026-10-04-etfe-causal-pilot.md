# ETFE causal components and January phase-B demand

Completed the [bounded component study](../specs/ETFE_CAUSAL_PILOT_20261004.md)
on fresh normalized Alpaca data. Session grids and fifteen technical diagnostics
cover January 2, 2024–October 2, 2026. Signals use a January 2 calculation prefix
and census January 18–19. This validates components and download demand; it does
not admit raw prices as adjusted model features, contracts as historically
eligible, or signal events as simulated trades.

## Measured result

| Component | Evidence |
| --- | --- |
| Session grids | 1,019,958 bins across SPY/QQQ/VOO × 1/5/15 minutes; calendar opens/early closes retained |
| Missing stock inputs | Twelve source VOO minute gaps remain null, producing twelve invalid bins at each timeframe; zero invalid SPY/QQQ bins |
| Shared diagnostics | Fifteen `raw__` values plus explicit missing masks; recursive RSI/MACD do not bridge a gap |
| Signal census | All twenty families, 2,817 variants per scope, **25,353 ticker/variant combinations** including zero-event variants |
| Logical demand | **458,133** variant/direction/signal/target links, with targets 0/1/5; weekly 2/4 withheld pending dated evidence |
| Candidate results | 195,435 links have an acquisition candidate; 262,698 lack a strictly prior-date observed candidate |
| Actual candidate DTE | 152,957 links at 0DTE and 42,478 at 5DTE; these are download candidates, not entry eligibility |
| Physical demand | **68 contracts / 136 contract-route keys / 404 intervals** after cross-scope deduplication |
| Existing transport | All **179 option-bar intervals** covered by ten verified prior request chains |
| Remaining transport | **225 option-trade intervals**, totaling 4,626 contract-minutes; no new network request in this study |
| Eligibility | Zero admitted selections/entries; historical discovery, dated terms/hours and source provenance remain unresolved |

Each logical link remains in the event Parquet. Per-scope demand has 1,246
intervals; merging across timeframes/variants yields the 404 physical intervals
without deleting logical membership. The independent audit checks all **13,746
distinct candidate decisions**, including ranking, prior-date observations,
0–5 actual DTE, the 85–115% spot band and source event prices. It independently
reconstructs every scope's intervals and compares them with the producer.

Feature windows are `[t-(m+1) minutes,t-1 minute)` and entry-reference windows
are `[t-1 minute,t)`. There are 8,109 feature links extending outside stock RTH,
including 3,387 with candidates. These remain recorded and are excluded from
this component's feature-window transport union; dated option-class hours must
resolve them. Stock hours do not establish option eligibility. Captured bar
request coverage does not establish valid no trading, sufficient pricing,
publication timing or historical listing completeness.

## Causality, recovery and resource checks

All four signal channels for **every real pilot variant** matched recomputation
on a shorter prefix. The recomputation also changed consumer batch width from
32 to 17. Synthetic tests check all twenty families at all three timeframes,
future perturbation of stock bars, early closes, null bins, ORB availability,
completed-minute HLC3 stock VWAP, dated eligibility, ambiguity, expiry cutoffs
and interval subtraction. The separate full-grid smoke exercised all 2,817
parameter variants before the study plan was sealed.

The first invocation completed SPY/1m, then stopped as requested by
`--max-scopes 1` with exit 2. Resume verified its scope receipt and three output
files unchanged and computed the remaining eight scopes. Total component
compute was **110.37 seconds**, with **1.20 GiB peak RSS** and **121.16 MiB**
local evidence/output footprint. Each invocation stayed inside the 30-minute
budget; the root stayed inside 4 GiB. These measurements apply to this bounded
component study, not full acquisition, execution or model fitting.

**109 focused tests passed**. Two installed-protobuf deprecation warnings remain;
no behavior test failed. Every produced Parquet and receipt hash was verified.
The independent audit reconciles event counts, feature masks, candidate ranking,
logical/physical demand and raw request-page chains. No capture, simulation,
training or deployment was started.

## Artifacts and remaining acceptance

Selected root: `nn_meta/validation/etfe-causal-20261004-r0/`.
Plan SHA256: `79b7f75d7d66a00adfe81cc31720659a944da2d3e744490f459fba3dd5fb86c2`.
GLOBAL_DEMAND SHA256:
`44fd73587ed8e2d503a5d7b7354d8cc8770034a96785aa8d2ab23104eccfc689`.
`PLAN`, `COMPLETE`, per-scope receipts, `GLOBAL_DEMAND`, `INDEPENDENT_AUDIT`,
`RESUME_BEFORE`, `RESUME_AUDIT` and `PAYLOAD_INDEX` provide the bindings.
The [machine receipt](2026-10-04-etfe-causal-pilot.json) records exact measurements.
The [2.53 MB evidence ZIP](2026-10-04-etfe-causal-pilot-evidence.zip) contains 71
metadata/source/report members and an index of eighteen local Parquet payloads;
it does not contain those large payloads. Its SHA256 is
`83404136d31432da45ec2cce541824936c6879b4bf00a3ac0d7fd143bfae36ee`.

This closes **ETFE-2.causal-components / ETFE-1.demand-pilot**, not ETFE-2 or
ETFE-4.pilot. The final 221-field/442-input schema, remaining TV/option/context
features, dated action adjustments, eligible contract selection, full-window
phase-B and holding/roll/physical-stock phase-C demand are still open. Historical
usable start remains null. Mathematical source kernels were reused under hashes;
no old runtime selectors, market data, metadata, feature arrays or models were
inputs. Complete the remaining trade windows and feature components, then the
integrated resource/execution/dataset pilot in [roadmap order](../../ROADMAP.md#etfe-first-run-sequence).
