import unittest
from scripts.execution_cost_scenarios import build_scenarios, run_cost_scenarios

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

    def test_missing_data_stays_partial_and_unverified(self):
        out = run_cost_scenarios({}, spread=10, slippage=2, commission=0,
                                 point_size=0.01, max_spread=0)
        self.assertEqual(out["status"], "partial")
        self.assertFalse(out["broker_costs_verified"])
        self.assertTrue(out["spread_gate"]["closed_until_defensible_limit"])

if __name__ == "__main__":
    unittest.main()
