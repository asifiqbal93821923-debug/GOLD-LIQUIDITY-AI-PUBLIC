"""Download one Dukascopy XAUUSD BID M1 feed and derive aligned MTF CSVs.

The three outputs are aggregated from the same raw M1 file. No missing source
minutes or candles are fabricated. Timestamps are UTC Unix seconds at bar open.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TIMEFRAMES = {"15m": 900, "1h": 3600, "4h": 14400}


def parse_epoch(value: str) -> int:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite timestamp")
    # dukascopy-node CSV timestamps are milliseconds.
    return int(number / 1000) if number > 10_000_000_000 else int(number)


def load_m1(path: Path) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("M1 CSV has no header")
        names = {x.strip().lower(): x for x in reader.fieldnames}
        required = ("timestamp", "open", "high", "low", "close")
        if any(k not in names for k in required):
            raise ValueError(f"Expected columns {required}; got {reader.fieldnames}")
        for line, raw in enumerate(reader, 2):
            t = parse_epoch(raw[names["timestamp"]])
            candle = {k: float(raw[names[k]]) for k in ("open", "high", "low", "close")}
            if not all(math.isfinite(v) and v > 0 for v in candle.values()):
                raise ValueError(f"Invalid OHLC at CSV line {line}")
            if candle["high"] < max(candle["open"], candle["close"], candle["low"]):
                raise ValueError(f"Invalid high at CSV line {line}")
            if candle["low"] > min(candle["open"], candle["close"], candle["high"]):
                raise ValueError(f"Invalid low at CSV line {line}")
            candle["time"] = t
            candle["volume"] = float(raw[names["volume"]]) if "volume" in names and raw.get(names["volume"], "").strip() else None
            rows.append(candle)
    rows.sort(key=lambda x: x["time"])
    if not rows:
        raise ValueError("No M1 candles downloaded")
    if len({r["time"] for r in rows}) != len(rows):
        raise ValueError("Duplicate M1 timestamps in provider data")
    return rows


def aggregate(rows: list[dict], seconds: int, now: int) -> tuple[list[dict], dict]:
    buckets: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        start = row["time"] - row["time"] % seconds
        if start + seconds <= now:
            buckets[start].append(row)
    result = []
    for start, items in sorted(buckets.items()):
        items.sort(key=lambda x: x["time"])
        out = {
            "timestamp": start,
            "open": items[0]["open"],
            "high": max(x["high"] for x in items),
            "low": min(x["low"] for x in items),
            "close": items[-1]["close"],
        }
        vols = [x["volume"] for x in items if x["volume"] is not None]
        if vols:
            out["volume"] = sum(vols)
        result.append(out)
    report = {
        "bars": len(result),
        "first_open_utc": datetime.fromtimestamp(result[0]["timestamp"], timezone.utc).isoformat() if result else None,
        "last_open_utc": datetime.fromtimestamp(result[-1]["timestamp"], timezone.utc).isoformat() if result else None,
        "source_m1_rows": sum(len(v) for k, v in buckets.items()),
        "source_m1_rows_min_per_bar": min((len(v) for v in buckets.values()), default=0),
        "source_m1_rows_max_per_bar": max((len(v) for v in buckets.values()), default=0),
        "alignment": "UTC epoch-aligned",
        "note": "Only observed provider M1 candles are aggregated; no missing rows are synthesized.",
    }
    return result, report


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["timestamp", "open", "high", "low", "close", "volume"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-date", default="2020-01-01")
    ap.add_argument("--to-date", default=datetime.now(timezone.utc).date().isoformat())
    ap.add_argument("--output-dir", default="data/phase2")
    ap.add_argument("--raw-dir", default="data/raw")
    args = ap.parse_args()
    out = Path(args.output_dir)
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / f"xauusd_m1_bid_{args.from_date}_{args.to_date}.csv"
    command = [
        "npx", "--yes", "dukascopy-node", "-i", "xauusd",
        "-from", args.from_date, "-to", args.to_date,
        "-t", "m1", "-f", "csv", "-p", "bid", "-v",
        "-o", str(raw_file),
    ]
    subprocess.run(command, check=True)
    if not raw_file.exists():
        # dukascopy-node versions may write their standard download/ path.
        candidates = list(Path("download").glob("xauusd-m1-bid-*.csv"))
        if len(candidates) != 1:
            raise FileNotFoundError(f"Expected raw file {raw_file}; found {candidates[:5]}")
        raw_file = candidates[0]
    source_rows = load_m1(raw_file)
    now = int(datetime.now(timezone.utc).timestamp())
    manifest = {
        "provider": "Dukascopy",
        "instrument": "XAUUSD",
        "source_timeframe": "M1",
        "price_side": "BID",
        "timezone": "UTC",
        "source_file": str(raw_file),
        "source_rows": len(source_rows),
        "source_first_utc": datetime.fromtimestamp(source_rows[0]["time"], timezone.utc).isoformat(),
        "source_last_utc": datetime.fromtimestamp(source_rows[-1]["time"], timezone.utc).isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "aggregation": {},
    }
    for tf, seconds in TIMEFRAMES.items():
        bars, report = aggregate(source_rows, seconds, now)
        if len(bars) < 250:
            raise RuntimeError(f"{tf} has only {len(bars)} bars; refusing insufficient dataset")
        filename = {"15m": "xauusd_15m.csv", "1h": "xauusd_1h.csv", "4h": "xauusd_4h.csv"}[tf]
        write_csv(out / filename, bars)
        manifest["aggregation"][tf] = {"file": filename, **report}
    (out / "xauusd_data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
