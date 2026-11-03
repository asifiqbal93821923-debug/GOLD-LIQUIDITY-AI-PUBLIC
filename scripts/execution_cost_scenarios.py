"""P2.5 realistic execution-cost scenario runner for the causal XAUUSD MTF replay.

Runs identical strategy settings over explicit base/conservative/adverse costs.
No scenario is broker-verified unless the input provenance says so. OHLC-only
execution remains conservative stop-first and cannot model true intrabar fills.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from server.multitimeframe_backtest import run_gold_mtf_backtest

def build_scenarios(spread: float, slippage: float, commission: float,
                    point_size: float, max_spread: float) -> dict:
    values = (spread, slippage, commission, point_size, max_spread)
    if any(not math.isfinite(float(x)) for x in values) or any(x < 0 for x in (spread, slippage, commission, max_spread)) or point_size <= 0:
        raise ValueError("Costs and max spread must be non-negative; point size must be positive")
    base = {"spread_points": spread, "slippage_points": slippage,
            "commission_points_per_side": commission, "point_size": point_size,
            "max_spread_points": max_spread}
    def scaled(spread_mult: float, slip_mult: float, commission_mult: float):
        return {**base, "spread_points": spread * spread_mult,
                "slippage_points": slippage * slip_mult,
                "commission_points_per_side": commission * commission_mult}
    return {
        "base": base,
        "conservative": scaled(1.25, 1.5, 1.0),
        "adverse": scaled(1.75, 2.0, 1.25),
    }

def _metrics(report: dict) -> dict:
    keys = ("status", "trade_count", "win_rate_pct", "net_pnl_price",
            "average_R", "profit_factor", "max_drawdown_price",
            "accepted_signals", "signals_evaluated", "skipped_signals", "veto_counts")
    return {k: report.get(k) for k in keys}

def run_cost_scenarios(frames: dict, *, spread: float, slippage: float,
                       commission: float, point_size: float, max_spread: float,
                       provenance: dict | None = None) -> dict:
    scenarios = build_scenarios(spread, slippage, commission, point_size, max_spread)
    reports = {}
    for name, costs in scenarios.items():
        report = run_gold_mtf_backtest(frames, costs=costs)
        reports[name] = {"costs": costs, "metrics": _metrics(report)}
    statuses = [x["metrics"]["status"] for x in reports.values()]
    return {
        "status": "ok" if all(x == "ok" for x in statuses) else "partial",
        "phase": "P2.5",
        "method": "Identical causal MTF strategy replay with fixed strategy settings and three explicit execution-cost scenarios",
        "scenario_reports": reports,
        "scenario_order": ["base", "conservative", "adverse"],
        "broker_costs_verified": bool((provenance or {}).get("broker_costs_verified", False)),
        "cost_provenance": provenance or {"broker_costs_verified": False, "note": "No broker evidence supplied"},
        "spread_gate": {"max_spread_points": max_spread,
                        "closed_until_defensible_limit": max_spread <= 0,
                        "note": "A zero limit keeps the spread gate closed; positive limits require observed broker evidence."},
        "execution_limits": [
            "OHLC candles cannot determine true intrabar price path or queue position.",
            "Same-bar stop/target conflicts use conservative stop-first handling.",
            "Scenario multipliers are stress assumptions, not XM360 observed costs.",
            "Session and rollover cost curves require timestamped broker quote observations; this report does not invent them."
        ],
        "acceptance": {"scenario_engine_implemented": True,\n                       "spread_gate_fail_closed_implemented": True,
                       "broker_calibration_passed": bool((provenance or {}).get("broker_costs_verified", False)),
                       "session_rollover_quote_validation": False}
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True); ap.add_argument("--output", required=True)
    ap.add_argument("--spread-points", type=float, required=True)
    ap.add_argument("--slippage-points", type=float, required=True)
    ap.add_argument("--commission-points-per-side", type=float, default=0)
    ap.add_argument("--point-size", type=float, required=True)
    ap.add_argument("--max-spread-points", type=float, default=0)
    ap.add_argument("--provenance", help="Optional JSON file containing broker_costs_verified and evidence metadata")
    a = ap.parse_args()
    frames = json.loads(Path(a.input).read_text(encoding="utf-8"))
    provenance = json.loads(Path(a.provenance).read_text(encoding="utf-8")) if a.provenance else None
    result = run_cost_scenarios(frames, spread=a.spread_points, slippage=a.slippage_points,
        commission=a.commission_points_per_side, point_size=a.point_size,
        max_spread=a.max_spread_points, provenance=provenance)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(result, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "acceptance": result["acceptance"]}, indent=2))
    if result["status"] != "ok": raise SystemExit(2)

if __name__ == "__main__":
    main()
