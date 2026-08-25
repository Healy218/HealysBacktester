# nn_meta/universe_pit.py — point-in-time universe membership (stage B).
"""Survivorship-free monthly universe reconstitution from OPRA daily option
aggregates (docs/specs/PIT_UNIVERSE_SPEC.md). Pure on a supplied daily frame:
no network, no clocks — stage A (scripts/build_universe_daily.py) writes the
daily rows this module consumes.

Data contract, daily rows (one row per OCC root per trading day):
    root, date, opt_dollar_vol, call_dollar_vol, put_dollar_vol,
    n_contracts, n_trades
Roots stay RAW in the daily files (aliases and exclusions can change without
a recrawl); mapping to tickers happens here.

Reconstitution at each month-end M, rows <= M only:
    score       = median opt_dollar_vol over the trailing 63 trading days
                  (missing days count as 0)
    eligibility = >= 50 active days in the window and score > 0
    membership  = HYSTERESIS: enter at rank <= 270, stay until rank > 330

Frozen artifact per month: v3/artifacts/universe_pit/<yyyy-mm>.json
(write-once, committed). Consolidated view: universe_membership.parquet
under v3/data/universe_daily/ (regenerable, untracked).

available_at = first trading day AFTER month-end M.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from nn_meta.config import TICKER_ALIASES

# Layout (v3/data is gitignored; v3/artifacts is tracked)
V3_ROOT = Path(__file__).resolve().parent.parent / "v3"
UNIVERSE_DAILY_DIR = V3_ROOT / "data" / "universe_daily"
ARTIFACT_DIR = V3_ROOT / "artifacts" / "universe_pit"

# Membership defaults (spec: retune from the churn report once, then freeze)
TARGET_N = 300
ENTER_RANK = 270
EXIT_RANK = 330
WINDOW_DAYS = 63
MIN_ACTIVE_DAYS = 50

# Index roots are the spx0 pool's business, not the equity universe's.
INDEX_ROOTS = frozenset({
    "SPX", "SPXW", "NDX", "NDXP", "VIX", "VIXW", "RUT", "RUTW",
    "XSP", "DJX", "OEX", "XEO", "BXO",
})

DAILY_COLUMNS = ["root", "date", "opt_dollar_vol", "call_dollar_vol",
                 "put_dollar_vol", "n_contracts", "n_trades"]

# OCC option symbol tail: yymmdd + C/P + 8-digit strike. The root is whatever
# precedes it (letters, plus digits for adjusted series like AAPL1).
_OCC_TAIL_RE = re.compile(r"^(\d{6})([CP])(\d{8})$")
_ADJUSTED_ROOT_RE = re.compile(r"\d$")


class UniversePitError(ValueError):
    pass


# ── OCC parsing / root→ticker mapping ────────────────────────────────────────

def split_occ(ticker: str) -> tuple[str, str] | None:
    """'O:AAPL241220C00150000' → ('AAPL', 'C'); None if not an OCC option."""
    if not ticker.startswith("O:"):
        return None
    body = ticker[2:]
    root, tail = body[:-15], body[-15:]
    m = _OCC_TAIL_RE.match(tail)
    if not root or m is None:
        return None
    return root, m.group(2)


def root_to_ticker(root: str) -> str | None:
    """Map an OCC root to the equity ticker membership is keyed on.
    None → drop (index products; adjusted series like 'AAPL1', whose
    liquidity belongs to non-standard deliverables, not the name)."""
    if root in INDEX_ROOTS or _ADJUSTED_ROOT_RE.search(root):
        return None
    return TICKER_ALIASES.get(root, root)


# ── stage A pure transform (the crawler calls this; tested here) ─────────────

def daily_rows_from_day_aggs(df: pd.DataFrame, day: str) -> pd.DataFrame:
    """Whole-market day_aggs_v1 rows (ticker, close, volume, transactions)
    → one row per OCC root: dollar volume (Σ close·volume·100), call/put
    split, contract and trade counts. Non-OCC rows are dropped; a frame
    that yields nothing raises (coverage gate: a day that parses to empty
    is a broken file, not a quiet holiday — holidays never download)."""
    required = {"ticker", "close", "volume", "transactions"}
    if missing := required - set(df.columns):
        raise UniversePitError(f"{day}: day_aggs missing columns {sorted(missing)}")
    parsed = df["ticker"].map(split_occ)
    keep = parsed.notna()
    if not keep.any():
        raise UniversePitError(f"{day}: no OCC rows parsed from {len(df)} rows")
    out = df.loc[keep, ["close", "volume", "transactions"]].copy()
    out["root"] = parsed[keep].str[0]
    out["cp"] = parsed[keep].str[1]
    out["dv"] = out["close"] * out["volume"] * 100.0
    g = out.groupby("root", sort=True)
    rows = pd.DataFrame({
        "opt_dollar_vol": g["dv"].sum(),
        "call_dollar_vol": out[out["cp"] == "C"].groupby("root")["dv"].sum(),
        "put_dollar_vol": out[out["cp"] == "P"].groupby("root")["dv"].sum(),
        "n_contracts": g.size(),
        "n_trades": g["transactions"].sum(),
    }).fillna(0.0).reset_index()
    rows["n_contracts"] = rows["n_contracts"].astype("int64")
    rows["n_trades"] = rows["n_trades"].astype("int64")
    rows.insert(1, "date", day)
    return rows[DAILY_COLUMNS]


# ── stage B: monthly reconstitution ──────────────────────────────────────────

def _ticker_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Raw per-root rows → per-(ticker, date) dollar volume, mapped/filtered."""
    if missing := {"root", "date", "opt_dollar_vol"} - set(daily.columns):
        raise UniversePitError(f"daily rows missing columns {sorted(missing)}")
    d = daily[["root", "date", "opt_dollar_vol"]].copy()
    d["ticker"] = d["root"].map(root_to_ticker)
    d = d.dropna(subset=["ticker"])
    d["date"] = pd.to_datetime(d["date"])
    return (d.groupby(["ticker", "date"], as_index=False)["opt_dollar_vol"].sum())


def monthly_membership(daily: pd.DataFrame, *,
                       enter_rank: int = ENTER_RANK, exit_rank: int = EXIT_RANK,
                       window_days: int = WINDOW_DAYS,
                       min_active_days: int = MIN_ACTIVE_DAYS,
                       through: str | None = None) -> pd.DataFrame:
    """Reconstitute membership at every month-end with a full trailing window.

    Returns one row per (month, member): month 'YYYY-MM', ticker, rank, score,
    entered (first month of the stint), exited (last month of the stint —
    always False for the final month, the future being unknown), available_at
    (first trading day after month-end; ISO date string).

    Months whose trailing window is short (fewer than `window_days` trading
    days of data) are skipped, not guessed: the first ~3 months of a backfill
    produce no membership. `through` ('YYYY-MM') caps reconstitution at the
    last COMPLETED month — a mid-month crawl must not masquerade as that
    month's reconstitution.
    """
    td = _ticker_daily(daily)
    if td.empty:
        raise UniversePitError("no daily rows after root→ticker mapping")
    trading_days = pd.DatetimeIndex(sorted(td["date"].unique()))
    month_ends = (pd.Series(trading_days, index=trading_days)
                  .groupby(trading_days.to_period("M")).max())
    if through is not None:
        month_ends = month_ends[month_ends.index <= pd.Period(through, "M")]

    wide = td.pivot(index="date", columns="ticker", values="opt_dollar_vol") \
             .reindex(trading_days)

    members: set[str] = set()
    rows: list[dict] = []
    prev_month: str | None = None

    for period, m_end in month_ends.items():
        month = str(period)
        upto = trading_days[trading_days <= m_end]
        if len(upto) < window_days:
            continue
        window = wide.loc[upto[-window_days:]]
        active = window.notna().sum()
        score = window.fillna(0.0).median()
        eligible = score[(active >= min_active_days) & (score > 0)]
        # deterministic rank: score desc, ticker asc on ties
        ranked = eligible.reset_index()
        ranked.columns = ["ticker", "score"]
        ranked = ranked.sort_values(["score", "ticker"], ascending=[False, True])
        ranked["rank"] = range(1, len(ranked) + 1)
        rank_of = dict(zip(ranked["ticker"], ranked["rank"]))
        score_of = dict(zip(ranked["ticker"], ranked["score"]))

        exits = {t for t in members if rank_of.get(t, 10**9) > exit_rank}
        entries = {t for t in rank_of if rank_of[t] <= enter_rank and t not in members}
        for t in exits:
            # mark the stint's last month (the previous one) as exited
            for r in reversed(rows):
                if r["ticker"] == t and r["month"] == prev_month:
                    r["exited"] = True
                    break
        members = (members - exits) | entries
        after = trading_days[trading_days > m_end]
        available_at = (after[0] if len(after)
                        else m_end + pd.offsets.BDay(1)).date().isoformat()
        for t in sorted(members):
            rows.append({"month": month, "ticker": t, "rank": rank_of[t],
                         "score": float(score_of[t]),
                         "entered": t in entries, "exited": False,
                         "available_at": available_at})
        prev_month = month

    if not rows:
        raise UniversePitError(
            f"no month has a full {window_days}-trading-day window; "
            "backfill more history before reconstituting")
    return pd.DataFrame(rows)


def churn_report(membership: pd.DataFrame) -> list[dict]:
    """Per-month membership counts and churn (entries/exits by ticker)."""
    out = []
    prev: set[str] = set()
    for month, grp in membership.groupby("month", sort=True):
        now = set(grp["ticker"])
        out.append({"month": month, "n_members": len(now),
                    "entries": sorted(now - prev), "exits": sorted(prev - now)})
        prev = now
    return out


# ── validation gates (fail-closed) ───────────────────────────────────────────

def delisting_canary_gate(membership: pd.DataFrame, *, min_months: int = 12) -> None:
    """Refuse a backfill in which no ticker ever exits across >= min_months:
    churn-free history is the signature of a survivorship-biased source,
    not a stable market."""
    months = membership["month"].nunique()
    if months < min_months:
        return
    report = churn_report(membership)
    if not any(m["exits"] for m in report[1:]):
        raise UniversePitError(
            f"delisting canary: {months} months of membership with ZERO exits "
            "— source looks survivorship-biased; refusing to freeze")


def assert_canaries(membership: pd.DataFrame, canaries: dict[str, str]) -> None:
    """Assert each canary ticker was a member while alive and is absent in
    every month at/after its death month ('YYYY-MM')."""
    for ticker, dead_month in canaries.items():
        stints = membership[membership["ticker"] == ticker]
        alive = stints[stints["month"] < dead_month]
        if alive.empty:
            raise UniversePitError(
                f"canary {ticker}: never a member before {dead_month}")
        dead = stints[stints["month"] >= dead_month]
        if not dead.empty:
            raise UniversePitError(
                f"canary {ticker}: still a member in {sorted(dead['month'])} "
                f"at/after its delisting month {dead_month}")


# ── freeze / load ────────────────────────────────────────────────────────────

def freeze_month(membership: pd.DataFrame, month: str, *,
                 artifact_dir: Path = ARTIFACT_DIR) -> Path:
    """Write-once monthly artifact (same discipline as fa freeze_ranking)."""
    path = Path(artifact_dir) / f"{month}.json"
    if path.exists():
        raise UniversePitError(f"universe month already frozen: {path}")
    grp = membership[membership["month"] == month]
    if grp.empty:
        raise UniversePitError(f"no membership rows for {month}")
    report = churn_report(membership)
    churn = next(m for m in report if m["month"] == month)
    payload = {"month": month,
               "available_at": grp["available_at"].iloc[0],
               "params": {"enter_rank": ENTER_RANK, "exit_rank": EXIT_RANK,
                          "window_days": WINDOW_DAYS,
                          "min_active_days": MIN_ACTIVE_DAYS},
               "churn": {"entries": churn["entries"], "exits": churn["exits"]},
               "members": grp.sort_values("rank")[["ticker", "rank", "score",
                                                   "entered"]]
                              .to_dict(orient="records")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load_daily_rows(daily_dir: Path = UNIVERSE_DAILY_DIR) -> pd.DataFrame:
    """Concatenate the stage-A monthly parquets; loud on absence."""
    files = sorted(Path(daily_dir).glob("*.parquet"))
    if not files:
        raise UniversePitError(f"no universe_daily parquets under {daily_dir}")
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def load_membership(artifact_dir: Path = ARTIFACT_DIR) -> pd.DataFrame:
    """Stage-C reader: the frozen monthlies → (month, ticker, rank, score,
    entered, available_at) frame. Reads artifacts only — consumers can never
    see a membership that was not frozen."""
    files = sorted(Path(artifact_dir).glob("*.json"))
    if not files:
        raise UniversePitError(f"no frozen universe months under {artifact_dir}")
    rows = []
    for f in files:
        p = json.loads(f.read_text())
        for m in p["members"]:
            rows.append({"month": p["month"], "available_at": p["available_at"],
                         **m})
    return pd.DataFrame(rows)


def write_membership_parquet(membership: pd.DataFrame,
                             daily_dir: Path = UNIVERSE_DAILY_DIR) -> Path:
    """Consolidated regenerable view beside the daily rows (untracked)."""
    out = Path(daily_dir) / "universe_membership.parquet"
    membership.to_parquet(out, index=False)
    return out


def members_asof(membership: pd.DataFrame, month: str) -> set[str]:
    """Members whose membership a consumer may use DURING calendar month
    `month`: the latest freeze whose available_at falls within (or before)
    that month — i.e. the previous month-end's reconstitution, which becomes
    available at this month's first trading day; never the one formed at
    this month's own end (its available_at lands in the NEXT month)."""
    avail = membership.drop_duplicates("month")[["month", "available_at"]]
    usable = avail[avail["available_at"].str[:7] <= month]
    if usable.empty:
        return set()
    src = usable["month"].max()
    return set(membership.loc[membership["month"] == src, "ticker"])


def membership_mask(symbols: pd.Series, entry_dates: pd.Series,
                    membership: pd.DataFrame | None = None) -> pd.Series:
    """Vectorized stage-C filter: True where the row's symbol was a usable
    member during the row's entry month (per members_asof — the latest
    freeze available before that month began). Loads the frozen artifacts
    when membership is None; loud if none exist."""
    if membership is None:
        membership = load_membership()
    months = pd.to_datetime(entry_dates).dt.strftime("%Y-%m")
    allowed = {m: members_asof(membership, m) for m in months.unique()}
    return pd.Series([s in allowed[m] for s, m in zip(symbols, months)],
                     index=symbols.index)


# ── freeze driver (spec step 3) ──────────────────────────────────────────────

def _parse_canaries(arg: str) -> dict[str, str]:
    """'MRO:2024-12,CTLT:2025-03' → {ticker: delisting month}."""
    out = {}
    for part in filter(None, (p.strip() for p in arg.split(","))):
        ticker, _, month = part.partition(":")
        if not month:
            raise UniversePitError(f"canary needs TICKER:YYYY-MM, got {part!r}")
        out[ticker] = month
    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--through", required=True,
                    help="last COMPLETED month to reconstitute (YYYY-MM)")
    ap.add_argument("--canary", default="",
                    help="TICKER:YYYY-MM[,...] delistings that must enter "
                         "while alive and exit after death")
    ap.add_argument("--freeze", action="store_true",
                    help="write the monthly artifacts (default: report only)")
    args = ap.parse_args()

    daily = load_daily_rows()
    membership = monthly_membership(daily, through=args.through)
    report = churn_report(membership)
    for m in report:
        print(f"{m['month']}: {m['n_members']} members, "
              f"+{len(m['entries'])} / -{len(m['exits'])}")

    delisting_canary_gate(membership)
    if args.canary:
        assert_canaries(membership, _parse_canaries(args.canary))
        print(f"canaries OK: {args.canary}")
    elif membership["month"].nunique() >= 12:
        raise UniversePitError(
            "a >=12-month freeze requires named delisting canaries (--canary)")

    if not args.freeze:
        print("\n(report only — rerun with --freeze to write artifacts)")
        return
    frozen = 0
    for month in sorted(membership["month"].unique()):
        if (ARTIFACT_DIR / f"{month}.json").exists():
            continue
        freeze_month(membership, month)
        frozen += 1
    out = write_membership_parquet(membership)
    print(f"\nfroze {frozen} new month(s) under {ARTIFACT_DIR}; "
          f"consolidated view: {out}")


if __name__ == "__main__":
    main()
