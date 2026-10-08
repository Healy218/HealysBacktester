# scripts/build_v8_universe_pit.py — V8.0-pit: PIT universe from V7 day aggregates.
"""Rebuild the monthly PIT option-activity universe for V8 from the OPRA
day_aggs files already captured by V7 (2021-01 → 2026-09-14), read IN PLACE
from the sealed MRHA store (never unpacked, never written to).

Stage A  (--stage daily): one sealed day file → nn_meta.universe_pit.
         daily_rows_from_day_aggs → <root>/universe_daily/<yyyy-mm>.parquet.
         Resumable per month; a month parquet is written atomically once all
         of its days are reduced.
Stage B  (--stage report): monthly_membership with the frozen V3 parameters
         (enter 270 / exit 330, 63-day median, >= 50 active days), churn
         report, delisting gates, overlap check against the committed
         v3/artifacts/universe_pit months. Writes <root>/membership.parquet
         and <root>/report.json; --freeze writes write-once month JSONs to
         <root>/universe_pit/.

Run under a memory cap, e.g.
    systemd-run --user --scope -p MemoryMax=6G ./venv/bin/python \
        scripts/build_v8_universe_pit.py --stage daily
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import universe_pit as up  # noqa: E402

STORE = Path("/run/media/healy/MRHA/HealysBacktester/sealed-v7-payloads-20260929")
DEFAULT_ROOT = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0"
_DAY_RE = re.compile(r"/options/day_aggs/(\d{4}-\d{2}-\d{2})/")


def sealed_day_files(store: Path = STORE) -> dict[str, tuple[str, Path]]:
    """{day: (sha, object path)} for every captured option day_aggs file.
    The same day can be indexed under several V7 datasets; they must agree
    on content (sha) or the store is ambiguous and we refuse."""
    con = sqlite3.connect(f"file:{store / 'files.sqlite3'}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select source, sha, status, destination from files "
            "where source like '%/options/day_aggs/%'").fetchall()
    finally:
        con.close()
    by_day: dict[str, set] = defaultdict(set)
    for source, sha, status, dest in rows:
        m = _DAY_RE.search(source)
        if m is None or status != "moved":
            raise SystemExit(f"unexpected store row: {source} status={status}")
        by_day[m.group(1)].add((sha, dest))
    out = {}
    for day, hits in sorted(by_day.items()):
        shas = {s for s, _ in hits}
        if len(shas) != 1:
            raise SystemExit(f"{day}: {len(shas)} distinct day_aggs payloads")
        sha, dest = sorted(hits)[0]
        out[day] = (sha, Path(dest))
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_daily(root: Path, verify_sha: bool) -> None:
    days = sealed_day_files()
    out_dir = root / "universe_daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    months: dict[str, list[str]] = defaultdict(list)
    for day in days:
        months[day[:7]].append(day)
    manifest = {}
    for month, mdays in sorted(months.items()):
        out = out_dir / f"{month}.parquet"
        if out.exists():
            continue
        frames = []
        for day in mdays:
            sha, obj = days[day]
            if verify_sha and _sha256(obj) != sha:
                raise SystemExit(f"{day}: sealed object sha mismatch {obj}")
            with gzip.open(obj, "rb") as f:
                raw = pd.read_csv(f, usecols=["ticker", "close", "volume",
                                              "transactions"])
            frames.append(up.daily_rows_from_day_aggs(raw, day))
            manifest[day] = sha
        rows = pd.concat(frames, ignore_index=True).sort_values(
            ["date", "root"], ignore_index=True)
        tmp = out.with_suffix(".tmp")
        rows.to_parquet(tmp, index=False)
        tmp.replace(out)
        print(f"{month}: {len(mdays)} days, {len(rows)} root-days", flush=True)
    man_path = root / "daily_manifest.json"
    old = json.loads(man_path.read_text()) if man_path.exists() else {}
    old.update(manifest)
    man_path.write_text(json.dumps(dict(sorted(old.items())), indent=1) + "\n")
    print(f"stage A complete: {len(days)} sealed days, "
          f"{min(days)} → {max(days)}")


def weekday_gaps(days: list[str]) -> list[str]:
    """Weekdays inside the span with no file — holidays or capture holes;
    printed for inspection (missing days count as 0 in the score)."""
    have = set(days)
    span = pd.bdate_range(min(days), max(days))
    return [d.date().isoformat() for d in span if d.date().isoformat() not in have]


# OPRA/OCC test roots seen in the 2021+ day files. They trade every few days
# with synthetic size and ranked ~116-213 in 2021-12..2022-06 before this
# exclusion. None appears in the V3 window's membership.
TEST_ROOTS = frozenset({
    "ATEST", "BPX", "CBO", "CBX", "CTEST", "IBO", "MTEST", "NTEST", "PTEST",
    "TESTY", "ZAZZT", "ZBZZT", "ZEXIT", "ZJZZT", "ZTEST", "ZVZZT", "ZZK", "ZZZ",
})


def apply_aliases(daily: pd.DataFrame, aliases: dict[str, str],
                  rekeys: list[tuple[str, str, str]] = ()) -> pd.DataFrame:
    """V8-local root hygiene applied before reconstitution, so the shared
    TICKER_ALIASES (and the frozen V3 artifacts) stay untouched:
    drop test roots; rekey (root, before-date, new) for a symbol that
    belonged to a different issuer before a rename seam; then map OLD→NEW
    renames (chains resolved, e.g. VIAC→PARA→PSKY)."""
    d = daily[~daily["root"].isin(TEST_ROOTS)].copy()
    for root, before, new in rekeys:
        hit = (d["root"] == root) & (d["date"] < before)
        d.loc[hit, "root"] = new
    if aliases:
        def resolve(r: str) -> str:
            seen = set()
            while r in aliases and r not in seen:
                seen.add(r)
                r = aliases[r]
            return r
        d["root"] = d["root"].map(lambda r: resolve(r) if r in aliases else r)
    return d  # same-date duplicates are summed by universe_pit._ticker_daily


def overlap_check(membership: pd.DataFrame) -> list[dict]:
    """Compare rebuilt months with the committed V3 monthlies."""
    out = []
    for f in sorted(up.ARTIFACT_DIR.glob("*.json")):
        p = json.loads(f.read_text())
        month = p["month"]
        old = {m["ticker"] for m in p["members"]}
        new = set(membership.loc[membership["month"] == month, "ticker"])
        out.append({"month": month, "v3": len(old), "v8": len(new),
                    "only_v3": sorted(old - new), "only_v8": sorted(new - old),
                    "available_at_v3": p["available_at"],
                    "available_at_v8": (membership.loc[membership["month"] == month,
                                                       "available_at"].iloc[0]
                                        if new else None)})
    return out


def stage_report(root: Path, through: str, canaries: dict[str, str],
                 aliases: dict[str, str], rekeys: list[tuple[str, str, str]],
                 freeze: bool) -> None:
    daily = up.load_daily_rows(root / "universe_daily")
    days = sorted(daily["date"].unique())
    gaps = weekday_gaps(days)
    print(f"daily rows: {len(daily)} over {len(days)} days; "
          f"weekday gaps ({len(gaps)}): {gaps}")
    membership = up.monthly_membership(apply_aliases(daily, aliases, rekeys),
                                       through=through)
    report = up.churn_report(membership)
    for m in report:
        print(f"{m['month']}: {m['n_members']} members, "
              f"+{len(m['entries'])} / -{len(m['exits'])}")
    up.delisting_canary_gate(membership)
    up.assert_canaries(membership, canaries)
    print(f"canaries OK: {canaries}")
    overlap = overlap_check(membership)
    for o in overlap:
        print(f"overlap {o['month']}: v3 {o['v3']} v8 {o['v8']} "
              f"only_v3 {o['only_v3']} only_v8 {o['only_v8']}"
              + ("" if o["available_at_v3"] == o["available_at_v8"]
                 else f" available_at {o['available_at_v3']}≠{o['available_at_v8']}"))
    membership.to_parquet(root / "membership.parquet", index=False)
    (root / "report.json").write_text(json.dumps({
        "through": through, "aliases": aliases, "canaries": canaries,
        "rekeys": rekeys, "test_roots_dropped": sorted(TEST_ROOTS),
        "params": {"enter_rank": up.ENTER_RANK, "exit_rank": up.EXIT_RANK,
                   "window_days": up.WINDOW_DAYS,
                   "min_active_days": up.MIN_ACTIVE_DAYS},
        "days": len(days), "first_day": days[0], "last_day": days[-1],
        "weekday_gaps": gaps, "churn": report, "overlap_v3": overlap,
    }, indent=1) + "\n")
    if freeze:
        art = root / "universe_pit"
        n = 0
        for month in sorted(membership["month"].unique()):
            if not (art / f"{month}.json").exists():
                up.freeze_month(membership, month, artifact_dir=art)
                n += 1
        print(f"froze {n} month(s) under {art}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["daily", "report"], required=True)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--verify-sha", action="store_true",
                    help="hash every sealed object against the index")
    ap.add_argument("--through", default="2026-08",
                    help="last COMPLETED month to reconstitute")
    ap.add_argument("--canary", default="",
                    help="TICKER:YYYY-MM[,...] delistings (required for report)")
    ap.add_argument("--alias", default="",
                    help="OLD:NEW[,...] V8-local root renames")
    ap.add_argument("--rekey", default="",
                    help="ROOT:YYYY-MM-DD:NEW[,...] rows of ROOT before the "
                         "date belong to another issuer, keyed NEW")
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()
    if args.stage == "daily":
        stage_daily(args.root, args.verify_sha)
        return
    if not args.canary:
        raise SystemExit("--canary is required for the report stage")
    aliases = dict(p.split(":", 1) for p in filter(None, args.alias.split(",")))
    rekeys = [tuple(p.split(":")) for p in filter(None, args.rekey.split(","))]
    stage_report(args.root, args.through, up._parse_canaries(args.canary),
                 aliases, rekeys, args.freeze)


if __name__ == "__main__":
    main()
