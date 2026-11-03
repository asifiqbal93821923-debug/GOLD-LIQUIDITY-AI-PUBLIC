"""Strict candle-by-candle TradingView/Python parity comparison.

Reference CSV is exported from TradingView Pine with one row per confirmed bar.
Required columns: time, signal. Optional numeric columns can be compared with
--numeric-columns "trend_line,atr,buy_level,sell_level".
Timestamps are UTC bar-open Unix seconds unless ISO-8601 with explicit timezone.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BUY = {"1", "1.0", "LONG", "BUY"}
SELL = {"-1", "-1.0", "SHORT", "SELL"}
WAIT = {"", "0", "0.0", "NONE", "FLAT", "WAIT", "NA", "N/A"}


def stamp(raw: str) -> int:
    s = raw.strip()
    try:
        n = float(s)
        if not math.isfinite(n):
            raise ValueError("non-finite timestamp")
        # Milliseconds are common in Pine exports; normalize to seconds.
        return int(n / 1000) if abs(n) >= 10_000_000_000 else int(n)
    except ValueError:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError(f"Timestamp must include timezone: {raw}")
        return int(dt.astimezone(timezone.utc).timestamp())


def side(raw: str) -> str:
    s = raw.strip().upper()
    if s in BUY:
        return "BUY"
    if s in SELL:
        return "SELL"
    if s in WAIT:
        return "WAIT"
    raise ValueError(f"Unsupported signal value: {raw!r}")


def load_csv(path: str, signal_column: str, numeric_columns: list[str]) -> dict[int, dict]:
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"time", signal_column, *numeric_columns}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"{path} requires columns {sorted(required)}; got {reader.fieldnames}")
        for line, row in enumerate(reader, 2):
            t = stamp(row["time"])
            if t in out:
                raise ValueError(f"{path}:{line}: duplicate timestamp {t}")
            values = {"signal": side(row[signal_column])}
            for col in numeric_columns:
                raw = row[col].strip()
                values[col] = None if raw == "" else float(raw)
                if values[col] is not None and not math.isfinite(values[col]):
                    raise ValueError(f"{path}:{line}: non-finite {col}")
            out[t] = values
    return out


def load_meta(path: str | None) -> dict | None:
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _metadata_issues(meta: dict | None, label: str) -> list[str]:
    if not isinstance(meta, dict):
        return [f"{label}: metadata must be a JSON object"]
    required_text = ("script_title", "pine_version", "symbol", "provider",
                     "timezone", "timeframe", "bar_timestamp", "bar_confirmation")
    issues = [f"{label}: missing/blank {key}" for key in required_text
              if not isinstance(meta.get(key), str) or not meta[key].strip()]
    settings = meta.get("settings")
    if not isinstance(settings, dict) or not settings:
        issues.append(f"{label}: settings must be a non-empty JSON object")
    return issues


def compare_metadata(reference_meta, candidate_meta):
    keys = ("script_title", "pine_version", "symbol", "provider", "timezone",
            "timeframe", "bar_timestamp", "bar_confirmation", "settings")
    differences = {}
    for key in keys:
        ref_value = reference_meta.get(key) if isinstance(reference_meta, dict) else None
        cand_value = candidate_meta.get(key) if isinstance(candidate_meta, dict) else None
        if ref_value != cand_value:
            differences[key] = {"tradingview": ref_value, "python": cand_value}
    issues = (_metadata_issues(reference_meta, "tradingview") +
              _metadata_issues(candidate_meta, "python"))
    return {"status": "PASS" if not differences and not issues else "FAIL",
            "differences": differences, "validation_errors": issues,
            "required_keys": list(keys)}


def compare(reference, candidate, numeric_columns=(), tolerance_seconds=0, numeric_tolerance=1e-8):
    # Backward-compatible input: older research tests pass {timestamp: "BUY"}.
    def normalize(rows):
        normalized = {}
        for timestamp, value in rows.items():
            normalized[timestamp] = value if isinstance(value, dict) else {"signal": side(str(value))}
        return normalized
    reference, candidate = normalize(reference), normalize(candidate)
    ref_times, cand_times = set(reference), set(candidate)
    common = sorted(ref_times & cand_times)
    missing = sorted(ref_times - cand_times)
    extra = sorted(cand_times - ref_times)
    confusion = {a: {b: 0 for b in ("BUY", "SELL", "WAIT")} for a in ("BUY", "SELL", "WAIT")}
    signal_mismatches = []
    numeric = {col: {"compared": 0, "mismatches": 0, "max_abs_error": 0.0} for col in numeric_columns}
    for t in common:
        a, b = reference[t]["signal"], candidate[t]["signal"]
        confusion[a][b] += 1
        if a != b:
            signal_mismatches.append({"time": t, "utc": datetime.fromtimestamp(t, timezone.utc).isoformat(),
                                      "tradingview": a, "python": b})
        for col in numeric_columns:
            av, bv = reference[t][col], candidate[t][col]
            if av is None or bv is None:
                if av != bv:
                    numeric[col]["mismatches"] += 1
                continue
            err = abs(av - bv)
            numeric[col]["compared"] += 1
            numeric[col]["max_abs_error"] = max(numeric[col]["max_abs_error"], err)
            if err > numeric_tolerance:
                numeric[col]["mismatches"] += 1
    signal_equal = len(common) > 0 and not signal_mismatches and not missing and not extra
    numeric_equal = all(x["mismatches"] == 0 and x["compared"] > 0 for x in numeric.values())
    return {
        "status": "PASS" if signal_equal and numeric_equal else "FAIL",
        "bars": {"tradingview": len(reference), "python": len(candidate), "common": len(common),
                 "missing_in_python": len(missing), "extra_in_python": len(extra)},
        "signal": {"exact_match": signal_equal,
                   "direction_accuracy_pct": round(100 * sum(confusion[s][s] for s in confusion) / len(common), 4) if common else None,
                   "confusion_matrix_rows_tradingview_cols_python": confusion,
                   "mismatch_count": len(signal_mismatches),
                   "mismatches_first_100": signal_mismatches[:100]},
        "numeric": numeric,
        "missing_timestamps_first_100": missing[:100],
        "extra_timestamps_first_100": extra[:100],
        "timestamp_matches": len(common),
        "direction_matches": sum(confusion[s][s] for s in confusion),
        "direction_accuracy_pct": round(100 * sum(confusion[s][s] for s in confusion) / len(common), 4) if common else 0.0,
        "timestamp_tolerance_seconds": tolerance_seconds,
        "note": "Strict exact timestamp join is used. Non-zero timestamp tolerance is diagnostic only and does not alter the candle-by-candle PASS gate."
    }


def compare_metadata(reference_meta, candidate_meta):
    keys = ("script_title", "pine_version", "symbol", "provider", "timezone",
            "timeframe", "bar_timestamp", "bar_confirmation", "settings")
    differences = {}
    for key in keys:
        if reference_meta.get(key) != candidate_meta.get(key):
            differences[key] = {"tradingview": reference_meta.get(key), "python": candidate_meta.get(key)}
    return {"status": "PASS" if not differences else "FAIL", "differences": differences,
            "required_keys": list(keys)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, help="TradingView per-bar CSV")
    ap.add_argument("--candidate", required=True, help="Python per-bar CSV")
    ap.add_argument("--signal-column", default="signal")
    ap.add_argument("--numeric-columns", default="")
    ap.add_argument("--reference-meta", required=True, help="Exact TradingView source/settings metadata JSON")
    ap.add_argument("--candidate-meta", required=True, help="Matching Python source/settings metadata JSON")
    ap.add_argument("--numeric-tolerance", type=float, default=1e-8)
    ap.add_argument("--output")
    a = ap.parse_args()
    if not math.isfinite(a.numeric_tolerance) or a.numeric_tolerance < 0:
        raise SystemExit("--numeric-tolerance must be a finite, non-negative number.")
    cols = [x.strip() for x in a.numeric_columns.split(",") if x.strip()]
    ref = load_csv(a.reference, a.signal_column, cols)
    cand = load_csv(a.candidate, "signal", cols)
    report = compare(ref, cand, cols, numeric_tolerance=a.numeric_tolerance)
    report["metadata"] = compare_metadata(load_meta(a.reference_meta), load_meta(a.candidate_meta))
    if report["metadata"]["status"] != "PASS":
        report["status"] = "FAIL"
    raw = json.dumps(report, indent=2)
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(raw + "\n", encoding="utf-8")
    print(raw)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
