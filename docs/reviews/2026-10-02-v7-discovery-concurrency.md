# V7 discovery concurrency revision — October 2, 2026

The user requested as many supported discovery workers as possible and a new ETA
from observed production throughput. This is a resource-only successor to the
optimized campaign adopted at 12:45. It retains the same campaign declaration,
wave v4 scientific producer, selected wave view, checkpoints and full denominator.

## Admission change

The production controller passes `OMP_NUM_THREADS=1` to keep scientific workers
single-threaded. GNU `nproc`, used by the shared autosizer, honors that variable;
it therefore capped the entire process pool at one even when the configured
ceiling was larger. The final policy removes `OMP_NUM_THREADS` and
`OMP_THREAD_LIMIT` only from the autosizer subprocess environment. Scientific
workers retain their one-thread settings. A test under the real inherited
one-thread environment demonstrated one admission before the correction and
eight afterward with identical memory. The initial r3 resource deployment
exposed this remaining cap; its observations are preserved, not used as evidence
of multiworker performance. The selected r4 corrects the autosizer environment.

The previous scheduler applied the free-memory-derived worker count as the total
pool ceiling even after running workers had consumed anonymous memory. Coupled
with the 3-GiB allowance and daytime limit of two, this admitted only one worker
in the initial production observation. The new policy restores owned anonymous
and kernel memory once when calculating the total budget. It does not count
reclaimable file cache as permanently resident worker memory.

`v7_discovery_resources_v4.py` uses the shared autosizer and permits up to the
minimum of twelve workers, CPU threads minus two, and the memory budget. The
allowance starts at 1 GiB per worker (roughly twice measured sample RSS), and
increases to at least 1.5 times the observed average anonymous/kernel working set
when larger workers are encountered. It remains within the
unchanged 14-GiB discovery service cap; 2 GiB is reserved inside that cap for
controller/cache. This is a budget, not a demonstrated maximum for every security.

Host reserve is 4 GiB, plus the unconsumed portion of a 12-GiB paper-scanner
allowance during its daytime window, a 20-GiB incubation allowance during the
15:30–21:00 weekday window or while incubation is active, and 1 GiB for replay.
Already consumed memory is not reserved a second time. No new slices start above
the admitted total. Existing slices drain normally; new slices are five minutes,
so the advance incubation reservation can reduce concurrency before 15:45.
Zero admission remains a memory wait, not lost work.

Replay and paper schedules are unchanged. Discovery remains nice 15, without a
CPU quota; raising its worker count is not itself evidence of higher throughput.
The service retains 12-GiB MemoryHigh, 14-GiB MemoryMax and no swap.

## Preservation and checks

The old discovery supervisor drained its running slice before replacement.
The corrected resource policy resumed at **13:39:30 Central**; nine workers were
observed active at 13:40, with no controller failures. A new
resource receipt binds the new scheduler without rewriting the existing campaign
or wave declarations. `finish_v7_discovery_resources_v4.py` selects scheduling
controller `run_v7_optimized_campaign_v3.py`; worker scientific arguments are
unchanged. Runtime override: `zzzz-resources-v4.conf` on the existing discovery
service. All prior source revisions remain preserved.

29 focused scheduler/adoption/watcher tests passed, including invariance when resident workers consume their
allowance, scanner growth within reserved capacity, zero/CPU/service limits,
incubator reservation, and preservation of the original campaign declaration.
Evidence root: `nn_meta/validation/v7-discovery-resources-20261002-r4/`.
`before.json`, `stopped.json` and `deployment.json` own the transition;
`measurement.json` and `measurement-summary.json` own measured production results.

The measurement uses the verified 591-job denominator of 1,641,934,235
horizon-target assessments. It tracks unique selected discovery work only,
excluding replay and benchmark replicas. Constant-rate extrapolation covers
original discovery only; future input capture/replay, changing work mix and
scheduled incubation can affect calendar completion. See the measurement receipt
for observation times, active workers and actual throughput.

## Production measurement, 13:39:30–13:54:30 Central

Selected discovery added **25,520 decision groups and 2,362,080 assessments**
in 15 minutes: **9,448,319 assessments/hour**. Seven to nine workers were active
at sampled boundaries (nine at the end); admission permits up to twelve when
resources allow. Retained totals are 1,584,782 groups and 148,502,835 assessments;
67 securities are terminal, including verified empty-demand cases. These counts
include pending-input outcomes, not completed labels or gate closure.

The independently matched full denominator is 1,641,934,235 assessments, leaving
1,493,431,400. Constant-rate original-discovery time is **6.59 continuous days**.
This short observation is 4.6–6.9 times the earlier 1.37–2.06 million/hour
one-worker samples, not a controlled same-security benchmark. Thirty-second
rates varied substantially. No precise calendar completion date is established:
work mix, paper activity and daily incubation reservations affect throughput;
further capture/reference/replay work is outside this estimate.

No discovery worker failures or OOM events were observed. MemoryHigh throttling
counts increased as file cache grew; MemoryMax/OOM counters stayed zero. V6
paper scans were blocked by the cancelled Massive options entitlement during
this observation, so this is **not** validation under a fully active paper scan.
The user subsequently requested removal of the V6 Massive dependency; that is a
separate provider migration and does not change this measured evidence.
