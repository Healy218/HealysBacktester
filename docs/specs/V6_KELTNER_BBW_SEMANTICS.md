# V6 Keltner and BB-width strategy semantics

Audited 2026-09-06. The existing v6 definitions are **Keltner breakout** and
**BB-width rolling-minimum breakout**. These choices preserve the implemented
sweep behavior. The current repository contains no competing mean-reversion or
percentile implementation for either family. No strategy formula, grid, default,
or historical artifact was changed by this audit.

`nn_meta.baseline` obtains sweep signals through `nn_meta.proposals.sweep_signals`,
recovers winning parameters with `params_from_portfolio`, and replays them through
`single_signals`. Both proposal paths call the same functions in
`signals/tv_signals.py` and preserve all four boolean outputs in this order:
long entry, long exit, short entry, short exit. Disabled shorting returns `None`
for the last two outputs. Entry and exit events are independent conditions;
the simulator controls whether an event changes an actual position.

## Keltner (`keltner`)

- Parameters: `kc_window` = 10, 20, 30, 40, 50; `kc_mult` = 1, 1.5, 2, 2.5, 3.
- Basis: close EMA, alpha `2 / (window + 1)`, first close as seed.
- Range: true range smoothed by `v3.indicators.rma`, alpha `1 / window`, first
  true range as seed. First true range is high minus low; later true ranges
  also include gaps to previous close. The existing pandas EWM initialization
  is part of this family. It is not a claim of fixture-verified Pine SMA-seeded
  `ta.rma` equivalence, and is not replaced by the new `pine_compat.rma` helper.
- Bands: basis plus/minus multiplier times smoothed range.
- Long entry: current close strictly above current upper band and previous
  close at or below previous upper band. Long exit: current close strictly
  below current basis and previous close at or above previous basis.
- Short entry/exit mirror these conditions at the lower band/basis. Touching
  a boundary is not a new crossing; remaining outside a band does not reenter.

## BB-width (`bbw_squeeze`)

- Parameters: `bbw_window` = 10, 20, 30; `bbw_lookback` = 60, 120, 180.
- Basis: full-window close SMA. Bands use twice the population standard
  deviation (`ddof=0`). Width is `(upper - lower) / basis`; a zero basis gives
  an undefined width.
- Squeeze: current width is at or below the minimum of the last `lookback`
  widths, including itself and including ties. The complete lookback must
  contain valid widths. There is no percentile threshold or percentile
  parameter. On complete input, the earliest possible armed entry is at
  zero-based index `window + lookback - 1`.
- Long entry: the **previous** bar was in a squeeze and the current close
  crosses above the current upper band from at/below the previous upper band.
  Short entry mirrors this at the lower band. Current squeeze status is not
  an extra condition; merely remaining outside a band is not a fresh entry.
- Long exit crosses strictly below the basis; short exit crosses strictly
  above it. Exits do not require squeeze status or an entry on the prior bar.
- This is a separate family from the existing `squeeze` implementation, which
  uses LazyBear-style BB-inside-Keltner release and momentum direction.

All calculations use the current closed bar and earlier bars only. They do not
backdate an event. Input history must be identical between sweep and replay:
truncating history changes EWM state and rolling warmup. Signal equality does
not assert equivalence to a TradingView execution fixture or determine fill
timing, which remains the executor's responsibility.

`tests/test_v6_keltner_bbw.py` checks every configured column after actual freeze
parameter extraction against all four replay frames, both shorting modes,
prefix invariance, two-sided hand-checkable events, boundary ties, complete
rolling warmup, nonminimum rejection, and flat input. These are existing v6
families; the 13 separately source-pinned TradingView ports retain their own
admission gates.
