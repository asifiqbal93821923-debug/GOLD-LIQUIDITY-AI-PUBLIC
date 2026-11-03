"""Gold Report AI orchestration: Alpha + SMC + WSB + AI Channels + liquidity.

This composes isolated adapters over caller-supplied chronological OHLCV.
It never fabricates missing candles or claims live market data.
"""
from __future__ import annotations
from typing import Any
try:
    from .alpha_signal import analyze_alpha_signal
    from .smc_structure import analyze_smc_structure
    from .wsb_setup import analyze_wsb
    from .ai_channels import analyze_ai_channels
    from .institutional_footprint import analyze_institutional_footprint
    from .unified_decision import analyze_unified_decision
except ImportError:
    from alpha_signal import analyze_alpha_signal
    from smc_structure import analyze_smc_structure
    from wsb_setup import analyze_wsb
    from ai_channels import analyze_ai_channels
    from institutional_footprint import analyze_institutional_footprint
    from unified_decision import analyze_unified_decision


def _trade_plan(side: str | None, candles: list[dict[str,Any]]) -> dict[str,Any]:
    if side not in ("BUY","SELL") or len(candles)<20:
        return {"valid":False,"reason":"NO_CONFIRMED_SETUP"}
    rows=candles[-20:]
    try:
        close=float(candles[-1]["close"])
        ranges=[max(float(x["high"])-float(x["low"]),
                    abs(float(x["high"])-float(candles[max(0,i-1)]["close"])),
                    abs(float(x["low"])-float(candles[max(0,i-1)]["close"]))) for i,x in enumerate(candles[-15:],start=max(0,len(candles)-15))]
        atr=sum(ranges)/len(ranges)
        if atr<=0: return {"valid":False,"reason":"ATR_INVALID"}
        entry=[close-0.05*atr,close+0.05*atr]
        midpoint=sum(entry)/2
        if side=="BUY":
            structural=min(float(x["low"]) for x in rows)
            stop=structural-0.10*atr
            risk=midpoint-stop
            if risk<0.25*atr: return {"valid":False,"reason":"STOP_DISTANCE_TOO_SMALL"}
            targets=[midpoint+risk*r for r in (1.0,2.0,3.0)]
        else:
            structural=max(float(x["high"]) for x in rows)
            stop=structural+0.10*atr
            risk=stop-midpoint
            if risk<0.25*atr: return {"valid":False,"reason":"STOP_DISTANCE_TOO_SMALL"}
            targets=[midpoint-risk*r for r in (1.0,2.0,3.0)]
        return {"valid":True,"entry":entry,"stop_loss":stop,"targets":targets,
                "method":"5m_20bar_structure_plus_ATR_buffer","risk_unit":risk}
    except (KeyError,TypeError,ValueError,ZeroDivisionError):
        return {"valid":False,"reason":"TRADE_PLAN_INPUT_INVALID"}


def build_gold_report(timeframes: dict[str,list[dict[str,Any]]],
                      data_fresh: bool=False,
                      spread_acceptable: bool=False) -> dict[str,Any]:
    required=("4h","1h","15m","5m")
    outputs={}
    for tf in required:
        rows=timeframes.get(tf) or []
        if not rows:
            outputs[tf]={"status":"not_available","reason":"TIMEFRAME_DATA_MISSING"}
            continue
        outputs[tf]={
          "alpha":analyze_alpha_signal(rows),
          "smc":analyze_smc_structure(rows),
          "wsb":analyze_wsb(rows),
          "ai_channels":analyze_ai_channels(rows),
          "liquidity":analyze_institutional_footprint(rows)
        }
    complete=all(len(timeframes.get(tf) or [])>=50 for tf in required)
    def fact(tf, engine, field="direction"):
        item=outputs.get(tf,{}).get(engine,{})
        if item.get("status")!="ok": return {"status":item.get("status","not_available"),"confirmed":False}
        value=item.get(field)
        return {"status":"ok","direction":value,"confirmed":True,"source":engine}
    h4=fact("4h","alpha")
    h1=fact("1h","alpha")
    m15=fact("15m","smc")
    wsb_result=outputs.get("5m",{}).get("wsb",{})
    breakout=wsb_result.get("breakout",{}) if wsb_result.get("status")=="ok" else {}
    m5={"status":"ok","direction":breakout.get("direction"),"confirmed":bool(breakout.get("confirmed")),"source":"wsb"} if wsb_result.get("status")=="ok" else {"status":wsb_result.get("status","not_available"),"confirmed":False}
    if m5.get("direction") not in ("bullish","bearish"):
        m5["direction"]=None
    side=None
    if all(x.get("status")=="ok" for x in (h4,h1,m15,m5)):
        dirs=[h4.get("direction"),h1.get("direction"),m15.get("direction"),m5.get("direction")]
        if dirs[0] in ("bullish","bearish") and len(set(dirs))==1:
            side="BUY" if dirs[0]=="bullish" else "SELL"
    plan=_trade_plan(side,timeframes.get("5m") or [])
    decision=analyze_unified_decision({
      "data":{"fresh":bool(data_fresh),"complete":bool(complete)},
      "4h_bias":h4,"1h_bias":h1,"15m_structure":m15,"5m_trigger":m5,
      "spread":{"acceptable":bool(spread_acceptable)},
      "ai_channel_context":{
        tf: {"status":outputs.get(tf,{}).get("ai_channels",{}).get("status"),
             "channel_state":outputs.get(tf,{}).get("ai_channels",{}).get("channel_state")}
        for tf in ("4h","1h")
      },
      "liquidity_context":{
        tf: outputs.get(tf,{}).get("liquidity",{})
        for tf in ("15m","5m")
      },
      "trade_plan":plan
    })
    return {
      "status":"ok" if complete and all(outputs[tf].get("alpha",{}).get("status")=="ok" for tf in required) else "partial",
      "report":"GOLD REPORT AI","market":"XAUUSD",
      "hierarchy":{"4h":"macro_confirmation","1h":"primary_decision","15m":"setup_structure","5m":"entry_trigger"},
      "engines":{"alpha":"trend_and_momentum","smc":"structure_BOS_CHoCH_FVG_OB_candidates",
        "wsb":"wick_absorption_breakout_setup","ai_channels":"adaptive_price_distribution_context",
        "institutional_footprint":"liquidity_pools_and_OHLCV_activity_proxies"},
      "timeframes":outputs,"decision":decision,
      "data_quality":{"freshness_asserted_by_caller":bool(data_fresh),"all_timeframes_present":complete,
        "live_provider_configured":False},
      "disclaimer":"Decision requires real chronological market candles and explicit caller assertions for freshness/spread. No live feed is connected by this module; order-book, CVD and institutional identity are not inferred."
    }
