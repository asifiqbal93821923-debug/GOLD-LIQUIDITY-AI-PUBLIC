"""Calibrate 1H structure/ATR entry, stop and targets on causal MTF replay.

Candidate selection uses train + validation only. The sealed test is evaluated
once after a winner is selected. This requires same-feed, closed MTF candles.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.optimize_alpha_settings import split_chronologically, robust_score
from server.multitimeframe_backtest import run_gold_mtf_backtest
from scripts.research_cost_policy import with_fail_closed_spread_gate

CANDIDATES = [
    {"atr_period": atr, "swing_lookback": lookback, "stop_atr_buffer": buffer,
     "entry_atr_half_width": width, "target_rr": list(rr)}
    for atr in (10, 15, 20)
    for lookback in (15, 30)
    for buffer in (0.05, 0.15)
    for width in (0.05, 0.15)
    for rr in ((1.0, 2.0, 3.0), (1.5, 2.5, 3.5))
]


def calibrate(frames: dict[str, list[dict[str, Any]]], costs: dict[str, float],
              min_trades: int = 10) -> dict[str, Any]:
    costs = with_fail_closed_spread_gate(costs)
    split = split_chronologically(frames)
    if split.get("status") != "ok":
        return {"status": "insufficient_history", "split": {k: v for k, v in split.items() if k != "partitions"}}
    parts = split["partitions"]
    ranked = []
    for index, params in enumerate(CANDIDATES):
        settings = {"trade_plan": params}
        train = run_gold_mtf_backtest(parts["train"], costs=costs, settings=settings)
        validation = run_gold_mtf_backtest(parts["validation"], costs=costs, settings=settings)
        if train.get("status") != "ok" or validation.get("status") != "ok":
            continue
        score = robust_score(train, validation, min_trades=min_trades)
        if score is not None:
            ranked.append({"candidate_index": index, "score": score, "parameters": params,
                           "train": _metrics(train), "validation": _metrics(validation)})
    if not ranked:
        return {
            "status": "no_robust_candidate",
            "candidate_count": len(CANDIDATES),
            "reason": "No candidate met minimum trades and positive net PnL in both train and validation.",
            "sealed_test_evaluated": False,
            "chronological_bar_counts": split.get("bar_counts"),
            "split_boundaries_epoch": split.get("boundary_epoch"),
            "costs": costs,
        }
    winner = max(ranked, key=lambda x: (x["score"], -x["candidate_index"]))
    # The sealed test is intentionally touched once, only after selection.
    sealed = run_gold_mtf_backtest(
        parts["test"], costs=costs, settings={"trade_plan": winner["parameters"]}
    )
    return {
        "status": "ok" if sealed.get("status") == "ok" else "sealed_test_blocked",
        "method": "60/20/20 chronological; candidate selection on train/validation only; single sealed evaluation",
        "candidate_count": len(CANDIDATES),
        "eligible_candidates": len(ranked),
        "winner": winner,
        "sealed_test": _metrics(sealed) if sealed.get("status") == "ok" else sealed,
        "sealed_test_evaluated": True,
        "chronological_bar_counts": split.get("bar_counts"),
        "split_boundaries_epoch": split.get("boundary_epoch"),
        "costs": costs,
        "warning": "Research calibration only. Not TradingView parity or a profitability guarantee; test is not to be re-optimized.",
    }


def _metrics(report: dict[str, Any]) -> dict[str, Any]:
    keys = ("trade_count", "win_rate_pct", "net_pnl_price", "average_R",
            "profit_factor", "max_drawdown_price", "accepted_signals",
            "signals_evaluated", "skipped_signals")
    result = {key: report.get(key) for key in keys}
    trades = report.get("trades") or []
    skipped = int(report.get("skipped_signals") or 0)
    signals = int(report.get("signals_evaluated") or 0)
    result["expectancy_R"] = (
        round(sum(float(t.get("net_R", 0.0)) for t in trades) / len(trades), 4)
        if trades else None
    )
    result["losing_trades"] = sum(1 for t in trades if float(t.get("net_pnl_price", 0.0)) < 0)
    result["skipped_signal_rate_pct"] = (
        round(100.0 * skipped / max(1, signals), 2) if signals else None
    )
    result["sample_size_warning"] = (
        "Small sample: interpret metrics cautiously." if len(trades) < 30 else None
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="trade-plan-calibration.json")
    ap.add_argument("--spread-points", type=float, required=True)
    ap.add_argument("--slippage-points", type=float, required=True)
    ap.add_argument("--commission-points-per-side", type=float, default=0)
    ap.add_argument("--point-size", type=float, default=0.01)
    ap.add_argument("--max-spread-points", type=float, required=True,
                    help="Defensible observed maximum spread; zero keeps all entries blocked")
    ap.add_argument("--min-trades", type=int, default=10)
    args = ap.parse_args()
    costs = {"spread_points": args.spread_points, "slippage_points": args.slippage_points,
             "commission_points_per_side": args.commission_points_per_side,
             "point_size": args.point_size, "max_spread_points": args.max_spread_points,
             "require_spread_limit": True}
    if (not all(math.isfinite(float(v)) for v in costs.values()) or min(costs.values()) < 0
            or costs["point_size"] <= 0):
        raise SystemExit("Costs must be non-negative and point-size positive")
    frames = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = calibrate(frames, costs, args.min_trades)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
