# ETFE bounded stock-quote acquisition — October 5, 2026

Fresh Alpaca-only successor transport; previous source-bound engines stay
unchanged. Historical stock quotes use `/v2/stocks/quotes`, explicit SIP,
`asof=-`, ascending order and all continuation tokens, including empty pages.
Only SPY/QQQ/VOO are allowed, one symbol per request, limit 10,000. Windows are
half-open internally with inclusive provider end at exclusive-end minus 1 ns.
Source, parameter, raw response, timestamp and occurrence hashes are retained.

The finite density pilot has 54 windows: three ETFs, six sessions, three
150-second windows per session. Sessions are January 19 and November 29, 2024;
April 4, October 31 and November 3, 2025; October 2, 2026. Anchors are stock open,
stock close minus 15 minutes, and stock close. Each window begins 30 seconds
before its anchor and ends two minutes after. Early-close and DST clocks come
from the fresh Alpaca calendar. Stock-close anchors are sampling strata, not
admitted option-class expiration cutoffs or exercise references.

Budget: 128 attempts/run, 256 total, 30 minutes/run, 512 MiB/root including typed
output, 32 MiB/page, serial requests at least one second apart. Reserve each GET
durably before networking, including retries and crashed calls. Resume keeps
committed pages immutable. Existing disk/RAM guards remain. Incomplete transport,
API errors and empty responses never establish a quiet or nonexistent market.
No automatic campaign follows this pilot. Measure page/row/byte density per
window; full-history extrapolations remain scenarios, not guaranteed budgets.

Typed Parquet preserves every raw JSON occurrence, nanosecond timestamp, prices,
raw size values, conditions/exchanges/tape (inside raw JSON), response provenance
and quality flags. Never deduplicate equal timestamps. Diagnostic midpoint is
available only for finite positive noncrossed prices and positive integer raw
sizes. Bid/ask quantities in shares remain null and execution admission false.
The independent audit reconciles exact source occurrences and unconverted sizes;
diagnostic normalization is not proof of historical availability or capacity.

Provider sources checked October 5, 2026:

- [Historical stock quotes](https://docs.alpaca.markets/us/reference/stockquotes-1):
  endpoint, pagination and explicit feed/as-of controls.
- [Alpaca's dated size-change notice](https://docs.alpaca.markets/us/v1.1/changelog/marketdata-bid-and-ask-size-display-change),
  published October 30, 2025, announces shares instead of round lots starting
  November 3. This notice alone does not prove whether historical API data was
  retroactively rewritten. Sample both sides and retain raw sizes; do not apply
  a blanket factor of 100 or infer representation from divisibility.
- [Alpaca automatic-exercise explanation](https://alpaca.markets/support/what-is-automatic-exercise)
  identifies the underlying's official close as its exercise reference. A stock
  quote midpoint is not that reference. This pilot does not acquire an official
  closing-price series, dated contract terms or rules. Those remain required
  before physical-delivery outcomes can be admitted.
