# V7 causal feature and proposal build

The previous causal proposal adapter recalculated action-epoch indicators for
each parameter batch. `nn_meta/v7/proposal_store.py` now computes each epoch once,
stores its causal technical/TradingView observations and normalized moving
averages, and packs the four signal channels into bits. The simulator reads only
a bounded number of variant columns across all epochs, keeping continuous stop
state without materializing the whole boolean parameter matrix in memory.

The stores retain raw minute prices separately from the continuous price basis
used for underlying strategy stops. Raw prices remain mandatory for option
selection and execution. Stored features preserve their original observation
times and contemporaneous units; a later action cannot overwrite an earlier
epoch. The full catalog includes variants with no signals or no closed trades.

Each epoch and proposal batch has an immutable completion receipt. A restart
checks parent inputs, code, runtime, catalog and all completed contents, skips
completed indicator/simulation work, and preserves failed partial directories.
Disk reserve checks retain the 100 GiB floor. Bit packing is lossless, including
epochs whose lengths are not multiples of eight. Signal reads enforce the same
explicit working-memory allowance as the original adapter.

`scripts/build_v7_proposals.py` connects the stores to captured raw Alpaca minute
data, the full dated security-history panel and compiled reviewed actions. It
routes each date to the selected stock ticker, verifies minute counts, rejects
unresolved identity spans and unresolved captured actions, and runs all 2,817
variants on each of 1/5/15/30 minutes with up to four single-threaded workers.
The default dates are the full active window. Date arguments also support bounded
integration verification. Entry and exit stock tickers follow dated routing;
the security identity and strategy stop state continue across reviewed renames.

This is the feature/proposal construction stage, not a 222-column labeled training
dataset or a full-universe admission. It does not yet join daily/sector/tick row
components, filter proposal entries by PIT membership, construct option demand,
or replay option/physical outcomes. Those consumers must be integrated before
training. Source completeness is not inferred merely because captured action
records have all been consumed.

## Validation

Tests compare all 20 strategy families against direct causal-epoch signals and
the original proposal simulator, verify parameter-specific averages, exercise
dated rename routing, reject changed inputs and corrupted signals, and enforce
memory/disk limits. An injected failure in the second action epoch confirms that
the first completed epoch is preserved and reused on restart. Completed proposal
batches are also reused without invoking the simulator again.

The initial real-data run computed all four full catalogs but failed while
opening the saved store: JSON converted package-version tuples to lists. The
reader now compares canonical runtime identities instead of Python container
types. That failed output is preserved at
`nn_meta/validation/v7-proposal-build-20260916`; it is not complete proposal
evidence. The corrected run uses `v7-proposal-build-20260916r2`. Final measured
results and test counts are recorded in the current handoff.

No new market-data capture or V6 runtime change is part of this work.

Corrected real AAPL run (March15–May10,2022): 11,268 variants, 757,465 proposals;
1m/5m/15m/30m counts 598,944/108,354/34,156/16,011. Slowest worker 114.92s,
peak RSS 896,120 KiB. Resume took 2.95–3.34s per worker and preserved all 736
completion receipts. Total output 887,697,704 bytes; compact proposal storage
is required before full-universe scaling. Full suite: 1,918 tests +18 subtests,
18 warnings,107.65s. Evidence `v7-proposal-build-verification-20260916`.

The user's subsequent option-premium stop amendment supersedes the generic stock
stop used in this component verification. Preserve its numerical results as
historical plumbing evidence; rebuild proposals/labels under the amended rules.
