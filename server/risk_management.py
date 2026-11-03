"""Conservative Phase 3 risk guard and position-size estimator."""
from __future__ import annotations
from datetime import datetime, timezone
import math
from typing import Any

DEFAULT_RISK_SETTINGS: dict[str, Any] = {
    "account_balance": None, "contract_size": None, "risk_percent": 0.5,
    "max_daily_loss_percent": 2.0, "max_trades_per_day": 3, "max_open_trades": 1,
    "cooldown_minutes": 60, "min_reward_risk": 1.0, "max_spread_points": None,
}

def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

def normalize_risk_settings(candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("Risk settings must be an object.")
    settings = {**DEFAULT_RISK_SETTINGS, **candidate}
    for key in ("account_balance", "contract_size", "max_spread_points"):
        value = settings.get(key)
        if value in (None, ""): settings[key] = None
        elif not _finite(value) or float(value) <= 0:
            raise ValueError(f"{key} must be a positive finite number or blank.")
        else: settings[key] = float(value)
    for key, low, high in (("risk_percent", 0.01, 5.0),
                           ("max_daily_loss_percent", 0.1, 20.0),
                           ("min_reward_risk", 0.1, 10.0)):
        value = settings.get(key)
        if not _finite(value) or not low <= float(value) <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
        settings[key] = float(value)
    for key, low, high in (("max_trades_per_day", 1, 50), ("max_open_trades", 1, 20),
                           ("cooldown_minutes", 0, 1440)):
        value = settings.get(key)
        if not _finite(value) or int(value) != float(value) or not low <= int(value) <= high:
            raise ValueError(f"{key} must be a whole number between {low} and {high}.")
        settings[key] = int(value)
    return {key: settings[key] for key in DEFAULT_RISK_SETTINGS}

def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value: return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError: return None

def evaluate_risk(decision: dict[str, Any], quote: dict[str, Any], settings: dict[str, Any],
                  journal: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    side = decision.get("decision") if isinstance(decision, dict) else None
    if side not in {"BUY", "SELL"}:
        return {"status": "not_eligible", "approved_for_alert": False,
                "blocking_reasons": ["NO_CONFIRMED_DIRECTIONAL_SIGNAL"], "position_size": None}
    plan = decision.get("trade_plan") or {}
    entry, targets, sl = plan.get("entry") or [], plan.get("targets") or [], plan.get("stop_loss")
    if len(entry) != 2 or len(targets) != 3 or not all(_finite(x) for x in [*entry, sl, *targets]):
        return {"status": "blocked", "approved_for_alert": False,
                "blocking_reasons": ["INVALID_RISK_PLAN"], "position_size": None}
    mid = (float(entry[0]) + float(entry[1])) / 2.0
    risk_distance = abs(mid - float(sl))
    reward_distance = abs(float(targets[0]) - mid)
    rr = reward_distance / risk_distance if risk_distance > 0 else 0.0
    blocks: list[str] = []
    warnings: list[str] = []
    spread = quote.get("spread_points") if isinstance(quote, dict) else None
    if quote.get("acceptable") is not True: blocks.append("BROKER_SPREAD_GATE_CLOSED")
    user_cap = settings.get("max_spread_points")
    if user_cap is not None and (not _finite(spread) or float(spread) > float(user_cap)):
        blocks.append("USER_MAX_SPREAD_EXCEEDED")
    if rr < float(settings["min_reward_risk"]): blocks.append("MINIMUM_REWARD_RISK_NOT_MET")
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    opened_today = open_trades = 0
    realized_today = 0.0
    latest_trade_time = None
    for trade in journal:
        status = str(trade.get("status", "")).upper()
        opened = _parse_time(trade.get("opened_at") or trade.get("created_at"))
        if opened and opened >= day_start: opened_today += 1
        if status == "OPEN": open_trades += 1
        closed = _parse_time(trade.get("closed_at"))
        if closed and closed >= day_start and _finite(trade.get("pnl_money")):
            realized_today += float(trade["pnl_money"])
        reference = closed or opened
        if reference and (latest_trade_time is None or reference > latest_trade_time):
            latest_trade_time = reference
    if opened_today >= int(settings["max_trades_per_day"]): blocks.append("MAX_TRADES_PER_DAY_REACHED")
    if open_trades >= int(settings["max_open_trades"]): blocks.append("MAX_OPEN_TRADES_REACHED")
    cooldown = int(settings["cooldown_minutes"])
    if latest_trade_time and cooldown:
        elapsed = (now - latest_trade_time).total_seconds() / 60.0
        if 0 <= elapsed < cooldown: blocks.append("TRADE_COOLDOWN_ACTIVE")
    balance = settings.get("account_balance")
    if balance is None: warnings.append("ACCOUNT_BALANCE_NOT_CONFIGURED_DAILY_LOSS_CAP_NOT_ENFORCED")
    elif realized_today <= -(float(balance) * float(settings["max_daily_loss_percent"]) / 100.0):
        blocks.append("MAX_DAILY_LOSS_REACHED")
    contract_size = settings.get("contract_size")
    position_size = None
    if balance is None: warnings.append("POSITION_SIZE_REQUIRES_ACCOUNT_BALANCE")
    elif contract_size is None: warnings.append("POSITION_SIZE_REQUIRES_BROKER_CONTRACT_SIZE")
    elif risk_distance > 0:
        risk_cash = float(balance) * float(settings["risk_percent"]) / 100.0
        lots = risk_cash / (risk_distance * float(contract_size))
        if _finite(lots) and lots > 0:
            position_size = {"risk_cash": round(risk_cash, 2), "risk_percent": float(settings["risk_percent"]),
                "stop_distance_price": round(risk_distance, 5), "contract_size": float(contract_size),
                "estimated_lots": round(lots, 4),
                "note": "Estimate only. Confirm contract size, tick value, lot step and margin with the broker before use."}
    return {"status": "approved" if not blocks else "blocked", "approved_for_alert": not blocks,
        "blocking_reasons": sorted(set(blocks)), "warnings": warnings,
        "reward_risk_to_tp1": round(rr, 2), "minimum_reward_risk": float(settings["min_reward_risk"]),
        "daily": {"trades_opened_utc_today": opened_today, "open_trades": open_trades,
            "realized_pnl_utc_today": round(realized_today, 2),
            "daily_loss_limit_cash": round(float(balance) * float(settings["max_daily_loss_percent"]) / 100.0, 2) if balance is not None else None},
        "position_size": position_size}
