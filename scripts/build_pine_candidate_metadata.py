"""Build the Python-side manifest for strict Alpha/Pine event parity.

The reference manifest is supplied by the operator from the exact TradingView
script, chart and inputs. This command only mirrors verified identity fields
after checking the Python settings file against the exported Pine settings.
It does not assert that the two algorithms are equivalent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_TEXT = (
    "script_title",
    "pine_version",
    "symbol",
    "provider",
    "timezone",
    "timeframe",
    "bar_timestamp",
    "bar_confirmation",
)
TIMEFRAME_1H = {"1h", "60", "60m", "1 hour", "1hour"}


def build_candidate_metadata(
    reference: dict[str, Any],
    python_settings: dict[str, Any],
    *,
    source: str,
    symbol: str,
) -> dict[str, Any]:
    if not isinstance(reference, dict):
        raise ValueError("TradingView reference metadata must be a JSON object")
    if not isinstance(python_settings, dict) or not python_settings:
        raise ValueError("Python Alpha settings must be a non-empty JSON object")

    missing = [
        key for key in REQUIRED_TEXT
        if not isinstance(reference.get(key), str) or not reference[key].strip()
    ]
    if missing:
        raise ValueError("TradingView metadata has missing/blank fields: " + ", ".join(missing))

    if not isinstance(reference.get("settings"), dict) or not reference["settings"]:
        raise ValueError("TradingView metadata settings must be a non-empty JSON object")
    if reference["settings"] != python_settings:
        raise ValueError(
            "alpha-settings.json does not exactly match the settings in "
            "pine-reference-meta.json; refusing a parity comparison"
        )
    if reference["provider"] != source:
        raise ValueError(
            f"Workflow provider {source!r} does not match TradingView metadata "
            f"provider {reference['provider']!r}"
        )
    if reference["symbol"] != symbol:
        raise ValueError(
            f"Workflow symbol {symbol!r} does not match TradingView metadata "
            f"symbol {reference['symbol']!r}"
        )
    if reference["timeframe"].strip().lower() not in TIMEFRAME_1H:
        raise ValueError("This workflow exports 1H Python signals; Pine metadata timeframe must be 1H")
    if "utc" not in reference["timezone"].lower():
        raise ValueError("TradingView metadata timezone must explicitly identify UTC")
    if "open" not in reference["bar_timestamp"].lower():
        raise ValueError("bar_timestamp must describe UTC bar-open timestamps")
    if "confirm" not in reference["bar_confirmation"].lower():
        raise ValueError("bar_confirmation must explicitly describe confirmed/closed bars")

    candidate = {key: reference[key] for key in REQUIRED_TEXT}
    candidate["settings"] = python_settings
    candidate["implementation"] = "Python Alpha Signal Engine"
    candidate["implementation_source"] = "scripts/export_python_signal_events.py"
    candidate["manifest_note"] = (
        "Identity/settings copied from the supplied TradingView reference only after "
        "exact source, symbol, timeframe and settings checks. This metadata is not "
        "evidence of algorithmic parity; the per-bar comparison provides that evidence."
    )
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-meta", required=True)
    parser.add_argument("--python-settings", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    reference = json.loads(Path(args.reference_meta).read_text(encoding="utf-8"))
    settings = json.loads(Path(args.python_settings).read_text(encoding="utf-8"))
    candidate = build_candidate_metadata(
        reference, settings, source=args.source, symbol=args.symbol
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "candidate_metadata_ready",
        "source": args.source,
        "symbol": args.symbol,
        "timeframe": candidate["timeframe"],
        "settings_keys": len(candidate["settings"]),
        "note": "Actual candle-by-candle comparison is still required.",
    }, indent=2))


if __name__ == "__main__":
    main()
