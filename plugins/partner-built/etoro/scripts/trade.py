import os
import sys
import json
import uuid
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ETORO_API_KEY  = os.getenv("ETORO_API_KEY")
ETORO_USER_KEY = os.getenv("ETORO_USER_KEY")
ETORO_ENV      = os.getenv("ETORO_ENVIRONMENT", "demo")   # "demo" | "real"
BASE_URL       = "https://public-api.etoro.com/api/v1"

MAX_POSITION_PCT = 0.05    # never exceed 5% of portfolio value
STOP_LOSS_PCT    = 0.08    # close position if down 8% from entry
LIMIT_SLIPPAGE   = 0.002   # limit price within 0.2% of ask/bid

def _headers() -> dict:
    return {
        "x-api-key":    ETORO_API_KEY,
        "x-user-key":   ETORO_USER_KEY,
        "x-request-id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }

def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "DELETE"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def _request(method: str, path: str, **kwargs) -> dict:
    """Authenticated request with error checking."""
    url  = f"{BASE_URL}{path}"
    resp = _session().request(method, url, headers=_headers(), timeout=10, **kwargs)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        log.error("HTTP %s — %s — %s", resp.status_code, url, resp.text[:300])
        raise
    # DELETE /positions/{id} returns 204 No Content
    if resp.status_code == 204 or not resp.content:
        return {"status": "ok"}
    return resp.json()

def get_market_status() -> dict:
    """
    Check if market is open before any trade.
    Returns: { isOpen: bool, nextOpen: str, nextClose: str }
    """
    return _request("GET", "/market-data/status")

def _assert_market_open():
    status = get_market_status()
    if not status.get("isOpen", False):
        raise RuntimeError(
            f"Market is closed. Next open: {status.get('nextOpen', 'unknown')}. "
            "No order placed."
        )

def _calc_limit_price(ask: float, is_buy: bool) -> float:
    """Always use limit orders within 0.2% of ask (buys) or bid (sells)."""
    if is_buy:
        return round(ask * (1 + LIMIT_SLIPPAGE), 2)
    return round(ask * (1 - LIMIT_SLIPPAGE), 2)

def place_order(
    instrument_id: str,
    amount_usd: float,
    is_buy: bool,
    ask_price: float,
    portfolio_value: float,
) -> dict:
    """
    Place a limit order on eToro.

    Args:
        instrument_id:   eToro numeric instrument ID (from research.resolve_instrument_id)
        amount_usd:      Dollar amount to invest
        is_buy:          True = buy, False = sell/short
        ask_price:       Current ask (for buy) or bid (for sell) from research.get_quote()
        portfolio_value: Total portfolio value — used to enforce 5% position cap
    """
    _assert_market_open()

    max_allowed = portfolio_value * MAX_POSITION_PCT
    if amount_usd > max_allowed:
        raise ValueError(
            f"Order amount ${amount_usd:.2f} exceeds 5% portfolio cap "
            f"(${max_allowed:.2f}). Reduce size."
        )

    limit_price = _calc_limit_price(ask_price, is_buy)
    path = f"/trading/execution/{ETORO_ENV}/limit-open-orders/by-amount"

    payload = {
        "InstrumentID": int(instrument_id),
        "Amount":        amount_usd,
        "IsBuy":         is_buy,
        "Rate":          limit_price,   # eToro field name for limit price
    }

    log.info(
        "%s $%.2f of instrument %s @ limit %.2f (%s)",
        "BUY" if is_buy else "SELL",
        amount_usd,
        instrument_id,
        limit_price,
        ETORO_ENV.upper(),
    )

    result = _request("POST", path, json=payload)
    return result

def close_position(position_id: str) -> dict:
    """
    Close an open position by position ID.
    Used for 8% stop-loss rule and end-of-day cleanup.
    """
    _assert_market_open()
    path = f"/trading/execution/{ETORO_ENV}/positions/{position_id}"
    log.info("Closing position %s (%s)", position_id, ETORO_ENV.upper())
    return _request("DELETE", path)

def check_stop_losses(positions: list) -> list:
    """
    Scan open positions for any that have dropped >= 8% from entry.
    Returns a list of positions that were closed.

    Pass in the positions array from research.get_portfolio()["data"]["positions"].
    """
    closed = []
    for pos in positions:
        pnl_pct = float(pos.get("pnlPercent", 0))
        if pnl_pct <= -(STOP_LOSS_PCT * 100):
            log.warning(
                "Stop-loss triggered on position %s: %.1f%% — closing.",
                pos["positionId"],
                pnl_pct,
            )
            result = close_position(str(pos["positionId"]))
            closed.append({
                "position_id":   pos["positionId"],
                "instrument":    pos.get("instrumentName", ""),
                "pnl_pct":       pnl_pct,
                "close_result":  result,
            })
    return closed

def cancel_pending_orders() -> dict:
    """Cancel all pending (unfilled) limit orders for the account."""
    _assert_market_open()
    path = f"/trading/execution/{ETORO_ENV}/orders"
    log.info("Cancelling all pending orders (%s)", ETORO_ENV.upper())
    return _request("DELETE", path)

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"

    if action == "status":
        print(json.dumps(get_market_status(), indent=2))

    elif action == "order":
        # usage: trade.py order <instrument_id> <amount_usd> <buy|sell> <ask_price> <portfolio_value>
        if len(sys.argv) < 7:
            print(
                "Usage: trade.py order <instrument_id> <amount_usd> "
                "<buy|sell> <ask_price> <portfolio_value>",
                file=sys.stderr,
            )
            sys.exit(1)
        instrument_id   = sys.argv[2]
        amount_usd      = float(sys.argv[3])
        is_buy          = sys.argv[4].lower() == "buy"
        ask_price       = float(sys.argv[5])
        portfolio_value = float(sys.argv[6])
        print(json.dumps(
            place_order(instrument_id, amount_usd, is_buy, ask_price, portfolio_value),
            indent=2,
        ))

    elif action == "close":
        # usage: trade.py close <position_id>
        if len(sys.argv) < 3:
            print("Usage: trade.py close <position_id>", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(close_position(sys.argv[2]), indent=2))

    elif action == "cancel":
        print(json.dumps(cancel_pending_orders(), indent=2))

    elif action == "stoploss":
        # reads portfolio and fires closes automatically
        from research import get_portfolio
        portfolio  = get_portfolio()
        positions  = portfolio.get("data", {}).get("positions", [])
        closed     = check_stop_losses(positions)
        print(json.dumps({"closed": closed}, indent=2))

    else:
        print(
            f"Unknown action '{action}'. Valid: status | order | close | cancel | stoploss",
            file=sys.stderr,
        )
        sys.exit(1)
