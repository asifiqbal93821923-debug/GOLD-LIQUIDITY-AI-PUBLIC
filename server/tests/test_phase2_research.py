import tempfile
import unittest
from pathlib import Path

from scripts.analyze_price_action_setups import classify, outcome_summary
from scripts.prepare_xauusd_dataset import read_export


class Phase2ResearchTests(unittest.TestCase):
    def test_sweep_and_false_breakout_are_confirmed_on_close(self):
        bars = []
        for i in range(20):
            bars.append({"time": i * 900, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1})
        bars.append({"time": 20 * 900, "open": 100, "high": 103, "low": 99.5, "close": 100.2, "volume": 1})
        events = classify(bars, lookback=20)
        self.assertEqual([x["type"] for x in events], ["liquidity_sweep", "false_breakout"])
        self.assertTrue(all(x["side"] == "SELL" for x in events))

    def test_retest_requires_breakout_then_later_rejection(self):
        bars = []
        for i in range(20):
            bars.append({"time": i * 900, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1})
        bars.append({"time": 20 * 900, "open": 100, "high": 103, "low": 100, "close": 102.5, "volume": 1})
        bars.append({"time": 21 * 900, "open": 102.5, "high": 103, "low": 100.8, "close": 102.7, "volume": 1})
        events = classify(bars, lookback=20)
        self.assertTrue(any(x["type"] == "retest" and x["side"] == "BUY" for x in events))

    def test_setup_outcomes_exclude_events_without_full_forward_horizon(self):
        bars = [{"time": i, "open": 100, "high": 101, "low": 99, "close": 100} for i in range(10)]
        events = [{"index": 9, "side": "BUY", "type": "retest", "time": 9}]
        self.assertEqual(outcome_summary(bars, events), {})

    def test_csv_import_rejects_unclosed_candles_and_local_naive_times(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bars.csv"
            path.write_text("time,open,high,low,close\\n2026-11-03T00:00:00,100,101,99,100\\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_export(str(path), "1h", 2_000_000_000)
            path.write_text("time,open,high,low,close\\n2026-11-03T00:00:00Z,100,101,99,100\\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_export(str(path), "1h", 1_500_000_000)


if __name__ == "__main__":
    unittest.main()
