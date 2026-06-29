#!/usr/bin/env python3
"""
London-session XAUUSD decision engine — alert-only, never auto-entry.

Encodes the trading rules in skills/london-session/SKILL.md. Given a setup it
returns SIGNAL / ALERT / SKIP and the computed entry, stop-loss and take-profit.

The three gates that matter most (where the real money was lost) are hard-coded:
  1. SESSION + STATE LOCKOUT  — London 3:00-5:30 PM MYT, max 2 trades, 2-loss stop
  2. TREND-DIRECTION FILTER   — long only in uptrend, short only in downtrend
  3. CONFIRMATION GATE        — candle CLOSED through level + volume > 500 + engulfing

Everything else (ATR sizing, 1:2.1 ratio, news blackout) layers on top. Pure
stdlib — no broker connection, no orders. Output is advisory only.

Usage:
  python3 london_session.py check --trend up --price 2358.0 \\
      --prev-high 2362.0 --prev-low 2356.0 --volume 720 \\
      --candle-closed --engulfing --atr 18 --rsi 48 \\
      --trades-today 0 --losses-today 0 --news-minutes 300

  python3 london_session.py session            # is the London window open right now?
  python3 london_session.py session --now 2026-06-29T15:20

Notes:
  * Times are Malaysia Time (MYT, UTC+8). --now overrides the clock for back-checks.
  * Pips are gold pips: default pip size 0.1 price units (override with --pip-size).
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

# --- constants from the rules ------------------------------------------------
MYT = timezone(timedelta(hours=8))
LONDON_OPEN = (15, 0)            # 3:00 PM MYT
LONDON_CLOSE = (17, 30)          # 5:30 PM MYT
MAX_TRADES = 2                   # per session
MAX_LOSSES = 2                   # then 24h lockout
NEWS_BLACKOUT_MIN = 120          # no entry within 2 hrs of major news
VOL_SKIP = 400                   # < 400 = too low to read
VOL_BUILD = 500                  # direction starting to build
VOL_CONFIRM = 700               # direction confirmed
SWEEP_EDGE_PIPS = 12            # entry sits this far past prev high/low
SWEEP_SL_PIPS = 10              # stop sits beyond the sweep
MIN_RR = 2.1                    # 1:2.1 minimum (break-even win rate 32.3%)
ALERT_PROXIMITY_PIPS = 8        # within this of the sweep edge => ALERT


def now_myt(override: str | None) -> datetime:
    if override:
        dt = datetime.fromisoformat(override)
        return dt.replace(tzinfo=MYT) if dt.tzinfo is None else dt.astimezone(MYT)
    return datetime.now(MYT)


def in_london(dt: datetime) -> bool:
    o = dt.replace(hour=LONDON_OPEN[0], minute=LONDON_OPEN[1], second=0, microsecond=0)
    c = dt.replace(hour=LONDON_CLOSE[0], minute=LONDON_CLOSE[1], second=0, microsecond=0)
    return o <= dt <= c


def session_label(dt: datetime) -> str:
    """Rough session name for the skip reason."""
    h = dt.hour
    if in_london(dt):
        return "London"
    if 8 <= h < 15:
        return "Asian"
    if h >= 21 or h < 6:
        return "NY/after-hours"
    return "off-session"


def evaluate(args) -> dict:
    pip = args.pip_size
    dt = now_myt(args.now)
    fails: list[str] = []
    notes: list[str] = []

    # --- GATE 1: session + state lockout ------------------------------------
    if not in_london(dt):
        fails.append(
            f"SESSION: {dt:%H:%M} MYT is {session_label(dt)} — trade London 15:00-17:30 only"
        )
    else:
        close = dt.replace(hour=LONDON_CLOSE[0], minute=LONDON_CLOSE[1], second=0, microsecond=0)
        mins_left = int((close - dt).total_seconds() // 60)
        notes.append(f"session OK — {mins_left} min to hard exit 17:30 MYT")
        if mins_left <= 20:
            notes.append("near hard exit — close weak positions, don't open fresh swings")

    if args.trades_today >= MAX_TRADES:
        fails.append(f"STATE: already {args.trades_today} trades (max {MAX_TRADES}/session)")
    if args.losses_today >= MAX_LOSSES:
        fails.append(f"STATE: {args.losses_today} losses — 24h lockout in effect")

    # --- News blackout (auto-skip flag) -------------------------------------
    if args.news_minutes is not None and args.news_minutes < NEWS_BLACKOUT_MIN:
        fails.append(
            f"NEWS: major news in {args.news_minutes} min (< {NEWS_BLACKOUT_MIN} min blackout)"
        )

    # --- GATE 2: trend-direction filter -------------------------------------
    trend = args.trend.lower()
    side = None
    if trend == "up":
        side = "long"
    elif trend == "down":
        side = "short"
    else:
        fails.append("TREND: no session direction set (up=long-only, down=short-only)")

    # --- Volume (auto-skip flag + confirmation input) -----------------------
    if args.volume < VOL_SKIP:
        fails.append(f"VOLUME: {args.volume} < {VOL_SKIP} — too low to read")
    elif args.volume < VOL_BUILD:
        notes.append(f"volume {args.volume} — building but below {VOL_BUILD} confirm threshold")
    elif args.volume >= VOL_CONFIRM:
        notes.append(f"volume {args.volume} — direction confirmed (>= {VOL_CONFIRM})")
    else:
        notes.append(f"volume {args.volume} — direction building")

    # --- GATE 3: confirmation gate ------------------------------------------
    confirmed = True
    if not args.candle_closed:
        confirmed = False
        notes.append("candle not yet CLOSED through level — wait for close, not the wick")
    if not args.engulfing:
        confirmed = False
        notes.append("no engulfing candle — need engulf FIRST, signal SECOND")
    if args.volume < VOL_BUILD:
        confirmed = False
    if confirmed and side and args.volume < VOL_CONFIRM:
        notes.append("confirmation thin — prefer volume >= 700 before committing")

    # --- Oscillator sanity (don't trade against oscillators) ----------------
    if args.rsi is not None and side:
        if side == "long" and args.rsi >= 70:
            fails.append(f"RSI: {args.rsi} overbought — don't buy into it")
        if side == "short" and args.rsi <= 30:
            fails.append(f"RSI: {args.rsi} oversold — don't sell into it")

    # --- Entry / SL / TP (sweep-edge method + 1:2.1) ------------------------
    levels = None
    distance_pips = None
    if side == "long":
        entry = args.prev_low - SWEEP_EDGE_PIPS * pip
        sl = entry - (SWEEP_SL_PIPS * pip + args.atr * pip)
        risk = entry - sl
        tp = entry + MIN_RR * risk
        distance_pips = (args.price - entry) / pip
        levels = (entry, sl, tp, risk)
    elif side == "short":
        entry = args.prev_high + SWEEP_EDGE_PIPS * pip
        sl = entry + (SWEEP_SL_PIPS * pip + args.atr * pip)
        risk = sl - entry
        tp = entry - MIN_RR * risk
        distance_pips = (entry - args.price) / pip
        levels = (entry, sl, tp, risk)

    # --- Decide --------------------------------------------------------------
    if fails:
        decision = "SKIP"
    elif side and confirmed:
        decision = "SIGNAL"
    else:
        # gates 1+2 clean but confirmation not in yet -> watch
        decision = "ALERT"
        if levels and distance_pips is not None and distance_pips < -ALERT_PROXIMITY_PIPS:
            notes.append(
                f"price {abs(distance_pips):.1f} pips past sweep edge already — chasing, wait for pullback"
            )

    return {
        "decision": decision,
        "side": side,
        "levels": levels,
        "distance_pips": distance_pips,
        "fails": fails,
        "notes": notes,
        "pip": pip,
    }


def render(res: dict) -> str:
    out = [f"DECISION: {res['decision']}"]
    if res["side"]:
        out.append(f"side: {res['side']}")
    if res["decision"] == "SKIP":
        for f in res["fails"]:
            out.append(f"  ✗ {f}")
    if res["levels"]:
        entry, sl, tp, risk = res["levels"]
        pip = res["pip"]
        out.append(
            f"  entry {entry:.2f} | SL {sl:.2f} ({risk/pip:.0f} pips) "
            f"| TP {tp:.2f} ({(abs(tp-entry))/pip:.0f} pips) | R 1:{MIN_RR}"
        )
        if res["distance_pips"] is not None:
            out.append(f"  price is {res['distance_pips']:+.1f} pips from entry")
    for n in res["notes"]:
        out.append(f"  • {n}")
    if res["decision"] == "SIGNAL":
        out.append("  → set TP + SL BEFORE entering. Lot 0.02. You click the order.")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="London-session XAUUSD decision engine (alert-only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("session", help="is the London window open?")
    ps.add_argument("--now", help="override clock, ISO MYT e.g. 2026-06-29T15:20")

    pc = sub.add_parser("check", help="evaluate a setup")
    pc.add_argument("--now", help="override clock, ISO MYT e.g. 2026-06-29T15:20")
    pc.add_argument("--trend", default="none", choices=["up", "down", "none"],
                    help="session direction (up=long-only, down=short-only)")
    pc.add_argument("--price", type=float, default=0.0, help="current price")
    pc.add_argument("--prev-high", type=float, default=0.0, help="prev session high")
    pc.add_argument("--prev-low", type=float, default=0.0, help="prev session low")
    pc.add_argument("--volume", type=float, default=0.0, help="current candle volume")
    pc.add_argument("--candle-closed", action="store_true", help="candle closed through level")
    pc.add_argument("--engulfing", action="store_true", help="engulfing candle present")
    pc.add_argument("--atr", type=float, default=15.0, help="ATR(14) in pips")
    pc.add_argument("--rsi", type=float, default=None, help="RSI value (optional)")
    pc.add_argument("--trades-today", type=int, default=0)
    pc.add_argument("--losses-today", type=int, default=0)
    pc.add_argument("--news-minutes", type=int, default=None,
                    help="minutes until next major news (NFP/CPI/Fed)")
    pc.add_argument("--pip-size", type=float, default=0.1, help="price units per pip (gold=0.1)")

    args = p.parse_args(argv)

    if args.cmd == "session":
        dt = now_myt(args.now)
        if in_london(dt):
            close = dt.replace(hour=LONDON_CLOSE[0], minute=LONDON_CLOSE[1], second=0, microsecond=0)
            mins = int((close - dt).total_seconds() // 60)
            print(f"OPEN — London session, {mins} min to hard exit 17:30 MYT ({dt:%H:%M} MYT)")
        else:
            print(f"CLOSED — {session_label(dt)} ({dt:%H:%M} MYT). Trade London 15:00-17:30 only.")
        return 0

    res = evaluate(args)
    print(render(res))
    return 0 if res["decision"] != "SKIP" else 1


if __name__ == "__main__":
    sys.exit(main())
