import csv
import tempfile
import unittest
from pathlib import Path
from scripts.analyze_broker_quotes import analyze_quotes

class BrokerQuoteAnalysisTests(unittest.TestCase):
    def _csv(self, rows):
        f = tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", delete=False)
        writer = csv.DictWriter(f, fieldnames=["timestamp", "bid", "ask", "point_size"])
        writer.writeheader()
        writer.writerows(rows)
        f.close()
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        return f.name

    def test_spread_distribution_and_rollover_buckets(self):
        path = self._csv([
            {"timestamp":"2026-01-05T06:00:00Z","bid":"4500","ask":"4500.10","point_size":"0.01"},
            {"timestamp":"2026-01-05T22:00:00Z","bid":"4500","ask":"4500.20","point_size":"0.01"},
            {"timestamp":"2026-01-05T22:05:00Z","bid":"4500","ask":"4500.30","point_size":"0.01"},
        ])
        report = analyze_quotes(path, broker="XM360", symbol="XAUUSD",
                                rollover_start_utc="21:55", rollover_end_utc="22:15",
                                minimum_samples=3)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["quote_count"], 3)
        self.assertEqual(report["overall"]["max_points"], 30.0)
        self.assertEqual(report["by_utc_session_and_rollover"]["rollover_configured_window"]["sample_count"], 2)
        self.assertFalse(report["provenance"]["broker_identity_verified"])

    def test_naive_timestamp_is_rejected(self):
        path = self._csv([{"timestamp":"2026-01-05T06:00:00","bid":"1","ask":"1.1","point_size":"0.01"},
                          {"timestamp":"2026-01-05T06:05:00Z","bid":"1","ask":"1.1","point_size":"0.01"}])
        with self.assertRaises(ValueError):
            analyze_quotes(path, broker="XM360", symbol="XAUUSD",
                           rollover_start_utc="21:55", rollover_end_utc="22:15")

    def test_bad_quote_is_rejected(self):
        path = self._csv([{"timestamp":"2026-01-05T06:00:00Z","bid":"1","ask":"0.9","point_size":"0.01"},
                          {"timestamp":"2026-01-05T06:05:00Z","bid":"1","ask":"1.1","point_size":"0.01"}])
        with self.assertRaises(ValueError):
            analyze_quotes(path, broker="XM360", symbol="XAUUSD",
                           rollover_start_utc="21:55", rollover_end_utc="22:15")

if __name__ == "__main__":
    unittest.main()
