import math
import unittest
from server.multitimeframe_backtest import _closed_prefix, run_gold_mtf_backtest

BASE=1700000000

def make_rows(count,step,phase=0):
    rows=[]
    for i in range(count):
        center=2300+0.0004*i*step+12*math.sin((i*step+phase)/18000)
        op=center-0.25*math.sin(i+phase)
        close=center+0.35*math.cos(i*0.7+phase)
        rows.append({"time":BASE+i*step,"open":op,"high":max(op,close)+0.8,
                     "low":min(op,close)-0.8,"close":close,"volume":100+(i%17)})
    return rows

class MultiTimeframeBacktestTests(unittest.TestCase):
    def test_closed_prefix_never_uses_forming_or_future_bars(self):
        rows=make_rows(5,900)
        cutoff=BASE+3600
        prefix=_closed_prefix(rows,"15m",cutoff)
        self.assertEqual(len(prefix),4)
        self.assertLessEqual(prefix[-1]["time"]+900,cutoff)

    def test_requires_4h_1h_and_15m_history(self):
        result=run_gold_mtf_backtest({"4h":make_rows(49,14400),
          "1h":make_rows(100,3600),"15m":make_rows(100,900)})
        self.assertEqual(result["status"],"insufficient_history")
        self.assertEqual(result["timeframe"],"4h")

    def test_replay_runs_without_optional_5m(self):
        frames={"4h":make_rows(80,14400),"1h":make_rows(320,3600),
                "15m":make_rows(1280,900)}
        result=run_gold_mtf_backtest(frames,costs={"point_size":0.01,"spread_points":20,"slippage_points":3})
        self.assertEqual(result["status"],"ok")
        self.assertEqual(result["timeframe"],"1h_primary")
        self.assertEqual(result["timeframe_policy"]["5m"],"optional latest fully closed WSB refinement")
        self.assertIn("scope_warning",result)

if __name__=="__main__": unittest.main()
