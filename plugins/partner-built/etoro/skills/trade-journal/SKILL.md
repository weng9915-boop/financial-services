---
name: trade-journal
description: Use when generating or updating the daily trade journal. Fills in the journal_template.md with live portfolio data, executed trades, stop-loss events, moving average research, and an end-of-day reflection. Run at market close or on demand.
---

# Daily Trade Journal

Generate a structured daily journal by combining data from the eToro research and trading skills into `scripts/journal_template.md`.

## When to Run

- **End of trading day** — after the market closes, produce the full journal.
- **On demand** — user asks "generate today's journal" or "fill in the trade journal".
- **Morning brief** — a partial journal (Portfolio Status + Market Research sections only) can be generated at 9:45 AM before trades are placed.

## Data Sources

Collect these before filling the template:

| Section | Source |
|---------|--------|
| Portfolio Status (cash, equity, total) | `research.get_portfolio()` or portfolio MCP tool |
| Open Positions table | Same portfolio response — `data.positions` |
| Market Research per symbol | `research.research_summary(symbol)` for each watchlist ticker |
| Trades Executed | `research.get_trade_history()` filtered to today's date |
| Stop-Losses Triggered | Positions closed by the stop-loss scan (pnlPercent ≤ −8%) |
| End-of-Day Reflection | Claude synthesises from the day's data — see Reflection Guidelines |

Fallback for all data: run `python3 scripts/research.py portfolio` and `python3 scripts/research.py history`.

## Template Variable Map

The template uses `{{PLACEHOLDER}}` tokens. Replace every token:

| Token | Value |
|-------|-------|
| `{{DATE}}` | Today's date — YYYY-MM-DD |
| `{{CASH}}` | Portfolio cash balance |
| `{{EQUITY}}` | Portfolio equity (open positions mark-to-market) |
| `{{TOTAL_VALUE}}` | Cash + Equity |
| `{{ENVIRONMENT}}` | `demo` or `real` from `ETORO_ENVIRONMENT` |
| `{{INSTRUMENT}}` | Position instrument name |
| `{{POS_ID}}` | Position ID |
| `{{QTY}}` | Units held |
| `{{ENTRY}}` | Average entry price |
| `{{CURRENT}}` | Current mark-to-market price |
| `{{PNL_PCT}}` | PnL % (positive or negative) |
| `{{STOP}}` | Calculated stop price = entry × 0.92 (8% below entry) |
| `{{SYMBOL_1}}` | Watchlist ticker researched today |
| `{{MA20}}` | 20-day SMA |
| `{{MA50}}` | 50-day SMA |
| `{{TREND}}` | bullish / mixed / bearish |
| `{{CLOSE}}` | Latest daily close price |
| `{{ABOVE_BELOW}}` | "above" or "below" |
| `{{NEWS_SUMMARY}}` | 1-sentence summary of top news item |
| `{{DECISION}}` | Buy / Hold / Skip with one-sentence rationale |
| `{{TIME}}` | Trade execution time (HH:MM ET) |
| `{{SYMBOL}}` | Traded ticker |
| `{{BUY_SELL}}` | Buy or Sell |
| `{{AMOUNT}}` | Dollar amount |
| `{{LIMIT}}` | Limit price used |
| `{{INST_ID}}` | eToro instrument ID |
| `{{REASON}}` | Trade rationale (1 sentence) |
| `{{REFLECTION}}` | End-of-day reflection (see below) |
| `{{WATCHLIST_NOTES}}` | Tickers to watch tomorrow, with brief note |

If a section has no data (e.g. no stop-losses triggered, no trades), replace the table row tokens with a single "None today." line.

Repeat table rows as needed — duplicate the row template for each position, trade, or event.

## Reflection Guidelines

The `{{REFLECTION}}` block should be 3-5 sentences covering:
1. Whether the day's research thesis played out (MA trends vs. actual price moves).
2. Any trades that worked well and why.
3. Any trades that did not work or stop-losses that fired — lessons learned.
4. One thing to do differently tomorrow.

Keep it factual and brief. Do not inflate gains or minimize losses.

## Output

Write the completed journal to a file named `journals/YYYY-MM-DD.md` (create the `journals/` directory if it does not exist). Print a one-line summary to stdout:

```
Journal written → journals/2026-05-27.md
Trades: 2 | Stop-losses: 0 | P&L today: +$142.30
```
