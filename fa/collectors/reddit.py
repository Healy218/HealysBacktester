# fa/collectors/reddit.py — Stage 0 collector: subreddit posts/comments.
"""Poll config.SUBREDDITS via the official Reddit API (free tier suffices for
polling cadence). Archive rows: ts_utc, subreddit, post_id, title, body,
score, num_comments. Cashtag extraction happens in Stage 1, NOT here —
collectors never analyze. Needs REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in .env.
"""


def collect() -> int:
    raise NotImplementedError("FA Stage 0 — see FA_SPEC.md")
