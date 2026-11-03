#!/usr/bin/env python3
"""Fetch and validate the free XAUS sampled XAU spot series for the public PWA.

This is indicative sampled spot data, not XM broker Bid/Ask, exchange OHLCV or
an execution feed. The workflow stores the raw samples with explicit provenance.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://xaus.com/api/v1/intraday?symbol=xau&hours=48"
OUT = Path("web/public/data/market-snapshot.json")
MAX_AGE_SECONDS = 15 * 60


def main():
    request = urllib.request.Request(URL, headers={"Accept": "application/json", "User-Agent": "GoldLiquidityAI-FreeCollector/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))

    raw = payload.get("points", [])
    points = []
    for item in raw if isinstance(raw, list) else []:
        try:
            stamp, price = int(float(item["t"])), float(item["p"])
        except (KeyError, TypeError, ValueError):
            continue
        if stamp > 0 and price > 0:
            points.append({"t": stamp, "p": price})
    points.sort(key=lambda item: item["t"])
    if len(points) < 3:
        raise RuntimeError("XAUS returned fewer than 3 valid samples")

    now = int(time.time())
    age = now - points[-1]["t"]
    if age < 0 or age > MAX_AGE_SECONDS:
        raise RuntimeError(f"Latest XAUS sample is stale/future (age={age}s); refusing to publish")

    result = {
        "schema_version": 1,
        "source": "XAUS public indicative XAU spot",
        "data_kind": "free_public_sampled",
        "not_broker_quote": True,
        "not_execution_data": True,
        "sample_interval_seconds": 300,
        "requested_hours": 48,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "latest_sample_age_seconds": age,
        "data_state": payload.get("data_state", {}),
        "points": points,
        "limitations": [
            "Indicative public spot samples, not XM Bid/Ask or broker ticks",
            "Five-minute samples, not true exchange OHLCV",
            "No real traded volume, order book, or institutional pending orders",
            "Not suitable for trade execution or guaranteed live signals"
        ]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(points)} samples; latest age={age}s; output={OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Collector failed safely: {exc}", file=sys.stderr)
        raise
