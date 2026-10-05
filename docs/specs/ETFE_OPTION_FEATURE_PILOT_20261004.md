# ETFE option trade/bar feature component study

Implement the ten registered option trade/bar formulas from ETFE_FEATURES and
ETFE_FEATURE_MAP without editing those frozen declarations or prior artifacts.
Use only the audited fresh January component inputs. Materialize diagnostics
for every unique `(candidate symbol, signal close, timeframe)` and retain links
for all 458,133 original logical events. Missing candidates stay explicit; never
reselect a contract based on the feature window. Purchase scope stays 0–5 DTE.

Outputs are `diagnostic__<registered name>` float64, uint8 missing masks and one
reason per field. They are not the final 221-field model schema. Every output
retains `model_feature_admitted=false`: dated selection, option sessions,
condition applicability, final-vintage/publication provenance and historical
coverage are still unresolved. No execution price, label, training or network
capture is produced by this component.

At decision t and timeframe m use exactly [t-(m+1) minutes,t-1 minute). Default
research availability is trade event +1s or bar end +1s. An explicit later
availability delays the observation; it can never advance the default. Capture
receipt time is separate from publication time. Late required observations mask
the affected feature family, rather than silently changing a window statistic.
Outside-stock-RTH pilot windows remain wholly missing with an option-hours
reason; stock RTH is a diagnostic scope restriction, not proven option hours.

Condition allowlist H/I/J/S and lowercase a–s is the registered research policy.
Retain excluded-condition counts/volume. Eligible invalid prices/sizes/quality
or unresolved repeated native IDs mask the trade family. Preserve no-ID
occurrences; do not deduplicate identical prints. Repeated occurrence IDs are a
consumer error. Duplicate bar vintages or invalid bars mask the bar family.

Terminal transport and an observed minute permit a final-vintage diagnostic,
not completeness admission. Any unobserved required minute leaves its respective
trade/bar family missing unless explicit no-trade evidence covers that minute
and was available by decision. Synthetic fixtures exercise verified-empty
semantics: count, volume and bar rates zero; undefined ratios/age missing. The
real pilot has no such no-trade evidence. Missing bars never become fills.

Use population trade-size standard deviation. Trade VWAP divides by eligible
trade size, never provider bar volume. Tick signs restart in each feature window:
first/leading-equal prints are unclassified, subsequent equals carry the preceding
nonzero sign. Without a verified total order, any equal-time eligible prints
mask signed/classified fields. VWAP-versus-last remains missing when final-time
prices disagree; order-independent fields need not be discarded. Never sort
by price or borrow a previous window's trade. Finite order-independent results
must agree under reversed input order within rtol=1e-12, atol=1e-12.

Nine serial scopes, at most 1 GiB root and 30 minutes per run, existing ETFE
RAM/disk reserves. Hash-bound plan, source snapshots, package versions and input
receipts; immutable per-scope output receipts. Actual stop after one scope and
verified resume; changes require a successor root. Require hand-worked formulas,
condition/gap/availability/empty/order tests at 1/5/15 minutes, real-window order
and future-perturbation checks, independent numerical/membership reconciliation,
and measured resources. This closes ETFE-2.option-trade-bar-components only;
full features, dated admission and integrated ETFE-4.pilot remain open.
