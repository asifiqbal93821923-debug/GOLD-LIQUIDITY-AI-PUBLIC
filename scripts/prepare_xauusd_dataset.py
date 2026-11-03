"""Prepare a same-feed XAUUSD MTF dataset from TradingView CSV exports.

All timeframe exports must come from the exact same chart provider/symbol. The
source/symbol arguments are explicit provenance labels, not automatic proof.
Bars are timestamped at bar-open UTC Unix seconds; unclosed bars are rejected.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DURATIONS = {"4h": 14_400, "1h": 3_600, "15m": 900, "5m": 300}
ALIASES = {
    "time": ("time", "timestamp", "datetime", "date"),
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c"),
    "volume": ("volume", "vol", "tick_volume"),
}


def _timestamp(raw: str) -> int:
    value = raw.strip()
    try:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("timestamp must be finite")
        # TradingView exports normally use seconds; tolerate milliseconds.
        return int(number / 1000) if number > 10_000_000_000 else int(number)
    except ValueError:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("ISO timestamp must include timezone; do not guess local time")
        return int(dt.astimezone(timezone.utc).timestamp())


def _column(headers: list[str], key: str, required: bool = True) -> str | None:
    lower = {h.strip().lower(): h for h in headers}
    for alias in ALIASES[key]:
        if alias in lower:
            return lower[alias]
    if required:
        raise ValueError(f"CSV missing {key} column; accepted: {ALIASES[key]}")
    return None


def read_export(path: str, timeframe: str, asof: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing CSV header")
        cols = {k: _column(reader.fieldnames, k, k != "volume") for k in ALIASES}
        for line, raw in enumerate(reader, start=2):
            try:
                t = _timestamp(raw[cols["time"]])  # type: ignore[index]
                candle = {"time": t}
                for key in ("open", "high", "low", "close"):
                    value = float(raw[cols[key]])  # type: ignore[index]
                    if not math.isfinite(value):
                        raise ValueError(f"{key} is not finite")
                    candle[key] = value
                if cols["volume"] and raw.get(cols["volume"], "").strip():
                    volume = float(raw[cols["volume"]])
                    if not math.isfinite(volume) or volume < 0:
                        raise ValueError("volume must be finite and non-negative")
                    candle["volume"] = volume
                else:
                    candle["volume"] = None
                if candle["high"] < max(candle["open"], candle["close"], candle["low"]):
                    raise ValueError("invalid high")
                if candle["low"] > min(candle["open"], candle["close"], candle["high"]):
                    raise ValueError("invalid low")
                if t + DURATIONS[timeframe] > asof:
                    raise ValueError("forming or future candle; export closed candles only")
                rows.append(candle)
            except (TypeError, KeyError, ValueError) as exc:
                raise ValueError(f"{path}:{line}: {exc}") from exc
    rows.sort(key=lambda x: x["time"])
    times = [x["time"] for x in rows]
    if not rows:
        raise ValueError(f"{path}: no candles")
    if len(times) != len(set(times)):
        raise ValueError(f"{path}: duplicate candle timestamps")
    return rows, {
        "file": Path(path).name,
        "bars": len(rows),
        "first_open_utc": datetime.fromtimestamp(times[0], timezone.utc).isoformat(),
        "last_open_utc": datetime.fromtimestamp(times[-1], timezone.utc).isoformat(),
        "gaps_over_one_bar": sum(1 for a, b in zip(times, times[1:]) if b - a > DURATIONS[timeframe]),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if not args.source.strip() or not args.symbol.strip():
        raise ValueError("source and symbol provenance labels are required")
    asof = int(args.asof_epoch) if args.asof_epoch else int(datetime.now(timezone.utc).timestamp())
    inputs = {"4h": args.h4, "1h": args.h1, "15m": args.m15, "5m": args.m5}
    frames: dict[str, list[dict[str, Any]]] = {}
    manifest: dict[str, Any] = {}
    for tf, path in inputs.items():
        if not path:
            frames[tf] = []
            continue
        frames[tf], manifest[tf] = read_export(path, tf, asof)
        manifest[tf]["closed_candles_only"] = True
    required = ("4h", "1h", "15m")
    missing = [tf for tf in required if not frames[tf]]
    too_short = {tf: len(frames[tf]) for tf in required if len(frames[tf]) < 250}
    partition_counts: dict[str, dict[str, int]] = {}
    short_partitions: dict[str, dict[str, int]] = {}
    if not missing and len(frames["1h"]) >= 3:
        h1 = frames["1h"]
        cut1 = int(len(h1) * 0.60)
        cut2 = int(len(h1) * 0.80)
        boundary1 = int(h1[cut1]["time"])
        boundary2 = int(h1[cut2]["time"])
        for split, predicate in (
            ("train", lambda row, duration: row["time"] + duration <= boundary1),
            ("validation", lambda row, duration: row["time"] >= boundary1 and row["time"] + duration <= boundary2),
            ("test", lambda row, duration: row["time"] >= boundary2),
        ):
            partition_counts[split] = {
                tf: sum(1 for row in frames[tf] if predicate(row, DURATIONS[tf]))
                for tf in required
            }
            short = {tf: count for tf, count in partition_counts[split].items() if count < 50}
            if short:
                short_partitions[split] = short
    else:
        short_partitions = {"all": {tf: 0 for tf in required}}
    ready = not missing and not too_short and not short_partitions
    return {
        "metadata": {
            "instrument": "XAUUSD",
            "source": args.source.strip(),
            "symbol": args.symbol.strip(),
            "timezone": "UTC",
            "timestamp_semantics": "bar_open_unix_seconds",
            "volume_semantics": "source-provided volume only; not assumed traded volume",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "provenance_note": "Source/symbol labels are operator assertions. Verify they match the TradingView chart header before accepting parity results.",
        },
        "data_quality": {
            "status": "ready_for_60_20_20_validation" if ready else "insufficient_or_missing_history",
            "missing_required_timeframes": missing,
            "timeframes_below_250_bars": too_short,
            "partition_counts": partition_counts,
            "partitions_below_50_bars": short_partitions,
            "manifest": manifest,
        },
        **frames,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Exact provider/feed name, e.g. OANDA")
    ap.add_argument("--symbol", required=True, help="Exact TradingView ticker, e.g. OANDA:XAUUSD")
    ap.add_argument("--4h", dest="h4")
    ap.add_argument("--1h", dest="h1", required=True)
    ap.add_argument("--15m", dest="m15", required=True)
    ap.add_argument("--5m", dest="m5")
    ap.add_argument("--asof-epoch", type=int)
    ap.add_argument("--output", default="data/xauusd_mtf_ohlcv.json")
    args = ap.parse_args()
    result = prepare(args)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["data_quality"], indent=2))
    if result["data_quality"]["status"] != "ready_for_60_20_20_validation":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
