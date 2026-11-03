"""Export the Alpha Python engine's per-bar signal series for Pine comparison."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from server.alpha_signal import analyze_alpha_signal


def export_signals(frames: dict, timeframe: str = "1h") -> list[dict]:
    candles = frames.get(timeframe) or []
    result = analyze_alpha_signal(candles)
    if result.get("status") != "ok":
        raise ValueError(f"{timeframe} Alpha engine not ready: {result}")
    by_index = {int(x["index"]): x["signal"] for x in result.get("signal_history", [])}
    return [{"time": int(bar["time"]), "signal": by_index.get(i, "WAIT")}
            for i, bar in enumerate(candles)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--timeframe", default="1h", choices=("4h", "1h", "15m", "5m"))
    ap.add_argument("--output", default="python-signals.csv")
    ap.add_argument("--settings", help="Optional JSON file containing exact Alpha engine input values")
    args = ap.parse_args()
    frames = json.loads(Path(args.input).read_text(encoding="utf-8"))
    settings = json.loads(Path(args.settings).read_text(encoding="utf-8")) if args.settings else None
    candles = frames.get(args.timeframe) or []
    result = analyze_alpha_signal(candles, settings)
    if result.get("status") != "ok":
        raise SystemExit(f"{args.timeframe} Alpha engine not ready: {result}")
    by_index = {int(x["index"]): x["signal"] for x in result.get("signal_history", [])}
    rows = [{"time": int(bar["time"]), "signal": by_index.get(i, "WAIT")}
            for i, bar in enumerate(candles)]
    with open(args.output, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("time", "signal"))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} {args.timeframe} bars; signals={sum(x['signal'] != 'WAIT' for x in rows)}")


if __name__ == "__main__":
    main()
