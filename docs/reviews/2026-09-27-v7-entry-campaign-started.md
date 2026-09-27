# V7-3 entry capture is running — September 27, 2026

The user directed starting the work needed for training and avoiding repetition
of completed work/checks. Reconciled the existing September 25–27 artifacts:
full catalog/daily context, full entry-demand union, storage cleanup, lossless
packing, dated entry hours and finite reference blackouts remain completed.
They are not being rebuilt. V7-3 is option-data preparation; it is not a model
training run. Earlier wording blurred that distinction and caused confusion.

A full-universe entry capture controller now streams the existing 591 demand
stores, merges only touching/overlapping exact quote/trade intervals, subtracts
the immutable retained packed coverage, and writes the already validated v2
format. No synthetic observations, sampling of the population or proposal
regeneration is used. Completed 32-range batches survive restart unchanged.

The actual first four batches captured 128 ranges successfully. The background
service then reused all four and continued capturing additional real ranges.
This is ongoing production acquisition, not another model/component pilot.

Service: `healys-v7-capture-20260927.service`.
Launcher: `bash scripts/start_v7_capture_campaign.sh`.
State: `nn_meta/validation/v7-entry-campaign-20260927/progress.json`.
Immutable declaration: same root, `declaration/`.
Packs: `nn_meta/data_v7/entry-campaign-20260927/<security>/<batch-hash>/`.
Existing base index: `v7-execution-sample-index-20260927-r12`.

The launcher derives the repo root and sizes workers from available RAM, capped
at four. The service has 10 GiB MemoryHigh, 14 GiB MemoryMax, no swap allocation,
400% CPU quota and low scheduling priority. It preserves the 20 GiB disk reserve,
shared 250 GB acquisition ledger and 640 GB project cap. Initial dispatch is
bounded to 100 GB of new campaign data under a conservative 490 GB project
baseline allowance. That 100 GB is an allocation limit, not a new total storage
estimate or a claim to fit the complete campaign. Monitor real growth and
complete the downstream budget before it reaches that limit. It pauses rather
than silently dropping work or exceeding a guard. Failed sandbox transport
attempts remain retained/charged; new real captures succeeded with network access.

Only two targeted tests were added/run: exact subtraction of existing coverage,
and actual packed publication/resume without a second download or quota charge.
Both pass. The launcher passes Bash syntax validation. The existing v2 writer's
raw roundtrip verification is reused on every real pack. The previously passing
2,457-test suite was not rerun merely to reconfirm completed work.

Model fitting has not started. Next: connect the completed packed reader and
hours inputs to the existing assembly/fold/trial code; process remaining actual
held/exit/roll/reference inputs and funded physical outcomes using existing
implementations. Preserve the completed gates. Do not claim the entry download
alone establishes full V7-3 or training readiness. There is no automatic training
launch attached to this entry-only service yet.
