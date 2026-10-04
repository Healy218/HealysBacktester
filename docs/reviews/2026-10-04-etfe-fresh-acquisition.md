# ETFE fresh Alpaca download setup and five-DTE cap

User clarification selects new Alpaca stock/option downloads and rebuilding ETFE
from those inputs. Old project metadata is not an input or a repair dependency.
The subsequent direction caps traded options at five DTE; the prior one-day
minimum is retained. [Collection successor](../specs/ETFE_FRESH_ACQUISITION_20261003.md),
[DTE successor](../specs/ETFE_DTE_20261004.md).

## Implemented and run

`nn_meta/etfe/acquisition.py` and `scripts/acquire_etfe_alpaca.py` implement a
fresh Alpaca-only manifest, GET transport, checksummed page chains, persistent
rate waits, immutable attempt receipts, resume, raw occurrence reader and audit.
No old cache, feature array, label or model is read. Credentials stay in .env;
only selected Alpaca pairs are loaded, and request/response secrets are filtered.
The downloader's serial rate budget is separate from future autosized workers.

| Fresh capture | Complete partitions | Pages / live GETs | Rows |
| --- | ---: | ---: | ---: |
| SIP raw stock 1m, three ETFs, January 2024 and October 1–2, 2026 | 6 | 9 | 50,106 |
| Alpaca option symbol discovery, two expiries × both statuses × three ETFs | 12 | 12 | 2,084 |
| Option 1m bars, two dates × call/put per ETF | 6 | 6 | 2,284 |
| Option trades, opening 30 minutes, same sample contracts | 6 | 9 | 39,975 |
| **Total** | **30** | **36** | **94,449** |

Every live GET returned 200; an initial sandbox transport failure is separately
retained. Every partition reached a terminal token; audit found no timestamp
ordering reversals. Six active-status discovery partitions are terminal empty
responses, not proof of no historical trading. Retain discovery fields raw;
they do not become historical model features or contract-economics rules.

Option samples are chosen deterministically from the new discovery and stock
responses (nearest strike to the 09:30 stock open, one call and put). Their dates
are January 18, 2024 and October 2, 2026. They test the real transport path;
sample selection is not point-in-time production eligibility. October same-day
contracts are not admitted purchases. January stock padding does not establish
the options-history floor or authorize earlier model warmup.

Stock requests use explicit SIP/raw and `asof=-`, following the
[stock API contract](https://docs.alpaca.markets/us/reference/stockbars).
Fresh discovery uses explicit expiry/status bounds rather than the
[contract endpoint defaults](https://docs.alpaca.markets/us/reference/get-options-contracts).
Option history requests omit unsupported feed selectors and preserve native
timestamp strings and all no-ID trade occurrences.

## Recovery and resource evidence

The live option capture stopped deliberately after its first committed page,
then resumed the remaining work. The prior body, receipt and page pointer hashes
are unchanged. Offline interruption tests also stop inside a multipage chain,
then demonstrate row equivalence with uninterrupted capture, including identical
trade occurrences and empty token-bearing pages. Complete-root resume makes no
new requests in the test.

Both raw roots together use approximately **9.55 MiB** before portable packaging.
Maximum reported process peak RSS: **835,710,976 bytes**. Successful capture
invocations used about **34.2 seconds** total; permission/preparation/wait time
is excluded. Disk/RAM reserves passed. Limits are 128 GETs/30 minutes per run,
512 MiB per root, 32 MiB per page and at most 60 GETs/minute. These measurements
do not forecast the complete feature/execution/dataset/training workload.

## Current scope and remaining work

New immutable v3 setup selects actual **1–5 calendar DTE** for every entry and
roll purchase. Default targets remain 1/5; eligible weekly targets are 2/4.
Target 7 is removed. Calendar DTE uses America/New_York at the actual attempt,
not UTC date, trading-day count or nominal target. The new `dte_frac` formula
divides by five; old frozen formula artifacts remain unchanged. The implemented
DTE guard is a component, not a completed execution engine.

All twenty families/25,353 ticker variants and the existing fixed end remain.
Context-only 1–45 DTE surfaces are still declared; they are not purchase demand.
The previous exact provider-global history prerequisite is replaced by scoped
SPY/QQQ/VOO acquisition/coverage work. Eligibility, terms, hours and provenance
validation remain required where features, execution and freezes consume them.

Next: typed normalization/quality and session reports, complete scoped demand
with the five-DTE purchase cap, measured expansion beyond bootstrap windows,
and integrated ETFE-4.pilot. No full-history completion, scientific admission,
dataset/model freeze, training campaign or deployment is claimed.

## Verification and portable evidence

**73 focused tests passed**: 12 new capture/recovery tests, nine new DTE tests,
and the existing setup/VWAP/pull tests. Current v3 setup integrity and the
preserved predecessor contract integrity checks pass. Raw receipt/body/source
hashes and live resume preservation are independently checked.

[Machine receipt](2026-10-04-etfe-fresh-acquisition.json) binds the
[portable bundle](2026-10-04-etfe-fresh-acquisition-evidence.zip), raw roots,
source snapshots, capture audits and current setup. No evaluated model verdict
or maturity increase follows from this engineering milestone.
