import tempfile
import unittest
from pathlib import Path
from scripts.compare_tradingview_signals import compare
from scripts.walk_forward_validation import run_walk_forward
from scripts.paper_trade_ledger import process

class ValidationToolTests(unittest.TestCase):
    def test_signal_parity_reports_direction_mismatch(self):
        out=compare({100:"BUY",200:"SELL"},{100:"BUY",200:"BUY"})
        self.assertEqual(out["timestamp_matches"],2)
        self.assertEqual(out["direction_matches"],1)
        self.assertEqual(out["direction_accuracy_pct"],50.0)

    def test_walk_forward_refuses_short_history(self):
        rows=[{"time":1700000000+i*3600,"open":2300,"high":2301,"low":2299,"close":2300.5,"volume":10} for i in range(100)]
        out=run_walk_forward({"4h":rows[:60],"1h":rows,"15m":rows})
        self.assertEqual(out["status"],"insufficient_history")
        self.assertGreater(out["required_minimum_for_split"],60)

    def test_paper_ledger_never_opens_on_wait(self):
        ledger,out=process({"trades":[],"last_candle_time":None},{"decision":"WAIT"},
          {"time":1700000000,"open":2300,"high":2301,"low":2299,"close":2300})
        self.assertFalse(out["opened"])
        self.assertEqual(len(ledger["trades"]),0)

    def test_paper_ledger_opens_only_inside_entry_zone(self):
        decision={"decision":"BUY","timestamp":1700000000,"trade_plan":{
          "entry":[2299,2301],"stop_loss":2290,"targets":[2310,2320,2330]}}
        ledger,out=process({"trades":[],"last_candle_time":None},decision,
          {"time":1700003600,"open":2300,"high":2305,"low":2298,"close":2302})
        self.assertTrue(out["opened"])
        self.assertEqual(ledger["trades"][0]["status"],"OPEN")

if __name__=="__main__": unittest.main()
