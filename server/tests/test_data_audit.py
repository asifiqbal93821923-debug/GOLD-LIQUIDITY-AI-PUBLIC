import unittest
from server.data_audit import audit_candle_history

BASE=1_800_000_000

def candle(t, close=2300):
    return {"time":t,"open":close,"high":close+2,"low":close-2,"close":close+1,"volume":100}

class HistoricalDataAuditTests(unittest.TestCase):
    def test_reports_coverage_and_closed_forming_future_separately(self):
        rows=[candle(BASE),candle(BASE+3600),candle(BASE+7200),candle(BASE+10800)]
        out=audit_candle_history(rows,"1h",BASE+9000)
        self.assertEqual(out["valid_unique_rows"],4)
        self.assertEqual(out["closed_rows"],3)
        self.assertEqual(out["forming_rows"],1)
        self.assertEqual(out["future_rows"],0)
        self.assertEqual(out["history_days"],0.125)

    def test_reports_duplicates_and_out_of_order_without_silent_hiding(self):
        rows=[candle(BASE+3600),candle(BASE),candle(BASE)]
        out=audit_candle_history(rows,"1h",BASE+10000)
        self.assertEqual(out["duplicate_rows"],1)
        self.assertEqual(out["out_of_order_rows"],1)
        self.assertEqual(out["valid_unique_rows"],2)

    def test_reports_gap_without_fabricating_missing_candles(self):
        rows=[candle(BASE),candle(BASE+3600),candle(BASE+4*3600)]
        out=audit_candle_history(rows,"1h",BASE+10*3600)
        self.assertEqual(out["gap_count"],1)
        self.assertEqual(out["estimated_missing_intervals"],2)
        self.assertEqual(out["valid_unique_rows"],3)

    def test_invalid_ohlc_is_reported(self):
        bad={"time":BASE,"open":10,"high":9,"low":8,"close":10}
        out=audit_candle_history([bad],"1h",BASE+7200)
        self.assertEqual(out["invalid_rows"],1)
        self.assertEqual(out["status"],"empty")

    def test_future_rows_are_not_counted_as_closed(self):
        out=audit_candle_history([candle(BASE+3600)],"1h",BASE)
        self.assertEqual(out["future_rows"],1)
        self.assertEqual(out["closed_rows"],0)

    def test_unsupported_timeframe_is_rejected(self):
        self.assertEqual(audit_candle_history([],"3m",BASE)["status"],"unsupported_timeframe")

if __name__=="__main__":
    unittest.main()
