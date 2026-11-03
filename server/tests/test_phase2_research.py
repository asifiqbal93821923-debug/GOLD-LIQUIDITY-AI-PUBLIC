import tempfile
import unittest
from pathlib import Path

from scripts.analyze_price_action_setups import classify, outcome_summary
from scripts.prepare_xauusd_dataset import read_export
from server.gold_report import _trade_plan_1h


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

    def test_1h_trade_plan_parameters_change_sl_and_targets(self):
        bars = [
            {"time": i * 3600, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 10}
            for i in range(60)
        ]
        plan = _trade_plan_1h("BUY", bars, {
            "atr_period": 10, "swing_lookback": 10,
            "stop_atr_buffer": 0.20, "entry_atr_half_width": 0.10,
            "target_rr": [1, 2, 3],
        })
        self.assertTrue(plan["valid"])
        self.assertEqual(plan["source_timeframe"], "1h")
        self.assertAlmostEqual(plan["stop_loss"], 98.6, places=5)
        self.assertAlmostEqual(plan["targets"][0], 101.4, places=5)

    def test_1h_trade_plan_rejects_non_increasing_rr(self):
        bars = [
            {"time": i * 3600, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 10}
            for i in range(60)
        ]
        plan = _trade_plan_1h("BUY", bars, {"target_rr": [1, 1, 2]})
        self.assertFalse(plan["valid"])

    def test_csv_import_rejects_unclosed_candles_and_local_naive_times(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bars.csv"
            path.write_text("time,open,high,low,close\n2026-11-03T00:00:00,100,101,99,100\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_export(str(path), "1h", 2_000_000_000)
            path.write_text("time,open,high,low,close\n2026-11-03T00:00:00Z,100,101,99,100\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_export(str(path), "1h", 1_500_000_000)


if __name__ == "__main__":
    unittest.main()
