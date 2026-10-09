# scripts/build_v9_alt_features.py — V9 ALT-0: alternative-data features per earnings event.
"""Coverage only. For every OEE event (early 2021-04 → 2022-02 and main
2022-03 → 2026-09-14 tables), features public before the entry-day close
(16:00 ET), from data on disk:

  analyst actions (Benzinga headlines, nn_meta.v9_alt.parse_analyst), 30 and 90 days:
    an{w}_raise, an{w}_cut, an{w}_up, an{w}_down, an{w}_n
    an{w}_net_pt   (raise - cut) / (raise + cut)
    an{w}_net_rating (up - down) / (up + down)
    an90_pt_upside median new price target / entry spot - 1
  consensus (earnings headlines, parse_earnings), the latest within 200 days:
    prior_eps_surprise, prior_sales_surprise (vs consensus), beats_last4 (EPS
    beats among the last four parsed reports, >= 2 needed)
  insider (Form 4 open-market P and S, 90 days): ins90_net = (buy$ - sell$) /
    (buy$ + sell$), ins90_buyers (distinct buying owners)
  attention (Wikipedia, page views): wiki_abn = mean views E-5..E-1 / mean
    E-65..E-6 - 1 (rows available before the cut)
  pre_announcement flag (nn_meta.v9_oee.preannouncement_flags)

The release's own reported surprise (the headline after the release) is an
outcome; it is written to post_release.parquet and not summarized here.
News ends 2025-12-31, so 2026 analyst/consensus features are missing until
the archive is extended. Output (<out>/): features.parquet,
post_release.parquet, report.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v9_alt as A  # noqa: E402
from nn_meta import v9_oee  # noqa: E402

V = REPO / "nn_meta" / "validation"
EV = V / "v8-events-20261008-r0"
TABLES = [V / "v9-oee0-early-20261008-r0" / "events.parquet", V / "v9-oee0-20261008-r0" / "events.parquet"]
DEFAULT_OUT = V / "v9-alt0-20261008-r0"
TZ = "America/New_York"


def cut_time(entry_day: pd.Series) -> pd.Series:
    return (pd.to_datetime(entry_day).dt.tz_localize(TZ) + pd.Timedelta(hours=16)).dt.tz_convert("UTC")


def window_slice(times: np.ndarray, cut, days: int) -> slice:
    lo = np.searchsorted(times, (cut - pd.Timedelta(days=days)).to_datetime64(), side="left")
    hi = np.searchsorted(times, cut.to_datetime64(), side="left")
    return slice(lo, hi)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ev = pd.concat([pd.read_parquet(p).assign(table=p.parent.name) for p in TABLES], ignore_index=True)
    ev = ev[ev["status"] == "ok"].reset_index(drop=True)
    ev["pre_announcement"] = v9_oee.preannouncement_flags(ev, pd.read_parquet(EV / "sec" / "filings.parquet"))
    ev["cut"] = cut_time(ev["entry_day"])

    news = pd.read_parquet(EV / "news" / "news.parquet", columns=["ticker", "headline", "available_at_utc"])
    pa = news["headline"].fillna("").map(A.parse_analyst)
    an = news[pa.notna()].assign(action=[x[0] for x in pa.dropna()], pt=[x[2] for x in pa.dropna()])
    pe = news["headline"].fillna("").map(A.parse_earnings)
    er = news[pe.notna()].reset_index(drop=True)
    er = pd.concat([er, pd.DataFrame(list(pe.dropna()))], axis=1)
    er["eps_surprise"] = [A.surprise(a, e) for a, e in zip(er["eps_act"], er["eps_est"])]
    er["sales_surprise"] = [A.surprise(a, e) for a, e in zip(er["sales_act"], er["sales_est"])]

    ins = pd.read_parquet(EV / "insider" / "insider.parquet",
                          columns=["ticker", "trans_code", "trans_shares", "trans_pricepershare",
                                   "owner_ciks", "available_at_utc"])
    ins = ins[ins["trans_code"].isin(["P", "S"])].copy()
    ins["value"] = ins["trans_shares"] * ins["trans_pricepershare"]
    wiki = pd.read_parquet(EV / "wiki" / "pageviews.parquet", columns=["ticker", "date", "views", "available_at_utc"])

    groups = {
        "an": {t: g.sort_values("available_at_utc") for t, g in an.groupby("ticker")},
        "er": {t: g.sort_values("available_at_utc") for t, g in er.groupby("ticker")},
        "ins": {t: g.sort_values("available_at_utc") for t, g in ins.groupby("ticker")},
        "wiki": {t: g.sort_values("date") for t, g in wiki.groupby("ticker")},
    }
    rows, post = [], []
    for _, e in ev.iterrows():
        t, cut = e["ticker"], e["cut"]
        r = {"table": e["table"], "ticker": t, "accession": e["accession"], "entry_day": e["entry_day"],
             "pre_announcement": bool(e["pre_announcement"])}
        g = groups["an"].get(t)
        for w in (30, 90):
            if g is None:
                continue
            x = g.iloc[window_slice(g["available_at_utc"].values, cut, w)]
            c = x["action"].value_counts()
            ra, cu, up, dn = (int(c.get(k, 0)) for k in ("pt_raise", "pt_cut", "upgrade", "downgrade"))
            r.update({f"an{w}_raise": ra, f"an{w}_cut": cu, f"an{w}_up": up, f"an{w}_down": dn, f"an{w}_n": len(x),
                      f"an{w}_net_pt": (ra - cu) / (ra + cu) if ra + cu else np.nan,
                      f"an{w}_net_rating": (up - dn) / (up + dn) if up + dn else np.nan})
            if w == 90:
                pts = x["pt"].dropna()
                r["an90_pt_upside"] = float(pts.median() / e["S_entry"] - 1) if len(pts) else np.nan
        g = groups["er"].get(t)
        if g is not None:
            tt = g["available_at_utc"].values
            prior = g.iloc[window_slice(tt, cut, 200)]
            if len(prior):
                last = prior.iloc[-1]
                r["prior_eps_surprise"], r["prior_sales_surprise"] = last["eps_surprise"], last["sales_surprise"]
            hist = g.iloc[:np.searchsorted(tt, cut.to_datetime64(), side="left")].tail(4)["eps_surprise"].dropna()
            r["beats_last4"] = int((hist > 0).sum()) if len(hist) >= 2 else np.nan
            after = g.iloc[np.searchsorted(tt, cut.to_datetime64(), side="left"):]
            after = after[after["available_at_utc"] <= cut + pd.Timedelta(days=3)]
            if len(after):
                post.append({"accession": e["accession"], "ticker": t, "eps_surprise": after.iloc[0]["eps_surprise"],
                             "sales_surprise": after.iloc[0]["sales_surprise"]})
        g = groups["ins"].get(t)
        if g is not None:
            x = g.iloc[window_slice(g["available_at_utc"].values, cut, 90)]
            b, s = x.loc[x["trans_code"] == "P", "value"].sum(), x.loc[x["trans_code"] == "S", "value"].sum()
            r["ins90_net"] = (b - s) / (b + s) if b + s > 0 else np.nan
            r["ins90_buyers"] = int(x.loc[x["trans_code"] == "P", "owner_ciks"].nunique())
        g = groups["wiki"].get(t)
        if g is not None:
            g2 = g[g["available_at_utc"] < cut]
            d = pd.to_datetime(g2["date"])
            E = pd.Timestamp(e["entry_day"])
            recent = g2.loc[(d >= E - pd.Timedelta(days=7)) & (d < E), "views"].tail(5)
            base = g2.loc[(d >= E - pd.Timedelta(days=95)) & (d < E - pd.Timedelta(days=7)), "views"]
            if len(recent) >= 3 and len(base) >= 30 and base.mean() > 0:
                r["wiki_abn"] = float(recent.mean() / base.mean() - 1)
        rows.append(r)
    f = pd.DataFrame(rows)
    f.to_parquet(args.out / "features.parquet", index=False)
    pd.DataFrame(post).to_parquet(args.out / "post_release.parquet", index=False)
    feats = ["an30_n", "an90_net_pt", "an90_net_rating", "an90_pt_upside", "prior_eps_surprise",
             "prior_sales_surprise", "beats_last4", "ins90_net", "wiki_abn"]
    sched = f[~f["pre_announcement"]]
    cov = sched.groupby(sched["entry_day"].str[:4])[feats].agg(lambda s: round(float(s.notna().mean()), 3))
    rep = {"events_ok": len(f), "scheduled": len(sched), "pre_announcements": int(f["pre_announcement"].sum()),
           "parsed": {"analyst_actions": len(an), "earnings_headlines": len(er), "insider_open_market": len(ins)},
           "coverage_scheduled_by_year": cov.to_dict("index"),
           "an90_n_median": float(sched["an90_n"].median()),
           "post_release_matched": len(post),
           "note": "coverage only; post_release.parquet holds outcomes and is not summarized"}
    (args.out / "report.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
