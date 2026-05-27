# eToro Trading Bot Plugin

Claude plugin for automated stock trading on eToro — market research, disciplined order execution, stop-loss management, and daily trade journaling. Works with both **demo** and **real** eToro accounts.

## What This Plugin Does

| Capability | Description |
|---|---|
| Pre-trade research | Resolve tickers to eToro instrument IDs, fetch live quotes, compute 20/50-day MAs, pull news |
| Order execution | Place limit orders within 0.2% of ask/bid; enforces 5% per-position size cap |
| Stop-loss management | Automatically closes any position down ≥ 8% from entry |
| Trade journal | Fills `journal_template.md` with live data; writes a dated file to `journals/` |

## Skills

| Skill | Trigger |
|---|---|
| `etoro-research` | "research NVDA", "check portfolio", "what's the MA on TSLA", "show me open positions" |
| `etoro-trading` | "buy $500 of NVDA", "close position 12345", "run stop-loss check", "cancel pending orders" |
| `trade-journal` | "generate today's journal", "fill in the trade journal", "morning brief" |

## MCP Integration

The plugin connects to the eToro MCP server:

```json
{ "mcpServers": { "etoro": { "url": "https://mcp.etoro.com/sse" } } }
```

## Python Scripts (Fallback / Direct Use)

The `scripts/` directory contains standalone Python modules that call the eToro REST API directly. Use these when the MCP server is unavailable or for scripted automation.

### Environment Variables

```bash
export ETORO_API_KEY="your-api-key"
export ETORO_USER_KEY="your-user-key"
export ETORO_ENVIRONMENT="demo"   # or "real"
```

### Research

```bash
python3 scripts/research.py status               # market open/closed
python3 scripts/research.py portfolio            # cash, equity, positions
python3 scripts/research.py resolve NVDA         # ticker → instrument ID
python3 scripts/research.py quote 8104           # live bid/ask
python3 scripts/research.py ma 8104              # 20/50-day moving averages
python3 scripts/research.py news NVDA            # last 7 days of social/news
python3 scripts/research.py research NVDA        # full bundle: ID + quote + MAs + news
python3 scripts/research.py history              # closed trade history
```

### Trading

```bash
python3 scripts/trade.py status                              # market status
python3 scripts/trade.py order 8104 500 buy 882.50 20000     # buy $500 of instrument 8104
python3 scripts/trade.py order 8104 500 sell 882.50 20000    # sell
python3 scripts/trade.py close <positionId>                  # close a position
python3 scripts/trade.py cancel                              # cancel all pending orders
python3 scripts/trade.py stoploss                            # scan + auto-close breached positions
```

## Trading Rules

All three rules are enforced in code and cannot be bypassed:

1. **Market must be open** — no orders when `isOpen` is `false`
2. **5% position cap** — no single position may exceed 5% of total portfolio value
3. **8% stop-loss** — any position down ≥ 8% from entry is closed automatically

Orders are always **limit orders** priced within 0.2% of the current ask (buys) or bid (sells).

## Daily Workflow

| Time | Action |
|---|---|
| 9:45 AM | Run research on all watchlist tickers; review MAs and news |
| 9:45–10:00 AM | Check stop-losses on open positions; close any that breached −8% |
| 10:00 AM–3:45 PM | Place limit orders for approved tickers within size cap |
| 4:00 PM | Generate daily trade journal |

## Requirements

- eToro account (demo or real) with API access
- `ETORO_API_KEY` and `ETORO_USER_KEY` environment variables
- Python 3.9+ with `requests` and `urllib3` (`pip install requests`)
