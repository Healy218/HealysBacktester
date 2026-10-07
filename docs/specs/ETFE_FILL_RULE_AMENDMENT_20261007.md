# ETFE fill-rule amendment — October 7, 2026

User-selected after a leakage review. Supersedes the execution contract's entry
and exit references ("newest completed one-minute option bar", usable from end
+ 1 s) for all labels from `etfe-labels-v2-20261007-r0` on.

## Why

The trained GBT (win AUC ≈ 0.70) ranked rows by how far the **signal minute's**
option close sat above that minute's VWAP. The top score decile averaged a close
4.9% above the VWAP it "bought" at, so mean isolated R was +5.9%. A fill at the
average price of a minute that has already ended is not executable. On SPY-1,
correlation(signal-bar close/VWAP, label R) was +0.251. The same bias applied to
exits and stops (selling at the prior minute's average after the move).

## Rule (`label_kernel` `fill_rule='next_bar_vwap'`, default)

Every fill uses the VWAP of a one-minute option bar that **starts at or after the
decision**, so all its trades follow the decision:

- Entry: the signal closes at t; fill in the bar [t, t+60 s). If it is missing
  or invalid, the row is `observed_unfilled` (`next_bar_missing`).
- Exits, stops, expiry sales: from the first bar starting at or after the
  decision clock (a stop detected when bar B becomes known therefore skips the
  bar already in progress), bar by bar under the participation cap, while the
  bar starts before the option close.
- Rolls: begun at minute M, fill in [M, M+60 s).

Sizing, costs, participation, settlement, exercise, censoring and stresses are
unchanged. `fill_rule='signal_bar_vwap'` remains only for parity with the
synthetic reference `Scheduler`.

## Effect

Labels v2: 2,627,937 settled. On SPY-1 the correlation falls to −0.017, and mean
settled R moves from +0.66% to −7.63%. Funding-unresolved rises to 46,907 (exits
signaled at an expiry-day close have no later bar, so the position is exercised).
Labels r0–r2, label stress r0–r1, dataset v1, experiment v2 and training v2 are
superseded for edge assessment; they remain valid records of the earlier rule.
