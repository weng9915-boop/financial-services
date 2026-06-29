---
name: london-session
description: Use when trading gold (XAUUSD) during the London session, deciding whether to take a trade, or checking a setup against the discipline rules. Enforces the London-only session window, the 2-trade / 2-loss lockout, trend-direction filter, sweep-edge entry, 1:2.1 TP/SL ratio, and the 5-point pre-trade checklist. Generates SIGNAL / ALERT / SKIP decisions, never auto-entries.
---

# London Session Trading Rules (XAUUSD)

A disciplined, alert-only gold scalping system for the **London session only**. This skill
is a *coach and gatekeeper*, not an auto-trader: it produces **SIGNAL / ALERT / SKIP**
decisions and never places an order on its own. The user always clicks BUY/SELL.

> The three rules that matter most — where the real money was lost — are hard-coded:
> **(1) session + state lockout, (2) trend-direction filter, (3) confirmation gate.**
> Everything else (CCI, Stoch, Fib) is confluence polish.

## How to Use

When the user asks "can I take this trade?", "check this setup", "is the session open?",
or describes a price/level/volume situation, run the decision engine:

```bash
python3 scripts/london_session.py check \
  --trend up --price 2358.0 --prev-high 2362.0 --prev-low 2356.0 \
  --volume 720 --candle-closed --engulfing --atr 18 --rsi 48 \
  --trades-today 0 --losses-today 0 --news-minutes 300
```

The script returns a decision plus the computed entry / SL / TP and the reason every gate
passed or failed. Use `--now "2026-06-29T15:20"` to override the clock (MYT) for back-checks.
If any gate fails the answer is **SKIP** — relay the failed gate to the user verbatim and
do not soften it.

For charting, `scripts/london_session.pine` is the TradingView (Pine Script v5) version of
the same rules — paste it into the Pine Editor on an XAUUSD chart. It plots the sweep-edge
levels, shades the session, and fires LONG/SHORT/approaching alerts. It is alert-only and
shares this skill's gates; news blackout and the 2-loss lockout are manual inputs there.

## 1. Core Rules (non-negotiable)

| Rule | Value |
|------|-------|
| Session | London only — **3:00–5:30 PM MYT**. Hard exit 5:30 PM. |
| Never trade | Asian session, or NY session 9 PM+ |
| Max trades | **2 per session** |
| Loss lockout | **2 losses → stop 24 hours** |
| TP hit | Close the platform for the session |
| News blackout | No entry within **2 hrs** of NFP / CPI / Fed |
| Lot size | Consistent **0.02** — never revenge-size up |

## 2. Direction Engine — trade WITH the trend only

- Set session direction **once, at the open**: lower highs ⇒ **SHORT all session**;
  higher lows ⇒ **LONG all session**.
- **Flip only** after 2 consecutive opposing candles **+** volume. Never flip on one bounce.
- **News-first override**: check news direction *before* technicals every time. News overrides
  technicals. Never short into bullish news momentum (or vice versa).
- **Correlation confirm** (validated drivers): DXY ↔ Gold strong negative (most reliable);
  real yields / 10Y TIPS ↔ Gold negative (#1 driver); Fed hawkish ⇒ gold down; oil spike
  (only on real supply cut) ⇒ gold up.

## 3. Entry Logic — the sweep-edge method

- Enter at the **furthest institutional sweep point, NOT the level**. Look LEFT for liquidity:
  round numbers, prior session high/low, equal highs/lows.
- **Entry formula** (deep sweep edge): Short = prev **HIGH + 12 pips**; Long = prev **LOW − 12 pips**.
- **Sweep vs breakout**: low-volume tap that reverses = SWEEP (fade it, enter). High-volume
  break that continues = BREAKOUT (follow, don't fade). A 15+ pip break on high volume is a
  real breakout — the SL stays.
- The truth: *"Enter in the pullback of a trend, in the direction it wants."*
  *"If it feels like a good entry, it's a scam — a good point feels like a big risk."*

## 4. TP / SL — the finalized ratio

- **Stop-loss**: place *beyond* the sweep (swing high/low + 8–12 pip sweep + ATR). ATR buffer:
  scalp = 0.5× ATR(14) ≈ 10 pips, swing = 1× ATR(14) ≈ 15–25 pips. **Never widen a stop** —
  widening means the setup was wrong.
- **Take-profit** (single TP, no partials): ST scalp SL 5 → TP ~10; LT SL 20 → TP ~42–50.
- **Ratio: 1:2.1 minimum** (break-even win rate = 32.3%). Place TP on the nearest opposing
  liquidity level. If that level is closer than 2.1R, **SKIP** the trade.

## 5. Confirmation Stack

- **Volume**: <400 = too low, skip · 500 = direction building · 700 = direction confirmed.
- **Candle**: see engulfing FIRST, signal SECOND. Wait for candle **CLOSE** through the level,
  not the wick. No engulf + no signal = SKIP.
- **Indicators (confluence)**: RSI zones · Stochastic 5,3,3 (5m, wait for confirmation) ·
  CCI direction · EMA touch-then-enter (no close beyond it) · FVG + sweep + order block (ICT) ·
  multi-timeframe M30→M15→M5. Don't trade against the oscillators.

## 6. The 5-Point Pre-Trade Checklist (gate every trade)

Before clicking BUY/SELL, **ALL** must be YES — any "no" = SKIP:

1. WITH the trend? (down ⇒ short only, up ⇒ long only)
2. Price AT a level? (not mid-chop)
3. In discount (long) / premium (short)?
4. Liquidity swept / confirmed?
5. TP + SL set BEFORE entering?

Too close to the previous trade = skip.

## 7. Psychology Gates

Do **not** trade when: tired / drunk / just woke up; not at the laptop (no phone impulse
trades); feeling FOMO; trying to win back a loss (revenge). Mindset: humility ("starting a
trade confirms you'll lose money"), survival > winning big, +$100–150/day is enough,
consistency > home runs. Don't predict — set up and follow the plan.

## 8. Decision Engine Output

The script reports one of three outcomes:

| Decision | Meaning |
|----------|---------|
| **SIGNAL** | All gates pass — setup is valid. Shows entry, SL, TP, R-multiple. |
| **ALERT** | Price approaching a key sweep level but confirmation not yet in — watch, don't enter. |
| **SKIP** | One or more gates failed — names the gate(s). No trade. |

**Auto-skip flags** (any one ⇒ SKIP): news within 2 hrs · Asian/NY session · volume < 400 ·
already 2 trades or 2 losses · against trend.

Always echo the failed/passed gates to the user. Never convert a SKIP into a SIGNAL because
the user is impatient — that is exactly the FOMO the notes warn about.
