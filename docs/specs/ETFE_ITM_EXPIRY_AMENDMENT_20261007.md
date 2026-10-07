# ETFE ITM-expiry resolution amendment — October 7, 2026

User-selected. An option position that is in the money at expiry and can neither
be sold (1% participation cap) nor exercised in the isolated $100,000 account
(puts without settled shares; calls without strike cash) **closes at intrinsic
value**: max(0, official closing-auction reference − strike) for calls (strike −
reference for puts) × 100 per contract, less 0.10% fee and 0.05% slippage,
settled T+1 like an option sale. Funded call exercise and liquidation are
unchanged. Implementation: `label_kernel` `unfunded_itm='intrinsic'` (the default
`'unresolved'` keeps earlier label roots reproducible).

**Disclosure:** this rule was chosen after the v4 validation replay showed that
v4's result depends on how these positions resolve (positive with favorable
resolution, negative if they lose their premium). Validation folds therefore
cannot arbitrate v4 under this rule. The 2026 test, never evaluated under any v4
design, is the deciding period, followed by forward paper data. Successor
artifacts: labels v4, dataset v4, experiment v5.
