# ETFE feature amendment for decision-clock rows — October 7, 2026

User-selected. Applies the [row-unit amendment](ETFE_ROW_UNIT_AMENDMENT_20261007.md)
and the bars-only envelope to the registered 221-field schema
([feature map](ETFE_FEATURE_MAP_20261003.json)). The 221 values + 221 masks layout
and order are unchanged; semantics change only where listed. Implementation:
`nn_meta/etfe/feature_build.py`. First run builds SPY and QQQ (training scope);
VOO stays in the label census only, with re-warm deferred.

| Fields | Registered meaning | Amended meaning |
| --- | --- | --- |
| `strat_<family>` (20) | One-hot of the row's variant family | Fraction of that family's variants firing the row's entry channel (call 0 / put 2) at the bar |
| `timeframe_*` (3) | Variant timeframe | Row timeframe (unchanged) |
| `param_*` (54) | Variant parameters | Always missing: `row_unit_amendment` |
| `dir_short` | Variant direction | 1 for put rows, 0 for call rows |
| `bars_since_signal` | log1p bars since the variant's previous signal | log1p bars since this scope's previous decision bar on the same right |
| `ma_gap`, `px_vs_fast` | Variant's own fast/slow MA (10/30 for non-MA) | Median over firing MA-family variants' own windows; missing when none fired |
| option bar fields (3) | Captured minute bars; absence needs explicit no-trade evidence | Unchanged formula; complete terminal capture of the window is the no-trade evidence (as in the labels) |
| `etfe_option_trade_count_per_second`, `..._trade_volume_per_second` | Condition-allowlisted trades | Sum of bar `n` / `v` over the window per second; no condition filter (bars-only) |
| `etfe_option_trade_range_bps`, `..._trade_size_cv`, `..._vwap_last_bps`, `..._tickrule_*` (5) | Trades | Always missing: `bars_only_first_run` |
| 7 option-context fields | Closing minute-bar VWAP surface with freshness proof | Same formula (1–45 DTE, premium >= $0.20, \|log K/S\| < 1%, `proxy_iv`, near <= 20 DTE) on census **daily close** and volume, available at the next open; freshness unverifiable. Far tenor and put/call ratio missing after 2026-08-25, near after 2026-09-19 (census expiries end 2026-10-09) |
| `dte_frac`, `moneyness` | Dated selected contract | Selection-v2 contract: DTE/5, log(strike / signal-bar close) |
| `sec_*` (9) | Dated sector evidence | Static: SPY and QQQ are `idx_etf` |

Technical (13), TV (96) and stock daily context (3) use the audited producers
unchanged on full-history charts.
