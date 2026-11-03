"""Institutional Footprint & Liquidity Intelligence — candle-derived proxy engine.

This module does NOT expose hidden institutional orders. Without a licensed,
venue-specific order-book/trade feed, it estimates liquidity pools and activity
from OHLCV only. All proxy fields are explicitly labelled as estimates.
"""
from __future__ import annotations

from statistics import median
from typing import Any


def _validate(candles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(candles, list) or len(candles) < 30:
        return [], "INSUFFICIENT_HISTORY"
    rows = []
    for i, row in enumerate(candles):
        try:
            o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            v = float(row.get("volume") or 0.0)
            if not all(map(lambda x: x == x and abs(x) != float("inf"), (o, h, l, c, v))):
                raise ValueError("Non-finite OHLCV")
            if h < max(o, c, l) or l > min(o, c, h) or v < 0:
                raise ValueError("Invalid OHLCV bounds")
            rows.append({**row, "open": o, "high": h, "low": l, "close": c, "volume": v, "_i": i})
        except (KeyError, TypeError, ValueError) as exc:
            return [], f"INVALID_CANDLE_{i}: {exc}"
    for a, b in zip(rows, rows[1:]):
        if a.get("time") is not None and b.get("time") is not None:
            try:
                if float(b["time"]) <= float(a["time"]):
                    return [], "TIMESTAMPS_NOT_STRICTLY_INCREASING"
            except (TypeError, ValueError):
                if str(b["time"]) <= str(a["time"]):
                    return [], "TIMESTAMPS_NOT_STRICTLY_INCREASING"
    return rows, None


def _volume_baseline(rows: list[dict[str, Any]], lookback: int = 20) -> tuple[float, float]:
    prior = [r["volume"] for r in rows[-lookback-1:-1] if r["volume"] > 0]
    current = rows[-1]["volume"]
    if not prior:
        return current, 0.0
    base = median(prior)
    return base, (current / base if base > 0 else 0.0)


def _pivot_levels(rows: list[dict[str, Any]], side: str, left: int = 3, right: int = 3) -> list[float]:
    key = "high" if side == "high" else "low"
    out = []
    # Confirm pivots only after right-side bars have closed.
    for i in range(left, len(rows) - right):
        value = rows[i][key]
        window = [r[key] for r in rows[i-left:i+right+1]]
        if side == "high" and value == max(window) and window.count(value) == 1:
            out.append(value)
        if side == "low" and value == min(window) and window.count(value) == 1:
            out.append(value)
    return out


def _cluster(levels: list[float], tolerance: float) -> list[dict[str, Any]]:
    groups: list[list[float]] = []
    for level in sorted(levels):
        if groups and abs(level - sum(groups[-1]) / len(groups[-1])) <= tolerance:
            groups[-1].append(level)
        else:
            groups.append([level])
    return [
        {"price": round(sum(g) / len(g), 5), "touches": len(g),
         "strength": "high" if len(g) >= 3 else "medium" if len(g) == 2 else "low"}
        for g in groups if len(g) >= 2
    ]


def analyze_institutional_footprint(
    candles: list[dict[str, Any]], settings: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Estimate liquidity and order-flow proxies from chronological OHLCV."""
    p = {"pivot_left": 3, "pivot_right": 3, "volume_lookback": 20,
         "volume_spike_multiple": 2.0, "cluster_tolerance_atr": 0.12,
         "atr_period": 14, **(settings or {})}
    rows, error = _validate(candles)
    if error:
        return {"status": "insufficient_history" if error == "INSUFFICIENT_HISTORY" else "invalid_data",
                "reason": error, "data_quality": "not_ready"}
    last = rows[-1]
    ranges = [r["high"] - r["low"] for r in rows]
    tr = []
    for i, r in enumerate(rows):
        prev_close = rows[i-1]["close"] if i else r["close"]
        tr.append(max(r["high"] - r["low"], abs(r["high"] - prev_close), abs(r["low"] - prev_close)))
    n = max(2, int(p["atr_period"]))
    atr = sum(tr[-n:]) / min(n, len(tr))
    tolerance = max(atr * float(p["cluster_tolerance_atr"]), 0.00001)

    highs = _pivot_levels(rows, "high", int(p["pivot_left"]), int(p["pivot_right"]))
    lows = _pivot_levels(rows, "low", int(p["pivot_left"]), int(p["pivot_right"]))
    buy_side = _cluster(highs, tolerance)
    sell_side = _cluster(lows, tolerance)

    recent_high = max(r["high"] for r in rows[-20:-1])
    recent_low = min(r["low"] for r in rows[-20:-1])
    swept_high = last["high"] > recent_high and last["close"] < recent_high
    swept_low = last["low"] < recent_low and last["close"] > recent_low

    body = abs(last["close"] - last["open"])
    candle_range = max(last["high"] - last["low"], 1e-12)
    upper_wick = last["high"] - max(last["open"], last["close"])
    lower_wick = min(last["open"], last["close"]) - last["low"]
    close_location = (last["close"] - last["low"]) / candle_range
    baseline, relative_volume = _volume_baseline(rows, int(p["volume_lookback"]))
    vol_spike = relative_volume >= float(p["volume_spike_multiple"]) if baseline > 0 else False

    # Heuristic buy/sell volume split from candle close location; not true bid/ask delta.
    estimated_buy_volume = last["volume"] * close_location
    estimated_sell_volume = last["volume"] * (1.0 - close_location)
    estimated_delta = estimated_buy_volume - estimated_sell_volume
    absorption_buy = bool(vol_spike and lower_wick / candle_range >= 0.45 and close_location >= 0.60)
    absorption_sell = bool(vol_spike and upper_wick / candle_range >= 0.45 and close_location <= 0.40)
    ambiguous_sweep = swept_high and swept_low
    recent_window = rows[-20:]
    estimated_cvd_20 = sum(r["volume"] * (((r["close"] - r["low"]) / max(r["high"] - r["low"], 1e-12)) * 2.0 - 1.0) for r in recent_window)
    activity_score = min(100, int((25 if vol_spike else 0) + (20 if absorption_buy or absorption_sell else 0) + (20 if swept_high or swept_low else 0) + (10 if buy_side or sell_side else 0) + (10 if relative_volume >= 1.3 else 0)))

    return {
        "status": "ok",
        "engine": "Institutional Footprint & Liquidity Intelligence",
        "symbol": last.get("symbol", "XAUUSD"),
        "timestamp": last.get("time"),
        "timeframe": last.get("timeframe"),
        "data_quality": "ohlcv_proxy",
        "source_mode": "CANDLE_DERIVED_ESTIMATE",
        "order_book": {
            "status": "not_connected",
            "bid_ask_depth": None,
            "resting_order_sizes": None,
            "iceberg_detection": "unavailable_without_order_level_feed",
            "note": "No verified live exchange order book is connected. No pending-order quantities are inferred."
        },
        "liquidity_pools": {
            "buy_side_above_swing_highs": buy_side,
            "sell_side_below_swing_lows": sell_side,
            "recent_range": {"high": recent_high, "low": recent_low}
        },
        "liquidity_heatmap": {
            "levels": [{"side": "buy_side", **x} for x in buy_side] + [{"side": "sell_side", **x} for x in sell_side],
            "semantics": "PIVOT_CLUSTER_ESTIMATES_NOT_RESTING_ORDERS"
        },
        "liquidity_sweep": {
            "buy_side_sweep_and_reclaim": bool(swept_high),
            "sell_side_sweep_and_reclaim": bool(swept_low),
            "ambiguous_both_sides": bool(ambiguous_sweep)
        },
        "activity_proxies": {
            "volume": last["volume"],
            "prior_median_volume": round(baseline, 5),
            "relative_volume": round(relative_volume, 3),
            "unusual_volume": bool(vol_spike),
            "estimated_buy_volume": round(estimated_buy_volume, 5),
            "estimated_sell_volume": round(estimated_sell_volume, 5),
            "estimated_delta": round(estimated_delta, 5),
            "estimated_cvd_20_bars": round(estimated_cvd_20, 5),
            "open_interest": None,
            "large_trade_tape": "unavailable_without_trade_print_feed",
            "delta_semantics": "CANDLE_CLOSE_LOCATION_ESTIMATE_NOT_TRUE_CVD"
        },
        "absorption_proxy": {
            "possible_buy_absorption": absorption_buy,
            "possible_sell_absorption": absorption_sell,
            "confidence": "low_to_medium" if vol_spike else "low",
            "note": "Heuristic wick + relative-volume pattern; not proof of iceberg or institutional activity."
        },
        "institutional_activity_score": {
            "score": activity_score,
            "label": "proxy_activity_only",
            "confidence": "low",
            "note": "Rule-based OHLCV activity score, not a probability or proof of institutional participation."
        },
        "risk_flags": {
            "ambiguous_sweep": bool(ambiguous_sweep),
            "insufficient_volume_history": baseline <= 0,
            "intrabar_order_unknown": True
        },
        "metrics": {"atr_simple": round(atr, 5), "body_to_range": round(body / candle_range, 3),
                    "upper_wick_ratio": round(upper_wick / candle_range, 3),
                    "lower_wick_ratio": round(lower_wick / candle_range, 3)},
        "disclaimer": "Estimated liquidity pools and OHLCV proxies only. Not actual resting orders, named institutions, or verified CVD."
    }


def build_gold_report(timeframes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Build a multi-timeframe report; missing feeds remain explicitly unavailable."""
    required = ("4h", "1h", "15m", "5m")
    analyses = {}
    for tf in required:
        rows = timeframes.get(tf)
        if not rows:
            analyses[tf] = {"status": "not_available", "reason": "TIMEFRAME_DATA_MISSING"}
            continue
        tagged = [{**row, "timeframe": tf} for row in rows]
        analyses[tf] = analyze_institutional_footprint(tagged)
    return {
        "status": "partial" if any(x.get("status") != "ok" for x in analyses.values()) else "ok",
        "report": "GOLD REPORT AI",
        "market": "XAUUSD",
        "timeframe_hierarchy": {"4h": "macro_confirmation", "1h": "primary_decision",
                                "15m": "setup", "5m": "entry_confirmation"},
        "institutional_footprint": analyses,
        "decision": "WAIT",
        "decision_note": "Footprint proxies alone never trigger BUY/SELL. Connect validated data and the full trend/structure/trigger/risk pipeline first.",
        "live_exchange_order_book": "not_connected",
    }
