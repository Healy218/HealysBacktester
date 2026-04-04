# Data Sources Guide

## Why yfinance Gets Rate Limited

Yahoo Finance does not have an official public API. yfinance reverse-engineers their endpoints using browser cookies, and Yahoo actively rate-limits bots. You'll see:

```
YFRateLimitError: Too Many Requests. Rate limited. Try after a while.
```

This happens when:
- You download the same symbol multiple times in quick succession
- You run multiple backtest scripts back-to-back without cache hits
- Yahoo's rate limit resets (usually 1–24 hours)

**The cache in `data/cache/` is your best defense.** Once data is downloaded, it never re-downloads unless you delete the cache file or set `force_download=True` in `load_price_data()`.

The data loader now also retries with exponential backoff (up to 4 attempts: 5s, 10s, 20s, 40s waits).

---

## yfinance Intraday Data Limits

Yahoo Finance restricts intraday history regardless of rate limits:

| Interval | Max History |
|---|---|
| 1m | 7 days |
| 5m | 60 days |
| 15m | 60 days |
| 30m | 60 days |
| 1h | 730 days |
| 1D | Full history |

For longer backtests, use daily bars (`INTERVAL: "1D"`) or switch to a better data source.

---

## Better Free Data Sources

### Option 1: Alpaca Markets (Recommended)

Alpaca gives free real-time + historical data with a paper trading account.

**Setup:**
1. Sign up at https://alpaca.markets (free)
2. Create a paper trading account
3. Get your API key from the dashboard
4. Install: `pip install alpaca-py`

**Capabilities:**
- Real-time streaming via websocket
- Up to 5 years of minute bars (free tier)
- No rate limiting on historical pulls
- US equities, crypto

**How to use with this backtester:**

Add to `config/settings.py`:
```python
ALPACA_CONFIG = {
    'API_KEY': 'your_key_here',       # or load from .env
    'API_SECRET': 'your_secret_here', # or load from .env
    'BASE_URL': 'https://paper-api.alpaca.markets',  # paper trading
}
```

Add to `.env` (preferred, keeps secrets out of code):
```
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here
```

Example loader (drop this into `data/alpaca_loader.py`):
```python
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from datetime import datetime
import pandas as pd

def load_alpaca_bars(symbol, start, end, timeframe='5Min',
                     api_key=None, api_secret=None):
    client = StockHistoricalDataClient(api_key, api_secret)

    # Map common interval strings to Alpaca TimeFrame
    tf_map = {
        '1m':  TimeFrame(1, TimeFrameUnit.Minute),
        '5m':  TimeFrame(5, TimeFrameUnit.Minute),
        '15m': TimeFrame(15, TimeFrameUnit.Minute),
        '1h':  TimeFrame(1, TimeFrameUnit.Hour),
        '1D':  TimeFrame(1, TimeFrameUnit.Day),
    }
    tf = tf_map.get(timeframe, TimeFrame(5, TimeFrameUnit.Minute))

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        adjustment='all'  # split + dividend adjusted
    )
    bars = client.get_stock_bars(request)
    df = bars.df

    # Flatten MultiIndex if single symbol
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level='symbol')

    # Rename to standard OHLCV column names
    df = df.rename(columns={
        'open': 'Open', 'high': 'High', 'low': 'Low',
        'close': 'Close', 'volume': 'Volume'
    })
    df.index.name = None
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]
```

---

### Option 2: Polygon.io

Free tier gives 2 years of delayed data (15-min delay). Paid plans have real-time.

- Install: `pip install polygon-api-client`
- Sign up: https://polygon.io
- Free tier: delayed data, limited API calls/minute

---

### Option 3: Stooq (via pandas_datareader)

Completely free, no account needed, daily data only.

```python
import pandas_datareader as pdr
df = pdr.get_data_stooq('AAPL', start='2020-01-01', end='2024-01-01')
df = df.sort_index()  # Stooq returns descending order
```

No intraday data, but unlimited historical daily bars.

---

### Option 4: Fix yfinance with a Session

Sometimes yfinance rate limits can be worked around using a custom session with proper headers:

```python
import yfinance as yf
import requests

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
ticker = yf.Ticker('AAPL', session=session)
df = ticker.history(start='2024-01-01', end='2024-12-31', interval='5m')
```

---

## Real-Time Data (Live Trading / Paper Trading)

For live signal generation you need streaming data. The best free option:

**Alpaca WebSocket stream:**
```python
from alpaca.data.live import StockDataStream

stream = StockDataStream(api_key, api_secret)

async def bar_handler(bar):
    print(f"{bar.symbol} | Close: {bar.close} | Volume: {bar.volume}")

stream.subscribe_bars(bar_handler, 'FUBO', 'SPY')
stream.run()
```

This gives you real-time 1-minute bars as they close. You can feed these into your signal generators to get live entry/exit decisions.

---

## Recommended Setup

For development/backtesting:
- Keep using yfinance with the cache (it works fine once data is downloaded)
- Use daily bars for long historical backtests

For fresh intraday data:
- Set up an Alpaca paper account
- Use `alpaca_loader.py` when you need data newer than what's cached
- The existing `data_loader.py` cache mechanism works with any loader

For live trading:
- Alpaca websocket + paper trading to test your strategies in real-time
- Graduate to live account when strategies are validated
