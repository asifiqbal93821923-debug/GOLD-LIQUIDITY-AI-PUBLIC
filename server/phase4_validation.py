"""One-call Phase 4 historical validation orchestration.

The orchestrator combines data-quality checks, causal MTF replay, execution-cost
stress scenarios, and chronological walk-forward/holdout evaluation. It never
claims TradingView parity or broker-cost verification without supplied evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from .data_audit import audit_candle_history
    from .multitimeframe_backtest import run_gold_mtf_backtest
except ImportError:
    from data_audit import audit_candle_history
    from multitimeframe_backtest import run_gold_mtf_backtest

from scripts.execution_cost_scenarios import run_cost_scenarios
from scripts.rolling_walk_forward_validation import run_rolling_walk_forward
from scripts.research_cost_policy import with_fail_closed_spread_gate

REQUIRED_TIMEFRAMES = ("4h", "1h", "15m")
ALL_TIMEFRAMES = ("4h", "1h", "15m", "5m")
METRIC_KEYS = (
    "status", "trade_count", "win_rate_pct", "net_pnl_price", "average_R",
    "profit_factor", "max_drawdown_price", "signals_evaluated",
    "accepted_signals", "skipped_signals", "veto_counts", "spread_gate",
)


def _metric_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {key: report.get(key) for key in METRIC_KEYS if key in report}


def _finite_number(values: dict[str, Any], key: str, *, positive: bool = False) -> tuple[float | None, str | None]:
    try:
        value = float(values.get(key))
    except (TypeError, ValueError):
        return None, f"{key} must be a numeric value."
    if not isfinite(value):
        return None, f"{key} must be finite."
    if positive and value <= 0:
        return None, f"{key} must be greater than zero."
    if not positive and value < 0:
        return None, f"{key} must be non-negative."
    return value, None


def _preflight(
    frames: dict[str, list[dict[str, Any]]],
    costs: dict[str, Any],
    metadata: dict[str, Any],
    now_epoch: int,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str], dict[str, Any]]:
    audits: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    warnings: list[str] = []

    for tf in ALL_TIMEFRAMES:
        rows = frames.get(tf) or []
        if rows:
            audits[tf] = audit_candle_history(rows, tf, now_epoch)
        else:
            audits[tf] = {
                "status": "missing", "timeframe": tf, "received_rows": 0,
                "valid_unique_rows": 0, "invalid_rows": 0, "duplicate_rows": 0,
                "out_of_order_rows": 0, "closed_rows": 0, "forming_rows": 0,
                "future_rows": 0, "gap_count": 0, "estimated_missing_intervals": 0,
            }

        audit = audits[tf]
        if tf in REQUIRED_TIMEFRAMES:
            if not rows:
                blockers.append(f"{tf.upper()}: required history is missing.")
            if audit.get("invalid_rows", 0) > 0:
                blockers.append(f"{tf.upper()}: invalid OHLC/volume rows or duplicate timestamps were found.")
            if audit.get("out_of_order_rows", 0) > 0:
                blockers.append(f"{tf.upper()}: candles are not in chronological order.")
            if audit.get("future_rows", 0) > 0:
                blockers.append(f"{tf.upper()}: future-dated candles are present.")
            if audit.get("closed_rows", 0) < 50:
                blockers.append(f"{tf.upper()}: only {audit.get('closed_rows', 0)} closed bars; at least 50 are required.")
        elif rows:
            if audit.get("invalid_rows", 0) or audit.get("out_of_order_rows", 0) or audit.get("future_rows", 0):
                blockers.append("5M: supplied optional data contains invalid, out-of-order, or future candles.")
            if audit.get("closed_rows", 0) < 30:
                warnings.append("5M history has fewer than 30 closed candles; MTF replay will omit 5M refinement.")
        else:
            warnings.append("5M data was not supplied; the replay will run without optional 5M refinement.")

        if audit.get("gap_count", 0):
            warnings.append(
                f"{tf.upper()}: {audit['gap_count']} calendar-time gaps detected "
                "(weekends/session closures are not automatically treated as feed faults)."
            )
        if audit.get("forming_rows", 0):
            warnings.append(
                f"{tf.upper()}: {audit['forming_rows']} currently-forming candle(s) will be excluded from replay."
            )

    symbol = str(metadata.get("symbol", "")).strip().upper()
    provider = str(metadata.get("provider", "")).strip()
    timezone_name = str(metadata.get("timezone", "")).strip()
    if symbol != "XAUUSD":
        blockers.append("Symbol must be explicitly confirmed as XAUUSD.")
    if not provider:
        blockers.append("Data provider/broker name is required.")
    if not timezone_name:
        blockers.append("Dataset timezone is required.")
    else:
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            blockers.append("Timezone must be a valid IANA name such as UTC or Asia/Kolkata.")
    if metadata.get("same_feed_confirmed") is not True:
        blockers.append("Same-feed confirmation for the supplied timeframes is required.")
    warnings.append(
        "Provider, timezone and same-feed declaration are user-attested metadata; "
        "the app cannot independently authenticate the CSV's origin."
    )

    normalized_costs: dict[str, Any] = {}
    for key, positive in (
        ("point_size", True),
        ("spread_points", False),
        ("slippage_points", False),
        ("commission_points_per_side", False),
        ("max_spread_points", True),
    ):
        value, error = _finite_number(costs, key, positive=positive)
        if error:
            blockers.append(error)
        elif value is not None:
            normalized_costs[key] = value

    if all(key in normalized_costs for key in ("spread_points", "max_spread_points")):
        if normalized_costs["spread_points"] > normalized_costs["max_spread_points"]:
            blockers.append("Observed spread is above the configured maximum-spread cap.")
    normalized_costs["require_spread_limit"] = True
    return audits, blockers, warnings, normalized_costs


def run_phase4_validation(
    timeframes: dict[str, list[dict[str, Any]]],
    *,
    costs: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    folds: int = 4,
) -> dict[str, Any]:
    """Run Phase 4 preflight, replay, cost scenarios and OOS validation."""
    costs = dict(costs or {})
    metadata = dict(metadata or {})
    settings = dict(settings or {})
    if not isinstance(folds, int) or folds < 2 or folds > 4:
        return {
            "phase": "PHASE_4", "status": "blocked",
            "final_certification": "NOT_CERTIFIED",
            "blockers": ["Walk-forward folds must be between 2 and 4."],
        }

    frames = {tf: list(timeframes.get(tf) or []) for tf in ALL_TIMEFRAMES}
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    audits, blockers, warnings, normalized_costs = _preflight(
        frames, costs, metadata, now_epoch
    )
    report: dict[str, Any] = {
        "phase": "PHASE_4",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked",
        "data_audit": audits,
        "feed_provenance": {
            "symbol": str(metadata.get("symbol", "")).strip().upper() or None,
            "provider": str(metadata.get("provider", "")).strip() or None,
            "timezone": str(metadata.get("timezone", "")).strip() or None,
            "same_feed_user_attested": metadata.get("same_feed_confirmed") is True,
            "independently_verified": False,
        },
        "warnings": warnings,
        "blockers": blockers,
        "baseline_replay": {"status": "not_run"},
        "execution_cost_scenarios": {"status": "not_run"},
        "walk_forward": {"status": "not_run"},
        "pine_parity": {
            "status": "blocked_missing_reference",
            "required": "Matching TradingView confirmed-bar CSV export and exact Pine version/settings metadata.",
        },
        "broker_cost_verification": {
            "status": "unverified",
            "note": "Entered spread, slippage, commission and point size are assumptions until supported by timestamped broker evidence.",
        },
        "live_mt5_feed": {"status": "not_verified"},
        "paper_forward_test": {"status": "not_started"},
        "final_certification": "NOT_CERTIFIED",
        "cost_inputs": normalized_costs,
    }
    if blockers:
        return report

    safe_costs = with_fail_closed_spread_gate(normalized_costs)
    replay = run_gold_mtf_backtest(frames, costs=safe_costs, settings=settings)
    report["baseline_replay"] = _metric_summary(replay)
    if replay.get("status") != "ok":
        report["blockers"].append(
            f"Baseline causal MTF replay could not complete: {replay.get('reason') or replay.get('status')}."
        )
        return report

    scenarios = run_cost_scenarios(
        frames,
        spread=safe_costs["spread_points"],
        slippage=safe_costs["slippage_points"],
        commission=safe_costs["commission_points_per_side"],
        point_size=safe_costs["point_size"],
        max_spread=safe_costs["max_spread_points"],
        provenance={
            "broker_costs_verified": False,
            "source": metadata.get("provider"),
            "note": "User-entered assumptions; broker evidence has not been supplied.",
        },
    )
    report["execution_cost_scenarios"] = scenarios

    # Use pre-window candles only to warm indicators/structure. Trade-start
    # gating prevents these context bars from being counted as OOS trades.
    wfo = run_rolling_walk_forward(
        frames,
        folds=folds,
        train_fraction=0.50,
        test_fraction=0.10,
        holdout_fraction=0.10,
        mode="anchored",
        costs=safe_costs,
        settings=settings,
        min_bars=50,
    )
    report["walk_forward"] = wfo
    report["research_scope"] = {
        "strategy": "Current Python Gold Report adapters; fixed default/configured settings",
        "timeframe_hierarchy": "4H macro · 1H primary · 15M setup · optional 5M refinement",
        "entry_execution": "next available 1H bar, entry-zone validation",
        "intrabar_ambiguity": "conservative stop-first",
        "cost_scenarios": ["base", "conservative", "adverse"],
        "walk_forward": "Chronological disjoint OOS folds plus one sealed 10% holdout",
        "oos_warmup": "last 50 pre-window bars per timeframe; excluded from OOS trade counting",
        "parameter_selection": "No tuning on OOS or sealed holdout; settings remain fixed",
        "pine_parity": "not certified",
    }
    if wfo.get("status") == "ok" and scenarios.get("status") == "ok":
        report["status"] = "complete_not_certified"
    else:
        report["status"] = "partial"
        if wfo.get("status") != "ok":
            report["blockers"].append(
                f"Walk-forward/OOS did not complete all folds: {wfo.get('reason') or wfo.get('status')}."
            )
        if scenarios.get("status") != "ok":
            report["blockers"].append("One or more execution-cost scenario replays were incomplete.")

    report["blockers"].extend([
        "TradingView/Pine candle-by-candle parity remains unverified until the matching export and settings are supplied.",
        "Broker spread, slippage, commission and point-size assumptions are not independently verified.",
        "Authenticated MT5 candles and bid/ask ticks have not been confirmed live in the user's terminal.",
        "A persistent forward paper-trading run has not yet been observed.",
    ])
    report["performance_interpretation"] = {
        "baseline_trade_count": replay.get("trade_count", 0),
        "baseline_expectancy_R": replay.get("average_R"),
        "baseline_profit_factor": replay.get("profit_factor"),
        "baseline_max_drawdown_price": replay.get("max_drawdown_price"),
        "oos_zero_or_nonpositive_folds": (
            wfo.get("aggregate_oos", {}).get("losing_or_zero_trade_or_nonpositive_folds")
            if isinstance(wfo, dict) else None
        ),
        "profitability_claim": False,
        "note": "A completed replay means the calculations ran, not that the strategy is profitable. Judge sample size, expectancy, costs, drawdown and unseen folds—not win rate alone.",
    }
    return report
