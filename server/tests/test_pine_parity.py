import tempfile
import unittest
from pathlib import Path
from scripts.compare_tradingview_signals import compare, compare_metadata, load_csv


class PineParityTests(unittest.TestCase):
    def test_exact_bar_signal_parity(self):
        ref = {1: {"signal": "BUY"}, 2: {"signal": "WAIT"}}
        got = {1: {"signal": "BUY"}, 2: {"signal": "WAIT"}}
        self.assertEqual(compare(ref, got, [])["status"], "PASS")

    def test_missing_or_extra_bar_fails(self):
        ref = {1: {"signal": "BUY"}, 2: {"signal": "WAIT"}}
        got = {1: {"signal": "BUY"}, 3: {"signal": "WAIT"}}
        report = compare(ref, got, [])
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["bars"]["missing_in_python"], 1)
        self.assertEqual(report["bars"]["extra_in_python"], 1)

    def test_signal_mismatch_fails_even_with_same_timestamps(self):
        report = compare({1: {"signal": "BUY"}}, {1: {"signal": "SELL"}}, [])
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["signal"]["mismatch_count"], 1)

    def test_numeric_series_tolerance(self):
        ref = {1: {"signal": "BUY", "atr": 1.0}}
        got = {1: {"signal": "BUY", "atr": 1.0000001}}
        self.assertEqual(compare(ref, got, ["atr"], numeric_tolerance=0.000001)["status"], "PASS")
        self.assertEqual(compare(ref, got, ["atr"], numeric_tolerance=0.00000001)["status"], "FAIL")

    def test_metadata_exact_match_required(self):
        meta = {k: "x" for k in ("script_title", "pine_version", "symbol", "provider",
                "timezone", "timeframe", "bar_timestamp", "bar_confirmation", "settings")}
        self.assertEqual(compare_metadata(meta, dict(meta))["status"], "PASS")
        other = dict(meta, timeframe="15m")
        self.assertEqual(compare_metadata(meta, other)["status"], "FAIL")

    def test_duplicate_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "dup.csv"
            p.write_text("time,signal\n1,BUY\n1,SELL\n")
            with self.assertRaises(ValueError):
                load_csv(str(p), "signal", [])


if __name__ == "__main__":
    unittest.main()
