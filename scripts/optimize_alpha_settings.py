"""Deterministic parameter sweep for the Alpha Signal MTF engine.

Select parameters on chronological train/validation windows, then evaluate the
single selected candidate once on a sealed chronological test window.
This is research tooling, not a profitability guarantee or certified Pine parity.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from pathlib import Path
from typing import Any

from server.market_data import validate_candles
from server.multitimeframe_backtest import run_gold_mtf_backtest

TIMEFRAME_SECONDS = {"4h": 14_400, "1h": 3_600, "15m": 900, "5m": 300}
REQUIRED_TIMEFRAMES = ("4h", "1h", "15m")

BASE_ALPHA = {
    "atr_period": 14,
    "band_multiplier": 3.0,
    "atr_weight": 1.0,
    "price_move_weight": 5.0,
    "ema_smoothing": 1,
    "volatility_fingerprint": False,
    "vf_lookback": 300,
    "stall_filter": True,
    "flatness_threshold": 0.05,
    "slope_filter": True,
    "regression_length": 5,
    "slope_threshold": 0.05,
    "volume_filter": True,
    "volume_ma_length": 20,
    "range_filter": True,
    "range_lookback": 100,
    "range_percentile": 20.0,
    "bps_filter": True,
    "min_bps_delta": 1.0,
    "breakout_override": True,
    "breakout_atr_multiple": 1.5,
}


def parameter_candidates(count: int = 100, seed: int = 20261103) -> list[dict[str, Any]]:
    """Return a reproducible sample of a broad, bounded Alpha parameter grid."""
    if count < 1 or count > 500:
        raise ValueError("count must be between 1 and 500")
    axes = itertools.product(
        (10, 14, 18),                         # ATR period
        (2.5, 3.0, 3.5, 4.0),                 # band multiplier
        (0.75, 1.0, 1.25),                    # ATR weight
        (2.5, 5.0, 7.5),                      # price-move weight
        (0.03, 0.05, 0.08),                   # slope threshold
        (True, False),                        # volume filter
        (True, False),                        # range filter
        (0.5, 1.0, 1.5),                      # minimum BPS delta
    )
    names = (
        "atr_period", "band_multiplier", "atr_weight", "price_move_weight",
        "slope_threshold", "volume_filter", "range_filter", "min_bps_delta",
    )
    all_rows = [dict(zip(names, values)) for values in axes]
    base = {k: BASE_ALPHA[k] for k in names}
    all_rows = [x for x in all_rows if x != base]
    rng = random.Random(seed)
    rng.shuffle(all_rows)
    return [base] + all_rows[: count - 1]


def split_chronologically(
    frames: dict[str, list[dict[str, Any]]],
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    minimum_bars: int = 50,
) -> dict[str, Any]:
    """Create non-overlapping splits; bars crossing a boundary are excluded."""
    if not 0.50 <= train_fraction <= 0.70:
        raise ValueError("train_fraction must be 0.50..0.70")
    if not 0.10 <= validation_fraction <= 0.25:
        raise ValueError("validation_fraction must be 0.10..0.25")
    if train_fraction + validation_fraction >= 0.90:
        raise ValueError("At least 10% must remain for the sealed test window")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for tf in ("4h", "1h", "15m", "5m"):
        rows = frames.get(tf) or []
        normalized[tf] = validate_candles(rows) if rows else []
    missing = [tf for tf in REQUIRED_TIMEFRAMES if not normalized[tf]]
    if missing:
        return {"status": "insufficient_history", "reason": "MISSING_REQUIRED_TIMEFRAME", "missing": missing}

    h1 = normalized["1h"]
    cut1 = int(len(h1) * train_fraction)
    cut2 = int(len(h1) * (train_fraction + validation_fraction))
    if cut1 <= 0 or cut2 <= cut1 or cut2 >= len(h1):
        return {"status": "insufficient_history", "reason": "SPLIT_BOUNDARIES_INVALID"}
    boundary1, boundary2 = int(h1[cut1]["time"]), int(h1[cut2]["time"])

    partitions: dict[str, dict[str, list[dict[str, Any]]]] = {
        "train": {}, "validation": {}, "test": {}
    }
    for tf, rows in normalized.items():
        duration = TIMEFRAME_SECONDS[tf]
        partitions["train"][tf] = [
            x for x in rows if int(x["time"]) + duration <= boundary1
        ]
        partitions["validation"][tf] = [
            x for x in rows
            if int(x["time"]) >= boundary1 and int(x["time"]) + duration <= boundary2
        ]
        partitions["test"][tf] = [x for x in rows if int(x["time"]) >= boundary2]

    counts = {
        split: {tf: len(rows) for tf, rows in bucket.items()}
        for split, bucket in partitions.items()
    }
    short = {
        split: {tf: n for tf, n in counts[split].items() if tf in REQUIRED_TIMEFRAMES and n < minimum_bars}
        for split in partitions
    }
    short = {k: v for k, v in short.items() if v}
    if short:
        return {
            "status": "insufficient_history",
            "reason": "EACH_TRAIN_VALIDATION_TEST_WINDOW_REQUIRES_CLOSED_BARS",
            "minimum_bars_per_required_timeframe_per_window": minimum_bars,
            "bar_counts": counts,
            "short_windows": short,
            "required_4h_history_approx": minimum_bars / (1 - train_fraction - validation_fraction),
        }
    return {
        "status": "ok",
        "boundary_epoch": {"train_end": boundary1, "validation_end": boundary2},
        "bar_counts": counts,
        "partitions": partitions,
    }


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        if isinstance(value, str) and value.lower() == "infinite":
            return 5.0
        out = float(value)
        return out if out == out and abs(out) != float("inf") else default
    except (TypeError, ValueError):
        return default


def _metrics(report: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "trade_count", "win_rate_pct", "net_pnl_price", "average_R",
        "profit_factor", "max_drawdown_price", "accepted_signals", "signals_evaluated",
    )
    return {k: report.get(k) for k in fields}


def robust_score(train: dict[str, Any], validation: dict[str, Any], min_trades: int = 10) -> float | None:
    """Conservative score: worst split matters; reject weak/undersampled candidates."""
    if min(_num(train.get("trade_count")), _num(validation.get("trade_count"))) < min_trades:
        return None
    if min(_num(train.get("net_pnl_price")), _num(validation.get("net_pnl_price"))) <= 0:
        return None
    worst_r = min(_num(train.get("average_R")), _num(validation.get("average_R")))
    worst_pf = min(_num(train.get("profit_factor")), _num(validation.get("profit_factor")))
    worst_wr = min(_num(train.get("win_rate_pct")), _num(validation.get("win_rate_pct")))
    dd_ratio = max(
        _num(train.get("max_drawdown_price")) / max(abs(_num(train.get("net_pnl_price"))), 1e-9),
        _num(validation.get("max_drawdown_price")) / max(abs(_num(validation.get("net_pnl_price"))), 1e-9),
    )
    r_component = max(0.0, min(2.0, worst_r)) / 2.0
    pf_component = max(0.0, min(3.0, worst_pf)) / 3.0
    wr_component = max(0.0, min(100.0, worst_wr)) / 100.0
    dd_component = 1.0 - min(1.0, max(0.0, dd_ratio) / 2.0)
    return 0.45 * r_component + 0.30 * pf_component + 0.15 * wr_component + 0.10 * dd_component


def optimize_parameters(
    frames: dict[str, list[dict[str, Any]]],
    costs: dict[str, float],
    count: int = 100,
    seed: int = 20261103,
    min_trades: int = 10,
) -> dict[str, Any]:
    split = split_chronologically(frames)
    if split.get("status") != "ok":
        return split

    partitions = split["partitions"]
    ranked: list[dict[str, Any]] = []
    failed = 0
    for candidate_id, alpha in enumerate(parameter_candidates(count, seed), start=1):
        settings = {"alpha": alpha}
        train_report = run_gold_mtf_backtest(partitions["train"], costs=costs, settings=settings)
        if train_report.get("status") != "ok":
            failed += 1
            continue
        validation_report = run_gold_mtf_backtest(partitions["validation"], costs=costs, settings=settings)
        if validation_report.get("status") != "ok":
            failed += 1
            continue
        train_metrics, validation_metrics = _metrics(train_report), _metrics(validation_report)
        score = robust_score(train_metrics, validation_metrics, min_trades=min_trades)
        if score is None:
            failed += 1
            continue
        ranked.append({
            "candidate_id": candidate_id,
            "score": round(score, 6),
            "alpha_settings": alpha,
            "train": train_metrics,
            "validation": validation_metrics,
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    if not ranked:
        return {
            "status": "no_robust_candidate",
            "candidates_requested": count,
            "candidates_rejected_or_failed": failed,
            "reason": "No candidate passed minimum trade count and positive train/validation PnL gates.",
            "warning": "Do not lower gates just to force a winning configuration.",
            "bar_counts": split["bar_counts"],
        }

    # Touch the sealed test partition only once, for the selected candidate.
    winner = ranked[0]
    test_report = run_gold_mtf_backtest(
        partitions["test"], costs=costs, settings={"alpha": winner["alpha_settings"]}
    )
    if test_report.get("status") != "ok":
        return {
            "status": "selected_candidate_test_blocked",
            "winner_from_train_validation": winner,
            "test_status": test_report.get("status"),
            "test_reason": test_report.get("reason"),
            "bar_counts": split["bar_counts"],
        }
    return {
        "status": "ok",
        "method": "seeded parameter sweep; chronological 60/20/20; select on train+validation; sealed test evaluated once",
        "candidates_requested": count,
        "candidates_rejected_or_failed": failed,
        "robust_candidates": len(ranked),
        "selected": winner,
        "sealed_test": _metrics(test_report),
        "top_10_train_validation": ranked[:10],
        "bar_counts": split["bar_counts"],
        "cost_assumptions": costs,
        "warning": "Research only. No certified TradingView Pine parity, no guaranteed returns. Validate target-broker costs and repeat on additional unseen periods before live use.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON with 4h, 1h, 15m and optional 5m OHLCV arrays")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument("--candidates", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261103)
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--spread-points", type=float, required=True)
    parser.add_argument("--slippage-points", type=float, required=True)
    parser.add_argument("--commission-points-per-side", type=float, default=0.0)
    parser.add_argument("--point-size", type=float, default=0.01)
    args = parser.parse_args()
    costs = {
        "spread_points": args.spread_points,
        "slippage_points": args.slippage_points,
        "commission_points_per_side": args.commission_points_per_side,
        "point_size": args.point_size,
    }
    if args.point_size <= 0 or min(args.spread_points, args.slippage_points, args.commission_points_per_side) < 0:
        parser.error("point size must be positive and costs must be non-negative")
    frames = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = optimize_parameters(
        frames, costs, count=args.candidates, seed=args.seed, min_trades=args.min_trades
    )
    rendered = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
