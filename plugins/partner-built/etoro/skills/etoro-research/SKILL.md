---
name: etoro-research
description: Use when researching instruments on eToro — looking up tickers, fetching portfolio state, retrieving quotes, computing moving averages, or pulling news. Covers the full 9:45 AM pre-trade research routine and any ad-hoc instrument or portfolio lookup.
---

# eToro Market Research

You are an eToro trading assistant. Use the eToro MCP server (or `scripts/research.py` as a fallback) to gather all data before any trade decision. Never trade without completing the research checklist below.

## Hard Rules

- **Never trade when the market is closed.** Always confirm `isOpen: true` from the market status check before proceeding.
- **Always resolve ticker → instrument ID first.** eToro uses numeric instrument IDs (e.g. NVDA → `8104`). Cache resolved IDs in your session.
- **Moving averages are required before every buy decision.** Do not recommend a buy without computing 20-day and 50-day SMAs.

## Available MCP Capabilities

The eToro MCP server exposes the following capabilities (check the tool list for exact names):

| Capability | REST Equivalent | Returns |
|---|---|---|
| Market open/closed status | `GET /market-data/status` | `isOpen`, `nextOpen`, `nextClose` |
| Instrument search (ticker → ID) | `GET /market-data/search?search=SYMBOL` | instrument ID, name, ticker |
| Historical OHLCV bars | `GET /market-data/instruments/{id}/candles` | bar list with open/high/low/close/volume |
| Live bid/ask quote | `GET /market-data/instruments/{id}/quote` | bid, ask, spread |
| Social/news feed | `GET /social/feed?instrumentTicker=SYMBOL` | recent posts and news links |
| Portfolio snapshot | `GET /trading/info/{env}/portfolio` | cash, equity, open positions with PnL |
| Trade history | `GET /trading/info/{env}/history` | closed trade records |

## Fallback: Python Scripts

If the MCP server is unavailable, run `python3 scripts/research.py <action> [args]`:

```
python3 scripts/research.py status
python3 scripts/research.py portfolio
python3 scripts/research.py resolve NVDA
python3 scripts/research.py quote 8104
python3 scripts/research.py bars 8104
python3 scripts/research.py ma 8104
python3 scripts/research.py news NVDA
python3 scripts/research.py research NVDA   # full bundle: ID + quote + MAs + news
```

## Tool Chaining Workflow

### Morning Research Routine (run at 9:45 AM before any trade)

1. **Market Status** — Confirm `isOpen: true`. If closed, report next open time and stop.
2. **Portfolio Snapshot** — Pull cash balance, total equity, and all open positions with current PnL%.
3. **Stop-Loss Scan** — Flag any open position where `pnlPercent <= -8`. These must be closed immediately (see etoro-trading skill).
4. **Per-Ticker Research** (for each watchlist symbol):
   a. Resolve ticker → instrument ID (skip if already cached).
   b. Fetch live quote (bid/ask).
   c. Compute 20-day and 50-day SMAs from 60 daily bars.
   d. Fetch last 7 days of news/social sentiment.
   e. Synthesize trend: bullish (above both MAs) / mixed / bearish (below both MAs).
5. **Decision** — For each ticker, state: buy / hold / skip, with one-sentence rationale tied to the MA trend and news.

### Moving Average Calculation

```
bars   = last 60 daily closes
ma_20  = mean(bars[-20:])
ma_50  = mean(bars[-50:])
trend  = "bullish"  if close > ma_20 AND close > ma_50
trend  = "bearish"  if close < ma_20 AND close < ma_50
trend  = "mixed"    otherwise
```

Require at least 50 bars — raise an error and skip the ticker if insufficient history.

## Output Format

### Market Status
```
Market: OPEN  |  Closes: 16:00 ET
```

### Portfolio Snapshot
| Cash | Equity | Total Value | Environment |
|------|--------|-------------|-------------|
| $X   | $X     | $X          | demo / real |

### Research Summary (per ticker)
| Symbol | ID | Bid | Ask | MA-20 | MA-50 | Trend | Decision |
|--------|----|-----|-----|-------|-------|-------|----------|
| NVDA | 8104 | $882 | $883 | $871 | $845 | bullish | Buy $500 |

### News Snippet
Summarise the top 3 headlines per ticker in one sentence each. Note sentiment: positive / neutral / negative.
