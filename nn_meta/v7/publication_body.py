"""Conservative reported cash-announcement evidence from captured article bodies.

This verifies what a retained article reported and when that version was
available. It does not turn a news report into an original issuer document or
establish the full action inventory, security identity or adjustment semantics.
"""
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re

import pandas as pd

MONTHS = {name: i for i, names in enumerate([
    ('January', 'Jan'), ('February', 'Feb'), ('March', 'Mar'), ('April', 'Apr'),
    ('May',), ('June', 'Jun'), ('July', 'Jul'), ('August', 'Aug'),
    ('September', 'Sep', 'Sept'), ('October', 'Oct'), ('November', 'Nov'),
    ('December', 'Dec')], 1) for name in names}
DATE = r'(' + '|'.join(MONTHS) + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s+(20\d{2})\b'
DECLARATION = re.compile(r'\b(?:declared|declares|announced|announces|approved)\b'
    r'[^$.;]{0,120}?\b(?:cash\s+)?dividend\s+(?:of\s+|at\s+)?'
    r'\$([0-9]+(?:\.[0-9]+)?)\s*(?:/|per\s+)(?:common\s+)?share\b', re.I)
PAY_DATE = re.compile(r'\b(?:payable|paid|payment\s+date)\b[^0-9$.;]{0,40}?' + DATE, re.I)
RECORD_DATE = re.compile(r'\brecord\b[^0-9$.;]{0,40}?' + DATE, re.I)
AMBIGUOUS = re.compile(r'\b(?:annual|special|variable|preferred|class|ADS|ADR|depositary|not|cancelled|canceled|proposed)\b'
    r'|(?:C\$|A\$|HK\$|\bCAD\b|\bAUD\b|\bEUR\b)', re.I)


class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.parts, self.hidden = [], [], 0

    def flush(self):
        text = ' '.join(' '.join(self.parts).split())
        if text:
            self.blocks.append(text)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'li', 'div', 'br', 'tr', 'h1', 'h2', 'h3', 'h4'):
            self.flush()

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'li', 'div', 'tr', 'h1', 'h2', 'h3', 'h4'):
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _dates(pattern, text):
    found = set()
    for match in pattern.finditer(text):
        month = next(v for k, v in MONTHS.items() if k.lower() == match.group(1).lower())
        try:
            found.add(pd.Timestamp(year=int(match.group(3)), month=month, day=int(match.group(2))).date().isoformat())
        except ValueError:
            return None
    return found


def cash_body_publication(action, article, effective_at):
    if (action.get('currency') != 'USD' or article.get('symbols') != [action.get('ticker')]
            or not article.get('id') or not article.get('url') or not article.get('content')
            or not all(action.get(k) for k in ('declaration_date', 'ex_dividend_date', 'record_date', 'pay_date'))):
        return None
    try:
        amount = Decimal(str(action['cash_amount']))
        created, updated, effective = [pd.Timestamp(t) for t in
            (article.get('created_at'), article.get('updated_at'), effective_at)]
    except (ValueError, TypeError, InvalidOperation):
        return None
    if (not amount.is_finite() or amount <= 0
            or any(pd.isna(t) or t.tzinfo is None for t in (created, updated, effective))
            or not created <= updated < effective
            or created.tz_convert('America/New_York').date().isoformat() != action['declaration_date']
            or effective.tz_convert('America/New_York').date().isoformat() != action['ex_dividend_date']):
        return None
    parser = Paragraphs()
    parser.feed(article['content']); parser.flush()
    matches = []
    for number, text in enumerate(parser.blocks):
        if len(text) > 1800 or AMBIGUOUS.search(text):
            continue
        amounts = {Decimal(m.group(1)) for m in DECLARATION.finditer(text)}
        if (amounts != {amount} or _dates(PAY_DATE, text) != {action['pay_date']}
                or _dates(RECORD_DATE, text) != {action['record_date']}):
            continue
        matches.append(number)
    if not matches:
        return None
    return dict(action_id=action['id'], ticker=action['ticker'], cash_amount=str(amount),
        article_id=article['id'], url=article['url'], created_at=created.isoformat(),
        available_at=updated.isoformat(), author=article.get('author'),
        match_basis='same_paragraph_amount_record_and_pay_dates', paragraph_numbers=matches,
        amount_publication_verified=True, reported_record_date=action['record_date'],
        reported_pay_date=action['pay_date'], original_issuer_document=False,
        effective_date_verified=False, security_identity_verified=False,
        combined_action_units_verified=False, research_ready=False)
