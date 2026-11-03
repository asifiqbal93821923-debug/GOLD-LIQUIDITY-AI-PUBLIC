"""Research-only 1H Alpha flip replay with next-bar execution and explicit costs.

This is not the complete 4H/1H/15M/5M Gold Report strategy and is not parity
certified. OHLC bars cannot reveal intrabar path; when stop and target are both
touched in one bar, the simulator applies the conservative stop-first rule.
"""
from __future__ import annotations
from typing import Any
from math import isfinite
try:
    from .alpha_signal import analyze_alpha_signal
    from .market_data import validate_candles
except ImportError:
    from alpha_signal import analyze_alpha_signal
    from market_data import validate_candles

def _plan_at_signal(candles: list[dict[str,Any]], index: int, side: str) -> dict[str,Any]:
    if index<49: return {"valid":False,"reason":"LESS_THAN_50_BARS_AT_SIGNAL"}
    hist=candles[:index+1]; rows=hist[-20:]; close=float(hist[-1]["close"])
    trs=[]
    for i,x in enumerate(hist[-15:],start=max(0,len(hist)-15)):
        prev=float(hist[i-1]["close"]) if i else float(x["close"])
        high=float(x["high"]); low=float(x["low"])
        trs.append(max(high-low,abs(high-prev),abs(low-prev)))
    atr=sum(trs)/len(trs)
    if not isfinite(atr) or atr<=0: return {"valid":False,"reason":"ATR_INVALID"}
    entry=[close-0.05*atr,close+0.05*atr]; mid=sum(entry)/2
    if side=="BUY":
        stop=min(float(x["low"]) for x in rows)-0.10*atr; risk=mid-stop
        if risk<0.25*atr: return {"valid":False,"reason":"STOP_DISTANCE_TOO_SMALL"}
        targets=[mid+risk*k for k in (1,2,3)]
    else:
        stop=max(float(x["high"]) for x in rows)+0.10*atr; risk=stop-mid
        if risk<0.25*atr: return {"valid":False,"reason":"STOP_DISTANCE_TOO_SMALL"}
        targets=[mid-risk*k for k in (1,2,3)]
    return {"valid":True,"entry_zone":entry,"stop_loss":stop,"targets":targets,"signal_close":close,"atr":atr}

def simulate_trade_events(candles: list[dict[str,Any]], events: list[dict[str,Any]],
                          costs: dict[str,float] | None=None) -> dict[str,Any]:
    p={"point_size":0.01,"spread_points":0.0,"slippage_points":0.0,
       "commission_points_per_side":0.0,**(costs or {})}
    point=float(p["point_size"]); spread=float(p["spread_points"])
    slip=float(p["slippage_points"]); commission=float(p["commission_points_per_side"])
    if point<=0 or min(spread,slip,commission)<0:
        return {"status":"invalid_settings","reason":"Cost values must be non-negative and point_size positive."}
    half_cost=(spread/2.0+slip)*point
    trades=[]; skipped=[]; busy_until=-1
    for event in sorted(events,key=lambda x:int(x.get("index",-1))):
        idx=int(event.get("index",-1)); side=str(event.get("signal","")).upper()
        if idx<0 or idx+1>=len(candles) or side not in ("BUY","SELL"):
            skipped.append({"index":idx,"reason":"INVALID_OR_NO_NEXT_BAR"}); continue
        if idx+1<=busy_until:
            skipped.append({"index":idx,"reason":"POSITION_ALREADY_OPEN"}); continue
        plan=event.get("plan",{})
        if not isinstance(plan,dict) or plan.get("valid") is not True:
            skipped.append({"index":idx,"reason":plan.get("reason","INVALID_PLAN") if isinstance(plan,dict) else "INVALID_PLAN"}); continue
        zone=plan.get("entry_zone"); stop=plan.get("stop_loss"); targets=plan.get("targets")
        if not isinstance(zone,list) or len(zone)!=2 or not isinstance(targets,list) or len(targets)!=3:
            skipped.append({"index":idx,"reason":"INVALID_PLAN_LEVELS"}); continue
        entry_bar=candles[idx+1]; raw_entry=float(entry_bar["open"])
        if not float(zone[0])<=raw_entry<=float(zone[1]):
            skipped.append({"index":idx,"reason":"NEXT_OPEN_OUTSIDE_ENTRY_ZONE"}); continue
        entry=raw_entry+half_cost if side=="BUY" else raw_entry-half_cost
        stop=float(stop); targets=[float(x) for x in targets]
        if side=="BUY" and not stop<entry<targets[0]<targets[1]<targets[2]:
            skipped.append({"index":idx,"reason":"GAP_INVALIDATED_LONG_PLAN"}); continue
        if side=="SELL" and not stop>entry>targets[0]>targets[1]>targets[2]:
            skipped.append({"index":idx,"reason":"GAP_INVALIDATED_SHORT_PLAN"}); continue
        risk=abs(entry-stop); remaining=1.0; gross=0.0; hit=[]; exit_reason="END_OF_DATA"; exit_index=len(candles)-1
        for j in range(idx+1,len(candles)):
            bar=candles[j]; op=float(bar["open"]); hi=float(bar["high"]); lo=float(bar["low"])
            stop_hit=(lo<=stop) if side=="BUY" else (hi>=stop)
            hit_targets=[k for k,t in enumerate(targets) if k not in hit and ((hi>=t) if side=="BUY" else (lo<=t))]
            if stop_hit:
                fill=min(stop,op) if side=="BUY" else max(stop,op)
                exit_fill=fill-half_cost if side=="BUY" else fill+half_cost
                gross+=((exit_fill-entry) if side=="BUY" else (entry-exit_fill))*remaining
                remaining=0.0; exit_reason="STOP_FIRST" if hit_targets else "STOP"; exit_index=j
                break
            for k in hit_targets:
                fraction=min(1.0/3.0,remaining)
                fill=targets[k]-half_cost if side=="BUY" else targets[k]+half_cost
                gross+=((fill-entry) if side=="BUY" else (entry-fill))*fraction
                remaining-=fraction; hit.append(k)
                exit_reason="TP"+str(k+1); exit_index=j
            if remaining<=1e-9:
                remaining=0.0; break
        if remaining>1e-9:
            exit_reason="END_OF_DATA"
            close=float(candles[exit_index]["close"])
            fill=close-half_cost if side=="BUY" else close+half_cost
            gross+=((fill-entry) if side=="BUY" else (entry-fill))*remaining
        commission_cost=2.0*commission*point
        net=gross-commission_cost
        trades.append({"signal_index":idx,"entry_index":idx+1,"exit_index":exit_index,"side":side,
          "entry":round(entry,5),"stop_loss":round(stop,5),"targets":targets,
          "targets_hit":["TP"+str(k+1) for k in hit],"exit_reason":exit_reason,
          "bars_held":exit_index-idx,"gross_pnl_price":round(gross,5),
          "commission_price":round(commission_cost,5),"net_pnl_price":round(net,5),
          "initial_risk_price":round(risk,5),"net_R":round(net/risk,4) if risk else 0.0})
        busy_until=exit_index
    pnls=[x["net_pnl_price"] for x in trades]
    wins=[x for x in trades if x["net_pnl_price"]>0]
    losses=[x for x in trades if x["net_pnl_price"]<0]
    gross_win=sum(x["net_pnl_price"] for x in wins)
    gross_loss=abs(sum(x["net_pnl_price"] for x in losses))
    equity=peak=drawdown=0.0
    for pnl in pnls:
        equity+=pnl; peak=max(peak,equity); drawdown=max(drawdown,peak-equity)
    return {"status":"ok","trade_count":len(trades),"skipped_signals":len(skipped),
      "win_rate_pct":round(100*len(wins)/len(trades),2) if trades else 0.0,
      "net_pnl_price":round(sum(pnls),5),"average_R":round(sum(x["net_R"] for x in trades)/len(trades),4) if trades else 0.0,
      "profit_factor":round(gross_win/gross_loss,4) if gross_loss else (None if gross_win==0 else "infinite"),
      "max_drawdown_price":round(drawdown,5),"cost_assumptions":p,
      "execution_model":"next_bar_open_with_entry_zone_check; partial 1/3 exits at TP1/TP2/TP3; conservative stop-first on same-bar conflict",
      "trades":trades,"skipped":skipped}

def run_alpha_1h_backtest(candles: list[dict[str,Any]], settings: dict[str,Any] | None=None,
                          costs: dict[str,float] | None=None) -> dict[str,Any]:
    try: rows=validate_candles(candles)
    except ValueError as exc: return {"status":"invalid_data","reason":str(exc)}
    if len(rows)<50: return {"status":"insufficient_history","required_minimum":50,"received":len(rows)}
    alpha=analyze_alpha_signal(rows,settings)
    if alpha.get("status")!="ok": return {"status":alpha.get("status"),"engine":alpha}
    events=[]
    for sig in alpha.get("signal_history",[]):
        idx=int(sig["index"]); side=sig["signal"]
        plan=_plan_at_signal(rows,idx,side)
        events.append({"index":idx,"signal":side,"plan":plan})
    result=simulate_trade_events(rows,events,costs)
    result.update({"strategy":"Alpha Signal 1H flip research backtest","timeframe":"1h",
      "source_engine":"Alpha Signal Engine Pro","signal_count":len(events),
      "scope_warning":"This is a single-engine 1H research replay, not the complete 4H/1H/15M/optional-5M confluence strategy. No Pine parity or profitability is implied."})
    return result
