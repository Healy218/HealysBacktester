# ETFE dated contract existence census — October 6, 2026

User-selected October 6 to replace capture-dependent existence evidence. The
exact-window census found a selectable contract for only 227,529 of 4,311,060
decision clocks (5.3%), because selection could use only contracts observed in
earlier bounded captures.

Capture: fresh Alpaca daily option bars (`/v1beta1/options/bars`,
`timeframe=1Day`, ascending) for every admitted SPY/QQQ/VOO contract (dated
policy v1) expiring 2024-01-18 through 2026-10-09, in requests of at most 100
contracts sharing one expiry. Each request covers the 50 calendar days before
expiry (not before 2024-01-01) through expiry, capped at the October 2, 2026
fixed end. Engine `nn_meta/etfe/option_daily_capture.py`: a route-specific
successor of the frozen engines with the same page lineage, resume, 1 s pacing,
128-GET runs and free-space guards, and a 4 GiB root limit.

Rule: a contract's first session with a daily bar of volume >= 1 establishes
existence. It becomes selectable from the **next** trading session, which
satisfies the execution contract's "observed on a strictly earlier trading
date". Contracts that never traded before a decision remain unavailable; no
listing date is inferred from discovery metadata. Daily bars are existence
evidence only, never prices for execution or features.
