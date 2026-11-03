#!/usr/bin/env python3
"""Collect free XAUS indicative samples and retain a rolling 90-day archive.

This is sampled public spot data, not XM Bid/Ask, exchange OHLCV, or execution data.
"""
import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://xaus.com/api/v1/intraday?symbol=xau&hours=48"
SNAPSHOT = Path("web/public/data/market-snapshot.json")
HISTORY = Path("web/public/data/market-history.json")
MAX_AGE_SECONDS = 15 * 60
RETENTION_SECONDS = 90 * 24 * 60 * 60


def read_points(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw = payload.get("points", [])
    except (OSError, ValueError, AttributeError):
        return []
    result = []
    for item in raw if isinstance(raw, list) else []:
        try:
            stamp, price = int(float(item["t"])), float(item["p"])
        except (KeyError, TypeError, ValueError):
            continue
        if stamp > 0 and math.isfinite(price) and price > 0:
            result.append({"t": stamp, "p": price})
    return result


def main():
    request = urllib.request.Request(URL, headers={
        "Accept": "application/json",
        "User-Agent": "GoldLiquidityAI-FreeCollector/1.0",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict):
        raise RuntimeError("XAUS response is not a JSON object")
    incoming = read_points_from_payload(payload)
    incoming = list({p["t"]: p for p in incoming}.values())
    incoming.sort(key=lambda p: p["t"])
    if len(incoming) < 3:
        raise RuntimeError("XAUS returned fewer than 3 valid samples")

    now = int(time.time())
    age = now - incoming[-1]["t"]
    if age < 0 or age > MAX_AGE_SECONDS:
        raise RuntimeError(f"Latest XAUS sample is stale/future (age={age}s); refusing to publish")

    # Preserve earlier samples from previous successful scheduled runs.
    merged = {p["t"]: p for p in read_points(HISTORY)}
    merged.update({p["t"]: p for p in incoming})
    points = [merged[k] for k in sorted(merged) if k >= now - RETENTION_SECONDS]
    meta = {
        "schema_version": 1,
        "source": "XAUS public indicative XAU spot",
        "data_kind": "free_public_sampled",
        "not_broker_quote": True,
        "not_execution_data": True,
        "sample_interval_seconds": 300,
        "retention_days": 90,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "latest_sample_age_seconds": age,
        "data_state": payload.get("data_state", {}),
        "points": points,
        "limitations": [
            "Indicative public spot samples, not XM Bid/Ask or broker ticks",
            "Five-minute samples, not true exchange OHLCV",
            "No real traded volume, order book, or institutional pending orders",
            "Historical coverage grows only while scheduled collection succeeds",
            "Not suitable for trade execution or guaranteed live signals",
        ],
    }
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps({**meta, "points": incoming}, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    HISTORY.write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved snapshot={len(incoming)} samples; archive={len(points)} samples; latest age={age}s")


def read_points_from_payload(payload):
    raw = payload.get("points", []) if isinstance(payload, dict) else []
    points = []
    for item in raw if isinstance(raw, list) else []:
        try:
            stamp, price = int(float(item["t"])), float(item["p"])
        except (KeyError, TypeError, ValueError):
            continue
        if stamp > 0 and math.isfinite(price) and price > 0:
            points.append({"t": stamp, "p": price})
    points = list({item["t"]: item for item in points}.values())
    points.sort(key=lambda item: item["t"])
    return points


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Collector failed safely: {exc}", file=sys.stderr)
        raise
