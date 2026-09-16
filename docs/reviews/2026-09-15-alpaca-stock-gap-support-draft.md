# Alpaca historical SIP gap — retired support draft, not sent

Superseded for V7: the user moved the research start to March 15, 2022.
The March 8 repair is no longer an active V7 task. Preserve this as evidence.

Prepared September 15, 2026. No credentials or customer identifiers included.
User confirms an existing Alpaca Pro subscription. Alpaca remains the V7
underlying-stock source; Massive supplies historical options. These incomplete
SIP responses require data/request investigation, not an assumed stock-plan
upgrade. The Massive stock probe below is historical diagnostic evidence only.

## Reproduction

For BAC, authenticated requests to `https://data.alpaca.markets`:

1. `GET /v2/stocks/bars` with `symbols=BAC`, `timeframe=1Min`, `feed=sip`,
   `adjustment=raw`, `asof=-`, `sort=asc`, `limit=10000`,
   `start=2022-03-08T00:00:00Z`, `end=2022-03-08T23:59:59.999999999Z`.
   The fully paginated response has 125 minute bars and **zero** in
   `[2022-03-08T14:30:00Z, 2022-03-08T21:00:00Z)`.
2. `GET /v2/stocks/BAC/bars` for the same regular session returns just the
   closing-auction bar at 21:00 UTC when the endpoint includes that boundary.
3. `GET /v2/stocks/BAC/trades`, `feed=sip`, `limit=100`, `sort=asc`,
   `start=2022-03-08T14:30:00Z`, `end=2022-03-08T21:00:00Z` returns only
   three records, no next page, at 14:30:00.791400960Z through 14:30:01.612835113Z.
   This is not a page-limit issue.
4. The raw daily bar for March 8 has O/H/L/C all 38.59, volume 6,302,913,
   and 1,168 trades. It also appears inconsistent with full-session coverage.

The issue persists in fresh raw and `adjustment=all` captures and an older
saved BAC 2022 minute-data backup. We have not substituted daily bars or
manufactured intraday prices. Please confirm whether this is a known historical
SIP gap, whether affected data can be restored, and whether another supported
endpoint supplies the complete original regular-session history.

## Other affected roots

Freshly recaptured roots with the same missing regular session on March 8, 2022:

BAC, BB, BILL, BKKT, CAT, CHPT, CHWY, CLF, CVS, DHR, FSR, JNJ, KO, KSS, LVS, MMM, NEM, PFE, PLTR, SE, SNOW, SPCE, V, VALE, VLO, XPEV.

This is a 26-root confirmed query result, not a claim that the entire provider
universe is affected. Separate single-day biotech/trading-halt cases are excluded.

## Local evidence

- `nn_meta/data_v7/isolated-stock-gaps-20260915/`: raw and adjusted responses,
  original pages, validated Parquet and completion receipts.
- `nn_meta/validation/v7-isolated-gap-recapture-20260915.json`: 30-day recapture
  summary (26 March 8 cases plus four separate cases).
- `nn_meta/data_v7/stock-gap-alpaca-probe-20260915/`: single-symbol, daily and
  trade endpoint responses.
- `nn_meta/data_v7/stock-gap-backup-probe-20260915/`: diagnostic backup copy.
- `nn_meta/data_v7/stock-gap-massive-probe-20260915/`: alternate-provider query
  rejected with HTTP 403 for this historical stock-data timeframe. No upgrade purchased.

**Delivery:** draft only. Sending to support requires an explicit user instruction.
