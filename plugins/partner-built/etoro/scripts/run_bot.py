"""
eToro Trading Bot — daily runner.

Usage:
    python run_bot.py                  # full routine (research + trade + journal)
    python run_bot.py --research-only  # skip trading, just log research
    python run_bot.py --stoploss-only  # only run stop-loss scan

Credentials are loaded automatically from the .env file in the repo root.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# allow imports from the same scripts/ directory
sys.path.insert(0, str(Path(__file__).parent))


def _load_env():
    """Load .env from repo root — works on Windows without source/export."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and not os.environ.get(key):   # don't overwrite existing env vars
            os.environ[key] = val


_load_env()

import research
import trade

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SCRIPT_DIR   = Path(__file__).parent
WATCHLIST    = SCRIPT_DIR.parent / "watchlist.json"
JOURNALS_DIR = SCRIPT_DIR / "journals"
TEMPLATE     = SCRIPT_DIR / "journal_template.md"
ENV          = os.getenv("ETORO_ENVIRONMENT", "demo")


def load_watchlist() -> dict:
    with open(WATCHLIST) as f:
        return json.load(f)


def fill_journal(
    date: str,
    portfolio: dict,
    research_rows: list[dict],
    trades_placed: list[dict],
    stops_closed: list[dict],
) -> str:
    template = TEMPLATE.read_text()
    port_data = portfolio.get("data", {})
    cash      = port_data.get("cash", 0)
    equity    = port_data.get("equity", 0)
    total     = cash + equity

    template = template.replace("{{DATE}}", date)
    template = template.replace("{{CASH}}", f"{cash:,.2f}")
    template = template.replace("{{EQUITY}}", f"{equity:,.2f}")
    template = template.replace("{{TOTAL_VALUE}}", f"{total:,.2f}")
    template = template.replace("{{ENVIRONMENT}}", ENV)

    # Open positions table
    positions = port_data.get("positions", [])
    if positions:
        rows = []
        for p in positions:
            entry  = float(p.get("openRate", 0))
            stop   = round(entry * 0.92, 2)
            rows.append(
                f"| {p.get('instrumentName','')} "
                f"| {p.get('positionId','')} "
                f"| {p.get('amount','')} "
                f"| ${entry} "
                f"| ${p.get('currentRate','')} "
                f"| {p.get('pnlPercent',0):.1f}% "
                f"| ${stop} |"
            )
        template = template.replace(
            "| {{INSTRUMENT}} | {{POS_ID}} | {{QTY}} | ${{ENTRY}} | ${{CURRENT}} | {{PNL_PCT}}% | ${{STOP}} |",
            "\n".join(rows),
        )
    else:
        template = template.replace(
            "| {{INSTRUMENT}} | {{POS_ID}} | {{QTY}} | ${{ENTRY}} | ${{CURRENT}} | {{PNL_PCT}}% | ${{STOP}} |",
            "| — | — | — | — | — | — | — |",
        )

    # Market research blocks
    research_blocks = []
    for r in research_rows:
        ma   = r["moving_averages"]
        news = r.get("news", {})
        posts     = news.get("data", []) if isinstance(news, dict) else []
        news_text = posts[0].get("text", "No recent news")[:120] if posts else "No recent news"
        block = (
            f"### {r['symbol']}\n"
            f"- 20-day MA: ${ma['ma_20']} | 50-day MA: ${ma['ma_50']} — {ma['trend']}\n"
            f"- Latest close: ${ma['latest_close']} — "
            f"{'above' if ma['above_ma_20'] and ma['above_ma_50'] else 'below'} both MAs\n"
            f"- News (last 7 days): {news_text}\n"
            f"- Decision: {r.get('decision', 'Hold')}"
        )
        research_blocks.append(block)

    # Replace the placeholder research block
    old_block = (
        "### {{SYMBOL_1}}\n"
        "- 20-day MA: ${{MA20}} | 50-day MA: ${{MA50}} — {{TREND}}\n"
        "- Latest close: ${{CLOSE}} — {{ABOVE_BELOW}} both MAs\n"
        "- News (last 7 days): {{NEWS_SUMMARY}}\n"
        "- Decision: {{DECISION}}"
    )
    template = template.replace(old_block, "\n\n".join(research_blocks) if research_blocks else "No symbols researched.")

    # Trades executed table
    if trades_placed:
        rows = [
            f"| {t['time']} | {t['symbol']} | {t['action']} "
            f"| ${t['amount']:.2f} | ${t['limit']:.2f} | {t['instrument_id']} | {t['reason']} |"
            for t in trades_placed
        ]
        template = template.replace(
            "| {{TIME}} | {{SYMBOL}} | {{BUY_SELL}} | ${{AMOUNT}} | ${{LIMIT}} | {{INST_ID}} | {{REASON}} |",
            "\n".join(rows),
        )
    else:
        template = template.replace(
            "| {{TIME}} | {{SYMBOL}} | {{BUY_SELL}} | ${{AMOUNT}} | ${{LIMIT}} | {{INST_ID}} | {{REASON}} |",
            "| — | — | — | — | — | — | None today |",
        )

    # Stop-losses
    if stops_closed:
        rows = [
            f"| {s['position_id']} | {s['instrument']} | {s['pnl_pct']:.1f}% | Closed (8% rule) |"
            for s in stops_closed
        ]
        template = template.replace(
            "| {{POS_ID}} | {{INSTRUMENT}} | {{PNL_PCT}}% | Closed (8% rule) |",
            "\n".join(rows),
        )
    else:
        template = template.replace(
            "| {{POS_ID}} | {{INSTRUMENT}} | {{PNL_PCT}}% | Closed (8% rule) |",
            "| — | — | — | None today |",
        )

    # Reflection
    bullish = [r["symbol"] for r in research_rows if r["moving_averages"]["trend"] == "bullish"]
    bearish = [r["symbol"] for r in research_rows if r["moving_averages"]["trend"] == "bearish"]
    reflection = (
        f"Researched {len(research_rows)} symbol(s). "
        f"Bullish: {', '.join(bullish) or 'none'}. "
        f"Bearish: {', '.join(bearish) or 'none'}. "
        f"Placed {len(trades_placed)} trade(s). "
        f"Stop-losses triggered: {len(stops_closed)}."
    )
    watchlist_notes = ", ".join(
        f"{r['symbol']} ({r['moving_averages']['trend']})" for r in research_rows
    )
    template = template.replace("{{REFLECTION}}", reflection)
    template = template.replace("{{WATCHLIST_NOTES}}", watchlist_notes or "—")

    return template


def run(research_only: bool = False, stoploss_only: bool = False):
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    config   = load_watchlist()
    symbols  = config["symbols"]
    amount   = float(config.get("trade_amount_usd", 500))
    max_trades = int(config.get("max_daily_trades", 3))

    log.info("=== eToro Bot starting — %s [%s] ===", today, ENV.upper())

    # 1. Market status
    status = research.get_market_status()
    if not status.get("isOpen", False):
        log.warning("Market is closed. Next open: %s. Exiting.", status.get("nextOpen"))
        sys.exit(0)
    log.info("Market is OPEN")

    # 2. Portfolio
    portfolio = research.get_portfolio()
    port_data = portfolio.get("data", {})
    total_value = float(port_data.get("cash", 0)) + float(port_data.get("equity", 0))
    log.info("Portfolio: total=$%.2f  cash=$%.2f  equity=$%.2f", total_value,
             port_data.get("cash", 0), port_data.get("equity", 0))

    # 3. Stop-loss scan (always runs unless research_only)
    stops_closed = []
    if not research_only:
        positions = port_data.get("positions", [])
        stops_closed = trade.check_stop_losses(positions)
        if stops_closed:
            log.warning("Stop-losses closed: %d position(s)", len(stops_closed))

    if stoploss_only:
        log.info("Stop-loss scan complete. Exiting (--stoploss-only).")
        print(json.dumps({"closed": stops_closed}, indent=2))
        return

    # 4. Research watchlist
    # Build a set of instrument names/tickers already held to avoid re-buying
    held_instruments = {
        str(p.get("instrumentName", "")).upper()
        for p in port_data.get("positions", [])
    }
    held_tickers = {
        str(p.get("ticker", p.get("instrumentTicker", ""))).upper()
        for p in port_data.get("positions", [])
    }
    already_held = held_instruments | held_tickers
    if already_held:
        log.info("Already holding positions in: %s", ", ".join(sorted(already_held)))

    research_rows = []
    for symbol in symbols:
        try:
            log.info("Researching %s ...", symbol)
            bundle = research.research_summary(symbol)
            ma     = bundle["moving_averages"]

            if symbol.upper() in already_held:
                decision = "Hold — position already open"
            elif ma["trend"] == "bullish":
                decision = f"Buy ${amount:.0f}"
            elif ma["trend"] == "mixed":
                decision = "Hold — mixed trend"
            else:
                decision = "Skip — bearish"

            bundle["decision"] = decision
            research_rows.append(bundle)
            log.info(
                "  %s: close=$%s  MA20=$%s  MA50=$%s  trend=%s  → %s",
                symbol, ma["latest_close"], ma["ma_20"], ma["ma_50"],
                ma["trend"], bundle["decision"],
            )
        except Exception as e:
            log.error("Research failed for %s: %s", symbol, e)

    if research_only:
        log.info("Research complete. Exiting (--research-only).")
        return

    # 5. Trade execution — buy bullish symbols not already held, up to max_daily_trades
    trades_placed = []
    for row in research_rows:
        if len(trades_placed) >= max_trades:
            log.info("Daily trade limit (%d) reached.", max_trades)
            break
        if row["moving_averages"]["trend"] != "bullish":
            continue
        if row["symbol"].upper() in already_held:
            log.info("Skipping %s — position already open.", row["symbol"])
            continue
        try:
            quote         = row["quote"]
            ask           = float(quote.get("ask", quote.get("Ask", 0)))
            instrument_id = row["instrument_id"]

            result = trade.place_order(
                instrument_id=instrument_id,
                amount_usd=amount,
                is_buy=True,
                ask_price=ask,
                portfolio_value=total_value,
            )
            limit = trade._calc_limit_price(ask, is_buy=True)
            now   = datetime.now(timezone.utc).strftime("%H:%M")
            trades_placed.append({
                "time":          now,
                "symbol":        row["symbol"],
                "action":        "Buy",
                "amount":        amount,
                "limit":         limit,
                "instrument_id": instrument_id,
                "reason":        f"Bullish MA trend (MA20={row['moving_averages']['ma_20']})",
                "result":        result,
            })
            log.info("Order placed: BUY %s $%.2f @ limit %.2f", row["symbol"], amount, limit)
        except Exception as e:
            log.error("Trade failed for %s: %s", row["symbol"], e)

    # 6. Journal
    JOURNALS_DIR.mkdir(exist_ok=True)
    journal_path = JOURNALS_DIR / f"{today}.md"
    journal_text = fill_journal(today, portfolio, research_rows, trades_placed, stops_closed)
    journal_path.write_text(journal_text)
    log.info("Journal written → %s", journal_path)

    print(f"\nJournal written → {journal_path}")
    print(f"Trades: {len(trades_placed)} | Stop-losses: {len(stops_closed)} | "
          f"Symbols researched: {len(research_rows)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="eToro daily trading bot")
    parser.add_argument("--research-only", action="store_true",
                        help="Run research but skip order execution")
    parser.add_argument("--stoploss-only", action="store_true",
                        help="Only run the stop-loss scan")
    args = parser.parse_args()
    run(research_only=args.research_only, stoploss_only=args.stoploss_only)
