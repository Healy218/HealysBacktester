# V7 proposal-to-dataset assembly, September 17

The missing production consumer now connects compact proposals, selected-contract
entry demand, captured option ticks, stored causal feature rows, option replay
and bounded factorized shards. This is implementation progress toward the full
build; it is not full-history training readiness or a completed production run.

## Executable path

`./venv/bin/python scripts/build_v7_dataset.py --manifest WORKER.json --output
nn_meta/validation/CAMPAIGN --workers 4` runs all four timeframes for each supplied
security. The CLI uses the registered full parameter catalog and checks that its
proposal parent binds the current OPTION_RISK active manifest. It does not fetch
providers, alter V6, or train models. Worker/thread/disk controls remain four
outer processes, one inner thread and a 100 GiB disk reserve.

A `v7-dataset-worker-v1` JSON manifest supplies these paths:

- `proposal_root`: one security's 1/5/15/30 directories.
- `demand`: its completed proposal-based entry demand.
- `daily`: a sealed directory containing `daily.parquet` from the causal daily
  context contract and `inputs.json`; every source session is explicit.
- `sectors`: the frozen dated sector store.
- `calendar`: the captured extended Alpaca calendar, agreeing with every original
  stock session and providing next-session availability beyond the study end.
- `sessions`: a sealed `sessions.json` with schema
  `v7-dated-option-sessions-v1`, explicit root/date opens/closes and `rule_id`.
  Its `rules` name `start`, `end`, `symbols`, `description` and retained
  path-to-SHA256 `sources`. Unknown class/date hours remain missing; the reader
  does not establish historical validity just because source bytes are hashed.
- `quotes`: one archive path or a list of bounded capture-export paths. All
  archives share one bounded payload cache; overlapping or duplicate captures
  are rejected. Windows can span adjacent captures in different exports.
- `references`: dated standard-contract receipts.
- `stock_quotes`: explicit Alpaca capture directories for expiry classification.
- `tick_policy`: the frozen SIP/condition policy JSON and its retained references.

Each proposal yields five deterministic target identities, including selections
without a contract. Missing tick capture retains an outcome record without a
fabricated feature vector. Available features retain all 222 columns and their
daily/sector/action/tick lineage. Missing execution or censored paths retain
null targets. Filled paths use the existing 12.5% arithmetic midpoint option
stop, strategy exits, rolls and ITM expiry behavior. The initial replay contract
must equal the contract used for features. Alpaca expiry classification uses the
arithmetic midpoint of the same validated two-sided quote, retaining its original
SIP timestamp and security identity; the physical stock ledger's conservative
bid mark is unchanged.

Chunks are transactional and resumable. Each has a full outcome census,
compressed path and feature lineage, plus numerical shards when features exist.
Long paths stream directly to disk instead of accumulating across the entire
chunk. Completed chunks and summaries are verified before reuse. An immutable
`index/shards.json` feeds `scripts/prepare_v7_training_fold.py` directly. This
index does not grant training admission.

## Verification and remaining integration

The new regression uses actual compact-store, selection, tick/archive,
standard-reference, feature-join, replay and factorized-reader code against
explicit fictional test captures. Every numerical row is compared with direct
row construction, all five target identities are reconciled, and midpoint-stop
labels, missing trade captures, partial resume, complete resume, mutation
rejection, underlying-midpoint identity, adjacent multi-archive reads and
unknown future session hours after an already-completed exit are exercised. These tests are
software integration evidence, not real-market execution or coverage evidence.

Production causal daily/market context and dated option-session bundles are not
yet available for the full campaign. Actual proposal-driven entry/exit/mark/roll
capture is still incomplete. Funded physical outcomes and settlement horizons
must be integrated before admitting full labels; the current option replay
explicitly leaves failed expiry liquidation unresolved. Shared portfolio,
full-universe assembly/resource verification and final readiness gates remain
open. No full-history dataset or training job was launched by this change.

Final full suite: **1,976 passed and 18 subtests**, 18 warnings, 122.33 seconds.
Log: `/tmp/v7-assembly-final-tests.log`. Six new integration tests passed.
This implementation is uncommitted and paused for user review as of September17;
no further build or acquisition is authorized until the user resumes the work.
