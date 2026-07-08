# fa/entities.py — Stage 1: entity resolution (the unglamorous hard part).
"""Cashtag/company-name/nickname → ticker ($TSLA, 'tesla', 'Elon' → TSLA).
Maintain an alias map as data (artifacts/aliases.json), unit-tested against a
hand-labeled sample. Ambiguity policy: unresolvable mentions are DROPPED, not
guessed — precision beats recall here."""


def resolve(text: str) -> list[str]:
    """Tickers mentioned in `text` (resolved, deduped)."""
    raise NotImplementedError("FA Stage 1 — see FA_SPEC.md")
