# ETFE closing-auction exercise reference capture — October 6, 2026

Implements the user-selected exercise reference of
[dated-input policy v1](ETFE_DATED_INPUT_POLICY_20261006.md): the official
closing-auction print of the primary listing exchange (NYSE Arca for SPY/VOO,
Nasdaq for QQQ) on each expiry session, applied with OCC's strict $0.01
exercise-by-exception rule. Contracts within $0.05 of the strike are reported
as pin statistics, not excluded.

Capture: fresh Alpaca SIP stock trades (`/v2/stocks/trades`, `feed=sip`,
`asof=-`, ascending) from 5 seconds before to 30 seconds after the dated
calendar close (early closes included), one request per underlying/expiry
session that has admitted contracts on or after 2024-01-18. Engine:
`nn_meta/etfe/stock_trade_capture.py`, a route-specific successor of the
frozen quote engine with identical page lineage, resume, pacing (1 s), 128-GET
runs, 512 MiB root and 100 GiB / 20% free-space guards. The full plan is split
into one root per year to stay under the root limit. Expiry sessions after the October 2, 2026 fixed end
cannot be captured and remain unresolved.

## Probe evidence and extraction rule

A six-request probe (2024-11-29 early close and 2025-06-13; root
`alpaca-fresh-closing-auction-probe-20261006-r0`, `PROBE_FINDINGS.json`) used a
125-second window. In every job the listing exchange printed the closing cross
with condition `6` and then a condition `M` (Market Center Official Close) at the
same price and size, within 0.4 s of the close. Other venues also emit `M` prints
at other prices, so the venue filter is required. The probe root's sources
predate the narrowed window; its raw bodies are bound by hash in the findings.

Rule (`closing_reference.official_close`): the reference is the listing-exchange
`M` print. Missing → `missing`; conflicting `M` prices, or an `M` price absent
from the listing-exchange `6` prints → `ambiguous`. Both leave the expiry outcome
unresolved. No reference is inferred from quotes or bars.
