# Massive stock repair entitlement investigation — superseded

**Subsequent user clarification:** use existing Alpaca Pro for underlying
stocks and Massive for options. The upgrade path below is historical research,
not an active recommendation or pending purchase. The later March 15 research
start removes March 8–14 from active inputs and retires this repair investigation.
See [date migration](2026-09-15-v7-march15-start.md).

Checked September 15, 2026. User authorized investigation; no subscription
was purchased and no message was sent.

## Minimum advertised plan

**Stocks Starter: $29/month**, five years of history, minute aggregates and
unlimited API calls. March 8, 2022 is within that history window today.
The 15-minute delivery delay does not impede this historical repair.
Stocks Developer ($79/month) adds ten-year history and trades; Advanced
($199/month) adds quotes and real-time access. Neither higher tier is required
by the stated minute-bar repair alone. Stocks and Options have separate plans.
[Official stock plans](https://massive.com/stocks) and
[endpoint entitlement table](https://massive.com/docs/rest/stocks/aggregates/custom-bars).

This recommendation covers the 2022 gap, not replacement of all 2021 warmup
history. Starter's rolling five-year window does not cover early 2021 today.

## What our evidence establishes

Saved probe: `nn_meta/data_v7/stock-gap-massive-probe-20260915`.
The raw BAC one-minute request for March 8 returned HTTP403/NOT_AUTHORIZED;
its message explicitly identifies the plan's data timeframe restriction.
This establishes the access blocker, not availability of the missing records.
The probe contains no regular-session bars to validate.

## Verification request prepared for review — not sent

Please confirm that Stocks Starter grants access to raw one-minute stock
aggregates for March 8, 2022, and check actual regular-session coverage for:

BAC, BB, BILL, BKKT, CAT, CHPT, CHWY, CLF, CVS, DHR, FSR, JNJ, KO, KSS,
LVS, MMM, NEM, PFE, PLTR, SE, SNOW, SPCE, V, VALE, VLO, XPEV.

Alpaca has no regular-session minute bars for these ticker/date combinations.
Before subscribing, please provide regular-session bar counts and first/last
timestamps, or a sample response for BAC. The interval is 09:30–16:00 New York
(14:30–21:00 UTC), with bar starts strictly before the close. Our request is:

```text
GET /v2/aggs/ticker/BAC/range/1/minute/2022-03-08/2022-03-08
    ?adjusted=false&sort=asc&limit=50000
```

Massive provides a [support contact](https://massive.com/contact), but no
confirmation has been obtained. A paid entitlement alone cannot prove that
these observations exist.

## Acceptance after access is available

Capture the raw BAC response with a receipt, then all 26 ticker sessions if
the probe succeeds. Preserve original Alpaca files and the shared 250 GB quota.
Validate dated identity, timezone, ordering, duplicates and OHLCV; distinguish
regular trading from auction/extended-hours records. Reconcile nearby sessions
and the raw-price/action basis before wiring a separate repair source into
assembly. Do not require 390 bars blindly: a minute without eligible trades
can legitimately be absent. The stock gap remains open until this validation.
