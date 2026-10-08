# scripts/freeze_v8_pool.py — V8.0-pit: re-freeze the V8 pool from the PIT rebuild.
"""Apply the frozen V8 pool rule (docs/specs/V8_POOL_20261007.json "rule") to
the V8 PIT monthlies built by scripts/build_v8_universe_pit.py.

Tech = monthly PIT member whose SEC SIC falls in the declared ranges, or a
declared tech-adjacent platform; ETFs = the fixed set, every month.

SIC resolution (cached in <root>/sic.json, network only for misses):
  1. SEC company_tickers.json (current tickers) → submissions JSON.
  2. Dead/renamed tickers are absent from (1). Fall back to EDGAR full-text
     search for 10-K/10-Q documents whose filename carries the ticker as its
     XBRL prefix ("twtr-20211231.htm"); the issuer CIK and filing-time SIC
     come from those hits. Recorded with resolved_by="fts-filename" so every
     such mapping is reviewable; unresolved names are listed, never guessed.

Run: ./venv/bin/python scripts/freeze_v8_pool.py --fetch      (resolve SIC)
     ./venv/bin/python scripts/freeze_v8_pool.py --out docs/specs/<file>.json
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0"
RULE_SOURCE = REPO / "docs" / "specs" / "V8_POOL_20261007.json"
SEED_SIC = REPO / "nn_meta" / "validation" / "v8-stage0-20261007-r0" / "sic.json"
EDGAR = Path("/home/healy/Coding/HealysAutomation/fa/collectors/edgar.py")

# Dead/renamed/foreign issuers the filename search misses, resolved by issuer
# name on EDGAR full-text search and verified against their submissions
# record (2026-10-07). Foreign filers (20-F) never match the 10-K/10-Q search.
MANUAL_CIKS = {
    "EA": 712515, "ANY": 1591956, "DIDI": 1764757, "GSX": 1768259,
    "FAZE": 1839360, "DRAM": 1812477, "X": 1163302, "XL": 1772720,
    "RIDE": 1759546, "BBIG": 1717556,
}
# Filename-prefix false matches: the ticker's earlier owner, not the
# security in this window (MSTX = Mast Therapeutics' old ticker; here it is
# a leveraged MSTR ETF).
NOT_ISSUERS = frozenset({"MSTX"})


def _user_agent() -> dict:
    for line in EDGAR.read_text().splitlines():
        if line.startswith("_UA ="):
            return eval(line.split("=", 1)[1])  # a literal dict in that file
    raise SystemExit(f"no _UA in {EDGAR}")


def load_months(root: Path) -> dict[str, dict]:
    out = {}
    for f in sorted((root / "universe_pit").glob("*.json")):
        p = json.loads(f.read_text())
        out[p["month"]] = {"available_at": p["available_at"],
                           "members": [m["ticker"] for m in p["members"]]}
    if not out:
        raise SystemExit(f"no V8 PIT monthlies under {root / 'universe_pit'}")
    return out


def _submission(cik: int, ua: dict) -> dict:
    r = requests.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                     headers=ua, timeout=30)
    time.sleep(0.15)
    if r.status_code != 200:
        return {"cik": cik, "sic": None, "desc": f"http {r.status_code}", "name": None}
    j = r.json()
    return {"cik": cik, "sic": j.get("sic"), "desc": j.get("sicDescription"),
            "name": j.get("name")}


def _fts_cik(ticker: str, ua: dict) -> tuple[int | None, dict]:
    """Most common CIK among 10-K/10-Q docs whose filename starts with the
    ticker as XBRL prefix. Returns (cik, evidence)."""
    pref = ticker.lower().replace(".", "") + "-"
    votes: collections.Counter = collections.Counter()
    names: dict[int, str] = {}
    for start in (0, 100):
        r = requests.get("https://efts.sec.gov/LATEST/search-index",
                         params={"q": f'"{ticker}"', "forms": "10-K,10-Q",
                                 "from": start}, headers=ua, timeout=30)
        time.sleep(0.2)
        if r.status_code != 200:
            break
        hits = r.json()["hits"]["hits"]
        for h in hits:
            fname = h["_id"].split(":", 1)[-1].lower()
            src = h["_source"]
            if fname.startswith(pref) and len(src.get("ciks", [])) == 1:
                c = int(src["ciks"][0])
                votes[c] += 1
                names[c] = (src.get("display_names") or [""])[0]
        if len(hits) < 100:
            break
    if not votes:
        return None, {}
    (cik, n), *rest = votes.most_common()
    return cik, {"fts_votes": n, "fts_runner_up": rest[0][1] if rest else 0,
                 "fts_display": names[cik]}


def fetch_sic(root: Path, tickers: set[str], etfs: set[str]) -> dict:
    path = root / "sic.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    if not cache and SEED_SIC.exists():
        seed = json.loads(SEED_SIC.read_text())
        cache = {t: {**v, "resolved_by": "company_tickers"}
                 for t, v in seed.items() if v.get("sic")}
    ua = _user_agent()
    current = requests.get("https://www.sec.gov/files/company_tickers.json",
                           headers=ua, timeout=30).json()
    cik_of = {v["ticker"].upper(): int(v["cik_str"]) for v in current.values()}
    for t in NOT_ISSUERS & tickers:
        cache[t] = {"cik": None, "sic": None, "desc": None, "name": None,
                    "resolved_by": "not-an-issuer"}
    todo = sorted(t for t in tickers if t not in etfs and t not in NOT_ISSUERS
                  and not cache.get(t, {}).get("sic"))
    for t in todo:
        c = cik_of.get(t) or cik_of.get(t.replace(".", "-"))
        if t in MANUAL_CIKS:
            cache[t] = {**_submission(MANUAL_CIKS[t], ua),
                        "resolved_by": "manual-name-search"}
        elif c is not None:
            cache[t] = {**_submission(c, ua), "resolved_by": "company_tickers"}
        else:
            c, ev = _fts_cik(t, ua)
            cache[t] = ({**_submission(c, ua), "resolved_by": "fts-filename", **ev}
                        if c else {"cik": None, "sic": None, "desc": None,
                                   "name": None, "resolved_by": None})
        print(t, cache[t].get("resolved_by"), cache[t].get("sic"),
              cache[t].get("name"), flush=True)
        path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    return cache


def is_tech(ticker: str, sic: dict, rule: dict) -> bool:
    if ticker in rule["tech_adjacent"]:
        return True
    code = (sic.get(ticker) or {}).get("sic")
    if not code:
        return False
    return any(lo <= int(code) <= hi for lo, hi in rule["tech_sic_ranges"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rule = json.loads(RULE_SOURCE.read_text())["rule"]
    etfs = set(rule["etfs_every_month"])
    months = load_months(args.root)
    members = set().union(*(set(m["members"]) for m in months.values()))
    if args.fetch:
        fetch_sic(args.root, members, etfs)
    sic = json.loads((args.root / "sic.json").read_text())
    unresolved = sorted(t for t in members
                        if t not in etfs and not (sic.get(t) or {}).get("sic"))
    print(f"{len(members)} members; unresolved SIC: {len(unresolved)} {unresolved}")
    if not args.out:
        return
    out_months = {}
    for month, m in months.items():
        out_months[month] = {
            "available_at": m["available_at"],
            "tech": sorted(t for t in m["members"]
                           if t not in etfs and is_tech(t, sic, rule))}
    tech_all = sorted(set().union(*(set(v["tech"]) for v in out_months.values())))
    sic_bytes = (args.root / "sic.json").read_bytes()
    pit_digest = hashlib.sha256(b"".join(
        f.read_bytes() for f in sorted((args.root / "universe_pit").glob("*.json"))
    )).hexdigest()
    payload = {
        "schema": "v8-pool-v1",
        "spec": "docs/specs/V8_DESIGN_20261007.md",
        "supersedes": "docs/specs/V8_POOL_20261007.json",
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rule": {**rule, "source": (
            "V8 PIT option-activity universe rebuilt from V7 day aggregates "
            "2021-01-04..2026-09-14 (scripts/build_v8_universe_pit.py; enter "
            "rank 270 / exit 330, 63-day median, >=50 active days)")},
        "pit_source": {"root": str(args.root.relative_to(REPO)),
                       "monthlies_sha256": pit_digest,
                       "report": "report.json"},
        "sic_source": {
            "endpoint": "SEC company_tickers.json + data.sec.gov submissions; "
                        "EDGAR full-text search (XBRL filename prefix) for "
                        "dead/renamed tickers",
            "sha256": hashlib.sha256(sic_bytes).hexdigest()},
        "limitations": [
            "SIC codes for live issuers are current (fetched 2026-10-07) and "
            "applied to past months; for dead issuers they are the SIC on "
            "their filings. Not strictly point-in-time.",
            "Membership runs 2021-04 to 2026-08 (first full 63-day window "
            "after the 2021-01-04 start; 2026-09 is incomplete).",
            f"Members with no resolvable SIC are excluded from tech: {unresolved}",
        ],
        "sic": {t: {"sic": sic[t]["sic"], "desc": sic[t]["desc"],
                    **({"resolved_by": sic[t]["resolved_by"]}
                       if sic[t].get("resolved_by") != "company_tickers" else {})}
                for t in tech_all if t in sic},
        "months": out_months,
    }
    args.out.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    sizes = [len(v["tech"]) for v in out_months.values()]
    print(f"wrote {args.out}: {len(out_months)} months, tech {min(sizes)}-"
          f"{max(sizes)} per month, {len(tech_all)} distinct; ETFs {len(etfs)}")


if __name__ == "__main__":
    main()
