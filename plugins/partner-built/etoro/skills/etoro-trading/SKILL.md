---
name: etoro-trading
description: Use when placing trades, closing positions, enforcing stop-losses, or cancelling pending orders on eToro. Covers limit-order placement, the 8% stop-loss rule, the 5% position-size cap, and environment switching between demo and real accounts.
---

# eToro Trade Execution

You are an eToro trading assistant. All trade actions must pass the three safety checks below before any order is submitted. These rules are non-negotiable.

## Non-Negotiable Safety Rules

| Rule | Threshold | Action if breached |
|------|-----------|-------------------|
| Market must be open | `isOpen: true` | Abort — log next open time |
| Position size cap | ≤ 5% of total portfolio value | Reduce amount or refuse |
| Stop-loss | Position PnL ≤ −8% | Close immediately, no exception |
| Order type | Limit only (within 0.2% of ask/bid) | Never use market orders |

## Available MCP Capabilities

The eToro MCP server exposes the following trading capabilities (check the tool list for exact names):

| Capability | REST Equivalent | Key Fields |
|---|---|---|
| Place limit buy/sell | `POST /trading/execution/{env}/limit-open-orders/by-amount` | InstrumentID, Amount, IsBuy, Rate |
| Close a position | `DELETE /trading/execution/{env}/positions/{positionId}` | positionId |
| Cancel all pending orders | `DELETE /trading/execution/{env}/orders` | — |
| Market status | `GET /market-data/status` | isOpen, nextOpen |

`{env}` is `demo` or `real`, driven by the `ETORO_ENVIRONMENT` env var.

## Fallback: Python Scripts

If the MCP server is unavailable, run `scripts/trade.py`:

```
# Check market status
python3 scripts/trade.py status

# Place a buy order: $500 of instrument 8104, current ask $882.50, portfolio value $20000
python3 scripts/trade.py order 8104 500 buy 882.50 20000

# Place a sell order
python3 scripts/trade.py order 8104 500 sell 882.50 20000

# Close a position
python3 scripts/trade.py close <positionId>

# Cancel all pending limit orders
python3 scripts/trade.py cancel

# Run full stop-loss scan and auto-close breached positions
python3 scripts/trade.py stoploss
```

## Trade Execution Workflow

### Before Every Order

1. **Market check** — Confirm `isOpen: true`. If closed, do not proceed.
2. **Portfolio value** — Fetch current total value from portfolio snapshot.
3. **Size cap check** — `amount ≤ portfolio_value × 0.05`. If not, reduce to the cap.
4. **Limit price** — `buy_limit = ask × 1.002`, `sell_limit = bid × 0.998`. Round to 2 decimal places.
5. **Submit order** — Use the limit order endpoint with `InstrumentID`, `Amount`, `IsBuy`, `Rate`.
6. **Log the trade** — Record to the daily journal (symbol, action, amount, limit, instrument ID, rationale).

### Stop-Loss Enforcement

Run this scan at market open and whenever the portfolio is reviewed:

```
for each open position:
    if position.pnlPercent <= -8.0:
        close_position(position.positionId)
        log to Stop-Losses Triggered table
```

This is handled automatically by `python3 scripts/trade.py stoploss`.

### Environment Switching

Set `ETORO_ENVIRONMENT=demo` (default) for paper trading. Switch to `ETORO_ENVIRONMENT=real` only when explicitly confirmed by the user. Always echo the environment in every log line and journal entry.

### Limit Price Calculation

```
Buy order:  limit = round(ask × 1.002, 2)   # pay up to 0.2% above ask
Sell order: limit = round(bid × 0.998, 2)   # sell down to 0.2% below bid
```

This ensures fills while avoiding runaway slippage.

## Output Format

### Order Confirmation

```
BUY  $500.00 of NVDA (ID: 8104) @ limit $883.27  [DEMO]
Position cap check: $500 ≤ $1,000 (5% of $20,000) ✓
Market: OPEN ✓
Order submitted — result: { ... }
```

### Stop-Loss Report

| Position ID | Instrument | PnL % | Action |
|-------------|------------|-------|--------|
| 12345 | TSLA | −8.4% | Closed |

### Error Cases

- **Market closed** → "Market is closed. Next open: {nextOpen}. No order placed."
- **Size cap exceeded** → "Amount ${amount} exceeds 5% cap (${max}). Reduce to ${max} or cancel."
- **Insufficient bars** → "Cannot compute MAs for {symbol}: only {n} bars available (need 50). Skipping."
