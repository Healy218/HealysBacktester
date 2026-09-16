# September 16 V6 repeated rapid exits: direct runtime replay

The user reopened the V6 question after additional alerts appeared to report
5% stop exits shortly after entry. This supersedes the earlier instruction only
as to investigating the new observations. No runtime, portfolio state, strategy,
pricing, spread cap, service or notification settings were changed.

Replayed the actual activated runtime at `/home/healy/Coding/HealysV6` against
its frozen release, September 15 stock seeds and the retained September 16
19:00:31 UTC adjusted-stock capture. Key runtime files exactly match activation
hashes. Each underlying vectorbt trade reproduced the held entry and recorded
exit bar/time. Its strategy exit boolean is true in all five cases. All prices
through each exit remained clear of the exact 5% stock stop, computed from the
simulated stock entry including its stock slippage. The simulator receives
underlying OHLC and strategy signals, not option bid/ask or option P&L.

| Symbol | Strategy | Stock entry close | 5% stop level | Lowest stock price after entry | Option return after costs |
|---|---|---:|---:|---:|---:|
| CELH | Keltner | 28.745 | 27.3214 | 28.26 | Still pending at snapshot |
| SIL | BBW squeeze | 92.95 | 88.3467 | 90.96 | -19.47% |
| RH | TV setup | 131.095 | 124.6025 | 129.22 | -35.64% |
| AFRM | BBW squeeze | 72.93 | 69.3181 | 71.21 | -30.79% |
| SNDK | TV SR | 1547.31 | 1470.6795 | 1519.00 | -13.04% |

SIL and RH entered around 18:03:54 UTC; their exit signals arrived with the
18:15 bar close. AFRM and SNDK entered around 18:49:01 UTC and triggered at
19:00. These are real next-bar exits in the paper experiment, not instantaneous
option P&L stop tests. Quote availability delayed some completed sales.

The label `frozen underlying strategy/5% stop exit` is hardcoded for **every**
closed underlying simulation trade in `detect_symbol`; it does not identify
which exit condition fired. It is therefore misleading when interpreted as a
confirmed stop-loss event. This diagnosis identifies the explicit strategy exit
signals and rules out the generic 5% stock stop for these five trades; individual
strategy rules (for example setup-specific ATR exits) remain part of each
strategy's signal definition.

The user's spread-cost concern is supported independently of that label:
SIL's bid/ask stayed 4.20/5.20 at both entry and sale, yielding -19.47% under
ask-entry/bid-exit plus costs. AFRM entered at ask 6.05 with bid 4.75 and sold
at bid 4.20. RH entered at ask 15.80 with bid 7.60, then sold at bid 10.20.
These quotes show substantial immediate liquidation costs. Underlying exit
signals can realize them after one bar; the fact that the stop is stock-based
does not solve this execution problem. Changing a display mark to midpoint
would not establish a midpoint execution.

Evidence retained in `nn_meta/validation/v6-incident-20260916-late`:
`positions.json`, `replay.json`, `summary.json`, exact `replay-source.txt` and
`replay.log`. Replay process exited 0. The first diagnostic attempt failed only
while serializing nested pandas attrs; that diagnostic was corrected and rerun.
It did not alter runtime or portfolio state. The 19:00 producer status separately
showed CELH awaiting a fresh exit quote and withholding new allocations.

The V7 preparation goal remains active. Future V7 execution/portfolio validation
must separately expose exit causes and spread costs; a 5% underlying stop is not
an option-loss cap. No new V6 trading policy is adopted by this read-only replay.
