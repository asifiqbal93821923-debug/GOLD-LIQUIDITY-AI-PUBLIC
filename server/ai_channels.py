"""AI Channels (K-means) price-distribution context adapter.

Two explicit modes:
- pine_parity: preserves the documented source convergence check of first 3
  centroids (needs direct TradingView fixture validation before certification).
- corrected: checks every centroid and uses a numeric tolerance.
This is a regime/context feature, not a trade trigger.
"""
from __future__ import annotations
from math import sqrt
from typing import Any


def _percentile(sorted_values: list[float], pct: float) -> float:
    if len(sorted_values)==1: return sorted_values[0]
    pos=(len(sorted_values)-1)*pct/100.0
    lo=int(pos); hi=min(lo+1,len(sorted_values)-1); frac=pos-lo
    return sorted_values[lo]*(1-frac)+sorted_values[hi]*frac


def analyze_ai_channels(candles: list[dict[str,Any]], settings: dict[str,Any] | None=None):
    p={"window":30,"clusters":5,"max_iterations":100,"denoise":True,
       "variant":"corrected","tolerance":1e-8,"max_history":5000,**(settings or {})}
    k=int(p["clusters"]); length=int(p["window"])
    if k<3 or k>10 or length<k or int(p["max_iterations"])<1:
        return {"status":"invalid_settings","reason":"clusters must be 3..10, window >= clusters and max_iterations >= 1"}
    if len(candles)<length:
        return {"status":"insufficient_history","required_minimum":length,"received":len(candles)}
    closes=[]
    try:
        for i,row in enumerate(candles):
            x=float(row["close"])
            if x!=x or abs(x)==float("inf"): raise ValueError(f"invalid close at {i}")
            closes.append(x)
    except (KeyError,TypeError,ValueError) as exc:
        return {"status":"invalid_data","reason":str(exc)}
    sample=closes[-min(length,int(p["max_history"])):]
    ordered=sorted(sample)
    centers=[_percentile(ordered,int(i/(k+1)*100)) for i in range(1,k+1)]
    variant=str(p["variant"]).lower()
    if variant not in ("corrected","pine_parity"):
        return {"status":"invalid_settings","reason":"variant must be corrected or pine_parity"}
    iterations=0
    assignments=[0]*len(sample)
    for iteration in range(int(p["max_iterations"])):
        buckets=[[] for _ in range(k)]
        for ix,value in enumerate(sample):
            nearest=min(range(k),key=lambda j:(abs(value-centers[j]),j))
            assignments[ix]=nearest
            buckets[nearest].append(value)
        new=[]
        for j in range(k):
            new.append(sum(buckets[j])/len(buckets[j]) if buckets[j] else centers[j])
        delta=[abs(new[j]-centers[j]) for j in range(k)]
        centers=new
        iterations=iteration+1
        check=delta[:3] if variant=="pine_parity" else delta
        if all(d<=float(p["tolerance"]) for d in check):
            break
    # Reassign using final centers.
    buckets=[[] for _ in range(k)]
    for value in sample:
        buckets[min(range(k),key=lambda j:(abs(value-centers[j]),j))].append(value)
    pairs=sorted(zip(centers,buckets),key=lambda x:x[0])
    centers=[x[0] for x in pairs]; buckets=[x[1] for x in pairs]
    if not buckets[0] or not buckets[-1]:
        return {"status":"degraded","reason":"EMPTY_EXTREME_CLUSTER","data_quality":"empty_cluster"}
    def stdev(values):
        if len(values)<2: return 0.0
        m=sum(values)/len(values)
        return sqrt(sum((x-m)**2 for x in values)/len(values))
    lower,upper=centers[0],centers[-1]
    middle=centers[(k-1)//2]
    upper_disp=stdev(buckets[-1]); lower_disp=stdev(buckets[0])
    upper_inner=upper-upper_disp; lower_inner=lower+lower_disp
    price=closes[-1]
    if price>upper: raw="bullish"
    elif price<lower: raw="bearish"
    else: raw="neutral"
    state=raw
    # Monotonic denoising relative to previous close's channel classification.
    # This is intentionally reset per request until persistent replay state is stored.
    if p["denoise"] and len(closes)>length:
        prev=closes[-2]
        if prev>upper: state="bullish"
        elif prev<lower: state="bearish"
    location="above" if price>upper else "below" if price<lower else "inside"
    return {
      "status":"ok","engine":"AI Channels K-means","implementation_variant":variant,
      "window_size":len(sample),"cluster_count":k,"iterations_used":iterations,
      "upper_centroid":upper,"central_centroid":middle,"lower_centroid":lower,
      "upper_dispersion":upper_disp,"lower_dispersion":lower_disp,
      "upper_band_inner":upper_inner,"lower_band_inner":lower_inner,
      "channel_state":state,"raw_channel_state":raw,"price_location":location,
      "denoised":bool(p["denoise"]),"trailing_stop_mode":False,
      "data_quality":"valid","disclaimer":"Adaptive close-price clustering context only; not S/D, a forecast, or institutional positioning. Persistent Pine denoise parity requires replay fixtures."
    }
