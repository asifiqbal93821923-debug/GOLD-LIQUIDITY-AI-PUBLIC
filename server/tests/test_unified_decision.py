import unittest
from server.unified_decision import analyze_unified_decision

def valid_payload():
    return {
        "data": {"fresh": True, "complete": True},
        "4h_bias": {"status": "ok", "direction": "bullish", "confirmed": True},
        "1h_bias": {"status": "ok", "direction": "bullish", "confirmed": True},
        "15m_structure": {"status": "ok", "direction": "bullish", "confirmed": True},
        "5m_trigger": {"status": "ok", "direction": "bullish", "confirmed": True},
        "spread": {"acceptable": True},
        "trade_plan": {"valid": True, "entry": [2700, 2702], "stop_loss": 2694, "targets": [2710, 2718, 2725]},
    }

class UnifiedDecisionTests(unittest.TestCase):
    def test_aligned_inputs_allow_buy(self):
        result = analyze_unified_decision(valid_payload())
        self.assertEqual(result["decision"], "BUY")
        self.assertEqual(result["evidence_groups_passed"], 4)

    def test_missing_data_returns_wait(self):
        payload = valid_payload()
        payload["data"]["fresh"] = False
        result = analyze_unified_decision(payload)
        self.assertEqual(result["decision"], "WAIT")
        self.assertIn("DATA_NOT_FRESH_OR_COMPLETE", result["reason_codes"])

    def test_timeframe_conflict_returns_wait(self):
        payload = valid_payload()
        payload["5m_trigger"]["direction"] = "bearish"
        result = analyze_unified_decision(payload)
        self.assertEqual(result["decision"], "WAIT")
        self.assertIn("FIVE_MINUTE_TRIGGER_CONFLICT", result["reason_codes"])

    def test_unconfirmed_bar_returns_wait(self):
        payload = valid_payload()
        payload["15m_structure"]["confirmed"] = False
        result = analyze_unified_decision(payload)
        self.assertEqual(result["decision"], "WAIT")
        self.assertIn("15M_STRUCTURE_BAR_NOT_CONFIRMED", result["reason_codes"])

    def test_bad_stop_returns_wait(self):
        payload = valid_payload()
        payload["trade_plan"]["stop_loss"] = 2701
        result = analyze_unified_decision(payload)
        self.assertEqual(result["decision"], "WAIT")
        self.assertIn("LONG_RISK_LEVELS_INVALID", result["reason_codes"])

    def test_sell_levels(self):
        payload = valid_payload()
        for key in ("4h_bias", "1h_bias", "15m_structure", "5m_trigger"):
            payload[key]["direction"] = "bearish"
        payload["trade_plan"] = {"valid": True, "entry": [2700, 2702], "stop_loss": 2708, "targets": [2692, 2685, 2678]}
        result = analyze_unified_decision(payload)
        self.assertEqual(result["decision"], "SELL")

    def test_opposing_ai_channel_context_blocks_trade(self):
        payload = valid_payload()
        payload["ai_channel_context"] = {
            "4h": {"status": "ok", "channel_state": "bearish"},
            "1h": {"status": "ok", "channel_state": "bullish"},
        }
        result = analyze_unified_decision(payload)
        self.assertEqual(result["decision"], "WAIT")
        self.assertIn("FOUR_H_CHANNEL_CONTEXT_CONFLICT", result["reason_codes"])

    def test_ambiguous_liquidity_sweep_blocks_trade(self):
        payload = valid_payload()
        payload["liquidity_context"] = {
            "5m": {"liquidity_sweep": {"ambiguous_both_sides": True}}
        }
        result = analyze_unified_decision(payload)
        self.assertEqual(result["decision"], "WAIT")
        self.assertIn("5M_AMBIGUOUS_LIQUIDITY_SWEEP", result["reason_codes"])

if __name__ == "__main__":
    unittest.main()
