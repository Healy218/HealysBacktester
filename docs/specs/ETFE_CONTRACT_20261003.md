# ETFE source and history contract

This revision specifies the first ETFE research run and records what prevents
ETFE-0.contract from closing. The four component contracts are declared; source
admission is **blocked**, not complete. The exact provider-global first timestamp
and dated contract/rule coverage are not established by the available API.
The user-selected dates and universe remain unchanged.

| Component | Versioned specification |
| --- | --- |
| Features and all inherited columns | [Feature contract](ETFE_FEATURES_20261003.md), [field registry](ETFE_FEATURE_MAP_20261003.json) |
| Fills, portfolio and terminal outcomes | [Execution contract](ETFE_EXECUTION_20261003.md) |
| Targets, folds, fits and acceptance | [Evaluation contract](ETFE_EVALUATION_20261003.md), [trial declaration](ETFE_EXPERIMENT_20261003.json) |
| Sources, partitions and bounded pilot | [Acquisition contract](ETFE_ACQUISITION_20261003.md) |
| Evidence and verification | [Contract review](../reviews/2026-10-03-etfe-contract.md), [portable receipt](../reviews/2026-10-03-etfe-contract.json) |

These documents supplement the immutable
[v2 scope](ETFE_SCOPE_VWAP_20261003.json). They do not mutate its preparation
receipt, admit inputs, deploy services or authorize bulk capture/training.
[ROADMAP](../../ROADMAP.md#etfe-first-run-sequence) retains the execution order.

## History boundary finding

The provider's [overview](https://docs.alpaca.markets/us/docs/historical-option-data)
still states February 2024. Retained live receipts contain January 18, 2024
observations. The earliest retained **sample** bar opens at
`2024-01-18T14:30:00Z`; the earliest sampled trade is SPY at
`2024-01-18T14:30:00.009729024Z`. Neither is a provider-global lower bound.
Do not conflate the bar's opening timestamp, its completion at 14:31:00,
its modeled availability at 14:31:01, and an individual trade timestamp.

New controls captured October 3 at 20:08:37 Central (October 4 01:08:37 UTC)
returned HTTP 200 and empty, terminal pages for trades and bars before
January 18 14:30 UTC in three named January 19 contracts. This establishes only
absence in those six queries. The [trades](https://docs.alpaca.markets/us/reference/optiontrades)
and [bars](https://docs.alpaca.markets/us/reference/optionbars) routes require
contract symbols; neither offers an all-symbol earliest-event query. Expired
contracts not sampled could have earlier history. Increasing a sample does not
prove global absence.

**H1 remains open:** obtain a provider-authenticated exact history floor and its
scope (trades, bars, feeds and any backfills), or a demonstrably complete
provider-wide contract/event inventory from which the minimum can be verified.
A full SPY/QQQ/VOO census could establish the scoped minimum, but not the literal
provider-global minimum required by the current gate. Do not replace the gate
with that narrower claim. No provider message has been sent on the user's behalf.
`verified_start_utc` remains null; January 18 is a discovery lead only.

## Fixed end and time conventions

The exclusive civil-time boundary is **2026-10-03 00:00 America/New_York =
2026-10-03T04:00:00Z**. Alpaca's APIs use inclusive endpoints; request through
`2026-10-03T03:59:59.999999999Z`, then normalize to the half-open interval.
Never use a floating-point timestamp for nanosecond identities.

The captured October 2 stock calendar confirms regular open 09:30 EDT and
close 16:00 EDT, **13:30–20:00 UTC**. This is stock-calendar evidence, not
option-class expiry-hours evidence. Session alignment uses IANA
America/New_York and actual calendars, including DST, holidays and early closes.
No signal bar may extend past its stock-session close. A final option bar that
becomes available after its contract's trading close cannot fill before close.

Current Nasdaq [hours](https://www.nasdaqtrader.com/Trader.aspx?id=optionshours)
list SPY, QQQ and VOO among 16:15 classes, while its separate
[holiday-hours PDF](https://www.nasdaq.com/holiday-trading-hours) omits VOO
from that list. These current pages do not establish VOO's effective history or
each expiring series' closing time. **R2 remains open:** resolve dated class,
expiration-day and early-close exceptions with effective-date evidence. For a
verified 16:15 EDT class close the UTC close is 20:15 and the 15-minute cutoff
is 20:00; for a verified 16:00 close they are 20:00 and 19:45. These conversions
are conditional examples, not an admitted hours table.

## Source eligibility and research assumptions

Use Alpaca historical option trades/bars only, and SIP stock bars/quotes.
Alpaca staff [confirms historical option bars use OPRA](https://forum.alpaca.markets/t/data-source-for-option-historical-bars/17704).
The documented historical endpoints do not expose a feed selector; preserve
that fact, the endpoint/version, account entitlement evidence and provider source
statement. Do not label a made-up `feed` query parameter as feed verification.
Latest indicative observations cannot fill historical gaps. Historical trade
feed semantics require **P1**, a captured provider specification or
confirmation distinguishing the historical trade route from indicative trades.
Samples lack exchange trade IDs: the acquisition contract retains page/row
occurrences, without inventing IDs or original correction history.
The condition mapping is now explicitly declared
from [Alpaca's aggregation FAQ](https://docs.alpaca.markets/us/docs/market-data-faq);
bar provenance alone does not settle every trade-field interpretation.

Completed historical aggregates are revised research inputs. Baseline option
availability is end + 1 second; underlying bars use their completed close,
with the signal's one-second execution latency. Later known publication times
override these modeled times. No capture timestamp is backdated into a real
historical receipt. Lag/revision stresses are mandatory. This run can claim
causal computation under declared final-vintage assumptions, not proven
historical real-time availability or live parity.

**R1 remains open:** current expired-contract responses are discovery aids.
The new `show_deliverables=true` controls returned `size=100`, `multiplier=0`
and `settlement_type=T+1` for January 2024 expirations in all three examples.
Treat these as uninterpreted current provider fields, not a zero economic
multiplier or a historical settlement rule. [OCC memo 54436](https://infomemo.theocc.com/infomemos?number=54436)
dates equity T+1 conversion to May 28, 2024. Each selected contract needs dated
strike, multiplier, deliverable, adjustments and exercise reference evidence.
An OCC symbol and today's metadata alone are insufficient.

All required series get separate first-observed, first-feature-eligible and
coverage intervals. Cold-start at the ultimately verified options-history
boundary; do not import earlier warmup or V7 data. Initial native indicator
warmup remains visible. Lack of required history/source coverage cannot be
converted into permissible warmup or shorten the requested acquisition window.

## Admission decision

ETFE-0 feature, execution, evaluation and acquisition **definitions** can be
reviewed now. H1, R1, R2 and P1 prevent the claim of feasible, fully specified
required observations. Close them with explicit linked evidence, then seal an
immutable contract successor before ETFE-4.pilot. Full coverage is subsequently
proved at ETFE-1; it is not required to invent a coverage verdict here.
Neither ETFE-4.pilot nor bulk work was launched in this contract session.
