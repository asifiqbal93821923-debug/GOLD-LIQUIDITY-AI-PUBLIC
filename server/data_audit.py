"""Historical candle quality audit for XAUUSD research datasets.

Reports coverage and defects without manufacturing missing candles or assuming
that every market-closed interval is a data outage.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Any

TF_SECONDS = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


def audit_candle_history(rows: list[dict[str, Any]], timeframe: str,
                         now_epoch: int | None = None) -> dict[str, Any]:
    if timeframe not in TF_SECONDS:
        return {"status": "unsupported_timeframe", "timeframe": timeframe}
    if not isinstance(rows, list):
        return {"status": "invalid_data", "reason": "Candle input must be a list."}
    duration = TF_SECONDS[timeframe]
    now_epoch = int(now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp())
    seen: set[int] = set()
    timestamps: list[int] = []
    invalid_rows = 0
    invalid_reasons: dict[str, int] = {}
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise ValueError("ROW_NOT_OBJECT")
            raw_time = row.get("time")
            if isinstance(raw_time, bool):
                raise ValueError("INVALID_TIMESTAMP")
            stamp = int(float(raw_time))
            values = [float(row[k]) for k in ("open", "high", "low", "close")]
            if not all(isfinite(v) for v in values):
                raise ValueError("NON_FINITE_OHLC")
            op, hi, lo, close = values
            if hi < max(op, close, lo) or lo > min(op, close, hi):
                raise ValueError("IMPOSSIBLE_OHLC")
            volume = row.get("volume")
            if volume is not None and (not isfinite(float(volume)) or float(volume) < 0):
                raise ValueError("INVALID_VOLUME")
            if stamp <= 0:
                raise ValueError("INVALID_TIMESTAMP")
            if stamp in seen:
                invalid_rows += 1
                invalid_reasons["DUPLICATE_TIMESTAMP"] = invalid_reasons.get("DUPLICATE_TIMESTAMP", 0) + 1
                continue
            seen.add(stamp)
            timestamps.append(stamp)
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid_rows += 1
            reason = "INVALID_ROW"
            if isinstance(row, dict):
                try:
                    float(row.get("time"))
                except (TypeError, ValueError):
                    reason = "INVALID_TIMESTAMP"
                else:
                    reason = "INVALID_OHLC_OR_VOLUME"
            invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1

    ordered = sorted(timestamps)
    out_of_order = sum(1 for i in range(1, len(timestamps)) if timestamps[i] < timestamps[i - 1])
    gaps = []
    for previous, current in zip(ordered, ordered[1:]):
        delta = current - previous
        if delta > duration:
            gaps.append({"from": previous, "to": current, "missing_intervals_estimate": max(0, delta // duration - 1)})
    closed = [t for t in ordered if t + duration <= now_epoch]
    forming = [t for t in ordered if t <= now_epoch < t + duration]
    future = [t for t in ordered if t > now_epoch]
    coverage_seconds = max(0, (ordered[-1] - ordered[0])) if len(ordered) > 1 else 0
    deltas = [b - a for a, b in zip(ordered, ordered[1:])]
    return {
        "status": "ok" if ordered else "empty",
        "timeframe": timeframe,
        "bar_seconds": duration,
        "received_rows": len(rows),
        "valid_unique_rows": len(ordered),
        "invalid_rows": invalid_rows,
        "invalid_reasons": invalid_reasons,
        "out_of_order_rows": out_of_order,
        "duplicate_rows": invalid_reasons.get("DUPLICATE_TIMESTAMP", 0),
        "closed_rows": len(closed),
        "forming_rows": len(forming),
        "future_rows": len(future),
        "first_bar_open": ordered[0] if ordered else None,
        "last_bar_open": ordered[-1] if ordered else None,
        "history_days": round(coverage_seconds / 86400, 3),
        "expected_bars_for_elapsed_time": (coverage_seconds // duration + 1) if ordered else 0,
        "observed_interval_seconds": {
            "min": min(deltas) if deltas else None,
            "median": sorted(deltas)[len(deltas) // 2] if deltas else None,
            "max": max(deltas) if deltas else None,
        },
        "gap_count": len(gaps),
        "estimated_missing_intervals": sum(x["missing_intervals_estimate"] for x in gaps),
        "largest_gaps": sorted(gaps, key=lambda x: x["to"] - x["from"], reverse=True)[:10],
        "limitations": [
            "Gap estimates are calendar-time diagnostics; weekend and session closures are not automatically classified as feed failures.",
            "A valid OHLC shape does not prove broker authenticity, timezone correctness, or executable prices.",
            "No missing candles are synthesized and no sampled spot prices are converted into OHLC bars.",
        ],
    }
