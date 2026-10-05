# ETFE causal input and phase-B component pilot

Use only selected fresh normalized Alpaca inputs. This finite component milestone
builds the underlying session grid and fifteen shared technical diagnostic fields
over the collected calendar, then exercises every catalog variant on January
18–19 with a calculation prefix from the January 2 collection origin. This origin
is engineering padding, not an admitted research start or granted model warmup.
It does not close ETFE-2 or the integrated ETFE-4.pilot.

## Prices, clocks and missingness

Verify normalization plans, seals, independent reconciliation receipts, partition
hashes and Parquet before use. Build expected regular-session 1/5/15-minute bins
from the fresh Alpaca stock calendar, anchored at actual open, with early closes.
Keep missing/invalid bins as explicit null grid rows. Never compress the clock,
fill prices/volume or aggregate a partial minute set into a valid bar. Closed
stock bars are modeled available at bar end; actual historical publication timing
remains an admission dependency. Source/capture time remains separate.

Compute the first fifteen shared technical definitions in the feature registry,
using default MA 10/30 for shared diagnostics. Variant-specific MA projections
remain later row assembly. Output `raw__` values and missing masks: **raw,
unadjusted diagnostics**, not the final 221-field/442-input model schema. Dated
action reconstruction is unresolved; do not silently present raw features as
action-adjusted ones. Recursive RSI/MACD become missing after an input gap;
rolling features require complete windows. Do not reset state at partitions.

ORB uses all fifteen completed opening minutes. Underlying session VWAP uses
causal completed-minute HLC3 and volume, separate from option execution VWAP.
No ORB readiness before 09:45; a missing opening minute leaves it unavailable.
No same-session VWAP can bridge an unresolved minute gap.

## Signals and option demand

Use mathematical signal kernels and their declared source defaults, with new
ETFE adapters and catalog identities. Do not load old runtime selectors, market
data, reference tables, features or models. The pinned Setup math module from
the registry may be called as a pure function with ETFE-built minute context;
its source is bound just like other mathematical kernels. All twenty families,
all 25,353 ticker/variant combinations, 1/5/15 minutes and native directions
must appear in the census, even when a variant emits zero events. No winner
selection, generic burn-in or event cap. Warmup/event rules remain native.

Pilot observations are January 18–19; prefix calculations begin January 2 and
may not restart at the pilot window. Keep four signal channels for checks;
phase-B download demands use long/short entries and targets 0/1/5. Conditional
weekly 2/4 remain explicitly withheld pending dated listing evidence. Underlying
signals on raw prices remain unadmitted diagnostics. This is not an eligible
trade book, execution engine or economic evaluation.

Only strictly earlier-date price observations can establish an acquisition
candidate's prior existence. Use 0–5 actual DTE, expiry-distance/earlier-expiry,
nearest strike/lower strike/symbol ties, and the declared 85–115% spot band.
The acquisition candidate is distinct from a historically eligible selected
contract. Unknown historical discovery, source provenance or dated terms must
withhold selection. Dated terms must be effective and known by decision, bind
strike/multiplier/expiry close and have an evidence hash. Ambiguity fails closed;
unknown terms cannot be bypassed by choosing another contract. Actual entries
still need qualifying signals, prices, cash and the expiry cutoff.

Map each entry event to the exact option feature window
`[t-(m+1) minutes,t-1 minute)` and potential entry-reference minute `[t-1m,t)`.
Record windows outside stock RTH separately; stock hours do not prove option
class hours. Deduplicate physical download intervals by contract/route while
retaining every logical variant/direction/target link. Missing capture and
unresolved eligibility are not losing/unfilled trades. Phase-C holding/roll/
stock-quote demand remains outside this component; no network capture is run.

## Evidence and resource limits

Nine serial ticker/timeframe scopes; no worker pool. At most 32 signal columns
and 128 MiB temporary signal budget; write logical rows in batches of 5,000.
One study root capped at 4 GiB, 30 minutes per run, normal ETFE disk/RAM reserves.
Source-bound immutable plan/partition receipts support verified scope restart;
orphan files are not committed. No dataset/model freeze or model training.

Require unit tests for early close, gaps, future perturbation, ORB/VWAP timing,
dated eligibility, 0DTE, ambiguity and interval unions. Check all twenty families
on synthetic prefixes at every timeframe; compare every real pilot variant's
four channels with a shorter input prefix. Record full per-variant census and
reason counts. Perform real scope stop/resume, preserve completed hashes, and
audit logical-to-physical demand plus output hashes before milestone closure.
