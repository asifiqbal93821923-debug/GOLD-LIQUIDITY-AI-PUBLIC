"""Causal multi-timeframe XAUUSD strategy replay.

At each closed 1H Alpha flip, only 4H/15M/5M bars that had fully closed
by that 1H close are supplied to the confluence engines. This is research
code, not a claim of Pine parity or strategy profitability.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Any
try:
    from .market_data import validate_candles
    from .alpha_signal import analyze_alpha_signal
    from .smc_structure import analyze_smc_structure
    from .wsb_setup import analyze_wsb
    from .ai_channels import analyze_ai_channels
    from .institutional_footprint import analyze_institutional_footprint
    from .gold_report import _trade_plan_1h
    from .unified_decision import analyze_unified_decision
    from .backtest import simulate_trade_events
except ImportError:
    from market_data import validate_candles
    from alpha_signal import analyze_alpha_signal
    from smc_structure import analyze_smc_structure
    from wsb_setup import analyze_wsb
    from ai_channels import analyze_ai_channels
    from institutional_footprint import analyze_institutional_footprint
    from gold_report import _trade_plan_1h
    from unified_decision import analyze_unified_decision
    from backtest import simulate_trade_events

TF_SECONDS={"4h":14400,"1h":3600,"15m":900,"5m":300}

def _closed_prefix(rows:list[dict[str,Any]], timeframe:str, cutoff:int):
    duration=TF_SECONDS[timeframe]
    # Candle timestamps are bar-open Unix seconds. Include only bars fully closed
    # at or before the decision candle's close.
    end=0
    for row in rows:
        if int(row["time"])+duration<=cutoff: end+=1
        else: break
    return rows[:end]

def _fact(result:dict[str,Any], direction:str|None=None):
    if result.get("status")!="ok":
        return {"status":result.get("status","not_available"),"confirmed":False}
    return {"status":"ok","direction":direction or result.get("direction"),
            "confirmed":True,"source":result.get("engine")}

def run_gold_mtf_backtest(timeframes:dict[str,list[dict[str,Any]]],
                          costs:dict[str,float]|None=None,
                          settings:dict[str,Any]|None=None):
    normalized={}
    excluded_unclosed={}
    now_epoch=int(datetime.now(timezone.utc).timestamp())
    for tf in ("4h","1h","15m","5m"):
        raw=timeframes.get(tf) or []
        if raw:
            try: rows=validate_candles(raw)
            except ValueError as exc: return {"status":"invalid_data","timeframe":tf,"reason":str(exc)}
            duration=TF_SECONDS[tf]
            closed=[row for row in rows if int(row["time"])+duration<=now_epoch]
            excluded_unclosed[tf]=len(rows)-len(closed)
            normalized[tf]=closed
        else:
            normalized[tf]=[]
            excluded_unclosed[tf]=0
    for tf in ("4h","1h","15m"):
        if len(normalized[tf])<50:
            return {"status":"insufficient_history","timeframe":tf,"required_minimum":50,"received":len(normalized[tf])}
    h1=normalized["1h"]
    if len(h1)>3000:
        return {"status":"too_much_history","maximum_1h_bars":3000,"received":len(h1)}
    alpha1=analyze_alpha_signal(h1,(settings or {}).get("alpha"))
    if alpha1.get("status")!="ok":
        return {"status":alpha1.get("status"),"reason":"1H_ALPHA_NOT_READY","engine":alpha1}
    events=[]; vetoes=Counter(); evaluated=0
    for sig in alpha1.get("signal_history",[]):
        idx=int(sig["index"])
        if idx<49 or idx+1>=len(h1): continue
        h1_prefix=h1[:idx+1]
        decision_close=int(h1[idx]["time"])+3600
        h4_prefix=_closed_prefix(normalized["4h"],"4h",decision_close)
        m15_prefix=_closed_prefix(normalized["15m"],"15m",decision_close)
        m5_prefix=_closed_prefix(normalized["5m"],"5m",decision_close) if normalized["5m"] else []
        if len(h4_prefix)<50 or len(m15_prefix)<50:
            vetoes["HTF_OR_15M_HISTORY_NOT_READY"]+=1; continue
        h4_alpha=analyze_alpha_signal(h4_prefix,(settings or {}).get("alpha"))
        h1_smc=analyze_smc_structure(h1_prefix,(settings or {}).get("smc"))
        m15_smc=analyze_smc_structure(m15_prefix,(settings or {}).get("smc"))
        if h4_alpha.get("status")!="ok":
            vetoes["4H_ALPHA_NOT_READY"]+=1; continue
        h1_side="bullish" if sig["signal"]=="BUY" else "bearish"
        plan=_trade_plan_1h(sig["signal"],h1_prefix)
        if plan.get("valid"):
            plan={**plan,"entry_zone":plan.get("entry")}
        trigger=None
        if len(m5_prefix)>=30:
            wsb=analyze_wsb(m5_prefix,(settings or {}).get("wsb"))
            if wsb.get("status")=="ok":
                b=wsb.get("breakout",{})
                trigger={"status":"ok","direction":b.get("direction"),
                         "confirmed":bool(b.get("confirmed")),"source":"wsb"}
        ai4=analyze_ai_channels(h4_prefix,(settings or {}).get("ai_channels"))
        ai1=analyze_ai_channels(h1_prefix,(settings or {}).get("ai_channels"))
        liq1=analyze_institutional_footprint(h1_prefix,(settings or {}).get("liquidity"))
        liq15=analyze_institutional_footprint(m15_prefix,(settings or {}).get("liquidity"))
        max_spread=float((costs or {}).get("max_spread_points",0) or 0)
        spread_points=float((costs or {}).get("spread_points",0) or 0)
        spread_ok=(max_spread<=0 or spread_points<=max_spread)
        decision=analyze_unified_decision({
          "data":{"fresh":True,"complete":True},
          "4h_bias":_fact(h4_alpha),
          "1h_bias":_fact(alpha1,h1_side),
          "1h_structure":_fact(h1_smc),
          "15m_setup":_fact(m15_smc),
          "5m_trigger":trigger,
          "spread":{"acceptable":spread_ok},
          "ai_channel_context":{
            "4h":{"status":ai4.get("status"),"channel_state":ai4.get("channel_state")},
            "1h":{"status":ai1.get("status"),"channel_state":ai1.get("channel_state")}},
          "liquidity_context":{"1h":liq1,"15m":liq15},
          "trade_plan":plan})
        evaluated+=1
        if decision.get("decision") in ("BUY","SELL"):
            events.append({"index":idx,"signal":decision["decision"],"plan":plan})
        else:
            vetoes.update(decision.get("reason_codes",["DECISION_WAIT"]))
    replay_costs={k:v for k,v in (costs or {}).items()
                  if k in ("point_size","spread_points","slippage_points","commission_points_per_side")}
    result=simulate_trade_events(h1,events,replay_costs)
    result.update({
      "strategy":"Gold Report AI multi-timeframe causal replay",
      "timeframe":"1h_primary","signals_evaluated":evaluated,
      "accepted_signals":len(events),"veto_counts":dict(vetoes),
      "excluded_unclosed_candles":excluded_unclosed,
      "timeframe_policy":{"4h":"latest fully closed macro candle","1h":"primary Alpha direction and trade plan",
        "15m":"latest fully closed SMC setup","5m":"optional latest fully closed WSB refinement"},
      "scope_warning":"Research replay only. Uses current Python adapters, not certified Pine parity. 1H trade plan is uncalibrated; spread/costs are user assumptions. OHLC bars cannot resolve intrabar order, handled conservatively stop-first."})
    return result
