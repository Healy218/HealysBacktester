# V5/V6 nightly incubator activation — September 25, 2026

## User-directed scope

Run the existing frozen V5 and V6 bundles on each newly captured market day's
candidate features and save dated predictions. The incubator does not retrain
weights, submit orders or change live scanner decisions. Add V7 only after its
build/readiness gate. This supersedes the earlier V7-dependent V5/V6 timer
activation plan.

## Input and execution evidence

September 24 V5 scanner capture on Hetzner sealed 26 fifteen-minute passes,
8,190 candidate rows, and 26 matching Parquet hashes. The new staging job
copied that day to home, verified the model-config binding and each pass seal,
then checked the exact 09:30–15:45 New York bar set against the deployed
exchange calendar. Eight V6 candidate passes contained 5,085 rows. Both
daily feature matrices were sealed by the existing generation-specific code.

The dated direct pilot and the installed systemd service each loaded both
bundles and produced 8,190 V5 and 5,085 V6 predictions, with two completed
receipts, zero failed receipts, zero blocked inputs and
`prediction_refresh_complete=true`. The installed service result was success.
The result is at `incubator/runs/after-close/close-20260924/`; the earlier
direct pilot is at `close-20260924-pilot/`. The feature matrices are at
`incubator/artifacts/daily/v5-20260924/` and `v6-20260924/`.

The replay service has `PrivateNetwork=yes`, `ProtectSystem=strict`, bounded
write paths, `NoNewPrivileges=yes`, 200% CPU and 5 GiB memory limits. A
transient user service proved `PrivateNetwork=yes` works on this host before
the full installed replay passed. The separate V5 staging service has network
access only to copy the server captures; a failed stage blocks replay.

## Schedule and follow-up

`healys-ai-incubator-after-close.timer` is enabled. Its next listed trigger
is Friday, September 25 at 15:30 Chicago / 16:30 New York. The service
selects the last fully closed session from the V6 data-index calendar, so a
late or persistent catch-up does not select an unfinished new day. The
`AI_INCUBATOR_AS_OF` override was used for the September 24 service test and
removed before timer activation. Confirm the September 25 scheduled receipt,
both prediction counts, input completeness and V7 coexistence.

The pending-outcome predictions are **not** measured returns or accuracy.
Exact V5 outcomes and most V6 candidate outcomes remain unjoined. This
activation did not change the V5 server alert path, V6 simulator/broker
bridge, or V7-2 workers.

To stop future runs if an input or resource issue is found:
`systemctl --user disable --now healys-ai-incubator-after-close.timer`.
The dated input, result and receipt files remain available for inspection.
