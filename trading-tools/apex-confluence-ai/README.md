# Apex Confluence AI — Adaptive Multi-Factor Signal Engine (XAUUSD)

A TradingView **Pine Script v6** indicator that fuses ~12 classic factors into a
single weighted *confluence score*, prints **entry / take-profit / stop-loss**
signals, **self-backtests across your chart history**, and **adapts its own
strictness based on its recent win-rate**. Built and tuned with XAUUSD (gold) in
mind, including high-volatility regimes.

> File: [`ApexConfluenceAI.pine`](./ApexConfluenceAI.pine)

---

## ⚠️ Read this first — what "AI" honestly means here

TradingView's Pine Script **cannot** run machine learning, train a model, call a
news API, or remember anything once the chart reloads. So this tool does the most
capable, *honest* version of "an AI that learns from its mistakes":

| You asked for | What this actually does | Real or marketing? |
|---|---|---|
| AI that learns from mistakes | Tracks its own win/loss outcomes and **raises the score threshold after losing streaks / lowers it after winning streaks** | Real, but it's a feedback heuristic — **not** ML |
| Constantly backtests the chart | Replays every loaded bar, simulates each trade to TP/SL/force-exit, shows live **win-rate, profit-factor, net points** | Real |
| News awareness | **You** define blackout windows; it mutes signals inside them | Real (manual) — Pine can't read news feeds |
| Volume confirmation | Uses the feed's volume vs its average | Real, but most XAUUSD feeds are **tick** volume, not true volume |
| Improves itself over time | Adapts threshold *within the current chart session only*; resets on reload | Honest limitation |

If a vendor sells you a Pine script that claims real AI/ML or true news reading,
they're overselling. This one tells you exactly what it is.

---

## What's inside the signal

**12 weighted factors**, each voting bull / bear / neutral:

1. EMA fast vs slow (trend)
2. EMA-200 bias
3. Higher-timeframe trend (non-repainting read)
4. ADX / DMI (trend strength + direction gate)
5. RSI
6. MACD (line + histogram)
7. Stochastic
8. Relative volume (confirms candle direction)
9. VWAP
10. Supertrend
11. Bollinger breakout
12. Support/Resistance proximity (from confirmed pivots)

Votes × weights → **score**. A signal fires only when **everything** agrees:
`|score| ≥ adaptive threshold`, the trend filters agree, you're outside a
news-blackout/session window, **and the 3-question pre-trade checklist passes**
(see below). It then projects:

- **Entry** = bar close
- **Stop (SL)** = `ATR × multiplier` away
- **TP1 / TP2 / TP3** = `risk × 1.5 / 2 / 3` (TP1 is the primary + backtest target)

### Force-exit / invalidation
While a trade is open, if the thesis breaks **before** TP/SL — price crosses the
slow-EMA against you, or the score flips hard to the opposite side — it prints a
magenta **`EXIT`** marker and fires a force-exit alert so you can bail manually.

### Dashboard
A live table (corner of your choice) shows the current signal, score vs max,
adaptive threshold, entry/TP/SL, every factor's reading + vote, the
self-backtest stats (trades, win-rate, profit factor, net points, recent win-rate),
**and the pre-trade checklist with a TAKE/SKIP verdict.**

### The 3-question checklist (hard gate — ON by default)
Discipline beats indicators. Every signal must pass all three or it is **skipped**:

1. **With the trend?** Up day → longs only, down day → shorts only. "Today" is
   measured from the **daily open**. (Optional: allow a counter-trend entry only
   on a strong reversal / change-of-character — off by default.)
2. **At a level?** Price must sit at structure — a pivot **S/R**, **VWAP**, or a
   **round number** — not mid-chop. Distance is measured in ATR.
3. **SL + TP set before entry?** The engine never signals without a stop and
   targets already computed, so this is guaranteed by construction.

The dashboard shows ✓/✗ for each plus a final **✔ TAKE / ✘ SKIP** verdict, so you
can see *why* a setup was skipped. Toggle the whole gate (or each item) in the
**"✅ Pre-trade checklist"** settings group.

### Trade zones (the screenshot look)
On each signal it draws the setup as stacked boxes projecting to the right: a red
**SL** zone, a dashed **Entry** line with a **BUY/SELL** badge showing
`score | confidence%`, and green **TP1 / TP2 / TP3** zones with price tags. TP1 is
what the backtest banks; TP2/TP3 are stretch targets for runners. Tune them in the
**"Trade zones"** settings group (`showLevels` flat lines are off by default).

---

## Install on TradingView

1. Open a **XAUUSD** chart → bottom panel → **Pine Editor**.
2. Paste the full contents of `ApexConfluenceAI.pine`.
3. Click **Save**, then **Add to chart**.
4. Open the indicator's **⚙ Settings** to tune (see below).

### Alerts (so it pings you)
- **Rich, dynamic message** (entry price + TP + SL + confidence): create an alert,
  set **Condition → Apex Confluence AI → "Any alert() function call"**.
- **Per-event** (separate Long / Short / Force-Exit / TP / SL alerts): use the
  `alertcondition` triggers of the same names.
- Set **"Once per bar close"** to match the non-repaint logic.

---

## Tuning guide

### Scalping XAUUSD on 1-minute (your main use)
- Timeframe: **1m**, HTF filter: **15m** (default).
- `Base confluence threshold`: start **4.0**. Too many signals → raise to 5–6.
- `Stop = ATR ×`: **1.2–1.5**; `Reward:Risk`: **1.2–1.5** (gold whips on 1m).
- `Cost per trade`: set to your real spread+commission (gold ≈ **0.20–0.40**).
- Keep **News blackout ON** and set windows around 12:30 & 18:00 GMT
  (US data / FOMC). Adjust to your broker's timezone via the `Timezone` input.

### Swing / intraday (≤ 3 hours holds)
- Timeframe: **15m or 1H**, HTF filter: **4H**.
- Raise `Stop = ATR ×` to **2.0–2.5** and `Reward:Risk` to **2.0+**.
- Lengthen pivots (`Pivot left/right`) for cleaner structure.

### High-volatility / geopolitical regimes
- ATR widens automatically, so stops/targets scale with it.
- Raise the **base threshold** (more confluence required) and **keep adaptive ON**
  — after a cluster of losses it tightens itself.
- Widen the news blackout windows around scheduled headlines.

### Make it pickier / looser
- **Adaptive strength** controls how hard win-rate moves the threshold (0 = off).
- Drop factor **weights** you don't trust to zero; raise the ones you do.

---

## Known limitations & gotchas

- **Resets on reload.** Adaptive stats are session-only; Pine can't persist them.
- **Backtest is optimistic-bounded.** On a bar that touches both TP and SL, it
  assumes **SL first** (conservative), but real intrabar fills/slippage/gaps can
  still differ. Costs beyond your `Cost per trade` input aren't modeled.
- **Tick volume**, not real volume, on most gold feeds.
- **Live bar can flip** until it closes; historical signals don't repaint.
- If you ever see a *"could not be determined / bars_back"* compile error after
  heavy edits, add `max_bars_back = 1000` to the `indicator(...)` call.

## Two files: indicator + strategy
| File | Use it for |
|---|---|
| `ApexConfluenceAI.pine` | **Live trading** — signals, alerts, force-exit, zones, dashboard. |
| `ApexConfluenceAI_Strategy.pine` | **Backtesting & optimization** — same engine routed through TradingView's **Strategy Tester** (real fills, commission, slippage, equity curve, max-drawdown, trade list). |

### How to actually optimize (without fooling yourself)
The strategy file is the only honest way to tune settings:
1. Add `ApexConfluenceAI_Strategy.pine` to a XAUUSD chart.
2. **Settings ▸ Properties:** set Commission + Slippage to your broker's real numbers.
3. Pick **one** date range (in-sample). Adjust a *few* inputs at a time — threshold,
   ATR stop, R:R, weights. Watch **profit factor and max-drawdown**, not just net profit.
4. **Validate out-of-sample:** lock those settings and check a *different, unseen*
   date range. If it falls apart, you curve-fit — loosen and retry.
5. Prefer a broad **plateau** of decent settings over a single razor-thin peak; that's
   what survives a regime change (e.g. a geopolitical shock).

> TradingView's automated parameter optimizer is a Premium feature; on lower tiers,
> sweep inputs manually and record results. Either way, **in-sample → out-of-sample**
> discipline is what separates a real edge from a pretty backtest.

---

### Disclaimer
Educational tool, **not financial advice**. Markets — gold especially during
geopolitical stress — can move violently and gap. Past/backtested performance does
not predict future results. Forward-test on a demo account and risk only what you
can afford to lose. Every trade you place is your own decision.
