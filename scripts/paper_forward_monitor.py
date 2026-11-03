"""P2.6 deterministic forward-paper monitor. No broker connectivity or orders.

Input is JSONL: one record per fully closed 1H candle, with decision and
explicit execution-cost assumptions. Records are processed chronologically.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from scripts.paper_trade_ledger import process, save

def _finite(value, name):
    try: number=float(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number): raise ValueError(f"{name} must be finite")
    return number

def run_forward_paper(input_path, ledger_path, audit_path):
    source=Path(input_path)
    if not source.is_file(): raise ValueError("Forward event JSONL file not found")
    ledger_file=Path(ledger_path)
    if ledger_file.exists():
        try: ledger=json.loads(ledger_file.read_text(encoding="utf-8"))
        except Exception as exc: raise ValueError("Existing paper ledger is corrupt; refusing to reset it") from exc
        if not isinstance(ledger,dict) or not isinstance(ledger.get("trades"),list):
            raise ValueError("Existing paper ledger schema is invalid")
    else: ledger={"trades":[],"last_candle_time":None}
    audit=[]
    previous=None
    counters={"events":0,"opened":0,"closed":0,"wait_decisions":0,
              "spread_gate_wait":0,"duplicate_or_old":0,"rejected":0}
    for line_no,raw in enumerate(source.read_text(encoding="utf-8").splitlines(),start=1):
        if not raw.strip(): continue
        counters["events"]+=1
        try:
            event=json.loads(raw)
            decision=event["decision"]; candle=event["candle"]; costs=event["costs"]
            if not isinstance(decision,dict) or not isinstance(candle,dict) or not isinstance(costs,dict):
                raise ValueError("decision, candle and costs must be JSON objects")
            if candle.get("time") is None or candle.get("is_closed") is not True:
                raise ValueError("Only explicitly closed candles with time are accepted")
            t=int(candle["time"])
            if previous is not None and t<=previous:
                raise ValueError("Input candles must be strictly chronological and unique")
            previous=t
            if decision.get("timestamp") is not None and int(decision["timestamp"])>t:
                raise ValueError("Decision timestamp cannot be later than its candle close")
            for key in ("open","high","low","close"):
                _finite(candle.get(key),f"candle.{key}")
            if not (_finite(candle["low"],"low")<=min(_finite(candle["open"],"open"),_finite(candle["close"],"close"))
                    <=max(_finite(candle["open"],"open"),_finite(candle["close"],"close"))
                    <=_finite(candle["high"],"high")):
                raise ValueError("Malformed OHLC candle")
            spread=_finite(costs.get("spread_price"),"costs.spread_price")
            slip=_finite(costs.get("slippage_price"),"costs.slippage_price")
            commission=_finite(costs.get("commission_price_per_side"),"costs.commission_price_per_side")
            cap=costs.get("max_spread_price")
            cap=_finite(cap,"costs.max_spread_price") if cap is not None else 0
            if min(spread,slip,commission,cap)<0: raise ValueError("Execution costs cannot be negative")
            costs={**costs,"require_spread_limit":True,"spread_price":spread,
                   "slippage_price":slip,"commission_price_per_side":commission,
                   "max_spread_price":cap}
            ledger,result=process(ledger,decision,candle,costs)
            if result.get("opened"): counters["opened"]+=1
            if result.get("closed"): counters["closed"]+=int(result["closed"])
            if str(decision.get("decision","WAIT")).upper()=="WAIT": counters["wait_decisions"]+=1
            if result.get("spread_gate")=="WAIT": counters["spread_gate_wait"]+=1
            if result.get("status")=="duplicate_or_old_candle": counters["duplicate_or_old"]+=1
            audit.append({"line":line_no,"candle_time":t,"decision":decision.get("decision","WAIT"),
                          "result":result,"paper_only":True})
        except Exception as exc:
            counters["rejected"]+=1
            audit.append({"line":line_no,"status":"REJECTED","reason":str(exc),"paper_only":True})
    save(ledger_file,ledger)
    audit_file=Path(audit_path); audit_file.parent.mkdir(parents=True,exist_ok=True)
    audit_file.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in audit),encoding="utf-8")
    summary={"status":"ok" if counters["rejected"]==0 else "partial",
             "phase":"P2.6","mode":"offline_forward_paper_replay",
             "counters":counters,"open_positions":sum(x.get("status")=="OPEN" for x in ledger["trades"]),
             "closed_positions":sum(x.get("status")=="CLOSED" for x in ledger["trades"]),
             "paper_only":True,"broker_orders_sent":False,
             "acceptance":{"closed_candle_only":True,"chronological_unique_candles":True,
                           "cost_fields_required":True,"spread_gate_fail_closed":True,
                           "live_feed_connected":False,"minimum_forward_duration_met":False,
                           "historical_gates_passed":False},
             "limitations":["This runner processes supplied closed-candle events; it is not a live data collector.",
                            "OHLC cannot reconstruct intrabar path, queue position or guaranteed fills.",
                            "No broker order is sent; this is not evidence of profitability."]}
    summary_path=Path(audit_path).with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True,help="JSONL: decision,candle,costs per fully closed 1H candle")
    ap.add_argument("--ledger",default="data/paper-trades.json")
    ap.add_argument("--audit",default="reports/phase2/paper-forward-audit.jsonl")
    a=ap.parse_args()
    summary=run_forward_paper(a.input,a.ledger,a.audit)
    print(json.dumps(summary,indent=2))
    if summary["status"]!="ok": raise SystemExit(2)
if __name__=="__main__": main()
