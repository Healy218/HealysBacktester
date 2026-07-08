# v3/universe.py — Stage 1: point-in-time universe selection.
"""200+ names selected by liquidity AS OF the window start (not today's
leaderboard — survivorship bias), reconstituted per config.RECONSTITUTION.
Include delisted names where data permits.

The selected universe is committed AS DATA (artifacts/universe_<year>.json),
not derived at runtime, so every downstream build is reproducible.
"""


def select_universe(as_of: str, size: int) -> list[str]:
    """Liquidity-ranked constituents as of `as_of` (point-in-time)."""
    raise NotImplementedError("Stage 1 — see V3_SPEC.md")
