import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.compare_tradingview_signals import compare, compare_metadata, load_csv, main


def valid_meta():
    return {
        "script_title": "PRO XAU V2.0",
        "pine_version": "6",
        "symbol": "OANDA:XAUUSD",
        "provider": "OANDA",
        "timezone": "Etc/UTC",
        "timeframe": "15",
        "bar_timestamp": "bar_open",
        "bar_confirmation": "barstate.isconfirmed",
        "settings": {"EMA Length": 20, "ATR Length": 14},
    }


class PineParityTests(unittest.TestCase):
    def test_low_level_exact_bar_signal_comparison(self):
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

    def test_empty_numeric_series_cannot_pass(self):
        ref = {1: {"signal": "WAIT", "atr": None}}
        got = {1: {"signal": "WAIT", "atr": None}}
        report = compare(ref, got, ["atr"])
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["numeric"]["atr"]["compared"], 0)

    def test_metadata_exact_match_required(self):
        meta = valid_meta()
        self.assertEqual(compare_metadata(meta, dict(meta))["status"], "PASS")
        other = dict(meta, timeframe="60")
        self.assertEqual(compare_metadata(meta, other)["status"], "FAIL")

    def test_metadata_requires_exact_settings(self):
        ref = valid_meta()
        candidate = valid_meta()
        candidate["settings"] = {"EMA Length": 21, "ATR Length": 14}
        report = compare_metadata(ref, candidate)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("settings", report["differences"])

    def test_metadata_missing_fields_fails(self):
        meta = valid_meta()
        meta["provider"] = ""
        meta["settings"] = {}
        report = compare_metadata(meta, meta)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(report["validation_errors"])

    def test_metadata_non_object_fails(self):
        report = compare_metadata([], {})
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(report["validation_errors"])

    def test_duplicate_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "dup.csv"
            p.write_text("time,signal\n1,BUY\n1,SELL\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_csv(str(p), "signal", [])

    def test_cli_requires_both_metadata_files(self):
        with patch("sys.argv", ["compare_tradingview_signals.py",
                                "--reference", "ref.csv", "--candidate", "candidate.csv"]):
            with self.assertRaises(SystemExit) as exc:
                main()
            self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
