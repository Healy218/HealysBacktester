# V6 worker capacity — September 29, 2026

The user requested more V6 workers. The installed service now invokes the
operational resume wrapper with `--autosize-workers`. The shared autosizer budgets
4500 MiB per data worker, reserves 8192 MiB of available host memory, and caps
concurrency at four. Current sizing returned three; the next invocation decides
from then-available RAM. Training retains two threads. CPU quota is 400%,
MemoryHigh/Max 19/20 GiB, no swap. Market-window conditions and timer are unchanged.

Before the change, the two-worker service had a 6.05-GiB cgroup memory peak;
the host reported approximately 24 GiB available and 16 logical CPUs. This supports
a bounded increase, not a measured four-worker throughput or peak-memory claim.
If V7 resumes concurrently, review combined budgets and measured pressure.

The frozen launcher and all 74 contract-bound sources are unchanged. Only the
operational resume wrapper and service allocation changed. The wrapper passes
worker/thread overrides through the frozen launcher's existing final arguments;
no artifact hash was rewritten. The unfinished September 28 date, snapshot,
93 completed symbol receipts and partial seals remain selected in r3.

Validation: 15 focused continual/recovery/calendar tests passed. Direct checks
verified autosizer bounds, final CLI arguments, pinned date/snapshot and all
74 source hashes. Systemd unit verification and installed-property readback passed.

At approximately 08:05 Central, the prior two-worker invocation was still draining
queued deadline failures after its 08:00 cutoff, with 93/449 symbols complete.
Those timeouts are distinct from the previously repaired identity/provider errors.
Training has not started. No market-hours restart was requested. The new worker
count takes effect at the next permitted start; the regular after-close timer is
15:45 Central. Increased concurrency and full catch-up latency remain unmeasured.
