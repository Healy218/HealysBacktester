# ETFE dated-input policy v1 — October 6, 2026

**Status:** user-selected policy, applied and independently audited. It replaces
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

## Still open (not covered by v1)

Official exercise reference price, SIP quote size representation, historical
publication/corrections (P1), dated class hours/eligibility (R1/R2) and action
revision timelines. These remain ETFE-0 items; v1 does not admit features,
execution or a dataset build.
