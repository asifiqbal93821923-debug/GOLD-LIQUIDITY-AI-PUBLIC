"""Analyze timestamped broker bid/ask observations for P2.5.

CSV columns: timestamp (ISO-8601 with timezone), bid, ask, point_size.
This tool computes observed spread distributions; it never certifies broker
identity or contract provenance on its own. It does not synthesize quotes.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

def _parse_time(value: str) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise ValueError("timestamp is empty")
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must include an explicit timezone offset or Z")
    return dt.astimezone(timezone.utc)

def _parse_hhmm(value: str):
    try:
        h, m = (int(x) for x in value.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h * 60 + m
    except Exception as exc:
        raise ValueError(f"Invalid UTC clock time: {value}; expected HH:MM") from exc

def _in_window(minute: int, start: int, end: int) -> bool:
    return start <= minute < end if start < end else (minute >= start or minute < end)

def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * pct
    lo = math.floor(pos); hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)

def _stats(values: list[float], minimum_samples: int) -> dict[str, Any]:
    return {
        "sample_count": len(values),
        "adequate_sample_count": len(values) >= minimum_samples,
        "mean_points": round(mean(values), 4) if values else None,
        "median_points": round(median(values), 4) if values else None,
        "p90_points": round(_percentile(values, .90), 4) if values else None,
        "p95_points": round(_percentile(values, .95), 4) if values else None,
        "p99_points": round(_percentile(values, .99), 4) if values else None,
        "max_points": round(max(values), 4) if values else None,
    }

def analyze_quotes(csv_path: str | Path, *, broker: str, symbol: str,
                   rollover_start_utc: str, rollover_end_utc: str,
                   minimum_samples: int = 1000) -> dict[str, Any]:
    if minimum_samples < 1:
        raise ValueError("minimum_samples must be at least 1")
    start = _parse_hhmm(rollover_start_utc)
    end = _parse_hhmm(rollover_end_utc)
    if start == end:
        raise ValueError("rollover window start and end must differ")
    quotes = []
    seen = set()
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"timestamp", "bid", "ask", "point_size"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must contain timestamp,bid,ask,point_size columns")
        for line, row in enumerate(reader, start=2):
            try:
                dt = _parse_time(row["timestamp"])
                bid = float(row["bid"]); ask = float(row["ask"]); point = float(row["point_size"])
            except Exception as exc:
                raise ValueError(f"Invalid quote at CSV line {line}: {exc}") from exc
            if not all(math.isfinite(x) for x in (bid, ask, point)) or bid <= 0 or ask < bid or point <= 0:
                raise ValueError(f"Invalid bid/ask/point_size at CSV line {line}")
            if dt in seen:
                raise ValueError(f"Duplicate quote timestamp at CSV line {line}")
            seen.add(dt)
            quotes.append({"time": dt, "spread_points": (ask - bid) / point})
    quotes.sort(key=lambda x: x["time"])
    if len(quotes) < 2:
        raise ValueError("At least two unique quote observations are required")

    groups = {"asia_utc_00_07": [], "london_utc_07_12": [],
              "london_ny_overlap_utc_12_16": [], "new_york_utc_16_21": [],
              "late_utc_21_24": [], "rollover_configured_window": []}
    for quote in quotes:
        dt = quote["time"]
        minute = dt.hour * 60 + dt.minute
        spread = quote["spread_points"]
        if minute < 7 * 60:
            groups["asia_utc_00_07"].append(spread)
        elif minute < 12 * 60:
            groups["london_utc_07_12"].append(spread)
        elif minute < 16 * 60:
            groups["london_ny_overlap_utc_12_16"].append(spread)
        elif minute < 21 * 60:
            groups["new_york_utc_16_21"].append(spread)
        else:
            groups["late_utc_21_24"].append(spread)
        if _in_window(minute, start, end):
            groups["rollover_configured_window"].append(spread)

    spreads = [q["spread_points"] for q in quotes]
    adequate = len(spreads) >= minimum_samples
    return {
        "status": "ok" if adequate else "insufficient_samples",
        "broker_label": broker,
        "symbol": symbol,
        "timestamp_policy": "All observations parsed with explicit timezone and normalized to UTC",
        "quote_count": len(quotes),
        "first_quote_utc": quotes[0]["time"].isoformat(),
        "last_quote_utc": quotes[-1]["time"].isoformat(),
        "overall": _stats(spreads, minimum_samples),
        "by_utc_session_and_rollover": {name: _stats(values, minimum_samples)
                                        for name, values in groups.items()},
        "rollover_window_utc": {"start": rollover_start_utc, "end_exclusive": rollover_end_utc},
        "provenance": {
            "broker_identity_verified": False,
            "contract_specification_verified": False,
            "quote_authenticity_verified": False,
            "manual_review_required": True,
            "note": "This report summarizes supplied bid/ask rows only. Verify broker source, XAUUSD contract point size, timezone and collection continuity independently."
        },
        "limitations": [
            "UTC session buckets are fixed diagnostic windows, not DST-adjusted exchange sessions.",
            "Rollover window must be chosen from the broker's documented server schedule and reviewed against quote timestamps.",
            "Quote snapshots show observed spread only; they do not measure slippage or commission.",
            "No missing quotes or spreads are interpolated or synthesized."
        ]
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True); ap.add_argument("--output", required=True)
    ap.add_argument("--broker", required=True); ap.add_argument("--symbol", required=True)
    ap.add_argument("--rollover-start-utc", required=True)
    ap.add_argument("--rollover-end-utc", required=True)
    ap.add_argument("--minimum-samples", type=int, default=1000)
    args = ap.parse_args()
    report = analyze_quotes(args.input, broker=args.broker, symbol=args.symbol,
        rollover_start_utc=args.rollover_start_utc,
        rollover_end_utc=args.rollover_end_utc, minimum_samples=args.minimum_samples)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "quote_count": report["quote_count"],
                      "provenance": report["provenance"]}, indent=2))
    if report["status"] != "ok":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
