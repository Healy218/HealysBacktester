# V5 candidate capture deployment — 2026-09-24

The Hetzner V5 paper scanner remains on its server-compatible branch
`ops/server-alert-readiness-20260906`. Main and that branch are materially
divergent, so this deployment did not merge or switch to `main`, or touch the
server's unrelated tracked deletions of retired V3/V4 model files. The three
server-local commits were fetched and preserved. A narrow V5 capture backport
was committed as `059ff1d`, pushed to the same production branch, and deployed
by `git pull --ff-only origin ops/server-alert-readiness-20260906`; the server
fast-forwarded from `c79e877` to `059ff1d`.

The backport adds `incubator.v5_features`, an opt-in V5 scanner capture flag,
and a specific `configure_cron.py --enable-v5-incubator-capture` mode. The
scanner seals scored candidate rows by signal bar, with generation, exact
identity, model-config hash and parquet hash. Capture failure increments the
scanner error count but does not suppress paper alerts. Captured files under
`incubator/artifacts/v5-passes/` are ignored by Git. The active model-config
SHA-256 on home, in the backport, and on server is
`b4631653459490045a92e6305922b40440780f3fd6a8b93edcee462601044182`.

Verification: 19 targeted scanner/capture/cron tests passed. The full
server-branch suite has 59 failures in older alert/accounting tests both at
the untouched server commit (682 passed) and after the backport (685 passed);
the failure list is identical, so this deployment introduced no observed
suite regression. The server V5 40-member model self-test passed. The server
has `pyarrow` available and roughly 9 GB free disk at deployment.

The crontab preview changed only the active V5 scan line, adding
`--incubator-capture-root` pointed at
`/home/mrhea/HealysBacktester/incubator/artifacts/v5-passes`.
`configure_cron.py --enable-v5-incubator-capture --run` installed it and
saved the prior crontab at
`/home/mrhea/HealysBacktester/logs/ops/ops-fixes-20260924T111725Z/crontab-before.txt`.
A post-install check found server HEAD `059ff1d`, the flag on exactly the V5
scan line, and the rollback file present. No real V5 candidate pass can be
claimed until a market-hours scan actually emits one; the incubator after-close
timer remains disabled and has no execution opt-in.

Next: inspect the first sealed server pass and the V5 cron log for capture
errors, verify manifest/config/parquet hashes and candidate identities, then
stage that paper data on the home box only under the separately approved
paper-data boundary. Do not infer candidate features from the trade ledger or
the V6 compatibility matrix.
