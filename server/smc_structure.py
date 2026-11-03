"""SMC structure/context adapter for GOLD REPORT AI.

A conservative OHLCV-derived subset: confirmed pivots, BOS/CHoCH, simple
candle-derived OB candidates, FVGs, EQH/EQL and premium/discount. It is NOT
the complete LuxAlgo Pine port and does not expose actual resting orders.
"""
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone


def _valid(candles: list[dict[str, Any]]) -> tuple[list[dict[str, float]], str | None]:
    if len(candles) < 20:
        return [], "INSUFFICIENT_HISTORY"
    out=[]
    for i,row in enumerate(candles):
        try:
            o,h,l,c=(float(row[k]) for k in ("open","high","low","close"))
            if not all(map(lambda x: x == x and abs(x) != float("inf"),(o,h,l,c))):
                raise ValueError("non-finite price")
            if h < max(o,c,l) or l > min(o,c,h):
                raise ValueError("invalid OHLC bounds")
            out.append({"open":o,"high":h,"low":l,"close":c,"time":row.get("time")})
        except (KeyError,TypeError,ValueError) as exc:
            return [],f"INVALID_CANDLE_{i}:{exc}"
    return out,None


def _epoch(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            number=float(value)
            return int(number / 1000) if number > 10_000_000_000 else int(number)
        parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if parsed.tzinfo is None:
            parsed=parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        return None


def _pivots(rows: list[dict[str,float]], side: str, left: int, right: int):
    key="high" if side=="high" else "low"
    found=[]
    for i in range(left,len(rows)-right):
        val=rows[i][key]
        w=[r[key] for r in rows[i-left:i+right+1]]
        if w.count(val)==1 and val==(max(w) if side=="high" else min(w)):
            found.append({"index":i,"price":val,"confirmed_index":i+right})
    return found


def analyze_smc_structure(candles: list[dict[str,Any]], settings: dict[str,Any] | None=None):
    p={"pivot_left":3,"pivot_right":3,"max_zones":12,"equal_level_atr_fraction":0.12,
       "displacement_atr_multiple":1.25,"atr_period":14,**(settings or {})}
    rows,error=_valid(candles)
    if error:
        return {"status":"insufficient_history" if error=="INSUFFICIENT_HISTORY" else "invalid_data","reason":error}
    last=rows[-1]
    tr=[]
    for i,r in enumerate(rows):
        pc=rows[i-1]["close"] if i else r["close"]
        tr.append(max(r["high"]-r["low"],abs(r["high"]-pc),abs(r["low"]-pc)))
    n=max(2,int(p["atr_period"]))
    atr=sum(tr[-n:])/min(n,len(tr))
    highs=_pivots(rows,"high",int(p["pivot_left"]),int(p["pivot_right"]))
    lows=_pivots(rows,"low",int(p["pivot_left"]),int(p["pivot_right"]))
    # Only pivots whose right-side confirmation bars have closed are eligible.
    confirmed_highs=[x for x in highs if x["confirmed_index"] <= len(rows)-1]
    confirmed_lows=[x for x in lows if x["confirmed_index"] <= len(rows)-1]
    sh=confirmed_highs[-1] if confirmed_highs else None
    sl=confirmed_lows[-1] if confirmed_lows else None
    state="neutral"
    events=[]
    last_break=None
    if sh and last["close"]>sh["price"]:
        last_break="bullish"
    if sl and last["close"]<sl["price"]:
        if last_break:
            last_break="ambiguous"
        else:
            last_break="bearish"
    # Establish prior structure state using closed bars, excluding current bar.
    prior_state="neutral"
    for j in range(max(20,len(rows)-120),len(rows)-1):
        ph=[x for x in confirmed_highs if x["confirmed_index"]<=j]
        pl=[x for x in confirmed_lows if x["confirmed_index"]<=j]
        if ph and rows[j]["close"]>ph[-1]["price"]:
            prior_state="bullish"
        elif pl and rows[j]["close"]<pl[-1]["price"]:
            prior_state="bearish"
    if last_break in ("bullish","bearish"):
        kind="BOS" if prior_state in ("neutral",last_break) else "CHoCH"
        events.append({"type":kind,"direction":last_break,"level":sh["price"] if last_break=="bullish" else sl["price"],"confirmed":True})
        state=last_break
    elif last_break=="ambiguous":
        state="ambiguous"
    else:
        state=prior_state

    tol=max(atr*float(p["equal_level_atr_fraction"]),1e-8)
    def equal_clusters(points):
        groups=[]
        for x in points[-30:]:
            if groups and abs(x["price"]-sum(y["price"] for y in groups[-1])/len(groups[-1]))<=tol:
                groups[-1].append(x)
            else:
                groups.append([x])
        return [{"price":round(sum(y["price"] for y in g)/len(g),5),"touches":len(g)}
                for g in groups if len(g)>=2]
    eqh=equal_clusters(confirmed_highs)
    eql=equal_clusters(confirmed_lows)

    # FVGs are three-candle gaps, recorded only after the third candle closes.
    fvgs=[]
    for i in range(2,len(rows)):
        a,b,c=rows[i-2],rows[i-1],rows[i]
        if c["low"]>a["high"]:
            fvgs.append({"direction":"bullish","low":a["high"],"high":c["low"],"formed_index":i,"mitigated":False})
        if c["high"]<a["low"]:
            fvgs.append({"direction":"bearish","low":c["high"],"high":a["low"],"formed_index":i,"mitigated":False})
    active_fvgs=[]
    for z in fvgs[-int(p["max_zones"])*3:]:
        later=rows[z["formed_index"]+1:]
        mitigated=any(r["low"]<=z["high"] and r["high"]>=z["low"] for r in later)
        broken=any((z["direction"]=="bullish" and r["close"]<z["low"]) or
                    (z["direction"]=="bearish" and r["close"]>z["high"]) for r in later)
        status="invalidated" if broken else "mitigated" if mitigated else "active"
        z.update({"status":status,"start_time":_epoch(rows[z["formed_index"]].get("time")),
                  "zone_type":"fvg","source":"three_candle_gap_proxy"})
        if status=="active":
            active_fvgs.append({k:v for k,v in z.items() if k!="formed_index"})

    # OB candidates: last opposite candle before a confirmed displacement break.
    obs=[]
    for ev in events:
        idx=len(rows)-1
        start=max(0,idx-8)
        for j in range(idx-1,start-1,-1):
            r=rows[j]
            opposite=(ev["direction"]=="bullish" and r["close"]<r["open"]) or (ev["direction"]=="bearish" and r["close"]>r["open"])
            if opposite:
                obs.append({"direction":ev["direction"],"low":r["low"],"high":r["high"],
                            "source":"last_opposite_candle_candidate","confirmed":True,
                            "formed_index":j,"start_time":_epoch(r.get("time")),"zone_type":"order_block"})
                break
    for z in obs:
        later=rows[z["formed_index"]+1:]
        touched=any(r["low"]<=z["high"] and r["high"]>=z["low"] for r in later)
        broken=any((z["direction"]=="bullish" and r["close"]<z["low"]) or
                   (z["direction"]=="bearish" and r["close"]>z["high"]) for r in later)
        z["status"]="invalidated" if broken else "mitigated" if touched else "active"
        z.pop("formed_index",None)
    obs=obs[-int(p["max_zones"]):]
    hi=max(r["high"] for r in rows[-min(50,len(rows)):])
    lo=min(r["low"] for r in rows[-min(50,len(rows)):])
    midpoint=(hi+lo)/2
    location="premium" if last["close"]>midpoint else "discount" if last["close"]<midpoint else "equilibrium"
    displacement=abs(last["close"]-last["open"])>=atr*float(p["displacement_atr_multiple"])
    return {
      "status":"ok","engine":"SMC Structure Context","implementation_variant":"conservative_ohlcv_adapter",
      "source_attribution":"LuxAlgo SMC concepts; independent adapter, not a complete source port",
      "direction":state,"last_structure_event":events[-1] if events else None,"structure_events":events,
      "swing_high":sh,"swing_low":sl,"equal_high_pools":eqh,"equal_low_pools":eql,
      "order_block_candidates":obs,"active_fvgs":active_fvgs[-int(p["max_zones"]):],
      "zones":(fvgs[-int(p["max_zones"]):]+obs)[-int(p["max_zones"])*2:],
      "premium_discount":{"range_high":hi,"range_low":lo,"equilibrium":midpoint,"location":location},
      "displacement":{"current_bar":bool(displacement),"body_atr":round(abs(last["close"]-last["open"])/max(atr,1e-12),3)},
      "liquidity_sweep_proxy":{"above_swing_high_reclaim":bool(sh and last["high"]>sh["price"] and last["close"]<sh["price"]),
                               "below_swing_low_reclaim":bool(sl and last["low"]<sl["price"] and last["close"]>sl["price"])},
      "data_quality":"confirmed_pivots_only",
      "disclaimer":"OB/FVG/structure are OHLCV-derived candidates, not verified institutional orders. Full LuxAlgo parity and MTF no-lookahead validation remain pending."
    }
