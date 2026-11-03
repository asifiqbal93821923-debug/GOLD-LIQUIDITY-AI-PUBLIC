import unittest
from server.institutional_footprint import analyze_institutional_footprint, build_gold_report


def candles(n=100):
    out=[]
    price=2300.0
    for i in range(n):
        drift=0.35 if (i//12)%2==0 else -0.28
        op=price
        close=price+drift+((i%5)-2)*0.04
        high=max(op,close)+0.25+(i%4)*0.03
        low=min(op,close)-0.24-(i%3)*0.02
        volume=100.0 if i < n-1 else 260.0
        out.append({"time":i,"symbol":"XAUUSD","open":op,"high":high,"low":low,"close":close,"volume":volume})
        price=close
    return out


class InstitutionalFootprintTests(unittest.TestCase):
    def test_contract_and_orderbook_disclosure(self):
        result=analyze_institutional_footprint(candles())
        self.assertEqual(result["status"],"ok")
        self.assertEqual(result["source_mode"],"CANDLE_DERIVED_ESTIMATE")
        self.assertEqual(result["order_book"]["status"],"not_connected")
        self.assertIsNone(result["order_book"]["resting_order_sizes"])
        self.assertIn("buy_side_above_swing_highs",result["liquidity_pools"])

    def test_volume_spike_is_detected_as_proxy(self):
        result=analyze_institutional_footprint(candles())
        self.assertTrue(result["activity_proxies"]["unusual_volume"])
        self.assertEqual(result["activity_proxies"]["delta_semantics"],"CANDLE_CLOSE_LOCATION_ESTIMATE_NOT_TRUE_CVD")

    def test_insufficient_history(self):
        result=analyze_institutional_footprint(candles(10))
        self.assertEqual(result["status"],"insufficient_history")

    def test_invalid_ohlc(self):
        rows=candles()
        rows[-1]["low"]=99999
        self.assertEqual(analyze_institutional_footprint(rows)["status"],"invalid_data")

    def test_multi_timeframe_missing_data_is_not_fabricated(self):
        report=build_gold_report({"1h":candles()})
        self.assertEqual(report["status"],"partial")
        self.assertEqual(report["institutional_footprint"]["4h"]["status"],"not_available")
        self.assertEqual(report["decision"],"WAIT")


if __name__ == "__main__":
    unittest.main()
