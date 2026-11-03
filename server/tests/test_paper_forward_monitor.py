import json
import tempfile
import unittest
from pathlib import Path
from scripts.paper_forward_monitor import run_forward_paper
from scripts.paper_trade_ledger import process

class PaperForwardMonitorTests(unittest.TestCase):
    def _event(self, time=1700003600, decision="WAIT", spread=0.1, cap=0.2):
        return {"decision":{"decision":decision,"timestamp":time-3600},
                "candle":{"time":time,"is_closed":True,"open":2300,"high":2305,"low":2298,"close":2302},
                "costs":{"spread_price":spread,"slippage_price":0.02,
                         "commission_price_per_side":0.01,"max_spread_price":cap}}

    def test_spread_gate_blocks_entry_without_blocking_open_trade_management(self):
        decision={"decision":"BUY","timestamp":1000,"trade_plan":{
            "entry":[2299,2301],"stop_loss":2290,"targets":[2310,2320,2330]}}
        ledger={"trades":[{"id":"existing","side":"BUY","status":"OPEN","entry":2300,
             "stop_loss":2290,"tp1":2310,"tp2":2320,"tp3":2330,"hit_targets":[]}],
             "last_candle_time":None}
        candle={"time":2000,"open":2289,"high":2295,"low":2288,"close":2290}
        out,result=process(ledger,decision,candle,{"spread_price":0.5,"slippage_price":0,
             "commission_price_per_side":0,"max_spread_price":0.2,"require_spread_limit":True})
        self.assertEqual(result["closed"],1)
        self.assertFalse(result["opened"])
        self.assertEqual(result["spread_gate"],"WAIT")

    def test_monitor_accepts_closed_chronological_events_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"events.jsonl"; ledger=Path(d)/"ledger.json"; audit=Path(d)/"audit.jsonl"
            src.write_text(json.dumps(self._event())+"\n"+json.dumps(self._event(1700007200))+"\n")
            summary=run_forward_paper(src,ledger,audit)
            self.assertEqual(summary["status"],"ok")
            self.assertEqual(summary["counters"]["events"],2)
            self.assertTrue(summary["paper_only"])
            self.assertTrue(ledger.exists()); self.assertTrue(audit.exists())
            self.assertTrue(audit.with_suffix(".summary.json").exists())

    def test_monitor_rejects_forming_or_out_of_order_candles(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"events.jsonl"; ledger=Path(d)/"ledger.json"; audit=Path(d)/"audit.jsonl"
            bad=self._event(); bad["candle"]["is_closed"]=False
            src.write_text(json.dumps(bad)+"\n"+json.dumps(self._event(1700007200))+"\n"+
                           json.dumps(self._event(1700003600))+"\n")
            summary=run_forward_paper(src,ledger,audit)
            self.assertEqual(summary["status"],"partial")
            self.assertEqual(summary["counters"]["rejected"],2)

    def test_monitor_refuses_corrupt_existing_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"events.jsonl"; ledger=Path(d)/"ledger.json"; audit=Path(d)/"audit.jsonl"
            src.write_text(json.dumps(self._event())+"\n")
            ledger.write_text("{broken")
            with self.assertRaises(ValueError):
                run_forward_paper(src,ledger,audit)

if __name__=="__main__": unittest.main()
