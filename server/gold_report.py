"""Gold Report AI orchestration: 1H primary, 4H macro, 15M setup, optional 5M."""
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

def _trade_plan_1h(
    side: str | None,
    candles: list[dict[str,Any]],
    settings: dict[str,Any] | None = None,
) -> dict[str,Any]:
    """1H structure + ATR plan; settings are calibrated only via historical replay."""
    p = {
        "atr_period": 15,
        "swing_lookback": 20,
        "stop_atr_buffer": 0.10,
        "entry_atr_half_width": 0.05,
        "target_rr": [1.0, 2.0, 3.0],
        **(settings or {}),
    }
    if side not in ("BUY", "SELL") or len(candles) < 50:
        return {"valid": False, "reason": "NO_CONFIRMED_1H_SETUP", "source_timeframe": "1h"}
    try:
        atr_period = int(p["atr_period"])
        swing_lookback = int(p["swing_lookback"])
        stop_buffer = float(p["stop_atr_buffer"])
        entry_width = float(p["entry_atr_half_width"])
        rr = [float(x) for x in p["target_rr"]]
        if atr_period < 2 or swing_lookback < 2 or min(stop_buffer, entry_width) < 0:
            raise ValueError("invalid trade-plan settings")
        if len(rr) != 3 or not (0 < rr[0] < rr[1] < rr[2]):
            raise ValueError("target_rr must contain three increasing positive values")
        close = float(candles[-1]["close"])
        tr = []
        start = max(0, len(candles) - atr_period)
        for i in range(start, len(candles)):
            x = candles[i]
            prev = float(candles[i-1]["close"]) if i else float(x["close"])
            hi, lo = float(x["high"]), float(x["low"])
            tr.append(max(hi-lo, abs(hi-prev), abs(lo-prev)))
        atr = sum(tr) / len(tr)
        if atr <= 0:
            return {"valid": False, "reason": "ATR_INVALID", "source_timeframe": "1h"}
        rows = candles[-swing_lookback:]
        entry = [close-entry_width*atr, close+entry_width*atr]
        mid = sum(entry)/2
        if side == "BUY":
            stop = min(float(x["low"]) for x in rows) - stop_buffer*atr
            risk = mid-stop
            if risk < 0.25*atr:
                return {"valid": False, "reason": "STOP_DISTANCE_TOO_SMALL", "source_timeframe": "1h"}
            targets = [mid+risk*x for x in rr]
        else:
            stop = max(float(x["high"]) for x in rows) + stop_buffer*atr
            risk = stop-mid
            if risk < 0.25*atr:
                return {"valid": False, "reason": "STOP_DISTANCE_TOO_SMALL", "source_timeframe": "1h"}
            targets = [mid-risk*x for x in rr]
        return {
            "valid": True, "source_timeframe": "1h",
            "method": "calibratable_1h_structure_atr",
            "parameters": p, "atr": atr, "entry": entry,
            "stop_loss": stop, "targets": targets, "risk_unit": risk,
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return {"valid": False, "reason": "TRADE_PLAN_INPUT_INVALID", "source_timeframe": "1h"}
def build_gold_report(timeframes: dict[str,list[dict[str,Any]]], data_fresh: bool=False, spread_acceptable: bool=False) -> dict[str,Any]:
    required=("4h","1h","15m"); outputs={}
    for tf in ("4h","1h","15m","5m"):
        rows=timeframes.get(tf) or []
        if not rows:
            outputs[tf]={"status":"not_available","reason":"TIMEFRAME_DATA_MISSING"}; continue
        outputs[tf]={"alpha":analyze_alpha_signal(rows),"smc":analyze_smc_structure(rows),
          "wsb":analyze_wsb(rows),"ai_channels":analyze_ai_channels(rows),
          "liquidity":analyze_institutional_footprint(rows)}
    complete=all(len(timeframes.get(tf) or [])>=50 for tf in required)
    def fact(tf,engine):
        x=outputs.get(tf,{}).get(engine,{})
        if x.get("status")!="ok": return {"status":x.get("status","not_available"),"confirmed":False}
        return {"status":"ok","direction":x.get("direction"),"confirmed":True,"source":engine}
    h4=fact("4h","alpha"); h1=fact("1h","alpha")
    h1_smc=fact("1h","smc"); m15=fact("15m","smc")
    trigger=None
    w=outputs.get("5m",{}).get("wsb",{})
    if w.get("status")=="ok":
        b=w.get("breakout",{})
        trigger={"status":"ok","direction":b.get("direction"),"confirmed":bool(b.get("confirmed")),"source":"wsb"}
    primary=h1.get("direction")
    side="BUY" if primary=="bullish" else "SELL" if primary=="bearish" else None
    plan=_trade_plan_1h(side,timeframes.get("1h") or [])
    decision=analyze_unified_decision({
      "data":{"fresh":bool(data_fresh),"complete":bool(complete)},
      "4h_bias":h4,"1h_bias":h1,"1h_structure":h1_smc,"15m_setup":m15,"5m_trigger":trigger,
      "spread":{"acceptable":bool(spread_acceptable)},
      "ai_channel_context":{tf:{"status":outputs.get(tf,{}).get("ai_channels",{}).get("status"),
        "channel_state":outputs.get(tf,{}).get("ai_channels",{}).get("channel_state")} for tf in ("4h","1h")},
      "liquidity_context":{tf:outputs.get(tf,{}).get("liquidity",{}) for tf in ("1h","15m")},
      "trade_plan":plan})
    return {"status":"ok" if complete and all(outputs[tf].get("alpha",{}).get("status")=="ok" for tf in required) else "partial",
      "report":"GOLD REPORT AI","market":"XAUUSD",
      "hierarchy":{"4h":"macro_context","1h":"primary_direction_and_trade_plan","15m":"setup_confirmation","5m":"optional_entry_refinement"},
      "timeframes":outputs,"decision":decision,
      "data_quality":{"freshness_asserted_by_caller":bool(data_fresh),"required_timeframes_present":complete,
        "optional_5m_present":bool(timeframes.get("5m")),"live_provider_configured":False},
      "disclaimer":"1H exclusively determines primary direction and initial trade-plan levels. 5M is optional. The ATR/structure planner is not yet calibrated or backtest-validated. No live provider, verified order book, true CVD or institutional identity is connected."}
