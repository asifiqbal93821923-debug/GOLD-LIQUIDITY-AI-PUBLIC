import unittest
from alpha_signal import analyze_alpha_signal

def sample_candles(n=420):
    rows=[]
    price=2650.0
    for i in range(n):
        drift = 0.18 if (i//45)%2==0 else -0.16
        op=price
        cl=price+drift+((i%7)-3)*0.035
        hi=max(op,cl)+0.45+(i%3)*0.03
        lo=min(op,cl)-0.42-(i%4)*0.02
        rows.append({"time":i,"symbol":"XAUUSD","open":op,"high":hi,"low":lo,"close":cl,"volume":100+i%17})
        price=cl
    return rows

class AlphaSignalTests(unittest.TestCase):
    def test_returns_expected_contract(self):
        result=analyze_alpha_signal(sample_candles())
        self.assertEqual(result["status"],"ok")
        self.assertIn(result["signal"],{"BUY","SELL","WAIT"})
        self.assertIn(result["direction"],{"bullish","bearish"})
        self.assertIn(result["regime"],{"flat","trending"})
        self.assertIn("filters",result)

    def test_short_history_is_explicit(self):
        result=analyze_alpha_signal(sample_candles(20))
        self.assertEqual(result["status"],"insufficient_history")

    def test_disabled_filters_and_vf(self):
        settings={"volatility_fingerprint":True,"vf_lookback":50,"stall_filter":False,"slope_filter":False,"volume_filter":False,"range_filter":False,"bps_filter":False,"breakout_override":False}
        result=analyze_alpha_signal(sample_candles(),settings)
        self.assertEqual(result["status"],"ok")
        self.assertIsNotNone(result["volatility_fingerprint"])

    def test_invalid_ohlc_rejected(self):
        rows=sample_candles()
        rows[-1]["high"]=1
        result=analyze_alpha_signal(rows)
        self.assertEqual(result["status"],"invalid_candle_data")

if __name__ == "__main__":
    unittest.main()
