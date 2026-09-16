"""Narrow original-announcement matching; price/action admission is separate.

A matched headline proves an amount was published by its retained update
clock. It does not prove security continuity, effective dates, combined-action
units, or the correctness of a current provider adjustment factor.
"""
from decimal import Decimal, InvalidOperation
import re
import pandas as pd

AMOUNT = r'([0-9]+(?:\.[0-9]+)?)'
UNIT = r'\s*(?:/|\bper\s+)(?:common\s+)?share\b'
PATTERNS = (
    re.compile(r'\b(?:raises|increases|boosts)\b.*?\bdividend\b.*?\bto\s*\$'+AMOUNT+UNIT, re.I),
    re.compile(r'\b(?:declares|announces|maintains)\b.*?\b(?:dividend|distribution)\b\s*(?:of|at)?\s*\$'+AMOUNT+UNIT, re.I),
    re.compile(r'\b(?:declares|announces|maintains)\b.*?\$'+AMOUNT+UNIT+r'(?:\s+\w+){0,5}\s+(?:dividend|distribution)\b', re.I),
)


def cash_publication(action, article, effective_at):
    """Return exact amount-publication evidence or None; never guess missing units."""
    headline = article.get('headline', '')
    if (action.get('currency') != 'USD' or article.get('symbols') != [action.get('ticker')]
            or not action.get('declaration_date') or not article.get('id') or not article.get('url')
            or re.search(r'(?:C\$|A\$|HK\$|\bCAD\b|\bAUD\b|\bEUR\b)', headline, re.I)):
        return None
    try:
        amount = Decimal(str(action['cash_amount']))
        created, updated, effective = (pd.Timestamp(t) for t in
            (article.get('created_at'), article.get('updated_at'), effective_at))
    except (ValueError, TypeError, InvalidOperation):
        return None
    if (not amount.is_finite() or amount <= 0
            or any(pd.isna(t) or t.tzinfo is None for t in (created, updated, effective))
            or not created <= updated < effective
            or created.tz_convert('America/New_York').date().isoformat() != action['declaration_date']
            or effective.tz_convert('America/New_York').date().isoformat() != action['ex_dividend_date']):
        return None
    amounts = {Decimal(match.group(1)) for pattern in PATTERNS for match in pattern.finditer(headline)}
    if amounts != {amount}:
        return None
    return dict(action_id=action['id'], ticker=action['ticker'], cash_amount=str(amount),
                article_id=article['id'], url=article['url'], created_at=created.isoformat(),
                available_at=updated.isoformat(), amount_publication_verified=True,
                effective_date_verified=False, security_identity_verified=False,
                combined_action_units_verified=False, research_ready=False)
