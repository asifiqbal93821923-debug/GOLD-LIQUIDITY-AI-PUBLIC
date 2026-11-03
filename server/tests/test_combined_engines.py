import unittest
from server.smc_structure import analyze_smc_structure
from server.wsb_setup import analyze_wsb
from server.ai_channels import analyze_ai_channels
from server.gold_report import build_gold_report


def sample(n=160):
    rows=[]; price=2300.0
    for i in range(n):
        drift=0.32 if (i//20)%2==0 else -0.25
        op=price; close=price+drift+((i%5)-2)*0.03
        high=max(op,close)+0.22+(i%3)*0.02
        low=min(op,close)-0.20-(i%4)*0.015
        rows.append({"time":i,"symbol":"XAUUSD","open":op,"high":high,"low":low,"close":close,"volume":100+(i%11)})
        price=close
    return rows


class SMCAdapterTests(unittest.TestCase):
    def test_structure_contract(self):
        out=analyze_smc_structure(sample())
        self.assertEqual(out["status"],"ok")
        self.assertIn(out["direction"],{"bullish","bearish","neutral","ambiguous"})
        self.assertIn("active_fvgs",out)
        self.assertIn("order_block_candidates",out)

    def test_short_history(self):
        self.assertEqual(analyze_smc_structure(sample(10))["status"],"insufficient_history")


class WSBTests(unittest.TestCase):
    def test_wsb_contract(self):
        out=analyze_wsb(sample())
        self.assertEqual(out["status"],"ok")
        self.assertIn(out["breakout"]["direction"],{"bullish","bearish","none","ambiguous"})
        self.assertIn("CANDLE_CLOSE_LOCATION_VOLUME_SPLIT_NOT_TRUE_BID_ASK_DELTA",out["estimated_pressure"]["semantics"])

    def test_invalid_breakout_basis(self):
        self.assertEqual(analyze_wsb(sample(),{"breakout_basis":"magic"})["status"],"invalid_settings")


class AIChannelsTests(unittest.TestCase):
    def test_corrected_and_parity_modes(self):
        a=analyze_ai_channels(sample(),{"variant":"corrected"})
        b=analyze_ai_channels(sample(),{"variant":"pine_parity"})
        self.assertEqual(a["status"],"ok")
        self.assertEqual(b["status"],"ok")
        self.assertEqual(a["cluster_count"],5)

    def test_invalid_cluster_count(self):
        self.assertEqual(analyze_ai_channels(sample(),{"clusters":12})["status"],"invalid_settings")


class GoldReportTests(unittest.TestCase):
    def test_missing_timeframe_never_fabricates(self):
        out=build_gold_report({"1h":sample()})
        self.assertEqual(out["status"],"partial")
        self.assertEqual(out["timeframes"]["4h"]["status"],"not_available")
        self.assertEqual(out["decision"]["decision"],"WAIT")

    def test_complete_but_unasserted_data_stays_wait(self):
        data={tf:sample() for tf in ("4h","1h","15m","5m")}
        out=build_gold_report(data,data_fresh=False,spread_acceptable=False)
        self.assertEqual(out["status"],"ok")
        self.assertEqual(out["decision"]["decision"],"WAIT")
        self.assertIn("DATA_NOT_FRESH_OR_COMPLETE",out["decision"]["reason_codes"])
        self.assertIn("SPREAD_NOT_ACCEPTABLE",out["decision"]["reason_codes"])


if __name__=="__main__":
    unittest.main()
