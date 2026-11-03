"""Causal 15M OHLC diagnostics for sweeps, false breakouts and retests.

Events are emitted only when confirmed by the current closed candle. Forward
MFE/MAE statistics are a post-event outcome analysis, not an entry signal.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def classify(candles: list[dict[str, Any]], lookback: int = 20,
             retest_bars: int = 6, wick_fraction: float = 0.35) -> list[dict[str, Any]]:
    if lookback < 3 or retest_bars < 1 or not 0 < wick_fraction < 1:
        raise ValueError("Invalid classifier settings")
    events: list[dict[str, Any]] = []
    active_breakouts: list[dict[str, Any]] = []
    for i in range(lookback, len(candles)):
        bar = candles[i]
        prior = candles[i - lookback:i]
        prior_high = max(float(x["high"]) for x in prior)
        prior_low = min(float(x["low"]) for x in prior)
        op, hi, lo, cl = (float(bar[k]) for k in ("open", "high", "low", "close"))
        span = max(hi - lo, 1e-12)
        upper_wick = hi - max(op, cl)
        lower_wick = min(op, cl) - lo
        # Failed breakouts and liquidity sweeps are confirmed only after price
        # closes back through the pre-existing range boundary.
        if hi > prior_high and cl <= prior_high and upper_wick / span >= wick_fraction:
            events.append({"index": i, "time": bar.get("time"), "type": "liquidity_sweep",
                           "side": "SELL", "level": prior_high, "confirmation": "wick_above_close_back_below"})
            events.append({"index": i, "time": bar.get("time"), "type": "false_breakout",
                           "side": "SELL", "level": prior_high, "confirmation": "close_back_inside"})
        if lo < prior_low and cl >= prior_low and lower_wick / span >= wick_fraction:
            events.append({"index": i, "time": bar.get("time"), "type": "liquidity_sweep",
                           "side": "BUY", "level": prior_low, "confirmation": "wick_below_close_back_above"})
            events.append({"index": i, "time": bar.get("time"), "type": "false_breakout",
                           "side": "BUY", "level": prior_low, "confirmation": "close_back_inside"})
        # Confirmed close outside prior range creates a future retest candidate.
        if cl > prior_high:
            active_breakouts.append({"side": "BUY", "level": prior_high, "origin": i, "expires": i + retest_bars})
        elif cl < prior_low:
            active_breakouts.append({"side": "SELL", "level": prior_low, "origin": i, "expires": i + retest_bars})
        remaining = []
        for breakout in active_breakouts:
            if i <= breakout["origin"]:
                remaining.append(breakout)
                continue
            if i > breakout["expires"]:
                continue
            level = float(breakout["level"])
            if breakout["side"] == "BUY":
                touched = lo <= level and hi >= level and cl > level and cl >= op
            else:
                touched = hi >= level and lo <= level and cl < level and cl <= op
            if touched:
                events.append({"index": i, "time": bar.get("time"), "type": "retest",
                               "side": breakout["side"], "level": level,
                               "confirmation": "level_retested_and_close_rejected"})
            else:
                remaining.append(breakout)
        active_breakouts = remaining
    return events


def outcome_summary(candles: list[dict[str, Any]], events: list[dict[str, Any]],
                    horizons: tuple[int, ...] = (1, 4, 8, 12)) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        i, side = int(event["index"]), event["side"]
        if i + max(horizons) >= len(candles):
            continue
        entry = float(candles[i]["close"])
        outcomes = {}
        for horizon in horizons:
            future = candles[i + 1:i + horizon + 1]
            highs = [float(x["high"]) for x in future]
            lows = [float(x["low"]) for x in future]
            if side == "BUY":
                mfe, mae = max(highs) - entry, min(lows) - entry
                close_return = float(future[-1]["close"]) - entry
            else:
                mfe, mae = entry - min(lows), entry - max(highs)
                close_return = entry - float(future[-1]["close"])
            outcomes[str(horizon)] = {"mfe_price": round(mfe, 5), "mae_price": round(mae, 5),
                                      "close_return_price": round(close_return, 5)}
        groups[event["type"]].append({"time": event.get("time"), "side": side, "outcomes": outcomes})
    return {kind: {"event_count": len(rows), "samples": rows} for kind, rows in groups.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSON array of chronological closed 15M OHLC candles")
    ap.add_argument("--output", default="price-action-report.json")
    ap.add_argument("--lookback", type=int, default=20)
    ap.add_argument("--retest-bars", type=int, default=6)
    args = ap.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    candles = payload.get("15m", []) if isinstance(payload, dict) else payload
    if not isinstance(candles, list):
        raise SystemExit("Input must be a JSON candle array or prepared MTF dataset with a 15m array")
    events = classify(candles, args.lookback, args.retest_bars)
    report = {"status": "ok", "event_count": len(events), "events": events,
              "outcomes": outcome_summary(candles, events),
              "warning": "OHLC-only proxy; not real order-book liquidity or actual institutional orders. Forward outcomes are descriptive and do not alter event-time signals."}
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event_count": len(events), "types": report["outcomes"].keys()}, indent=2))


if __name__ == "__main__":
    main()
