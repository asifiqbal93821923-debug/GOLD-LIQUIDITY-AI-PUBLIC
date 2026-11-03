"""Anchored/rolling chronological walk-forward validation for XAUUSD MTF replay.

Parameters and execution-cost assumptions are fixed across all folds. This tool
never tunes on a fold's test segment and never carries training trades into OOS.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from server.multitimeframe_backtest import run_gold_mtf_backtest
from server.market_data import validate_candles

REQUIRED = ("4h", "1h", "15m")
METRICS = ("trade_count", "win_rate_pct", "net_pnl_price", "average_R",
           "profit_factor", "max_drawdown_price", "accepted_signals", "signals_evaluated")

def _metric_view(report):
    return {key: report.get(key) for key in METRICS}

def run_rolling_walk_forward(frames, *, folds=4, train_fraction=0.50,
                             test_fraction=0.10, mode="anchored",
                             costs=None, settings=None, min_bars=50):
    if folds < 2:
        raise ValueError("folds must be at least 2")
    if not 0.30 <= train_fraction <= 0.85:
        raise ValueError("train_fraction must be 0.30..0.85")
    if not 0.05 <= test_fraction <= 0.30:
        raise ValueError("test_fraction must be 0.05..0.30")
    if mode not in ("anchored", "rolling"):
        raise ValueError("mode must be anchored or rolling")
    normalized = {}
    for tf in ("4h", "1h", "15m", "5m"):
        rows = frames.get(tf) or []
        if rows:
            normalized[tf] = validate_candles(rows)
    quality = frames.get("data_quality", {})
    if isinstance(quality, dict) and quality.get("status") not in (None, "ready_for_60_20_20_validation"):
        return {"status": "insufficient_history", "reason": "DATASET_QUALITY_GATE_FAILED", "data_quality": quality}
    missing = [tf for tf in REQUIRED if tf not in normalized]
    if missing:
        return {"status": "insufficient_history", "reason": "MISSING_TIMEFRAMES", "missing": missing}
    h1 = normalized["1h"]
    n = len(h1)
    train_n = int(n * train_fraction)
    test_n = int(n * test_fraction)
    if train_n < min_bars or test_n < min_bars or train_n + folds * test_n > n:
        return {"status": "insufficient_history", "reason": "NOT_ENOUGH_BARS_FOR_FOLDS",
                "bars_1h": n, "required_train_bars": min_bars,
                "required_test_bars_per_fold": min_bars,
                "requested_train_bars": train_n, "requested_test_bars_per_fold": test_n,
                "folds": folds}
    # Test windows are disjoint and chronological. Anchored training starts at
    # dataset start; rolling training uses a fixed train_n lookback.
    first_test = n - folds * test_n
    fold_results = []
    for i in range(folds):
        test_start = first_test + i * test_n
        test_end = test_start + test_n
        train_start = 0 if mode == "anchored" else max(0, test_start - train_n)
        train_end = test_start
        train_boundary = h1[train_start]["time"]
        test_boundary = h1[test_start]["time"]
        test_end_boundary = h1[test_end]["time"] if test_end < n else h1[-1]["time"] + 3600
        train_frames = {tf: [r for r in rows if train_boundary <= r["time"] < test_boundary]
                        for tf, rows in normalized.items()}
        test_frames = {tf: [r for r in rows if test_boundary <= r["time"] < test_end_boundary]
                       for tf, rows in normalized.items()}
        counts = {"train": {tf: len(train_frames.get(tf, [])) for tf in REQUIRED},
                  "test": {tf: len(test_frames.get(tf, [])) for tf in REQUIRED}}
        short = {part: {tf: count for tf, count in values.items() if count < min_bars}
                 for part, values in counts.items()}
        short = {k: v for k, v in short.items() if v}
        if short:
            return {"status": "insufficient_history", "reason": "FOLD_TIMEFRAME_MINIMUM_FAILED",
                    "fold": i + 1, "counts": counts, "short_partitions": short}
        # Both replays receive only their own chronological slice. Fixed settings
        # and costs are passed unchanged; no test outcome influences later folds.
        train_report = run_gold_mtf_backtest(train_frames, costs=costs, settings=settings)
        test_report = run_gold_mtf_backtest(test_frames, costs=costs, settings=settings)
        fold_results.append({
            "fold": i + 1, "train_start_epoch": train_boundary,
            "train_end_exclusive_epoch": test_boundary,
            "test_start_epoch": test_boundary, "test_end_exclusive_epoch": test_end_boundary,
            "train_bars": counts["train"], "test_bars": counts["test"],
            "train_status": train_report.get("status"),
            "test_status": test_report.get("status"),
            "train": _metric_view(train_report), "out_of_sample": _metric_view(test_report),
            "test_veto_counts": test_report.get("veto_counts"),
        })
    valid = [f for f in fold_results if f["test_status"] == "ok"]
    all_oos_trades = sum((f["out_of_sample"].get("trade_count") or 0) for f in valid)
    all_oos_signals = sum((f["out_of_sample"].get("signals_evaluated") or 0) for f in valid)
    all_oos_pnl = sum((f["out_of_sample"].get("net_pnl_price") or 0) for f in valid)
    losing_or_zero = [f["fold"] for f in fold_results
                      if f["test_status"] != "ok" or (f["out_of_sample"].get("trade_count") or 0) == 0
                      or (f["out_of_sample"].get("net_pnl_price") or 0) <= 0]
    provenance = frames.get("metadata", {}) if isinstance(frames.get("metadata"), dict) else {}
    return {
        "status": "ok" if len(valid) == folds else "partial",
        "method": f"{mode} walk-forward; disjoint chronological OOS windows; fixed parameters and costs",
        "fold_count": folds, "mode": mode, "train_fraction_of_total": train_fraction,
        "test_fraction_per_fold": test_fraction, "min_bars_per_timeframe_per_partition": min_bars,
        "feed_provenance": {"source": provenance.get("source"), "symbol": provenance.get("symbol")},
        "fixed_costs": costs or {}, "fixed_settings": settings or {},
        "folds": fold_results,
        "aggregate_oos": {"completed_folds": len(valid), "trade_count": all_oos_trades,
                          "signals_evaluated": all_oos_signals, "net_pnl_price": all_oos_pnl,
                          "losing_or_zero_trade_or_nonpositive_folds": losing_or_zero},
        "leakage_controls": {"train_test_overlap": False, "oos_windows_disjoint": True,
                             "training_trades_counted_as_oos": False,
                             "test_results_used_for_parameter_selection": False},
        "warning": "Walk-forward evidence is only as valid as the supplied same-feed data and broker costs. It is not a profitability guarantee."
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True); ap.add_argument("--output")
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--train-fraction", type=float, default=.50)
    ap.add_argument("--test-fraction", type=float, default=.10)
    ap.add_argument("--mode", choices=("anchored", "rolling"), default="anchored")
    ap.add_argument("--spread-points", type=float, required=True)
    ap.add_argument("--slippage-points", type=float, required=True)
    ap.add_argument("--commission-points-per-side", type=float, default=0)
    ap.add_argument("--point-size", type=float, required=True)
    a = ap.parse_args()
    if min(a.spread_points, a.slippage_points, a.commission_points_per_side) < 0 or a.point_size <= 0:
        ap.error("costs must be non-negative and point-size must be positive")
    frames = json.loads(Path(a.input).read_text(encoding="utf-8"))
    costs = {"spread_points": a.spread_points, "slippage_points": a.slippage_points,
             "commission_points_per_side": a.commission_points_per_side, "point_size": a.point_size}
    result = run_rolling_walk_forward(frames, folds=a.folds, train_fraction=a.train_fraction,
                                      test_fraction=a.test_fraction, mode=a.mode, costs=costs)
    raw = json.dumps(result, indent=2)
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(raw + "\n", encoding="utf-8")
    print(raw)
    if result.get("status") != "ok":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
