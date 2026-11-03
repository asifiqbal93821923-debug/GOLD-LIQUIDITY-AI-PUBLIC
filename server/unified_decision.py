"""1H-primary decision gate. 4H macro veto, 15M setup, optional 5M refinement."""
from __future__ import annotations
from typing import Any
DIRECTION_MAP={"bullish":"BUY","bearish":"SELL","buy":"BUY","sell":"SELL"}
def _direction(x: Any):
    return DIRECTION_MAP.get(str(x.get("direction","")).lower()) if isinstance(x,dict) else None
def analyze_unified_decision(p: dict[str,Any]) -> dict[str,Any]:
    r=[]; data=p.get("data")
    if not isinstance(data,dict) or data.get("fresh") is not True or data.get("complete") is not True: r.append("DATA_NOT_FRESH_OR_COMPLETE")
    h1=p.get("1h_bias"); side=_direction(h1)
    if not isinstance(h1,dict) or h1.get("status")!="ok": r.append("ONE_HOUR_PRIMARY_NOT_READY")
    elif h1.get("confirmed") is not True: r.append("ONE_HOUR_BAR_NOT_CONFIRMED")
    elif side is None: r.append("ONE_HOUR_DIRECTION_MISSING")
    h4=p.get("4h_bias"); macro=_direction(h4)
    if not isinstance(h4,dict) or h4.get("status")!="ok": r.append("FOUR_HOUR_MACRO_NOT_READY")
    elif h4.get("confirmed") is not True: r.append("FOUR_HOUR_BAR_NOT_CONFIRMED")
    elif macro and side and macro!=side: r.append("FOUR_HOUR_MACRO_CONFLICT")
    s1=p.get("1h_structure")
    if isinstance(s1,dict) and s1.get("status")=="ok" and _direction(s1) and side and _direction(s1)!=side: r.append("ONE_HOUR_STRUCTURE_CONFLICT")
    s15=p.get("15m_setup"); d15=_direction(s15)
    if not isinstance(s15,dict) or s15.get("status")!="ok": r.append("FIFTEEN_MINUTE_SETUP_NOT_READY")
    elif s15.get("confirmed") is not True: r.append("FIFTEEN_MINUTE_SETUP_NOT_CONFIRMED")
    elif d15 is None: r.append("FIFTEEN_MINUTE_DIRECTION_MISSING")
    elif side and d15!=side: r.append("FIFTEEN_MINUTE_SETUP_CONFLICT")
    t5=p.get("5m_trigger")
    if isinstance(t5,dict) and t5.get("status")=="ok" and t5.get("confirmed") is True and _direction(t5) and side and _direction(t5)!=side: r.append("FIVE_MINUTE_OPPOSING_TRIGGER")
    ch=p.get("ai_channel_context")
    if isinstance(ch,dict) and side:
        for tf in ("4h","1h"):
            x=ch.get(tf,{})
            if isinstance(x,dict) and x.get("status")=="ok" and x.get("channel_state") in ("bullish","bearish") and _direction({"direction":x["channel_state"]})!=side: r.append(f"{tf.upper()}_CHANNEL_CONTEXT_CONFLICT")
    liq=p.get("liquidity_context")
    if isinstance(liq,dict):
        for tf,x in liq.items():
            sw=x.get("liquidity_sweep",{}) if isinstance(x,dict) else {}
            if isinstance(sw,dict) and sw.get("ambiguous_both_sides"): r.append(f"{tf.upper()}_AMBIGUOUS_LIQUIDITY_SWEEP")
    sp=p.get("spread")
    if not isinstance(sp,dict) or sp.get("acceptable") is not True: r.append("SPREAD_NOT_ACCEPTABLE")
    plan=p.get("trade_plan"); valid=isinstance(plan,dict) and plan.get("valid") is True
    if not valid: r.append("ONE_HOUR_TRADE_PLAN_INVALID")
    else:
        e=plan.get("entry"); sl=plan.get("stop_loss"); tp=plan.get("targets")
        ok=isinstance(e,list) and len(e)==2 and all(isinstance(x,(int,float)) for x in e) and e[0]<=e[1] and isinstance(sl,(int,float)) and isinstance(tp,list) and len(tp)==3 and all(isinstance(x,(int,float)) for x in tp)
        if not ok: r.append("TRADE_PLAN_LEVELS_INVALID")
        elif side:
            m=sum(e)/2
            if side=="BUY" and not (sl<m<tp[0]<tp[1]<tp[2]): r.append("LONG_RISK_LEVELS_INVALID")
            if side=="SELL" and not (sl>m>tp[0]>tp[1]>tp[2]): r.append("SHORT_RISK_LEVELS_INVALID")
    hierarchy={"4h":"macro_context_veto","1h":"primary_direction_and_trade_plan","15m":"setup_confirmation","5m":"optional_entry_refinement"}
    if r: return {"status":"ok","decision":"WAIT","direction":"neutral","reason_codes":sorted(set(r)),"evidence_groups_passed":0,"trade_plan":None,"hierarchy":hierarchy,"note":"1H is the primary trading timeframe; 5M is optional and never required."}
    return {"status":"ok","decision":side,"direction":"bullish" if side=="BUY" else "bearish","reason_codes":["ONE_HOUR_PRIMARY_CONFIRMED","FIFTEEN_MINUTE_SETUP_ALIGNED","RISK_PLAN_VALID","SPREAD_ACCEPTABLE"],"evidence_groups_passed":4,"trade_plan":{"source_timeframe":"1h","entry":plan["entry"],"stop_loss":plan["stop_loss"],"targets":plan["targets"]},"hierarchy":hierarchy,"entry_refinement":{"timeframe":"5m","used":bool(isinstance(t5,dict) and t5.get("status")=="ok" and t5.get("confirmed") is True)},"note":"Direction and risk levels come from 1H. 5M is optional. Not a profitability guarantee."}
