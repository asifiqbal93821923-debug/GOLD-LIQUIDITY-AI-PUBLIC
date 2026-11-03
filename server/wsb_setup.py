"""Wick Sequence Breakout adapter for GOLD REPORT AI (OHLCV only).

Implements a conservative rolling wick/absorption-candidate and range-breakout
setup. Estimated volume allocation is not bid/ask delta or institutional flow.
"""
from __future__ import annotations
from statistics import mean
from typing import Any


def analyze_wsb(candles: list[dict[str,Any]], settings: dict[str,Any] | None=None):
    p={"window":8,"wick_min_pct":0.45,"opposite_wick_max_pct":0.20,
       "atr_period":14,"min_range_atr":0.0,"volume_lookback":20,
       "absorption_volume_multiple":1.5,"absorption_max_range_atr":0.8,
       "breakout_basis":"close","breakout_size_atr":0.0,"max_wait_bars":12,**(settings or {})}
    if len(candles)<max(30,int(p["atr_period"])+3):
        return {"status":"insufficient_history","required_minimum":max(30,int(p["atr_period"])+3)}
    rows=[]
    for i,x in enumerate(candles):
        try:
            o,h,l,c=(float(x[k]) for k in ("open","high","low","close"))
            v=float(x.get("volume") or 0)
            if not all(z==z and abs(z)!=float("inf") for z in (o,h,l,c,v)) or h<max(o,c,l) or l>min(o,c,h) or v<0:
                raise ValueError("invalid OHLCV")
            rows.append({"open":o,"high":h,"low":l,"close":c,"volume":v,"time":x.get("time")})
        except (KeyError,TypeError,ValueError) as exc:
            return {"status":"invalid_data","reason":f"INVALID_CANDLE_{i}:{exc}"}
    tr=[]
    for i,r in enumerate(rows):
        pc=rows[i-1]["close"] if i else r["close"]
        tr.append(max(r["high"]-r["low"],abs(r["high"]-pc),abs(r["low"]-pc)))
    n=max(2,int(p["atr_period"]))
    atr=mean(tr[-n:])
    start=max(0,len(rows)-int(p["window"]))
    recent=rows[start:]
    bull_wicks=bear_wicks=0
    bull_abs=bear_abs=0
    for i,r in enumerate(recent):
        rng=max(r["high"]-r["low"],1e-12)
        up=(r["high"]-max(r["open"],r["close"]))/rng
        dn=(min(r["open"],r["close"])-r["low"])/rng
        range_ok=(r["high"]-r["low"])>=atr*float(p["min_range_atr"])
        if range_ok and dn>=float(p["wick_min_pct"]) and up<=float(p["opposite_wick_max_pct"]):
            bull_wicks+=1
        if range_ok and up>=float(p["wick_min_pct"]) and dn<=float(p["opposite_wick_max_pct"]):
            bear_wicks+=1
        # Absorption candidate: high relative volume + compressed range + directional close location.
        vi=start+i
        prior=[x["volume"] for x in rows[max(0,vi-int(p["volume_lookback"])):vi] if x["volume"]>0]
        base=mean(prior) if prior else 0
        loc=(r["close"]-r["low"])/rng
        if base>0 and r["volume"]>=base*float(p["absorption_volume_multiple"]) and (r["high"]-r["low"])<=atr*float(p["absorption_max_range_atr"]):
            if loc>=0.65: bull_abs+=1
            elif loc<=0.35: bear_abs+=1
    formation_high=max(r["high"] for r in recent)
    formation_low=min(r["low"] for r in recent)
    last=rows[-1]
    basis=str(p["breakout_basis"]).lower()
    if basis not in ("close","wick"):
        return {"status":"invalid_settings","reason":"breakout_basis_must_be_close_or_wick"}
    up_break=(last["close"]>formation_high if basis=="close" else last["high"]>formation_high)
    dn_break=(last["close"]<formation_low if basis=="close" else last["low"]<formation_low)
    # Current candle is included in the rolling range; use the prior window for actual boundary tests.
    prior_window=rows[max(0,len(rows)-int(p["window"])-1):-1]
    prior_high=max(r["high"] for r in prior_window)
    prior_low=min(r["low"] for r in prior_window)
    up_break=(last["close"]>prior_high if basis=="close" else last["high"]>prior_high)
    dn_break=(last["close"]<prior_low if basis=="close" else last["low"]<prior_low)
    ambiguous=up_break and dn_break
    size_ok=abs(last["close"]-last["open"])>=atr*float(p["breakout_size_atr"])
    pressure_bull=sum(r["volume"]*((r["close"]-r["low"])/max(r["high"]-r["low"],1e-12)) for r in recent)
    pressure_bear=sum(r["volume"]*((r["high"]-r["close"])/max(r["high"]-r["low"],1e-12)) for r in recent)
    if ambiguous: direction="ambiguous"
    elif up_break and size_ok and pressure_bull>pressure_bear: direction="bullish"
    elif dn_break and size_ok and pressure_bear>pressure_bull: direction="bearish"
    else: direction="none"
    return {
      "status":"ok","engine":"Wick Sequence Breakout","implementation_variant":"conservative_ohlcv_adapter",
      "timestamp":last["time"],"formation":{"high":formation_high,"low":formation_low,"window_bars":len(recent),
        "bullish_wick_count":bull_wicks,"bearish_wick_count":bear_wicks,
        "bullish_absorption_candidates":bull_abs,"bearish_absorption_candidates":bear_abs},
      "estimated_pressure":{"bullish":round(pressure_bull,5),"bearish":round(pressure_bear,5),
        "semantics":"CANDLE_CLOSE_LOCATION_VOLUME_SPLIT_NOT_TRUE_BID_ASK_DELTA"},
      "breakout":{"direction":direction,"basis":basis,"up_boundary":prior_high,"down_boundary":prior_low,
        "size_filter_passed":bool(size_ok),"ambiguous_both_sides":bool(ambiguous),
        "confirmed":direction in ("bullish","bearish")},
      "setup_score":{"bullish":min(100,bull_wicks*10+bull_abs*15+(20 if direction=="bullish" else 0)),
        "bearish":min(100,bear_wicks*10+bear_abs*15+(20 if direction=="bearish" else 0))},
      "data_quality":"ohlcv_volume_proxy" if any(r["volume"]>0 for r in rows) else "no_usable_volume",
      "disclaimer":"No actual bid/ask delta, resting orders or institutional identity. This adapter is not yet TradingView parity-certified."
    }
