import unittest

from server.phase4_validation import run_phase4_validation


class Phase4ValidationTests(unittest.TestCase):
    def test_preflight_blocks_missing_data_and_missing_cost_inputs(self):
        result = run_phase4_validation(
            {"4h": [], "1h": [], "15m": [], "5m": []},
            costs={},
            metadata={},
        )
        self.assertEqual(result["phase"], "PHASE_4")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["final_certification"], "NOT_CERTIFIED")
        self.assertIn("4H: required history is missing.", result["blockers"])
        self.assertTrue(any("provider" in item.lower() for item in result["blockers"]))
        self.assertTrue(any("max_spread_points" in item for item in result["blockers"]))

    def test_same_feed_user_attestation_is_required(self):
        result = run_phase4_validation(
            {"4h": [], "1h": [], "15m": []},
            costs={"point_size": 0.01, "spread_points": 10, "slippage_points": 2,
                   "commission_points_per_side": 0, "max_spread_points": 20},
            metadata={"symbol": "XAUUSD", "provider": "Example", "timezone": "UTC",
                      "same_feed_confirmed": False},
        )
        self.assertTrue(any("Same-feed confirmation" in item for item in result["blockers"]))

    def test_spread_above_maximum_is_blocked(self):
        result = run_phase4_validation(
            {"4h": [], "1h": [], "15m": []},
            costs={"point_size": 0.01, "spread_points": 25, "slippage_points": 2,
                   "commission_points_per_side": 0, "max_spread_points": 20},
            metadata={"symbol": "XAUUSD", "provider": "Example", "timezone": "UTC",
                      "same_feed_confirmed": True},
        )
        self.assertIn("Observed spread is above the configured maximum-spread cap.", result["blockers"])


if __name__ == "__main__":
    unittest.main()
