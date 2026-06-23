# Apex trading tools (XAUUSD) — Pine v6

### ⭐ Newest: `ApexMTFSniper.pine` — Apex MTF Sniper
A multi-timeframe sniper built from proven reference indicators, fused into one
locked signal:
- **Entry** = **UT Bot** (ATR trailing stop) on your chart's timeframe (1m) — the
  fakeout-filtered trigger.
- **Direction** = **VIDYA** trend computed on **1H** in the background, shown on 1m
  (longs only in a 1H uptrend).
- **Momentum** = **Two-Pole Oscillator** on **1H**, shown on 1m (must be bullish
  post change-of-character for longs).
- **Fakeout filter** = **KDE-optimised RSI** (Flux-style kernel-density on RSI
  pivots) — blocks entries into the statistical reversal zone. Simple RSI also available.
- On confirmation it **LOCKS** Entry / SL (safer of UT-Bot trail or swing) / TP
  (fixed 1:2) — levels never move. Non-repainting on closed bars.

> The 1H trend + momentum are pulled onto your 1m chart so you never flip timeframes.
> **1H read mode**: *Balanced* (live but must hold N bars — fast, no flip-flop),
> *Locked* (closed 1H bars only — zero repaint), or *Early* (live, can flicker).
> KDE is compute-heavy; if the chart lags, lower **KDE bins**.

### Also in this folder
- **`ApexConfluenceAI.pine`** — *Apex Trend-Pullback AI* (EMA-pullback model, below).
- **`ApexConfluenceAI_Strategy.pine`** — the Strategy-Tester version of the pullback model.

---

## Apex Trend-Pullback AI

A TradingView indicator + strategy that trades **with the trend**, enters on a
**pullback to the fast EMA + a confirmation candle**, and manages risk with a
**structure-based stop and a fixed 1:2 target** that is **locked at entry and
never moves**. Built for XAUUSD (gold), 1-minute and intraday.

## Why v2 (what changed and why)
v1 fired when a confluence **score crossed a threshold** — i.e. *after* the move
had already happened. On 1m gold that means buying the exhaustion of a swing, so
price reverts straight into the stop (the "every trade hits SL" problem). v2
flips the logic to a **trend pullback**, which is the entry that actually wins:

- **Direction is gated, not scored.** A long is only *possible* in an uptrend
  (EMA fast > slow **and** price > EMA200 **and** higher-TF up **and** day is up).
  Shorts mirror it. No more counter-trend fades.
- **Entry is a pullback, not a chase.** Price must dip back to the **fast EMA**
  within the look-back, then print a **confirmation candle** that closes back
  through it. You enter on the dip-and-go, not the extension.
- **Stop sits beyond structure.** The stop is the *further* of the recent swing
  low/high (+ an ATR buffer) or an ATR floor — so normal noise can't wick you out.
- **Fixed 1:2.** One stop, one target at `risk × 2`, locked the instant the
  signal prints. The score is now just a **confirmation filter** (do the
  indicators agree with the trend?), not the trigger.

## What you see on the chart
- 🔺/🔻 a **BUY/SELL** triangle on the confirmation bar (fires on **bar close**, never repaints).
- A **zone**: red **SL** box, dashed **Entry** line with a badge (`score | confidence%`),
  green **TP** box — all **frozen at entry** and attached to price (no floating ahead).
- A **dashboard** with the 3-question checklist (✓/✗ + TAKE/SKIP verdict), the
  confirmation-indicator grid, and a live self-backtest (trades, win%, profit factor).

## The checklist (the discipline, enforced)
Every signal must pass all three or it's **skipped**:
1. **With the trend?** Up day → longs only, down day → shorts only (day measured from the daily open).
2. **Pullback entry?** Price pulled back to the fast EMA and confirmed — not mid-chop, not chasing.
3. **SL + TP fixed?** Always — a structure stop and a 1:2 target are set before entry, and frozen.

---

## Install on TradingView
1. Open a **XAUUSD** chart → **Pine Editor**.
2. Paste `ApexConfluenceAI.pine` → **Save** → **Add to chart**. (It's Pine **v6** — if the editor complains, you're on an old version tab.)
3. Open **⚙ Settings** to tune.

### Alerts
- Rich message (entry/TP/SL): alert on **"Any alert() function call"**.
- Or per-event: `Apex Long Entry`, `Apex Short Entry`, `Apex Force Exit`.
- Use **"Once per bar close."**

---

## Tuning guide (XAUUSD)
**1-minute scalping (main use):** HTF filter 15m. Keep `useDayBias` ON.
`Pullback look-back` 6, `Pullback reach` 0.5×ATR. Stop: `Min stop` 1.0×ATR,
`Swing look-back` 10, `buffer` 0.3×ATR. R:R 2.0.

**Too few signals?** Loosen in this order: raise `Pullback reach` to 0.8–1.0,
lower `Min confluence score`, or turn off `useDayBias`. **Too many / choppy?**
Raise `Min confluence score`, raise `ADX min`, or shorten the trading session to
London/NY only.

**Fewer SL hits / let winners run:** widen the stop (`Min stop` 1.5×ATR or larger
`Swing look-back`). Remember a wider stop = a farther 1:2 target, so it trades
slower — that's the trade-off, and it's the honest one.

**Force-exit** is OFF by default so trades run cleanly to SL or TP ("keep it
fixed"). Turn it on if you want the trade closed when price crosses the slow EMA
against you.

---

## Backtest & optimize honestly (`..._Strategy.pine`)
The strategy file runs the identical model through TradingView's **Strategy
Tester** (real fills, equity curve, drawdown, risk-% position sizing).

1. Add it to a XAUUSD chart.
2. **Settings ▸ Properties:** set **Commission + Slippage** to your broker's real
   numbers, or the results are fiction.
3. Optimize on **one** date range — change a *few* inputs at a time, watch
   **profit factor and max-drawdown**, not just net profit.
4. **Validate out-of-sample:** lock the settings, test a *different unseen* range.
   If it falls apart, you curve-fit. Prefer a broad **plateau** of decent
   settings over one razor-thin peak — that's what survives a regime change.

---

## Honest limitations
- **No real ML.** "Adaptive" = it raises the score threshold after a losing
  streak; it resets when the chart reloads. Pine can't train or persist a model.
- **No news feed.** You set the blackout windows (CPI/NFP/FOMC/geopolitics).
- **Tick volume**, not real volume, on most gold feeds.
- **Backtest is conservative-bounded** (assumes SL fills first on ambiguous bars)
  but can't model real slippage/gaps beyond your cost/Properties inputs.
- **Signals fire on bar close** and don't repaint; a live bar can still flip until it closes.

### Disclaimer
Educational tool, **not financial advice**. Gold can move violently and gap.
Backtested performance does not predict the future. Forward-test on demo and risk
only what you can afford to lose. Every trade is your own decision.
