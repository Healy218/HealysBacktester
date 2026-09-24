# V6 held-option quote-gap repair — September 24, 2026

## Incident and decision

The active V6 forward producer failed many quarter-hour passes at
`monitor_exits` because at least one held option had no quote in the last 30
seconds. The separate minute-risk worker kept checking the same positions.
The user authorized using a validated observation from that worker within the
same five-minute entry window; an unobserved position still blocks new entries.
No broker order or filled option trade is implied.

Read-only Massive quote queries over a live 60-minute window found 157 valid
quotes for CELH261030P00028000, 230 for KTOS261030P00047000 and 475 for
TTWO261030P00205000. Their longest between-quote gaps were about 274, 344
and 287 seconds. An arbitrary 30-second polling instant can therefore miss a
real quote. At 19:30 UTC the minute-risk worker validated TTWO while the
forward scanner later missed TTWO; the scanner obtained CELH and KTOS quotes.
This was complementary independent evidence, not a stale price substitution.

## Repair boundary

The isolated V6 runtime branch `ops/v6-quote-evidence-20260924`, commit
`e6991f2`, adds the observed contract, leg count, opening time, SIP timestamp,
receipt time and assessment time to successful `holding` risk results. The
forward scanner may accept such a result for a held leg only when its own
quote request reports exactly `no fresh post-decision option quote`, the
result is from the same leg, the SIP quote is after the signal-bar close,
the observation passed the original 30-second quote-age rule, and the
assessment is at most 60 seconds old and within the five-minute entry
window. A failed minute-risk pass can still contain a valid result for a
different leg; only that exact leg's result is eligible. Missing, malformed,
old, pre-close or mismatched evidence retains the existing fail-closed path.
No execution price, stop threshold, candidate score, entry sizing or broker
policy changes.

The user-systemd minute-risk timer keeps its original every-minute check and
adds checks at :20 and :30 seconds of each quarter hour, immediately before
the slower producer reaches monitoring. These checks use the existing
activated numerical runtime and quote-age rule.

## Validation and deployment

The isolated candidate passed 1,612 tests plus 18 subtests; the new regression
rejects wrong-contract, pre-close, failed-same-leg and old evidence while
accepting a valid observation even if another leg failed. The activation
amendment verified all prior runtime hashes, allowing exactly the two reviewed
source changes, and verified the prior evidence hashes. The candidate source,
review receipt and complete test XML are at
`nn_meta/validation/v6-quote-evidence-20260924/`.

The live V6 checkout was stopped between scheduled passes, the prior
activation and SQLite ledger were backed up under
`nn_meta/live/v6_server/installations/quote-evidence-20260924/`, and the
repair was fetched and checked out through Git. The new activation reports
commit `e6991f2`, passes all installed runtime hashes, and was installed
atomically. The live ledger hash was identical before and after deployment:
`415435c2bc14f56b3f1ea216ac2bffaac252a47fb88670ead77d7227f767a0a2`.
Both paper timers were resumed. The first real post-deployment forward pass at
19:45 UTC completed with `status=recorded`, 20 closed and four open positions,
and two new paper openings. This establishes that the repaired path can record
a full in-hours pass. The 20:00 UTC pass still failed closed on four held
contracts (AAOI, CELH, CLF and TTWO) when it found no fresh post-decision
quotes at the market-close boundary. The latest-pass warning therefore remains
possible after the close; the V6 quote-gap incident is not fully resolved.
