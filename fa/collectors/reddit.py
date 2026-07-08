# fa/collectors/reddit.py — Stage 0 collector: subreddit post stream.
"""Poll each config.SUBREDDITS /new listing via Reddit's OAuth API (app-only
client_credentials grant — read-only public data, ~100 req/min allowance).
Archive one row per post, deduped on post_id (first sighting wins; attention
velocity in Stage 2 counts posts, not score evolution). Cashtag extraction
happens in Stage 1, NOT here — collectors never analyze.

Env: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (a "script" app's credentials).
Raises NotImplementedError when unset so fa.collect reports it as skipped.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

from fa import archive, config

_UA = "HealysBacktester/1.0 research (mrhealy115@gmail.com)"
_TIMEOUT = 30
_TOKEN: dict = {"value": None, "expires": 0.0}


def _token(session: requests.Session) -> str:
    if _TOKEN["value"] and time.time() < _TOKEN["expires"] - 60:
        return _TOKEN["value"]
    cid = os.environ.get("REDDIT_CLIENT_ID", "")
    secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not cid or not secret:
        raise NotImplementedError("REDDIT_CLIENT_ID/SECRET not set")
    r = session.post("https://www.reddit.com/api/v1/access_token",
                     auth=(cid, secret),
                     data={"grant_type": "client_credentials"},
                     headers={"User-Agent": _UA}, timeout=_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    _TOKEN["value"] = body["access_token"]
    _TOKEN["expires"] = time.time() + int(body.get("expires_in", 3600))
    return _TOKEN["value"]


def _post_rows(ts: pd.Timestamp, subreddit: str, listing: dict) -> list[dict]:
    """Flatten one /new listing response into archive rows."""
    rows = []
    for child in listing.get("data", {}).get("children", []):
        d = child.get("data", {})
        if not d.get("name"):
            continue
        rows.append({
            "ts_utc": ts,
            "subreddit": subreddit,
            "post_id": d["name"],
            "created_utc": pd.Timestamp(d.get("created_utc", 0),
                                        unit="s", tz="UTC"),
            "title": d.get("title", ""),
            "selftext": (d.get("selftext") or "")[:5000],
            "score": d.get("score", 0),
            "num_comments": d.get("num_comments", 0),
            "permalink": d.get("permalink", ""),
        })
    return rows


def collect() -> int:
    session = requests.Session()
    tok = _token(session)
    ts = pd.Timestamp.now(tz="UTC")
    rows: list[dict] = []
    for sub in config.SUBREDDITS:
        r = session.get(f"https://oauth.reddit.com/r/{sub}/new",
                        params={"limit": 100},
                        headers={"User-Agent": _UA,
                                 "Authorization": f"Bearer {tok}"},
                        timeout=_TIMEOUT)
        r.raise_for_status()
        rows.extend(_post_rows(ts, sub, r.json()))
        time.sleep(1)          # 4 subs/run — nowhere near limits, stay polite
    return archive.append("reddit", pd.DataFrame(rows), key=["post_id"])
