# ETFE dated-input policy v1 — October 6, 2026

**Status:** user-selected policy, applied and independently audited (exercise reference, pin and quote-size rules added later on October 6). It replaces
"unresolved" verdicts for four dated-input classes with declared, conservative
rules. Alpaca supplies no point-in-time contract terms, so further downloads
cannot close them. Implementation: `nn_meta/etfe/dated_policy.py`. Build:
`scripts/build_etfe_dated_policy.py`. Audit: `scripts/audit_etfe_dated_policy.py`.
Output: `nn_meta/validation/etfe-dated-policy-20261006-r0/`.
[Decision](../DECISIONS.md), [prior findings](../reviews/2026-10-06-etfe-full-coverage.md#dated-input-findings).

## Rules

| Class | Rule | Basis |
| --- | --- | --- |
| Contract economics | Standard OCC `SPY/QQQ/VOO` symbols whose single deliverable is 100 equity shares of the same underlying (100% allocation, size 100) are admitted at multiplier 100. Raw `multiplier=0` is overridden by that deliverable. Anything else is excluded. | All 43,720 zero-multiplier records are standard symbols expiring 2024-01-03…2024-04-26 that report size 100 and a 100-share deliverable. The five adjusted `1SPY` contracts are excluded. |
| Contract availability | A contract may be selected at decision time *d* only if a fresh observation is available at or before *d*: completed option bar (start + 1 minute) or option trade timestamp, from any audited fresh ETFE capture. | No dated listing clocks exist. First-seen is causal and conservative; unobserved contracts are unavailable. |
| Exercise settlement | Use the provider's dated calendar `settlement_date` for the exercise (expiry) date. Cross-check: SEC rule keyed on **trade date** — T+2 before 2024-05-28, T+1 from then on — over NYSE sessions minus Columbus/Veterans Day bank holidays. | The rule reproduces 689/690 in-range provider dates. Declared exception: trades on 2025-01-08 settle on 2025-01-09 (NYSE closed for a national day of mourning; banks and DTC settled). Current contract `settlement_type` metadata is ignored for history. |
| Corporate actions | An action is known from the first trading session strictly after its declaration date. QQQ ex-date 2024-03-18 uses the official Invesco payable date 2024-04-30; the announcement's value is retained. Revisions are not modeled. | All 33 in-scope actions are cash dividends; all become known before their ex-date. |
| History start | Research history starts 2024-01-18 09:30 ET, the first observed option bar for all three ETFs. | Earlier January requests returned no option bars. |
| Exercise reference | Official closing-auction price of the listing venue (NYSE Arca for SPY/VOO; Nasdaq `Q`/`T` for QQQ): condition `M` print, else condition `6` closing cross. Missing or conflicting → expiry outcome unresolved. [Capture spec](ETFE_CLOSING_AUCTION_20261006.md). | User-selected October 6. 1,486 of 1,487 expiry sessions resolve; median distance from the final 15:59 SIP bar close is 0.007%. |
| Exercise rule / pins | OCC exercise-by-exception at exactly $0.01 ITM per share (decimal cents). Contracts within $0.05 of the strike are counted as pins, not excluded. | 330 pins among 434,880 evaluated contracts (SPY 162, QQQ 150, VOO 18). |
| Stock quote size | Raw SIP quote size ×100 (round lots) for sessions before 2025-11-03; raw size is shares from 2025-11-03 on (`quote_size_shares`). | Pilot medians: 2–6 on every session through 2025-10-31, 80–360 from 2025-11-03, in all three ETFs, matching Alpaca's dated notice. History was not rewritten. |
| VOO missing minutes | No filling. After each of the twelve missing minutes, a recursive indicator's next *warmup* observed bars are excluded (`rewarm_mask`); the feature build applies each variant's declared warmup and counts exclusions. | Twelve SIP rechecks never returned those minutes. |

## Audited application (r0)

- 452,347 census contracts: 452,342 admitted (408,622 standard, 43,720
  deliverable override) and 5 excluded (nonstandard symbol).
- 4,291 contracts have a first-available observation. All **227,529** candidate
  decision rows in the exact-window census have their contract available by entry
  start, so the availability gate removes none of them.
- 33 actions, 12 VOO gaps, one declared settlement exception.
- Independent audit recomputes economics positionally, first-available with
  Arrow aggregation over every source, settlement lookups, action sessions with
  `searchsorted`, and gaps. All match.

## Exercise reference capture and extraction v2

The [capture spec](ETFE_CLOSING_AUCTION_20261006.md) is pinned by its capture
roots and is not edited after preparation; results are recorded here. A six-request
probe (`alpaca-fresh-closing-auction-probe-20261006-r0/PROBE_FINDINGS.json`)
showed the listing venue printing the closing cross (`6`) and then `M` at the
same price and size within 0.4 s of the close; other venues also emit `M` at
other prices. Three yearly roots (`alpaca-fresh-closing-auction-{2024,2025,2026}-20261006-r0`,
94/131/97 MB, about 3.0M trades) captured all 1,487 expiry-session windows
(−5 s/+30 s around the dated close, early closes included).

The full 2024 capture exposed two cases the pinned v1 rule did not cover: on
2024-11-20 no venue published `M` while listing-venue closing crosses existed,
and Nasdaq reported QQQ's cross under venue `T` (NASDAQ Int) as well as `Q`.
Extraction v2 (`nn_meta/etfe/exercise_reference.py`) uses the listing-venue
family's `M` print, else its single `6` cross; conflicts or absence stay
unresolved. Result (`nn_meta/validation/etfe-exercise-references-20261006-r0/`):
1,486/1,487 resolved (1,482 `M`+`6`, 3 `6` only, 1 `M` only). QQQ 2026-08-20 has
no closing-auction print from any venue and stays unresolved. Against the final
regular SIP minute-bar close: median 0.007%, p99 0.07%, max 0.96% (SPY
2025-04-09, the tariff-pause close). An independent pandas recomputation from raw
pages matches every session.

## Still open (not covered by v1)

Historical publication/corrections (P1), dated class hours/eligibility (R1/R2),
action revision timelines, QQQ 2026-08-20 exercise reference (no closing-auction
print captured) and expiries after the October 2, 2026 fixed end. These remain
documented as unmodeled; v1 does not admit features, execution or a dataset build.
