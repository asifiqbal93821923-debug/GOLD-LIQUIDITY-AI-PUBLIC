"""Offline paper-trade ledger. Never sends broker orders.

Feed one closed 1H candle plus the latest validated decision JSON per invocation.
A BUY/SELL decision opens a simulated position at the next supplied candle open
only when it is inside the 1H entry zone. Stop-first resolves same-bar conflicts.
"""
from __future__ import annotations
import argparse,csv,json
from datetime import datetime,timezone
from pathlib import Path

FIELDS=["id","signal_time","entry_time","side","entry","stop_loss","tp1","tp2","tp3","status","exit_time","exit_price","exit_reason","net_pnl_price","notes"]

def _load(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,ValueError): return {"trades":[],"last_candle_time":None}

def process(ledger,decision,candle,costs=None):
    costs=costs or {}; t=int(candle["time"])
    if ledger.get("last_candle_time") is not None and t<=int(ledger["last_candle_time"]):
        return ledger,{"status":"duplicate_or_old_candle","opened":False,"closed":0}
    trades=ledger.setdefault("trades",[]); closed=0
    spread=float(costs.get("spread_price",0)); slip=float(costs.get("slippage_price",0))
    half=spread/2+slip
    # Resolve existing open trade before considering a new signal.
    active=next((x for x in reversed(trades) if x["status"]=="OPEN"),None)
    if active:
        side=active["side"]; stop=float(active["stop_loss"])
        targets=[float(active[k.lower()]) for k in ("TP1","TP2","TP3")]
        hi=float(candle["high"]); lo=float(candle["low"])
        stop_hit=lo<=stop if side=="BUY" else hi>=stop
        target_hits=[i for i,x in enumerate(targets) if not active.get("hit_targets",[]).__contains__(i) and (hi>=x if side=="BUY" else lo<=x)]
        if stop_hit:
            px=min(stop,float(candle["open"])) if side=="BUY" else max(stop,float(candle["open"]))
            px=px-half if side=="BUY" else px+half
            active.update(status="CLOSED",exit_time=t,exit_price=px,exit_reason="STOP_FIRST" if target_hits else "STOP",
              net_pnl_price=round((px-float(active["entry"])) if side=="BUY" else (float(active["entry"])-px),5))
            closed+=1
        elif target_hits:
            # Paper ledger exits full size at first target touched; no invented partial fills.
            i=min(target_hits); px=targets[i]-half if side=="BUY" else targets[i]+half
            active.update(status="CLOSED",exit_time=t,exit_price=px,exit_reason=f"TP{i+1}",
              net_pnl_price=round((px-float(active["entry"])) if side=="BUY" else (float(active["entry"])-px),5))
            closed+=1
    opened=False
    side=str(decision.get("decision","WAIT")).upper()
    plan=decision.get("trade_plan") or {}
    if side in ("BUY","SELL") and not any(x["status"]=="OPEN" for x in trades):
        entry_zone=plan.get("entry"); sl=plan.get("stop_loss"); tp=plan.get("targets")
        if isinstance(entry_zone,list) and len(entry_zone)==2 and isinstance(tp,list) and len(tp)==3:
            px=float(candle["open"])
            if float(entry_zone[0])<=px<=float(entry_zone[1]):
                entry=px+half if side=="BUY" else px-half
                levels=[float(sl),*[float(x) for x in tp]]
                valid=(levels[0]<entry<levels[1]<levels[2]<levels[3]) if side=="BUY" else (levels[0]>entry>levels[1]>levels[2]>levels[3])
                if valid:
                    trades.append({"id":f"paper-{t}-{side}","signal_time":decision.get("timestamp",t),
                      "entry_time":t,"side":side,"entry":entry,"stop_loss":levels[0],
                      "tp1":levels[1],"tp2":levels[2],"tp3":levels[3],"status":"OPEN",
                      "exit_time":None,"exit_price":None,"exit_reason":None,"net_pnl_price":None,
                      "hit_targets":[],"notes":"SIMULATED ONLY; next supplied candle open; no broker execution"})
                    opened=True
    ledger["last_candle_time"]=t
    ledger["updated_at"]=datetime.now(timezone.utc).isoformat()
    return ledger,{"status":"ok","opened":opened,"closed":closed,"open_positions":sum(x["status"]=="OPEN" for x in trades),
      "warning":"Paper simulation only. Supply broker-matched closed OHLC and costs; no live order was sent."}

def save(path,ledger):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(ledger,indent=2)+"\\n",encoding="utf-8")
    csv_path=Path(path).with_suffix(".csv")
    with csv_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore"); w.writeheader(); w.writerows(ledger.get("trades",[]))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--ledger",default="data/paper-trades.json")
    ap.add_argument("--decision",required=True); ap.add_argument("--candle",required=True)
    ap.add_argument("--spread-price",type=float,default=0); ap.add_argument("--slippage-price",type=float,default=0)
    a=ap.parse_args(); ledger=_load(a.ledger)
    decision=json.loads(Path(a.decision).read_text(encoding="utf-8"))
    candle=json.loads(Path(a.candle).read_text(encoding="utf-8"))
    ledger,result=process(ledger,decision,candle,{"spread_price":a.spread_price,"slippage_price":a.slippage_price})
    save(a.ledger,ledger); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
