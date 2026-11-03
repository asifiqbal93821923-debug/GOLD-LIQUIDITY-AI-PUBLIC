"""Unified 4H -> 1H -> 15M -> 5M decision gate.

Consumes normalized, closed-bar engine facts. It does not create a trade
unless every required layer agrees and a valid risk plan is supplied.
"""
from __future__ import annotations
from typing import Any

DIRECTION_MAP={"bullish":"BUY","bearish":"SELL","buy":"BUY","sell":"SELL"}

def _direction(item: Any) -> str | None:
    if not isinstance(item,dict): return None
    return DIRECTION_MAP.get(str(item.get("direction","")).lower())

def analyze_unified_decision(payload: dict[str,Any]) -> dict[str,Any]:
    reasons=[]
    data=payload.get("data")
    if not isinstance(data,dict) or data.get("fresh") is not True or data.get("complete") is not True:
        reasons.append("DATA_NOT_FRESH_OR_COMPLETE")
    required=("4h_bias","1h_bias","15m_structure","5m_trigger")
    directions={}
    for key in required:
        item=payload.get(key)
        if not isinstance(item,dict) or item.get("status")!="ok":
            reasons.append(f"{key.upper()}_NOT_READY"); continue
        if item.get("confirmed") is not True:
            reasons.append(f"{key.upper()}_BAR_NOT_CONFIRMED")
        d=_direction(item)
        if d is None: reasons.append(f"{key.upper()}_DIRECTION_MISSING")
        else: directions[key]=d
    # 4H is macro veto, 1H is primary direction; 15M and 5M must confirm.
    if len(directions)==4:
        primary=directions["1h_bias"]
        if directions["4h_bias"]!=primary: reasons.append("FOUR_HOUR_MACRO_CONFLICT")
        if directions["15m_structure"]!=primary: reasons.append("FIFTEEN_MINUTE_STRUCTURE_CONFLICT")
        if directions["5m_trigger"]!=primary: reasons.append("FIVE_MINUTE_TRIGGER_CONFLICT")
    else: primary=None
    optional_1h=payload.get("1h_structure_confirm")
    if optional_1h is not None:
        d=_direction(optional_1h)
        if optional_1h.get("status")!="ok" or optional_1h.get("confirmed") is not True:
            reasons.append("ONE_HOUR_STRUCTURE_NOT_CONFIRMED")
        elif primary and d and d!=primary:
            reasons.append("ONE_HOUR_STRUCTURE_CONFLICT")
    spread=payload.get("spread")
    if not isinstance(spread,dict) or spread.get("acceptable") is not True:
        reasons.append("SPREAD_NOT_ACCEPTABLE")
    plan=payload.get("trade_plan")
    valid=isinstance(plan,dict) and plan.get("valid") is True
    if not valid: reasons.append("TRADE_PLAN_INVALID")
    else:
        entry=plan.get("entry"); stop=plan.get("stop_loss"); targets=plan.get("targets")
        prices=(isinstance(entry,list) and len(entry)==2 and all(isinstance(x,(int,float)) for x in entry)
          and entry[0]<=entry[1] and isinstance(stop,(int,float))
          and isinstance(targets,list) and len(targets)==3 and all(isinstance(x,(int,float)) for x in targets))
        if not prices: reasons.append("TRADE_PLAN_LEVELS_INVALID")
        elif primary:
            mid=sum(entry)/2
            if primary=="BUY":
                if not stop<mid or not (mid<targets[0]<targets[1]<targets[2]): reasons.append("LONG_RISK_LEVELS_INVALID")
            else:
                if not stop>mid or not (mid>targets[0]>targets[1]>targets[2]): reasons.append("SHORT_RISK_LEVELS_INVALID")
    if reasons:
        return {"status":"ok","decision":"WAIT","direction":"neutral",
          "reason_codes":sorted(set(reasons)),"evidence_groups_passed":0,"trade_plan":None,
          "hierarchy":{"4h":"macro_veto","1h":"primary_bias","15m":"setup_structure","5m":"entry_trigger"},
          "note":"WAIT-first decision. Missing feed, unconfirmed bars, conflict or invalid risk plan blocks entry."}
    side=directions["1h_bias"]
    return {"status":"ok","decision":side,"direction":"bullish" if side=="BUY" else "bearish",
      "reason_codes":["4H_1H_15M_5M_ALIGNED","RISK_PLAN_VALID","SPREAD_ACCEPTABLE"],
      "evidence_groups_passed":4,"trade_plan":{"entry":plan["entry"],"stop_loss":plan["stop_loss"],"targets":plan["targets"]},
      "hierarchy":{"4h":"macro_confirmation","1h":"primary_decision","15m":"setup_confirmation","5m":"entry_confirmation"},
      "note":"Confluence passed; not a profitability guarantee. Pine parity, historical and out-of-sample validation remain required."}
