"""Compare TradingView exported signal fixtures with engine signal events.

CSV schema: time,signal (BUY/SELL/WAIT); timestamps are parsed as UTC.
No automatic indicator parity is inferred from OHLC exports alone.
"""
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

def stamp(value: str) -> int:
    s=value.strip()
    try: return int(float(s))
    except ValueError:
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

def load(path: str) -> dict[int,str]:
    out={}
    with open(path,newline="",encoding="utf-8-sig") as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not {"time","signal"}.issubset(set(reader.fieldnames)):
            raise ValueError("CSV requires columns: time,signal")
        for row in reader:
            side=row["signal"].strip().upper()
            if side in ("LONG","BUY"): side="BUY"
            elif side in ("SHORT","SELL"): side="SELL"
            elif side in ("","NONE","FLAT","WAIT","0"): side="WAIT"
            else: raise ValueError(f"Unknown signal value: {side}")
            t=stamp(row["time"])
            if t in out: raise ValueError(f"Duplicate timestamp: {t}")
            out[t]=side
    return out

def compare(reference: dict[int,str], candidate: dict[int,str], tolerance_seconds: int=0):
    matched=[]; missing=[]; extra=[]; used=set()
    for t,side in sorted(reference.items()):
        choices=[x for x in candidate if x not in used and abs(x-t)<=tolerance_seconds]
        if not choices:
            missing.append({"time":t,"reference":side}); continue
        ct=min(choices,key=lambda x:abs(x-t)); used.add(ct)
        got=candidate[ct]
        matched.append({"time":t,"candidate_time":ct,"reference":side,"candidate":got,"match":side==got})
    for t,side in sorted(candidate.items()):
        if t not in used: extra.append({"time":t,"candidate":side})
    exact=sum(x["match"] for x in matched)
    return {"status":"ok","reference_events":len(reference),"candidate_events":len(candidate),
      "timestamp_matches":len(matched),"direction_matches":exact,
      "direction_accuracy_pct":round(100*exact/len(matched),2) if matched else None,
      "missing_reference_events":len(missing),"extra_candidate_events":len(extra),
      "mismatches":[x for x in matched if not x["match"]],"missing":missing,"extra":extra,
      "timestamp_tolerance_seconds":tolerance_seconds,
      "warning":"Only event-level CSV comparison. Exact parity requires same symbol/feed, timezone, Pine version, inputs, bar-close convention and reference event export."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--reference",required=True); ap.add_argument("--candidate",required=True)
    ap.add_argument("--tolerance-seconds",type=int,default=0); ap.add_argument("--output")
    a=ap.parse_args()
    result=compare(load(a.reference),load(a.candidate),a.tolerance_seconds)
    raw=json.dumps(result,indent=2)
    if a.output: Path(a.output).write_text(raw+"\\n",encoding="utf-8")
    print(raw)
if __name__=="__main__": main()
