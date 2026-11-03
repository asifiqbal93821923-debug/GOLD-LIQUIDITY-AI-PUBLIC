"""Chronological walk-forward harness for exported MTF candle JSON."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from server.multitimeframe_backtest import run_gold_mtf_backtest
from server.market_data import validate_candles

def metrics(report):
    keys=("trade_count","win_rate_pct","net_pnl_price","average_R","profit_factor","max_drawdown_price","accepted_signals","signals_evaluated")
    return {k:report.get(k) for k in keys}

def run_walk_forward(frames,train_fraction=0.70,costs=None,settings=None):
    if not 0.5<=train_fraction<=0.9: raise ValueError("train_fraction must be 0.50..0.90")
    normalized = {}
    for tf in ("4h", "1h", "15m", "5m"):
        rows = frames.get(tf) or []
        if rows:
            normalized[tf] = validate_candles(rows)
    provenance = frames.get("metadata", {}) if isinstance(frames.get("metadata"), dict) else {}
    data_quality = frames.get("data_quality", {}) if isinstance(frames.get("data_quality"), dict) else {}
    if data_quality.get("status") not in (None, "ready_for_60_20_20_validation"):
        return {"status": "insufficient_history", "reason": "DATASET_QUALITY_GATE_FAILED",
                "data_quality": data_quality}
    # Ensure both chronological partitions can independently meet the engine's
    # 50 closed-bar minimum. The test partition must never be shorter than 50.
    required=math.ceil(50/(1-train_fraction))
    for tf in ("4h","1h","15m"):
        count=len(normalized.get(tf,[]))
        if count<required:
            return {"status":"insufficient_history","timeframe":tf,
              "required_minimum_for_split":required,"received":count,
              "reason":"Both train and unseen test windows need at least 50 closed bars."}
    h1=normalized["1h"]; cut_index=int(len(h1)*train_fraction)
    boundary=h1[cut_index]["time"]
    train={tf:[x for x in rows if x["time"]<boundary] for tf,rows in normalized.items()}
    test={tf:[x for x in rows if x["time"]>=boundary] for tf,rows in normalized.items()}
    train_report=run_gold_mtf_backtest(train,costs=costs,settings=settings)
    test_report=run_gold_mtf_backtest(test,costs=costs,settings=settings)
    return {"status":"ok" if train_report.get("status")=="ok" and test_report.get("status")=="ok" else "blocked",
      "feed_provenance": {"source": provenance.get("source"), "symbol": provenance.get("symbol")},
      "method":"chronological holdout; fixed parameters; no future bars passed across split",
      "train_fraction":train_fraction,"boundary_epoch":boundary,
      "train":metrics(train_report),"out_of_sample":metrics(test_report),
      "train_status":train_report.get("status"),"out_of_sample_status":test_report.get("status"),
      "train_veto_counts":train_report.get("veto_counts"),
      "out_of_sample_veto_counts":test_report.get("veto_counts"),
      "warning":"Fixed-parameter chronological holdout, not parameter optimization. Minimum is a technical floor, not a statistically sufficient sample. Costs must match target broker."}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--output")
    ap.add_argument("--train-fraction",type=float,default=.70)
    ap.add_argument("--spread-points",type=float,required=True); ap.add_argument("--slippage-points",type=float,required=True)
    ap.add_argument("--commission-points-per-side",type=float,default=0); ap.add_argument("--point-size",type=float,default=.01)
    a=ap.parse_args(); frames=json.loads(Path(a.input).read_text(encoding="utf-8"))
    costs={"spread_points":a.spread_points,"slippage_points":a.slippage_points,
      "commission_points_per_side":a.commission_points_per_side,"point_size":a.point_size}
    result=run_walk_forward(frames,a.train_fraction,costs)
    raw=json.dumps(result,indent=2)
    if a.output: Path(a.output).write_text(raw+"\n",encoding="utf-8")
    print(raw)
if __name__=="__main__": main()
