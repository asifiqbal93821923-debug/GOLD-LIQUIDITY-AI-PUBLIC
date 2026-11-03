"""WAIT-first confluence gate for the Unified Gold Intelligence Engine.

This module combines normalized engine outputs; it does not calculate indicators.
All upstream modules must provide closed-bar, timestamped facts.
"""
from __future__ import annotations
from typing import Any

TIMEFRAME_KEYS = ("4h_bias", "1h_bias", "15m_structure", "5m_trigger")
DIRECTION_MAP = {"bullish": "BUY", "bearish": "SELL", "buy": "BUY", "sell": "SELL"}

def _direction(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    value = str(item.get("direction", "")).lower()
    return DIRECTION_MAP.get(value)

def analyze_unified_decision(payload: dict[str, Any]) -> dict[str, Any]:
    """Return BUY/SELL only when HTF, structure, trigger and risk all agree.

    Required inputs:
      data: {fresh: true, complete: true}
      4h_bias, 1h_bias, 15m_structure, 5m_trigger:
        {status: "ok", direction: "bullish"|"bearish", confirmed: true}
      trade_plan: {valid: true, entry: [low, high], stop_loss: number,
                   targets: [tp1, tp2, tp3]}
      spread: {acceptable: true}

    The endpoint is deliberately conservative. Missing or malformed evidence
    produces WAIT with explicit reason codes; it never invents price levels.
    """
    reasons: list[str] = []
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("fresh") is not True or data.get("complete") is not True:
        reasons.append("DATA_NOT_FRESH_OR_COMPLETE")

    directions: dict[str, str] = {}
    for key in TIMEFRAME_KEYS:
        item = payload.get(key)
        if not isinstance(item, dict) or item.get("status") != "ok":
            reasons.append(f"{key.upper()}_NOT_READY")
            continue
        if item.get("confirmed") is not True:
            reasons.append(f"{key.upper()}_BAR_NOT_CONFIRMED")
        direction = _direction(item)
        if direction is None:
            reasons.append(f"{key.upper()}_DIRECTION_MISSING")
        else:
            directions[key] = direction

    if len(directions) == len(TIMEFRAME_KEYS) and len(set(directions.values())) != 1:
        reasons.append("TIMEFRAME_DIRECTION_CONFLICT")

    spread = payload.get("spread")
    if not isinstance(spread, dict) or spread.get("acceptable") is not True:
        reasons.append("SPREAD_NOT_ACCEPTABLE")

    plan = payload.get("trade_plan")
    plan_valid = isinstance(plan, dict) and plan.get("valid") is True
    if not plan_valid:
        reasons.append("TRADE_PLAN_INVALID")
    else:
        entry = plan.get("entry")
        stop = plan.get("stop_loss")
        targets = plan.get("targets")
        valid_prices = (
            isinstance(entry, list) and len(entry) == 2
            and all(isinstance(x, (int, float)) for x in entry)
            and entry[0] <= entry[1]
            and isinstance(stop, (int, float))
            and isinstance(targets, list) and len(targets) == 3
            and all(isinstance(x, (int, float)) for x in targets)
        )
        if not valid_prices:
            reasons.append("TRADE_PLAN_LEVELS_INVALID")
        elif len(directions) == len(TIMEFRAME_KEYS) and len(set(directions.values())) == 1:
            side = next(iter(directions.values()))
            midpoint = (entry[0] + entry[1]) / 2
            if side == "BUY" and not (stop < midpoint and targets[0] > midpoint):
                reasons.append("LONG_RISK_LEVELS_INVALID")
            if side == "SELL" and not (stop > midpoint and targets[0] < midpoint):
                reasons.append("SHORT_RISK_LEVELS_INVALID")

    if reasons:
        return {
            "status": "ok",
            "decision": "WAIT",
            "direction": "neutral",
            "reason_codes": sorted(set(reasons)),
            "evidence_groups_passed": 0,
            "trade_plan": None,
            "note": "WAIT-first gate only; no indicator calculations or live price data are performed here.",
        }

    side = next(iter(directions.values()))
    return {
        "status": "ok",
        "decision": side,
        "direction": "bullish" if side == "BUY" else "bearish",
        "reason_codes": ["HTF_STRUCTURE_TRIGGER_AND_RISK_ALIGNED"],
        "evidence_groups_passed": 4,
        "trade_plan": {
            "entry": plan["entry"],
            "stop_loss": plan["stop_loss"],
            "targets": plan["targets"],
        },
        "note": "Decision gate passed. This is not a profitability guarantee; upstream engine parity and historical validation are still required.",
    }
