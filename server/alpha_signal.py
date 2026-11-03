"""Alpha Signal Engine Pro port.

Derived from MarkitTick's Pine Script source supplied by the user.
Original license: CC BY-NC-SA 4.0. Preserve attribution and share-alike terms.
This module implements the indicator's trend/signal logic only; it does not
claim to calculate order-book footprint, supply/demand zones, or take-profits.
"""
from __future__ import annotations
from math import floor, isfinite
from typing import Any

DEFAULTS = {
    "atr_period": 14, "band_multiplier": 3.0, "atr_weight": 1.0,
    "price_move_weight": 5.0, "ema_smoothing": 1,
    "volatility_fingerprint": False, "vf_lookback": 300,
    "stall_filter": True, "flatness_threshold": 0.05,
    "slope_filter": True, "regression_length": 5, "slope_threshold": 0.05,
    "volume_filter": True, "volume_ma_length": 20,
    "range_filter": True, "range_lookback": 100, "range_percentile": 20.0,
    "bps_filter": True, "min_bps_delta": 1.0,
    "breakout_override": True, "breakout_atr_multiple": 1.5,
}

def _sma(values: list[float | None], length: int) -> list[float | None]:
    out = [None] * len(values)
    for i in range(length - 1, len(values)):
        w = values[i-length+1:i+1]
        if all(v is not None and isfinite(v) for v in w):
            out[i] = sum(w) / length
    return out

def _rma(values: list[float | None], length: int) -> list[float | None]:
    """Wilder RMA, seeded with an SMA of the first complete window."""
    out = [None] * len(values)
    seed = None
    for i in range(len(values)):
        if values[i] is None or not isfinite(values[i]):
            continue
        if seed is None:
            start = i - length + 1
            if start >= 0 and all(v is not None and isfinite(v) for v in values[start:i+1]):
                seed = sum(values[start:i+1]) / length
                out[i] = seed
        else:
            out[i] = (out[i-1] * (length - 1) + values[i]) / length
    return out

def _percentile_nearest_rank(values: list[float | None], length: int, pct: float) -> list[float | None]:
    out = [None] * len(values)
    for i in range(length - 1, len(values)):
        w = values[i-length+1:i+1]
        if any(v is None or not isfinite(v) for v in w):
            continue
        ordered = sorted(w)
        rank = max(1, min(length, int((pct / 100.0) * length + 0.999999999)))
        out[i] = ordered[rank - 1]
    return out

def _linreg_slope(values: list[float | None], length: int) -> list[float | None]:
    """ta.linreg(src,n,0)-ta.linreg(src,n,1), equal to OLS slope."""
    out = [None] * len(values)
    xbar = (length - 1) / 2.0
    denom = sum((x - xbar) ** 2 for x in range(length))
    for i in range(length - 1, len(values)):
        w = values[i-length+1:i+1]
        if any(v is None or not isfinite(v) for v in w):
            continue
        ybar = sum(w) / length
        out[i] = sum((x-xbar)*(w[x]-ybar) for x in range(length)) / denom
    return out

def analyze_alpha_signal(candles: list[dict[str, Any]], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Analyze chronological OHLCV candles (oldest first).

    A signal is only reported for the latest candle, matching the Pine
    script's confirmed-bar alert semantics. Candle timestamps are passed
    through unchanged. Input should be standard time-based candlesticks.
    """
    p = {**DEFAULTS, **(settings or {})}
    if len(candles) < max(50, int(p["atr_period"]) + 5):
        return {"status": "insufficient_history", "required_minimum": max(50, int(p["atr_period"])+5), "received": len(candles)}
    o, h, l, c, v = [], [], [], [], []
    for row in candles:
        try:
            oo, hh, ll, cc = (float(row[k]) for k in ("open","high","low","close"))
            vv = float(row["volume"]) if row.get("volume") is not None else None
            if not all(isfinite(x) for x in (oo,hh,ll,cc)) or hh < max(oo,cc,ll) or ll > min(oo,cc,hh):
                raise ValueError("Invalid OHLC candle")
            o.append(oo); h.append(hh); l.append(ll); c.append(cc); v.append(vv)
        except (KeyError, TypeError, ValueError) as exc:
            return {"status":"invalid_candle_data","message":str(exc)}
    n = len(c)
    tr = [None] * n
    for i in range(1,n):
        tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    atr_series = _rma(tr, int(p["atr_period"]))
    # Pine variable atr = ta.atr(period)[1].
    atr = [atr_series[i-1] if i else None for i in range(n)]
    atr_pct = [((atr[i] / c[i-1] * 100.0) if i and atr[i] is not None and c[i-1] else None) for i in range(n)]
    vf_lb = int(p["vf_lookback"])
    p25 = _percentile_nearest_rank(atr_pct, vf_lb, 25)
    p50 = _percentile_nearest_rank(atr_pct, vf_lb, 50)
    p75 = _percentile_nearest_rank(atr_pct, vf_lb, 75)
    buckets = [None] * n
    for i in range(n):
        if atr_pct[i] is None: continue
        x = atr_pct[i]
        buckets[i] = 0 if (p25[i] is None or x < p25[i]) else 1 if (p50[i] is None or x < p50[i]) else 2 if (p75[i] is None or x < p75[i]) else 3
    vf_names = ["Alpha","Beta","Gamma","Delta"]
    gam_mults, phi_mults, tau_mults = [0.70,1.00,1.40,2.00], [0.70,1.00,1.30,1.80], [0.60,1.00,1.35,1.70]
    band_half, trend, direction, display_dir = [None]*n, [None]*n, [1]*n, [1]*n
    breakout, flat_guard = [False]*n, [False]*n
    pm_raw = [None]*n
    for i in range(2,n):
        pm_raw[i] = abs(c[i-1]-c[i-2]) / max(c[i-2], 1e-12)
    pm_p95 = _percentile_nearest_rank(pm_raw, 100, 95)
    vol_sma = _sma(v, int(p["volume_ma_length"]))
    ranges = [None] + [h[i-1]-l[i-1] for i in range(1,n)]
    range_pct = _percentile_nearest_rank(ranges, int(p["range_lookback"]), float(p["range_percentile"]))
    hlc3 = [(h[i]+l[i]+c[i])/3 for i in range(n)]
    cloud_ref = _sma(hlc3, 8) # display default; UI can expose cloud length separately
    stall = slope_flat = vol_flat = range_flat = bps_flat = False
    for i in range(n):
        prev = i-1
        bucket = buckets[i] if buckets[i] is not None else 1
        gm = gam_mults[bucket] if p["volatility_fingerprint"] else 1.0
        phim = phi_mults[bucket] if p["volatility_fingerprint"] else 1.0
        taum = tau_mults[bucket] if p["volatility_fingerprint"] else 1.0
        eff_gam = float(p["band_multiplier"])*gm
        eff_phi = float(p["atr_weight"])*phim
        eff_tau = float(p["price_move_weight"])*taum
        eff_kap = max(1.0, float(p["ema_smoothing"])*(gm if p["volatility_fingerprint"] else 1.0))
        if i >= 2 and atr[i] is not None and c[prev] != 0 and pm_raw[i] is not None:
            pm = min(pm_raw[i], pm_p95[i] if pm_p95[i] is not None else pm_raw[i])
            dyn = eff_gam + (atr[i]/c[prev])*eff_phi + pm*eff_tau
            raw_half = dyn*atr[i]
            alpha = 2.0/(eff_kap+1.0)
            band_half[i] = raw_half if band_half[i-1] is None else alpha*raw_half+(1-alpha)*band_half[i-1]
            mid = (h[prev]+l[prev])/2.0
            upper, lower = mid+band_half[i], mid-band_half[i]
            if trend[i-1] is None:
                # Pine's first non-na trendLine is seeded to upperBand;
                # close[1] > trendLine[1] is false while [1] is na.
                direction[i] = -1
                trend[i] = upper
            elif c[prev] > trend[i-1]:
                direction[i] = 1
                trend[i] = max(lower, trend[i-1])
            else:
                direction[i] = -1
                trend[i] = min(upper, trend[i-1])
        elif i > 0:
            trend[i] = trend[i-1]
            direction[i] = direction[i-1]
            band_half[i] = band_half[i-1]
        if i > 2 and atr[i] is not None and trend[i-1] is not None and trend[i-2] is not None:
            stall = p["stall_filter"] and abs(trend[i-1]-trend[i-2]) < atr[i]*float(p["flatness_threshold"])
            reg_len = int(p["regression_length"])
            slope_window = trend[max(0, i-reg_len):i]
            slope = None
            if len(slope_window) == reg_len and all(x is not None for x in slope_window):
                xbar = (reg_len - 1) / 2.0
                denom = sum((x-xbar)**2 for x in range(reg_len))
                ybar = sum(slope_window) / reg_len
                slope = sum((x-xbar)*(slope_window[x]-ybar) for x in range(reg_len)) / denom
            slope_flat = p["slope_filter"] and slope is not None and abs(slope)/max(atr[i],1e-12) < float(p["slope_threshold"])
            vol_threshold = vol_sma[prev] if vol_sma[prev] is not None else ((v[prev] + 1.0) if v[prev] is not None else None)
            vol_flat = p["volume_filter"] and v[prev] is not None and vol_threshold is not None and v[prev] <= vol_threshold
            eff_range = range_pct[prev]
            if p["volatility_fingerprint"] and eff_range is not None: eff_range *= gm
            range_threshold = eff_range if eff_range is not None else ((ranges[prev] + 1.0) if ranges[prev] is not None else None)
            range_flat = p["range_filter"] and range_threshold is not None and ranges[prev] is not None and ranges[prev] <= range_threshold
            bps = abs(trend[i-1]-trend[i-2])/max(c[i-2],1e-12)*10000.0
            bps_flat = p["bps_filter"] and bps < float(p["min_bps_delta"])*gm
            bo = p["breakout_override"] and abs(c[prev]-c[prev-1]) > atr[i]*float(p["breakout_atr_multiple"])*gm
            breakout[i] = bool(bo)
            flat_guard[i] = bool(stall or slope_flat or vol_flat or range_flat or bps_flat) and not bo
            display_dir[i] = display_dir[i-1] if flat_guard[i] else direction[i]
        elif i > 0:
            display_dir[i] = display_dir[i-1]
    last = n-1
    prev_display = display_dir[last-1] if last else 1
    long_sig = display_dir[last] == 1 and prev_display == -1
    short_sig = display_dir[last] == -1 and prev_display == 1
    bucket = buckets[last]
    regime = "trending" if not flat_guard[last] else "flat"
    strength = None
    if atr[last] and trend[last-1] is not None:
        strength = min(1.0, abs(c[last-1]-trend[last-1])/max(atr[last],1e-12)/3.0)
    return {
        "status":"ok", "engine":"Alpha Signal Engine Pro", "source_attribution":"MarkitTick",
        "timestamp":candles[last].get("time"), "symbol":candles[last].get("symbol","XAUUSD"),
        "direction":"bullish" if display_dir[last] == 1 else "bearish",
        "signal":"BUY" if long_sig else "SELL" if short_sig else "WAIT",
        "regime":regime, "breakout_override":"engaged" if breakout[last] else "nominal" if p["breakout_override"] else "off",
        "trend_line":trend[last], "atr_previous":atr[last], "trend_strength":strength,
        "volatility_fingerprint":({"bucket":bucket,"label":vf_names[bucket]} if p["volatility_fingerprint"] and bucket is not None else None),
        "filters":{
            "stall":{"enabled":p["stall_filter"],"flat":bool(stall) if last>2 else False},
            "slope":{"enabled":p["slope_filter"],"flat":bool(slope_flat) if last>2 else False},
            "volume":{"enabled":p["volume_filter"],"flat":bool(vol_flat) if last>2 else False},
            "range":{"enabled":p["range_filter"],"flat":bool(range_flat) if last>2 else False},
            "bps_delta":{"enabled":p["bps_filter"],"flat":bool(bps_flat) if last>2 else False},
        },
        "note":"Signal logic only. This engine does not calculate footprint, supply/demand zones, entry bands or TP/SL.",
    }
