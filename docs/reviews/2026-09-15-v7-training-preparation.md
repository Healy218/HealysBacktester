# V7 training preparation — September 15

Training has **not** been launched. This is a tested implementation milestone,
not full-universe admission. The final readiness report rejects eight missing
full-universe evidence stages. All 222 columns, 20 families, 11,268 variants per
ticker and the March 15, 2022–September 14, 2026 scope remain required.

## Rebuilt PIT membership and coverage

`build_v7_identity_universe.py` now requires the active filtered input root and
its full captured calendar. The five deleted March sessions consume positions
in the 63-session calendar window, but contribute neither zero volume nor
activity; older observations do not replace them. The minimum remains 50
active sessions. Median scores, ranks and hysteresis are recomputed.
Pre-March captures remain usable for PIT membership; price-feature warmup is
still a separate March 15 cold start. Tested missing-session, contaminated-input
and minimum-activity rejection.

New immutable output: `nn_meta/validation/v7-identity-universe-start-20220315`:
597 historical tickers, 595 securities, 16,580 research-relevant membership
rows. Reviewed identity transitions still pass. This changes the old 598-name
universe; downstream builds must consume the new one.

New coverage: `nn_meta/validation/v7-membership-session-coverage-rebuilt-20220315`:
340,272 eligible sessions, 189 original zeros, 67 verified aliases, **122 still
unresolved**. Those span ATVI, BBBY, BIIB, CLSK, COUP, DISCA, FRC, NVAX, REV,
SGEN, SI, TWTR, VERU, VMW and X. Lifecycle evidence must explain expected
absence and resolve positions/deliverables; simply deleting these rows is not
admission. Daily exact aliases remain required. No feed completeness claim.

Reproduction:

```bash
./venv/bin/python scripts/build_v7_identity_universe.py   --audit nn_meta/data_v7/start-20220315/audit   --active-source nn_meta/data_v7/start-20220315   --masters nn_meta/data_v7/security-master-20260915   --calendar nn_meta/data_v7/start-20220315/calendar.json   --references nn_meta/data_v7/reference-20260915   --identity-requests nn_meta/validation/v7-all-identity-boundaries-20260915/requests.json   --reviewed-boundaries nn_meta/validation/v7-reviewed-identity-boundaries-20260915.json   --output NEW_IMMUTABLE_UNIVERSE_PATH
```

## Selected-contract rows

`v7-selected-contract-rows-v2` defines `dte_frac` as actual calendar DTE at the
feature decision divided by nine, and `moneyness` as log(strike/raw spot) for
both calls and puts. Target DTE remains provenance rather than masquerading
as selected maturity. The completed raw minute close must be available by the
decision and at most 60 seconds old. Zero-day/expired and >9-day contracts,
future/stale/invalid spot, and wrong contract side/root are rejected.

Initial missing daily warmup now leaves all ten daily columns NaN and records
`warmup_unavailable`; it neither drops March 15 nor selects a future daily row.
The 222-column order is unchanged. Factorized stores advance to v2 and include
the semantic contract in their identity; v1 stores are incompatible even with
the same column names. The pipeline pilot passes raw spot and its timestamp.
Full-history daily/feature integration remains open.

## Physical expiry engine and shared replay

`PhysicalLedger` supports standard 100-share contracts with exact dated
metadata and official exercise reference evidence. It records nonexercise,
exercise, delivery commitments, settlement, stock delivery, observed stock
sale and sale settlement separately. It never creates an intrinsic-value fill.

Call exercise reserves strike cash from shared available cash. Pending entries
and competing exercises cannot reuse it. Put delivery requires settled shares
of the same explicit security identity. Optional inventory acquisition pays for
shares from existing cash and waits for settlement; no shares or exercise
capital are injected. Unfunded exercise and missing shares remain unresolved.
The existing 10%-premium allocation is unchanged and does not guarantee
exercise funding.

Fractional research quantities use the explicitly named pro-rata convention;
whole-contract mode is also validated. Exercise fee defaults to zero as a
research assumption, stock fee/slippage fractions to .001/.0005. These are
policy inputs, not assertions about actual historical broker fees. The
settlement business calendar must be separately captured. T+2/T+1 depends on
the event date; delivery and cash become usable conservatively at the next
trading open after settlement date. No broker-specific early release assumed.

Shared `portfolio_replay(..., physical=context)` uses this ledger. It preserves
slots through stock liquidation and sale settlement and records completion
clocks for extended label horizons. A path whose standalone option replay is
censored can complete only if the actual shared funding/resources permit it.
Missing/stale stock marks block new entries; purchases keep the existing
cash-reservation and symbol/slot constraints.

Ten physical tests cover funded calls, funded put inventory, missing shares,
competing exercise/entry reservations, fractional sizing, exact $0.01 threshold,
nonexercise, metadata/reference rejection, stock provider/size/session checks,
the settlement transition/holiday, complete costed cash reconciliation, and
shared replay horizons. **These are synthetic engine tests.** The production
physical context/receipt loader, official expiration references, settlement
calendar, Alpaca stock quote archive, corporate-action deliverables and real
observed physical replay remain unimplemented/unadmitted. Standalone proposal
labels still do not receive fictitious exercise capital. No new quote captures.

Primary rules checked: [OCC equity specifications](https://www.theocc.com/clearance-and-settlement/clearing/equity-options-product-specifications),
[OCC dated settlement conversion memo 54436](https://infomemo.theocc.com/infomemos?number=54436),
[OIC exercise FAQ](https://www.optionseducation.org/referencelibrary/faq/options-exercise).
Current documentation does not prove historical broker instructions.

## Executable readiness report

```bash
./venv/bin/python scripts/v7_readiness.py   --output nn_meta/validation/v7-readiness-20260915-preparation-final.json
```

Exit 1 is the correct current result. Active input hashes, new membership and
new coverage inventory pass. Lifecycle, causal prices, full daily context,
quotes, physical execution, assembly, trials and integrated resource pilots
still lack complete-universe evidence.

The aggregator requires immutable stage receipts, the current scope/row
contract, full historical ticker/security sets, source/runtime/input bindings,
all named checks and no unresolved limitations. Old component pilots cannot be
substituted. Seven tests exercise missing stages, old scope/source, partial
universe, missing checks and changed inputs. Stage producers and real integrated
validation are still required; this report does not turn absent builders into
a runnable full campaign.

## Verification and limits

Final suite: **1,746 tests plus 18 subtests passed**, 18 warnings, 81.97 seconds;
`/tmp/v7-preparation-20260915-final-tests.log`.
The earlier pre-readiness-code full suite passed 1,739 tests plus 18 subtests
in 82.43 seconds, with 18 warnings. Both runs include the preserved unrelated
V6 working-tree changes; neither is a clean-checkout reproduction.

No V6 runtime or timers changed, no server deployment, no notifications,
no full freeze/build/training. Acquisition quota was not reset or expanded.
