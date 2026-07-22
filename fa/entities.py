# fa/entities.py — Stage 1: entity resolution (the unglamorous hard part).
"""Cashtag/company-name/nickname → ticker ($TSLA, 'tesla', 'Elon' → TSLA).

The alias map is data (``artifacts/aliases.json``), unit-tested against a
hand-labeled sample.  Ambiguity policy: unresolvable mentions are DROPPED, not
guessed — precision beats recall here.  When a ``valid_tickers`` set is given,
even explicit cashtags must be in it to survive, so noise like ``$LOL`` drops.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Mapping

_CASHTAG = re.compile(r"\$([A-Za-z]{1,6})\b")


def load_aliases(path: str | Path) -> dict[str, str]:
    """Load the alias→ticker map (keys lowercased for case-insensitive match)."""
    raw = json.loads(Path(path).read_text())
    return {str(alias).lower(): str(ticker).upper() for alias, ticker in raw.items()}


def resolve(text: str, aliases: Mapping[str, str], *,
            valid_tickers: Iterable[str] | None = None) -> list[str]:
    """Tickers mentioned in ``text`` (resolved, deduped, sorted).

    Cashtags resolve directly; alias phrases match on word boundaries.  With
    ``valid_tickers`` supplied, anything outside it is dropped.
    """
    valid = {t.upper() for t in valid_tickers} if valid_tickers is not None else None
    found: set[str] = set()
    for tag in _CASHTAG.findall(text):
        found.add(tag.upper())
    low = text.lower()
    for alias, ticker in aliases.items():
        if re.search(rf"\b{re.escape(alias)}\b", low):
            found.add(ticker)
    if valid is not None:
        found &= valid
    return sorted(found)
