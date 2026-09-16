# V7 lifecycle and expiry checkpoint — September 16, 2026

V7 remains **not ready to train**. The persistent task is to continue until
all gates pass, then alert the user. No training, deployment or notification
was performed at this checkpoint.

## Evidence and access

The 122 unresolved zero-session rows now have a receipt-backed retrospective
review: 60 OTC successor sessions, 41 cash-merger sessions, 14 WBD successor
sessions, six halt sessions, and one unexplained VERU session (2022-11-09).
The review binds ticker **and security identity**, rejects overlapping
explanations, and never promotes an explanation into causal availability or
a resolved held position. Facts and primary-source URLs are in
`docs/specs/V7_LIFECYCLE_REVIEW_20260916.json`; generated output is
`nn_meta/validation/v7-lifecycle-review-20260916`.

The existing Massive reference capture was extended with 55 lifecycle boundary
requests and 74 exact successor-session requests. Dated reference activity
alone is insufficient: some merger dates still report the original ticker as
active. DISCA-to-WBD crosses FIGIs and needs an explicit corporate bridge.
REV stock changes to REVRQ on October 21, while its option root changes on
October 24; these clocks must remain distinct. VMW option deliverables are
$14,250 cash per standard contract under OCC 53611, despite the elective
stock/cash merger alternatives.

Alpaca historical stock acquisition now accepts an explicit `otc` feed, bound
in the task receipt; legacy tasks retain SIP. The bounded raw/all probes for
BBBYQ and FRCB returned **HTTP 403** outside the network sandbox. No successor
stock data was captured and no subscription changed. A user question is pending
about checking existing Massive access for these specific gaps; Alpaca-only
remains authoritative until answered. Probes and status are retained under
`nn_meta/data_v7/otc-probe-20260916`.

The bounded public-document capture retains immutable receipts and charges
new partial bytes against the shared quota. Novavax's issuer halt release was
captured. Direct OCC requests returned 403; Biogen's PDF timed out; SEC returned
403. The OCC facts were read through the web tool and recorded as structured
review, **not** represented as archived raw PDFs or exact publication clocks.
Current quota is 62,530,264,652 / 250,000,000,000 bytes; no reservations remain.

## Engine changes and limits

`PhysicalLedger.expire` handles receipt-bound mandatory cash merger deliverables
through a separate cash-exercise path. Calls and puts receive only their
positive contractual cash difference. There is no stock delivery, synthetic
market fill or strike-capital injection. The slot and receivable remain open
until settlement. Unknown/late terms and mismatched security identities fail.

An earlier-day official expiry price now requires an exact OCC override matching
the contract, security, expiry date, reference timestamp and price, available
before exercise. Ordinary stale prices remain rejected. This supports the
CLSK November 8 rule (OCC 55513 uses November 7's $13.57) once the real captured
adapter is complete. Current tests are synthetic; the review does not claim
these positions were replayed using complete historical execution evidence.

## Verification and remaining work

Full suite: **1,754 tests +18 subtests passed**, 18 warnings, 81.98 seconds;
`/tmp/v7-lifecycle-20260916-tests.log`. Includes the preserved unrelated V6
working-tree changes. Scoped diff whitespace checks passed.

`nn_meta/validation/v7-readiness-20260916-lifecycle.json` still fails eight
stages: lifecycle, causal prices, daily context, quotes, physical execution,
assembly, trials and integrated pilots. Active input, membership and coverage
inventory checks still pass. Do not attach this retrospective review as a
full-universe stage receipt.

Next work includes verified successor prices/identity bridges; VERU halt evidence;
real lifecycle/expiry adapters and settlement/stock captures; complete causal
action processing; all-security daily context; actual proposal/feature/roll
quote intervals; full-history factorized assembly and runnable declared model
trials; measured four-worker pilots while preserving V6 and the 250 GB cap.
