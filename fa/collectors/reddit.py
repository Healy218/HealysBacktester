# fa/collectors/reddit.py — Stage 0 collector: posts AND the comment stream.
"""Poll each config.SUBREDDITS via Reddit's OAuth API (app-only
client_credentials grant — read-only public data, ~100 req/min allowance).

Two archives per run:
- "reddit": one row per POST from /new, deduped on post_id.
- "reddit_comments": newest COMMENTS from the subreddit comment stream
  (/r/<sub>/comments, a few pages), deduped on comment_id. This is where
  the real ticker chatter lives — WSB concentrates it inside daily-
  discussion megathreads whose comments never appear as posts.

Cashtag extraction happens in Stage 1, NOT here — collectors never analyze.
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


def _comment_rows(ts: pd.Timestamp, subreddit: str, listing: dict) -> list[dict]:
    """Flatten one comment-stream listing response into archive rows."""
    rows = []
    for child in listing.get("data", {}).get("children", []):
        d = child.get("data", {})
        if not d.get("name") or not d.get("body"):
            continue
        rows.append({
            "ts_utc": ts,
            "subreddit": subreddit,
            "comment_id": d["name"],
            "link_id": d.get("link_id", ""),      # parent thread (megathread!)
            "created_utc": pd.Timestamp(d.get("created_utc", 0),
                                        unit="s", tz="UTC"),
            "body": d["body"][:2000],
            "score": d.get("score", 0),
        })
    return rows


COMMENT_PAGES = 3          # × 100 newest comments per subreddit per run


def collect() -> int:
    session = requests.Session()
    tok = _token(session)
    headers = {"User-Agent": _UA, "Authorization": f"Bearer {tok}"}
    ts = pd.Timestamp.now(tz="UTC")

    posts: list[dict] = []
    comments: list[dict] = []
    for sub in config.SUBREDDITS:
        r = session.get(f"https://oauth.reddit.com/r/{sub}/new",
                        params={"limit": 100}, headers=headers,
                        timeout=_TIMEOUT)
        r.raise_for_status()
        posts.extend(_post_rows(ts, sub, r.json()))
        after = None
        for _ in range(COMMENT_PAGES):
            r = session.get(f"https://oauth.reddit.com/r/{sub}/comments",
                            params={"limit": 100, "after": after},
                            headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            body = r.json()
            comments.extend(_comment_rows(ts, sub, body))
            after = body.get("data", {}).get("after")
            if not after:
                break
        time.sleep(1)          # 4 subs/run — nowhere near limits, stay polite
    n = archive.append("reddit", pd.DataFrame(posts), key=["post_id"])
    n += archive.append("reddit_comments", pd.DataFrame(comments),
                        key=["comment_id"])
    return n
