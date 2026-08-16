# FA Spec — Ticker Discovery via Sentiment + Fundamentals (DRAFT)

**Status:** draft — coded while v3 trains (see `ROADMAP.md`).
**Exception:** Stage 0 (raw collectors) deploys EARLY, on the live-alert
server, because social history cannot be bought retroactively — every month
the collectors run is a month of backtestable history gained.

**One-line goal:** a monthly, timestamped **Top-10 new tickers** ranking built
from social attention, news sentiment, filings NLP, and options flow — with a
forward-return feedback loop that decides which picks graduate into the next
training universe.

---

## Sources

| Source | What we take | Access / cost | Priority |
|---|---|---|---|
| Reddit (r/wallstreetbets, r/stocks, r/options, r/investing + sector subs) | mentions, upvotes, comment velocity per cashtag | official API, free tier is enough for polling | P0 |
| StockTwits | trending list snapshots, message volume, bull/bear tags | free public endpoints | P0 |
| Finnhub news | per-ticker news + sentiment | **key already in .env**; repo already has `sentiment/sentiment_data_loader.py` | P0 |
| AlphaVantage | news sentiment feed | **key already in .env**, same loader | P0 |
| SEC EDGAR | 10-K/10-Q (MD&A, risk factors), **8-K** (timelier than 10-K), **Form 4 insider buys**, 13F clusters, S-1 new listings | free, structured, bulk-downloadable | P0 (filings), P1 (13F) |
| Unusual options activity | volume/OI spikes vs trailing norm | **in-house from Massive data we already have** | P0 |
| Google Trends | search-interest velocity per company | free (pytrends), coarse | P1 |
| Earnings call transcripts | tone deltas quarter-over-quarter | provider needed (Finnhub has some) | P2 |
| X / Twitter | cashtag trends | **$100/mo basic is a trickle; real access $5k/mo — deferred** until the pilot proves social velocity carries signal | P2 |

Not worth it: Discord/Telegram (closed, unarchivable), scraping TradingView
ideas (ToS + noise).

## Architecture (archive-first)

```
collectors (cron, per source)          — dumb by design: fetch, timestamp, append
        ↓
raw archive (append-only parquet, partitioned source/month; never mutated)
        ↓
entity resolution                      — cashtag/company-name → ticker; the
        ↓                                unglamorous hard part (TSLA vs "tesla"
        ↓                                vs $TSLA vs "Elon"); maintain alias map
per-source attention & sentiment scores
        ↓                                velocity, not level: z-score vs each
        ↓                                ticker's own trailing 90-day baseline
composite ranker  ←  fundamental overlay (filings NLP, insider buys, options flow)
        ↓
Top-10 monthly report                  — frozen, timestamped artifact (json+md),
        ↓                                pushed via the live-alert channel
forward-return tracker                 — every pick tracked vs universe baseline
        ↓
graduation rule                        — picks enter the training universe only
                                         after a probation window (e.g. 3 months
                                         of tracking), and enter POINT-IN-TIME
                                         (as of their ranking date, not today)
```

## NLP approach

- Filings (10-K/10-Q/8-K): LLM-scored summaries of MD&A + risk-factor DELTAS
  vs the prior filing (what changed matters more than what's said every year).
  Claude API for extraction/scoring; cache per filing hash — each document is
  scored exactly once, cost stays trivial.
- Social text: cheap first (keyword/emoji polarity + volume), model later only
  if the cheap version shows signal. Volume/velocity usually beats fancy
  sentiment models on social data.
- Everything scored produces: `(ticker, date, source, score, evidence_ref)` —
  evidence links back to raw archive rows so any ranking is auditable.

## Anti-footgun rules

1. **Point-in-time or it didn't happen.** Every score is computed from data
   timestamped before the ranking date. Rankings are frozen artifacts; no
   retroactive edits.
2. **Manipulation resistance.** Social attention is gameable (pump groups).
   Mitigations: require corroboration across ≥2 independent source families
   (social / news / filings / options flow) for top-10 entry; cap the weight
   of any single source; flag tickers with attention spikes but zero options
   volume or institutional presence.
3. **Liquidity floor.** A trending ticker we can't trade options on is
   research trivia, not a candidate. Filter by ADV + options OI before ranking.
4. **The feedback loop is the product.** Forward returns of past top-10s vs
   the existing universe is THE metric. If discovery picks don't outperform
   after 6+ months of tracking, the ranker is redecorating, not discovering.

## Build order

0. **Collectors + raw archive** — Reddit, StockTwits, Finnhub/AV news, EDGAR
   index puller. Deploy on the live-alert server EARLY (see Roadmap). Each is
   ~a page of code plus a cron entry. No analysis yet; just hoard.
1. **Entity resolution + alias map** — cashtag extraction, name→ticker,
   dedupe. Unit-test against a hand-labeled sample.
2. **Attention/sentiment scores** — per-source velocity z-scores; backfill
   from whatever archive exists by then.
3. **Fundamental overlay** — EDGAR filings LLM scoring (delta-focused),
   Form 4 insider-buy screen, in-house unusual-options-activity detector.
4. **Composite ranker + monthly report** — weights start heuristic, documented;
   frozen top-10 artifact + push notification.
5. **Forward-return tracker + graduation rule** — automated monthly scoring of
   all past picks; graduation feeds the v3+ training-universe reconstitution.
6. **(Later, if signal proven)** X integration; earnings-call tone; learned
   ranker weights (replacing heuristics) trained on the tracker's history.

## Open questions

- Ranking cadence: monthly top-10 (as specced) vs weekly top-3 — decide after
  seeing how fast the underlying scores move.
- Does the ranker EXCLUDE current-universe tickers (pure discovery) or rank
  everything and highlight newcomers? (Leaning: rank all, flag new.)
- Probation window length before graduation: 3 vs 6 months.
- LLM scoring budget: which filings sections are worth full-document passes
  vs extraction-only.
