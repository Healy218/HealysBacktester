# v3/audit_data.py — Stage 0: data-availability audit (gates the window).
"""Empirically answer, before anything else in v3 is built:

1. How far back does Massive option-bar (15m) history reach, by year and
   liquidity tier? Per symbol-year: probe the contract listing for mid-year
   expirations, then fetch 15m bars for one sampled contract's final 45 days.
2. How deep is Alpaca 1m history? Per symbol-year: fetch one June week of
   1m bars and count rows.

Output: v3/artifacts/audit_results.parquet + audit_report.md. The report's
conclusion sets the REAL v3 window (config.WINDOW_START is the goal, not the
guarantee).

Run (repo root):  python -m v3.audit_data [--symbols SPY,AAPL,GME]
                                          [--years 2017-2026]
"""
import argparse
import os
from datetime import date, timedelta

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from nn_options_signal import config as nos_config
from nn_options_signal.download_contracts import _get_with_retry
from v3 import config

# Liquidity tiers: mega-liquid index, mega-cap single name, high-IV retail.
DEFAULT_SYMBOLS = ["SPY", "AAPL", "GME"]
BARS_WINDOW_DAYS = 45          # sample each contract's final 45 days of 15m bars


def probe_contracts(session: requests.Session, key: str, symbol: str,
                    year: int) -> list[dict]:
    """Mid-year expirations for symbol/year from the reference endpoint."""
    params = {
        "underlying_ticker": symbol,
        "expiration_date.gte": f"{year}-06-01",
        "expiration_date.lte": f"{year}-09-30",
        "expired": "false" if year >= date.today().year else "true",
        "limit": 100,
        "apiKey": key,
    }
    url = nos_config.MASSIVE_BASE_URL + "/v3/reference/options/contracts"
    body = _get_with_retry(session, url, params)
    return body.get("results", [])


def probe_option_bars(session: requests.Session, key: str,
                      contract: dict) -> dict:
    """15m bar coverage for one contract's final BARS_WINDOW_DAYS."""
    exp = date.fromisoformat(contract["expiration_date"])
    start = exp - timedelta(days=BARS_WINDOW_DAYS)
    url = (f"{nos_config.MASSIVE_BASE_URL}/v2/aggs/ticker/"
           f"{contract['ticker']}/range/15/minute/{start}/{exp}")
    body = _get_with_retry(session, url, {"limit": 50000, "apiKey": key})
    results = body.get("results") or []
    out = {"n_bars": len(results)}
    if results:
        out["first_bar"] = pd.Timestamp(results[0]["t"], unit="ms").date().isoformat()
        out["last_bar"] = pd.Timestamp(results[-1]["t"], unit="ms").date().isoformat()
    return out


def probe_underlying_1m(symbol: str, year: int) -> int:
    """Row count for one June week of Alpaca 1m bars (0 = no data)."""
    from data.alpaca_loader import load_alpaca_bars
    try:
        df = load_alpaca_bars(symbol, f"{year}-06-05", f"{year}-06-12", "1m")
        return len(df)
    except Exception:
        return 0


def _sample_contract(contracts: list[dict]) -> dict | None:
    """A middling-strike call — representative, not cherry-picked."""
    calls = [c for c in contracts if c.get("contract_type") == "call"]
    pool = calls or contracts
    if not pool:
        return None
    pool = sorted(pool, key=lambda c: float(c.get("strike_price", 0)))
    return pool[len(pool) // 2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    ap.add_argument("--years", default="2017-2026")
    args = ap.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    y0, y1 = (int(x) for x in args.years.split("-"))

    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key:
        raise SystemExit("MASSIVE_API_KEY not set")
    session = requests.Session()

    rows = []
    for symbol in symbols:
        for year in range(y0, y1 + 1):
            rec = {"symbol": symbol, "year": year, "n_contracts": 0,
                   "n_bars": 0, "first_bar": None, "last_bar": None,
                   "alpaca_1m_rows": 0}
            try:
                contracts = probe_contracts(session, key, symbol, year)
                rec["n_contracts"] = len(contracts)
                sample = _sample_contract(contracts)
                if sample:
                    rec["sample"] = sample["ticker"]
                    rec.update(probe_option_bars(session, key, sample))
            except Exception as e:
                rec["error"] = str(e)[:120]
            rec["alpaca_1m_rows"] = probe_underlying_1m(symbol, year)
            rows.append(rec)
            print(f"{symbol} {year}: contracts={rec['n_contracts']} "
                  f"15m_bars={rec['n_bars']} alpaca_1m={rec['alpaca_1m_rows']}"
                  + (f" ERROR={rec.get('error')}" if rec.get("error") else ""),
                  flush=True)

    df = pd.DataFrame(rows)
    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.ARTIFACTS / "audit_results.parquet", index=False)

    # verdict: earliest year per symbol with BOTH usable option bars and 1m data
    lines = ["# v3 Stage 0 — data availability audit", "",
             f"Probed {', '.join(symbols)} over {y0}–{y1}. Per symbol-year: "
             "mid-year contract listing, 15m bars for one sampled contract's "
             f"final {BARS_WINDOW_DAYS} days, one June week of Alpaca 1m bars.",
             "", df.to_markdown(index=False), ""]
    for symbol in symbols:
        d = df[df["symbol"] == symbol]
        ok = d[(d["n_bars"] > 100) & (d["alpaca_1m_rows"] > 1000)]
        lines.append(f"- **{symbol}**: earliest fully-usable year = "
                     f"**{int(ok['year'].min()) if not ok.empty else 'NONE'}**")
    (config.ARTIFACTS / "audit_report.md").write_text("\n".join(lines))
    print(f"\nwrote {config.ARTIFACTS / 'audit_report.md'}")


if __name__ == "__main__":
    main()
