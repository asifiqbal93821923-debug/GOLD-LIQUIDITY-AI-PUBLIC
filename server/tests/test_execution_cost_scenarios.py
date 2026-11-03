import unittest
from scripts.execution_cost_scenarios import build_scenarios, run_cost_scenarios
from server.multitimeframe_backtest import _spread_is_acceptable

class ExecutionCostScenarioTests(unittest.TestCase):
    def test_three_scenarios_are_monotonic(self):
        s = build_scenarios(10, 2, 1, 0.01, 15)
        self.assertEqual(list(s), ["base", "conservative", "adverse"])
        self.assertLess(s["base"]["spread_points"], s["conservative"]["spread_points"])
        self.assertLess(s["conservative"]["spread_points"], s["adverse"]["spread_points"])
        self.assertEqual(s["base"]["point_size"], 0.01)

    def test_rejects_invalid_cost_inputs(self):
        with self.assertRaises(ValueError):
            build_scenarios(-1, 0, 0, 0.01, 10)
        with self.assertRaises(ValueError):
            build_scenarios(1, 0, 0, 0, 10)

    def test_spread_gate_fails_closed_until_positive_limit_exists(self):
        self.assertFalse(_spread_is_acceptable({"require_spread_limit": True,
                                                "max_spread_points": 0, "spread_points": 5}))
        self.assertFalse(_spread_is_acceptable({"require_spread_limit": True,
                                                "max_spread_points": 4, "spread_points": 5}))
        self.assertTrue(_spread_is_acceptable({"require_spread_limit": True,
                                               "max_spread_points": 5, "spread_points": 5}))
        self.assertTrue(_spread_is_acceptable({"spread_points": 50}))

    def test_non_finite_costs_are_rejected(self):
        with self.assertRaises(ValueError):
            build_scenarios(float("nan"), 0, 0, 0.01, 10)

    def test_missing_data_stays_partial_and_unverified(self):
        out = run_cost_scenarios({}, spread=10, slippage=2, commission=0,
                                 point_size=0.01, max_spread=0)
        self.assertEqual(out["status"], "partial")
        self.assertFalse(out["broker_costs_verified"])
        self.assertTrue(out["spread_gate"]["closed_until_defensible_limit"])

if __name__ == "__main__":
    unittest.main()
