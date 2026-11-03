import unittest
from server.backtest import simulate_trade_events, run_alpha_1h_backtest

def bars(rows):
    return [{"time":i,"open":x[0],"high":x[1],"low":x[2],"close":x[3],"volume":100}
            for i,x in enumerate(rows)]

class BacktestSimulatorTests(unittest.TestCase):
    def test_same_bar_stop_and_target_uses_stop_first(self):
        data=bars([(100,101,99,100),(100,106,94,102),(101,102,100,101)])
        event={"index":0,"signal":"BUY","plan":{"valid":True,"entry_zone":[100,100],
          "stop_loss":95,"targets":[105,110,115]}}
        out=simulate_trade_events(data,[event])
        self.assertEqual(out["trade_count"],1)
        self.assertEqual(out["trades"][0]["exit_reason"],"STOP_FIRST")
        self.assertEqual(out["trades"][0]["net_pnl_price"],-5.0)
        self.assertEqual(out["trades"][0]["targets_hit"],[])

    def test_next_bar_outside_entry_zone_is_skipped(self):
        data=bars([(100,101,99,100),(102,103,101,102)])
        event={"index":0,"signal":"BUY","plan":{"valid":True,"entry_zone":[99.9,100.1],
          "stop_loss":95,"targets":[105,110,115]}}
        out=simulate_trade_events(data,[event])
        self.assertEqual(out["trade_count"],0)
        self.assertEqual(out["skipped"][0]["reason"],"NEXT_OPEN_OUTSIDE_ENTRY_ZONE")

    def test_spread_and_slippage_are_included_in_execution(self):
        data=bars([(100,101,99,100),(100,106,99,105),(105,106,104,105)])
        event={"index":0,"signal":"BUY","plan":{"valid":True,"entry_zone":[100,100],
          "stop_loss":95,"targets":[105,110,115]}}
        out=simulate_trade_events(data,[event],{"point_size":0.01,"spread_points":10,"slippage_points":2})
        self.assertGreater(out["cost_assumptions"]["spread_points"],0)
        self.assertLess(out["trades"][0]["entry"],100.2)

    def test_alpha_backtest_requires_history(self):
        out=run_alpha_1h_backtest(bars([(10,11,9,10)]*30))
        self.assertEqual(out["status"],"insufficient_history")

if __name__=="__main__": unittest.main()
