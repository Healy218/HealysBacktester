# fa/overlay.py — Stage 3: fundamental overlay.
"""Three legs:
1. Filings NLP — LLM-scored summaries of MD&A + risk-factor DELTAS vs the
   prior filing (what changed matters; boilerplate doesn't). Claude API,
   cached per filing hash: each document scored exactly once.
2. Form 4 insider-buy screen (open-market buys, clustered).
3. Unusual options activity — volume/OI spikes vs trailing norm, built from
   the Massive data we already have. In-house edge; no new vendor."""
