import unittest
from server.unified_decision import analyze_unified_decision

def valid_payload():
    return {"data":{"fresh":True,"complete":True},
      "4h_bias":{"status":"ok","direction":"bullish","confirmed":True},
      "1h_bias":{"status":"ok","direction":"bullish","confirmed":True},
      "1h_structure":{"status":"ok","direction":"bullish","confirmed":True},
      "15m_setup":{"status":"ok","direction":"bullish","confirmed":True},
      "spread":{"acceptable":True},
      "trade_plan":{"valid":True,"entry":[2700,2702],"stop_loss":2694,"targets":[2710,2718,2725],"source_timeframe":"1h"}}

class UnifiedDecisionTests(unittest.TestCase):
    def test_1h_primary_buy_without_5m(self):
        x=analyze_unified_decision(valid_payload())
        self.assertEqual(x["decision"],"BUY")
        self.assertFalse(x["entry_refinement"]["used"])
        self.assertEqual(x["trade_plan"]["source_timeframe"],"1h")
    def test_5m_opposing_confirmed_trigger_vetoes(self):
        p=valid_payload(); p["5m_trigger"]={"status":"ok","direction":"bearish","confirmed":True}
        x=analyze_unified_decision(p)
        self.assertEqual(x["decision"],"WAIT")
        self.assertIn("FIVE_MINUTE_OPPOSING_TRIGGER",x["reason_codes"])
    def test_4h_neutral_does_not_override_1h(self):
        p=valid_payload(); p["4h_bias"]["direction"]="neutral"
        self.assertEqual(analyze_unified_decision(p)["decision"],"BUY")
    def test_4h_opposition_vetoes(self):
        p=valid_payload(); p["4h_bias"]["direction"]="bearish"
        x=analyze_unified_decision(p)
        self.assertEqual(x["decision"],"WAIT")
        self.assertIn("FOUR_HOUR_MACRO_CONFLICT",x["reason_codes"])
    def test_ambiguous_1h_structure_waits(self):
        p=valid_payload(); p["1h_structure"]["direction"]="ambiguous"
        x=analyze_unified_decision(p)
        self.assertEqual(x["decision"],"WAIT")
        self.assertIn("ONE_HOUR_STRUCTURE_AMBIGUOUS",x["reason_codes"])
    def test_15m_setup_must_align(self):
        p=valid_payload(); p["15m_setup"]["direction"]="bearish"
        x=analyze_unified_decision(p)
        self.assertEqual(x["decision"],"WAIT")
        self.assertIn("FIFTEEN_MINUTE_SETUP_CONFLICT",x["reason_codes"])
    def test_unconfirmed_1h_waits(self):
        p=valid_payload(); p["1h_bias"]["confirmed"]=False
        x=analyze_unified_decision(p)
        self.assertEqual(x["decision"],"WAIT")
        self.assertIn("ONE_HOUR_BAR_NOT_CONFIRMED",x["reason_codes"])
    def test_bad_risk_plan_waits(self):
        p=valid_payload(); p["trade_plan"]["stop_loss"]=2701
        self.assertEqual(analyze_unified_decision(p)["decision"],"WAIT")

if __name__=="__main__": unittest.main()
