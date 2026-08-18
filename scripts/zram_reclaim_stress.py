#!/usr/bin/env python3
"""Drive the reclaim->zram path that both recorded crashes died in, and verify.

WHY THIS EXISTS
    Two kernel crashes on this box (Pop!_OS 2026-08-17 20:45, CachyOS
    2026-08-17 23:10) both died in kswapd at
    shrink_node > shrink_one > try_to_shrink_lruvec > evict_folios >
    shrink_folio_list -- across a different kernel AND a different filesystem.
    That is where evicted pages get handed to zram for compression. Waiting for
    the next random freeze costs days; this forces the path in minutes.

WHAT IT DETECTS
    Every page written carries a seeded, position-dependent pattern that is read
    back and verified after a round trip through zram. A mismatch is corruption
    caught IN USERSPACE -- it does not depend on the kernel noticing anything.
    Kernel-side signatures (Bad page state, oops) should be watched separately
    in dmesg; this process cannot see those.

WHAT IT DOES NOT DISTINGUISH
    A hit here says the damage happens on this path. It does NOT separate "zram
    is buggy" from "zram merely hammers marginal RAM harder than memtest did".
    Both produce identical symptoms. See HANDOFF.md.

SAFETY
    - oom_score_adj is raised to 1000 so THIS process is the kernel's preferred
      OOM victim. A runaway must not take out the stocktwits timer or the shell.
    - Working set defaults to a fraction of *available* memory, not total, and
      is sized to thrash rather than to approach the OOM ceiling. Maximum
      reclaim churn per byte allocated is the goal; filling zram is not.
    - Hard wall-clock deadline, and Ctrl-C is honoured between chunks.
    - Pure anonymous memory. Nothing is written to disk, so a hard lockup costs
      an unclean shutdown (btrfs replays its log) and nothing else.

USAGE
    ./venv/bin/python scripts/zram_reclaim_stress.py --minutes 10
    ./venv/bin/python scripts/zram_reclaim_stress.py --minutes 30 --frac 0.9
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import sys
import time

CHUNK = 64 << 20  # 64 MiB per chunk: big enough to be swapped as a unit,
                  # small enough that progress and interrupts stay responsive.


def meminfo() -> dict[str, int]:
    out = {}
    with open("/proc/meminfo") as fh:
        for line in fh:
            k, _, v = line.partition(":")
            out[k.strip()] = int(v.strip().split()[0]) * 1024
    return out


def zram_used() -> str:
    try:
        with open("/sys/block/zram0/mm_stat") as fh:
            f = fh.read().split()
        orig, compr = int(f[0]), int(f[1])
        ratio = (orig / compr) if compr else 0.0
        return f"zram orig={orig/2**30:.2f}G compr={compr/2**30:.2f}G ratio={ratio:.2f}x"
    except Exception:
        return "zram stats unavailable"


def pattern(seed: int, idx: int, compressible_frac: float = 0.5) -> bytes:
    """Deterministic, position-dependent, and DELIBERATELY HALF-COMPRESSIBLE.

    Compressibility is the load-bearing parameter here, because zram is backed
    by RAM: swapping a page out frees only (original - compressed), not the whole
    page. So:

      - Fully incompressible data frees ~nothing on swap-out, and a working set
        above RAM would simply OOM instead of thrashing -- no reclaim churn, no
        test. (An earlier version of this function claimed to be incompressible
        while actually emitting a repeated 64-byte block; the claim was wrong and
        the sizing model built on it was wrong too.)
      - Fully compressible data (a repeated block) lets zram absorb almost the
        entire working set for free, so pages move but zstd barely works.

    Half and half gives roughly 2x: zram frees real memory, so a large working
    set thrashes sustainably, while every page still costs genuine compress and
    decompress work on the way out and back.
    """
    seg = max(1, int(CHUNK * compressible_frac))
    seg -= seg % 64
    block = hashlib.blake2b(f"{seed}:{idx}".encode(), digest_size=64).digest()
    head = block * (seg // 64)                      # compresses to nearly nothing
    tail = bytearray()                              # resists compression
    n = CHUNK - len(head)
    ctr = 0
    while len(tail) < n:
        tail += hashlib.blake2b(f"{seed}:{idx}:{ctr}".encode(), digest_size=64).digest()
        ctr += 1
    return head + bytes(tail[:n])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--frac", type=float, default=0.80,
                    help="working set as a fraction of MemAvailable+SwapFree/2")
    ap.add_argument("--seed", type=int, default=20260818)
    args = ap.parse_args()

    # Be the OOM killer's first choice, always.
    try:
        with open("/proc/self/oom_score_adj", "w") as fh:
            fh.write("1000")
    except OSError as exc:
        print(f"warning: could not raise oom_score_adj ({exc})", file=sys.stderr)

    mi = meminfo()
    avail, swapfree = mi["MemAvailable"], mi.get("SwapFree", 0)
    # Sizing against zram, which is RAM-backed. SwapFree reports 15.5G but that
    # capacity is not additional memory -- it is the SAME RAM, minus whatever
    # compression buys. At ~2x (see pattern()), swapping out a page nets back
    # about half of it, so the extra headroom over MemAvailable is roughly
    # swapfree/4, not swapfree. Being conservative here is deliberate: the goal
    # is a working set that thrashes continuously, not one that races the OOM
    # killer. Raise --frac if zram DATA is not climbing.
    target = int((avail + swapfree / 4) * args.frac)
    nchunks = max(1, target // CHUNK)

    print(f"MemAvailable {avail/2**30:.1f}G  SwapFree {swapfree/2**30:.1f}G")
    print(f"working set  {nchunks * CHUNK / 2**30:.1f}G in {nchunks} x 64MiB chunks")
    print(f"deadline     {args.minutes:.0f} min")
    print(f"start        {zram_used()}")
    print("-" * 72, flush=True)

    deadline = time.monotonic() + args.minutes * 60
    chunks: list[ctypes.Array] = []
    sweeps = mismatches = 0

    try:
        # Fill: allocate and stamp. Touching every page is what makes it real.
        for i in range(nchunks):
            if time.monotonic() > deadline:
                break
            buf = (ctypes.c_char * CHUNK)()
            buf.raw = pattern(args.seed, i)
            chunks.append(buf)
            if (i + 1) % 16 == 0:
                print(f"  filled {(i+1)*CHUNK/2**30:5.1f}G  {zram_used()}", flush=True)

        print(f"filled {len(chunks)*CHUNK/2**30:.1f}G — sweeping to force reclaim\n",
              flush=True)

        # Sweep: read back and verify, forward then reverse. The reverse pass
        # maximises the chance that a page is evicted before it is re-read,
        # which is the whole point -- a round trip through zstd per page.
        while time.monotonic() < deadline:
            order = range(len(chunks)) if sweeps % 2 == 0 else range(len(chunks) - 1, -1, -1)
            for i in order:
                if time.monotonic() > deadline:
                    break
                expect = pattern(args.seed, i)
                got = chunks[i].raw
                if got != expect:
                    mismatches += 1
                    bad = next((k for k in range(len(expect)) if got[k] != expect[k]), -1)
                    print(f"\n*** CORRUPTION chunk={i} offset={bad} "
                          f"expected={expect[bad:bad+8].hex()} got={got[bad:bad+8].hex()}",
                          flush=True)
                    if mismatches >= 5:
                        print("*** 5 mismatches — stopping early", flush=True)
                        raise SystemExit(2)
            sweeps += 1
            print(f"  sweep {sweeps:3d} clean  {zram_used()}", flush=True)

    except KeyboardInterrupt:
        print("\ninterrupted", flush=True)
    finally:
        chunks.clear()

    print("-" * 72)
    print(f"sweeps={sweeps} mismatches={mismatches}")
    print(f"end   {zram_used()}")
    if mismatches:
        print("\nRESULT: CORRUPTION REPRODUCED on the reclaim->zram path.")
        print("This does NOT yet separate a zram bug from marginal RAM exposed")
        print("by zram's access pattern. Next: rerun with zram off (swapoff)")
        print("and with vm.swappiness=60, and compare.")
        return 2
    print("\nRESULT: no userspace corruption seen. NOT a clean bill of health —")
    print("check dmesg for kernel-side signatures (Bad page state / oops), which")
    print("this process cannot observe, and note that the real crashes took")
    print("hours to appear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
