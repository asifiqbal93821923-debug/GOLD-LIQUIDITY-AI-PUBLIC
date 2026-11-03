import tempfile
import unittest
from pathlib import Path
from server.market_data import CandleStore, validate_candles, to_epoch_seconds

class CandleValidationTests(unittest.TestCase):
    def test_iso_time_and_sorting(self):
        rows=validate_candles([
          {"time":"2026-01-02T01:00:00Z","open":10,"high":12,"low":9,"close":11},
          {"time":"2026-01-02T00:00:00Z","open":9,"high":11,"low":8,"close":10}])
        self.assertLess(rows[0]["time"],rows[1]["time"])
    def test_millisecond_epoch_normalized(self):
        self.assertEqual(to_epoch_seconds(1767312000000),1767312000)
    def test_invalid_ohlc_rejected(self):
        with self.assertRaises(ValueError):
            validate_candles([{"time":1,"open":10,"high":9,"low":8,"close":10}])
    def test_duplicate_timestamp_rejected(self):
        row={"time":1,"open":10,"high":11,"low":9,"close":10}
        with self.assertRaises(ValueError): validate_candles([row,row])
    def test_negative_volume_rejected(self):
        with self.assertRaises(ValueError):
            validate_candles([{"time":1,"open":10,"high":11,"low":9,"close":10,"volume":-1}])

class CandleStoreTests(unittest.TestCase):
    def test_import_and_read_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            rows=validate_candles([
              {"time":2,"open":11,"high":12,"low":10,"close":11.5,"volume":5},
              {"time":1,"open":10,"high":11,"low":9,"close":10.5,"volume":4}])
            self.assertEqual(store.upsert("XAUUSD","1h",rows,"unit-test"),2)
            data=store.read("XAUUSD","1h",10)
            self.assertEqual([x["time"] for x in data],[1,2])
            self.assertEqual(data[1]["close"],11.5)
    def test_upsert_replaces_existing_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            a=validate_candles([{"time":1,"open":10,"high":11,"low":9,"close":10}])
            b=validate_candles([{"time":1,"open":10,"high":12,"low":9,"close":11}])
            store.upsert("XAUUSD","1h",a,"a"); store.upsert("XAUUSD","1h",b,"b")
            self.assertEqual(store.count("XAUUSD","1h"),1)
            self.assertEqual(store.read("XAUUSD","1h",1)[0]["high"],12)

if __name__=="__main__": unittest.main()
