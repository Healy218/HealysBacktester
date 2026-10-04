# ETFE Alpaca pull diagnosis — October 3, 2026

The sampled historical trade/bar requests work. The remaining source-contract
issues concern historical metadata, dated rules and provenance, rather than a
general authentication or connectivity failure. ETFE-0 remains open.

## Captured controls

Two fresh bounded runs completed at 22:54:01 and 23:27:52 Central October 3
(October 4 03:54:01/04:27:52 UTC): **40 live GETs**, 37 HTTP 200 and three
intentional negative controls returning 400; zero transport failures, 401s,
403s or 429s. An earlier sandbox transport failure is retained separately as
r0 and does not count as a live response. No orders or provider messages sent.

[Portable receipt](2026-10-03-etfe-alpaca-pulls.json) binds raw response bodies,
requests, reports and exact diagnostic source versions in the
[evidence ZIP](2026-10-03-etfe-alpaca-pulls-evidence.zip). Local run roots:
`nn_meta/validation/etfe-alpaca-pulls-20261003-r1/` and `-r2/`.
The original [contract declarations](2026-10-03-etfe-contract.md) and setup
remain unchanged. This review narrows their open questions, not their hashes.

## What the API actually returned

| Control | Observation | Consequence |
| --- | --- | --- |
| Jan 18, 2024 opening minute, three known contracts | SPY: nine trades, 123 contracts; QQQ: one trade, ten contracts; VOO: two trades, two contracts | All three have historical trade and bar data before the documented February month boundary |
| Independently aggregate those 12 trades | OHLC, volume and count match all three bars exactly; maximum VWAP difference 0.00000003253, consistent with returned rounding | The sampled trade/bar prices reconcile; this is neither full-history quality nor executable-fill proof |
| Page limit 2 versus 10,000 | Six terminally completed pages recover exactly the same 12 ordered trade occurrences | Follow every token across symbols; do not deduplicate identical no-ID occurrences |
| Explicit historical-trade `feed=opra`, `indicative`, invalid control | All three return 400: `unexpected query parameter(s): feed` | Omit `feed` on historical option trades; this is not an entitlement failure or an accepted feed selector |
| Equal start/end at first SPY nanosecond timestamp | Exactly that trade is returned | Inclusive endpoints work in this control; adjacent capture windows must avoid boundary duplication |
| December 15, 2023 expired call catalogue | Terminal empty responses for all three ETFs | An empty catalogue query is not proof of no price data globally |
| Broader expiry window through January 17, 2024 | SPY January 3 and QQQ January 4 contracts returned, with continuation tokens; VOO terminal empty | Catalogue records can predate the observed trade-history floor; these SPY/QQQ pages are samples, not complete inventories |
| February/March 2024 samples | All 18 returned records have multiplier 0, size 100, and 100-share deliverables | Zero is a historical metadata anomaly for admission; do not multiply premiums by zero or silently replace the raw field |
| June 2024, January 2025 and October 2026 samples | All 27 returned records have multiplier 100, size 100, and 100-share deliverables | This is not a universal API field failure; exact transition/cause is unverified |
| Three June 2024 expiries queried before Jan 18, 2024 14:30 UTC | Six terminal empty trade/bar responses, querying since 1970 | More scoped evidence for the observed floor, still not provider-global proof |

The first r1 “small” request used limit 50 and fit on one page. It did **not**
test token traversal; r2's limit-2 control supplies that evidence. One sampled
VOO June contract carries `close_price_date=2022-08-30`, yet its pre-floor
trade/bar requests were empty. A reference close date is not a retrievable
market-data-history guarantee.

The [historical-trades reference](https://docs.alpaca.markets/us/reference/optiontrades)
documents symbol-first ordering, a total page limit rather than a per-symbol
limit, and inclusive endpoints. Preserve response bytes and timestamps at
nanosecond precision. Terminal emptiness means no rows returned for that exact
query; absent data and demonstrated no-trading remain distinct classifications.

## Two apparent inconsistencies explained by dated sources

QQQ's January $409.78 strike is consistent with a genuine adjustment, not an
API decimal-format error. [OCC memo 53848](https://infomemo.theocc.com/infomemos?number=53848),
dated December 26, 2023 and effective December 27, specifies subtracting the
$0.21584 special dividend from strikes and rounding to cents. For QQQ it retains
100-share delivery and premium multiplier 100. OCC's separately named “Contract
Multiplier” is 1; do not conflate it with premium scaling or Alpaca's zero field.
The separately described 4QQQ cash-settled product is outside ETFE's QQQ symbol.

The VOO closing-time discrepancy has a dated explanation:
[Nasdaq alert 2026-10](https://www.nasdaqtrader.com/MicroNews.aspx?id=OTA+2026-10)
changes VOO from 16:00 to 16:15 ET on all Nasdaq options exchanges effective
February 25, 2026. A timeless current list cannot represent the full research
window. This resolves the named Nasdaq-list ambiguity; complete exchange,
expiration and early-close coverage still requires the R2 dated schedule.

## Remaining source questions and next implementation rules

- **H1:** Observed Jan 18 history conflicts with the provider's coarse
  [February 2024 availability description](https://docs.alpaca.markets/us/docs/historical-option-data).
  Ask for the precise retained start and scope of the pre-February records.
  Symbol-specific samples cannot certify a provider-global earliest event.
- **R1:** Obtain dated contract eligibility/adjustments and interpret the old
  zero multiplier with provider confirmation plus authoritative contract terms.
  Preserve raw metadata; make normalized premium scale separately sourced.
  Current inactive status, open interest, close price and T+1 labels cannot be
  used as historical as-of observations without their own availability evidence.
- **R2:** Incorporate the dated VOO transition into an evidenced class/session
  schedule, including expiration and early-close exceptions. Do not substitute
  stock-calendar closes for option-class closes.
- **P1:** Feed selection is now diagnosed: the historical trade route rejects
  the parameter. [Alpaca staff confirms OPRA bars](https://forum.alpaca.markets/t/data-source-for-option-historical-bars/17704).
  The matched trades support an OPRA-consistent sample, but do not prove the
  provenance of every historical trade. Obtain explicit route-level confirmation
  rather than treating latest-feed defaults as historical-feed policy.

These are concrete provider questions suitable for a support request; none has
been sent. Preserve the fixed end and all three ETFs/strategy families. Historical
quotes remain unsupported; do not retry them. The next gate remains source
resolution and an immutable contract successor, then ROADMAP's bounded integrated
pilot. These diagnostics are not that pilot, a data freeze or model evaluation.

## Verification

Six offline tests exercise empty/short token-bearing pages, repeated-token and
page-cap failures, HTTP errors, duplicate occurrences, and volume-only/excluded
trade conditions. All passed. Existing portable contract verification still
passes with readiness false. No broad regression suite or training repeated.
