import os
import sys
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ETORO_API_KEY  = os.getenv("ETORO_API_KEY")
ETORO_USER_KEY = os.getenv("ETORO_USER_KEY")
ETORO_ENV      = os.getenv("ETORO_ENVIRONMENT", "demo")   # "demo" | "real"
BASE_URL       = "https://public-api.etoro.com/api/v1"

def _headers() -> dict:
    """Fresh headers per request — x-request-id must be unique each call."""
    return {
        "x-api-key":     ETORO_API_KEY,
        "x-user-key":    ETORO_USER_KEY,
        "x-request-id":  str(uuid.uuid4()),
        "Content-Type":  "application/json",
    }

def _session() -> requests.Session:
    """Session with exponential-backoff retry on 429 / 5xx."""
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def _get(path: str, params: dict = None) -> dict:
    """Authenticated GET with error checking."""
    url  = f"{BASE_URL}{path}"
    resp = _session().get(url, headers=_headers(), params=params, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        log.error("HTTP %s — %s — %s", resp.status_code, url, resp.text[:200])
        raise
    return resp.json()

def resolve_instrument_id(symbol: str) -> str:
    """
    eToro identifies instruments by numeric ID, not ticker symbol.
    This call resolves 'NVDA' → '8104' (example) before any trade or data call.
    Result should be cached in watchlist.json to avoid repeated lookups.
    """
    data = _get("/market-data/search", params={"search": symbol})
    instruments = data.get("data", [])
    if not instruments:
        raise ValueError(f"No instrument found for symbol: {symbol}")
    # prefer an exact ticker match when multiple results come back
    for inst in instruments:
        if inst.get("ticker", "").upper() == symbol.upper():
            return str(inst["instrumentId"])
    return str(instruments[0]["instrumentId"])

def get_market_status() -> dict:
    """
    Returns market open/closed status.
    Key fields: isOpen (bool), nextOpen, nextClose.
    Never trade when isOpen is False.
    """
    return _get("/market-data/status")

def get_portfolio() -> dict:
    """
    Current portfolio: cash balance, equity, open positions with PnL.
    Endpoint switches automatically between demo and real via ETORO_ENV.
    """
    path = f"/trading/info/{ETORO_ENV}/portfolio"
    return _get(path)

def get_trade_history() -> dict:
    """Closed trades for the account — useful for journal generation."""
    path = f"/trading/info/{ETORO_ENV}/history"
    return _get(path)

def get_bars(instrument_id: str, period: str = "day", count: int = 60) -> list:
    """
    Historical OHLCV bars for an instrument ID.
    period: 'minute' | 'hour' | 'day' | 'week'
    Returns a list of bar dicts with keys: open, high, low, close, volume, timestamp.
    """
    data = _get(
        f"/market-data/instruments/{instrument_id}/candles",
        params={"period": period, "count": count},
    )
    return data.get("data", {}).get("candles", [])

def get_quote(instrument_id: str) -> dict:
    """Latest bid/ask quote for an instrument — use for limit price calculation."""
    data = _get(f"/market-data/instruments/{instrument_id}/quote")
    return data.get("data", {})

def get_news(symbol: str, days_back: int = 7) -> dict:
    """
    Recent social/news feed for a symbol, limited to the past `days_back` days.
    eToro's social feed endpoint surfaces community sentiment + linked news.
    """
    start = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return _get(
        "/social/feed",
        params={"instrumentTicker": symbol, "limit": 5, "fromDate": start},
    )

def compute_moving_averages(instrument_id: str) -> dict:
    """
    Compute 20-day and 50-day simple moving averages.
    Required before every trade decision.

    Returns:
        {
          "instrument_id": "8104",
          "latest_close":  882.30,
          "ma_20":         871.15,
          "ma_50":         845.60,
          "above_ma_20":   True,
          "above_ma_50":   True,
          "trend":         "bullish" | "mixed" | "bearish"
        }
    """
    bars = get_bars(instrument_id, period="day", count=60)
    if len(bars) < 50:
        raise ValueError(
            f"Insufficient bars for instrument {instrument_id}: "
            f"need 50, got {len(bars)}"
        )

    closes  = [b["close"] for b in bars]
    latest  = closes[-1]
    ma20    = sum(closes[-20:]) / 20
    ma50    = sum(closes[-50:]) / 50
    above20 = latest > ma20
    above50 = latest > ma50

    if above20 and above50:
        trend = "bullish"
    elif not above20 and not above50:
        trend = "bearish"
    else:
        trend = "mixed"

    return {
        "instrument_id": instrument_id,
        "latest_close":  round(latest, 4),
        "ma_20":         round(ma20, 4),
        "ma_50":         round(ma50, 4),
        "above_ma_20":   above20,
        "above_ma_50":   above50,
        "trend":         trend,
    }

def research_summary(symbol: str) -> dict:
    """
    One-shot research bundle: instrument ID + quote + MAs + news.
    Call this for every watchlist ticker during the 9:45 AM routine.
    """
    instrument_id = resolve_instrument_id(symbol)
    return {
        "symbol":          symbol,
        "instrument_id":   instrument_id,
        "quote":           get_quote(instrument_id),
        "moving_averages": compute_moving_averages(instrument_id),
        "news":            get_news(symbol),
    }

if __name__ == "__main__":
    action        = sys.argv[1] if len(sys.argv) > 1 else "portfolio"
    symbol        = sys.argv[2] if len(sys.argv) > 2 else None
    instrument_id = sys.argv[3] if len(sys.argv) > 3 else None

    dispatch = {
        "status":    get_market_status,
        "portfolio": get_portfolio,
        "history":   get_trade_history,
        "research":  lambda: research_summary(symbol),
        "ma":        lambda: compute_moving_averages(instrument_id),
        "bars":      lambda: get_bars(instrument_id),
        "quote":     lambda: get_quote(instrument_id),
        "resolve":   lambda: resolve_instrument_id(symbol),
        "news":      lambda: get_news(symbol),
    }

    fn = dispatch.get(action)
    if fn is None:
        print(f"Unknown action '{action}'. Valid: {list(dispatch)}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(fn(), indent=2))
