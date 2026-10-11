# Handoff — October 9, 2026 — V9 closed (no edge); next: model the user's own market view

## Next session (Monday 2026-10-12): the user's view of the market

The user asked to start Monday by talking through **their own view of the market** and
building **models that think like them**. Reasoning from the last session: models can only
find information that is in their inputs, and every input V9 used (public, free, daily) is
already priced. The user's 20 years of trading carry information the models never saw:
setups they trusted, what they noticed and read before others, edges they won on and
later lost.

Plan:
1. **Interview first, no code.** Ask the user to describe, in as much detail as they can:
   - the trades and situations where they actually won;
   - what they saw beforehand;
   - how they sized and exited;
   - how each edge decayed.
2. **Write the answers into a dated spec** (`docs/specs/`). Separate testable rules from
   judgment calls.
3. **Turn each testable rule into a pre-registered hypothesis**, with the same discipline as
   V8/V9: freeze before looking, run once, Holm across the family, measured costs, and no
   unscheduled pre-announcements.
4. **Only then model the judgment calls.** For example, rank or classify setups the way the
   user would, from features they say they watch, and test whether the user's own picks beat
   chance.

Tone: the user had a heavy evening after V9 (20 years at this) and says they will not give
up. Be honest and direct; no false hope, no lectures.

## What V9 found (all pre-registered, user-approved, run once; details in [EXPERIMENTS](docs/EXPERIMENTS.md))

| Test | Variants | Verdict | What it showed |
|---|---|---|---|
| OEE-2 ATM earnings | 8 | FAIL | Implied moves fair (\|move\|/implied 0.99/0.97/1.00 by IV run-up tercile); IV run-up idea unsupported; directional ATM −9% to −14%/trade |
| OEE-H4 OTM earnings | 13 | FAIL | Further and cheaper OTM had higher means (t ≤ 1.5), carried by a few shocks, several of them unscheduled pre-announcements |
| OEE-J FA + TA-pool agreement | 6 | FAIL | 16 TA families / 2,840 variants: direction 49.0%; FA 49.6% |
| OVE-3 options flow + dark pool | 9 | FAIL | Copying unusual buyers loses 10–19%; pre-earnings flow 47.9% direction; DIX near-miss (t 2.48, Holm 0.061) is market beta (−0.12% vs universe) |
| OTM payoff out of sample (user's thesis) | 1 | FAIL | First run voided: its top event, IBM 2026-07-14, was a pre-announcement. Scheduled releases only: +1.3%/leg, −7.4% at 1.5× costs |
| ALT-2 alternative data | 8 | FAIL | Analyst revisions, consensus beats, revenue surprise, insider: direction 46.8–49.7%; ATM options −16% to −21%/trade; attention does not pick big movers |

Totals: **45 pre-registered variants, none passing.** Two runs voided for defects:
- expiry-day exit pricing;
- unscheduled pre-announcements in the event table (73 of 1,621 events; this also inflated
  the earlier OTM numbers).

The live NFLX 20% OTM call quoted a spread of about 56% of mid, so real costs on cheap OTM
options exceed the backtest model. The one edge that has passed a holdout in this project is
still **V8 H1 earnings drift** (stock form).

Full narrative, "why no edge" analysis and alternative-data survey:
[docs/reviews/2026-10-08-v9-findings-and-alt-data.md](docs/reviews/2026-10-08-v9-findings-and-alt-data.md).
Decisions (25% daily premium cap; no OTM paper observation):
[DECISIONS](docs/DECISIONS.md). Artifact paths:
[CURRENT_STATE](docs/CURRENT_STATE.md#v9-plan-october-8).

## Running (observed 2026-10-09)

- **V8 H1 paper test**, "stonks bot 2" (PA3U9D8Q8GQX):
  - signals ran 08:46 CDT; trade 10:31 ET; reconcile 16:20 ET.
  - earnings season builds from about Oct 20.
  - check: `./venv/bin/python scripts/run_v8_h1_paper.py status`.
- **OI recorder**:
  - 2026-10-09 08:00 ET snapshot: 144,786 contracts, OI as of 10-07.
  - `journalctl --user -u healys-v9-oi-recorder`.
- **Alpha Vantage pull**:
  - 23/162 tickers; the 10-09 run was rate-limited (quota not yet reset).
  - Its log echoed the API key before this session's fix. Consider rotating the key.
  - No longer needed for a current test; stop with
    `systemctl --user disable --now healys-v9-alphavantage.timer` if the user agrees.
- **Not installed** (user decision): the OTM paper observation (`scripts/run_v9_otm_paper.py`).

Constraints:
- Memory caps on big jobs.
- Stage only your own hunks. Other dirty V6/V7 work in the tree is not yours; this session
  appended its DECISIONS/EXPERIMENTS entries via the index.
- The 2026 window has been used for V8 H1 stock and for the OTM out-of-sample test.

[Previous handoff](handoff-history/HANDOFF-2026-10-08-alt2.md).
