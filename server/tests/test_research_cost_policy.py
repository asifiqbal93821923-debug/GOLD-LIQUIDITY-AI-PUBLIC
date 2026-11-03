import unittest

from scripts.research_cost_policy import with_fail_closed_spread_gate


class ResearchCostPolicyTests(unittest.TestCase):
    def test_missing_or_zero_cap_fails_closed(self):
        for costs in (None, {}, {"spread_points": 4}):
            with self.subTest(costs=costs):
                result = with_fail_closed_spread_gate(costs)
                self.assertTrue(result["require_spread_limit"])
                self.assertEqual(result["max_spread_points"], 0.0)

    def test_positive_cap_is_preserved(self):
        result = with_fail_closed_spread_gate({
            "spread_points": 3.0, "slippage_points": 1.0,
            "max_spread_points": 5.0, "point_size": 0.01,
        })
        self.assertTrue(result["require_spread_limit"])
        self.assertEqual(result["max_spread_points"], 5.0)
        self.assertEqual(result["spread_points"], 3.0)

    def test_rejects_invalid_cap(self):
        for value in (-1, float("nan"), float("inf"), "bad"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    with_fail_closed_spread_gate({"max_spread_points": value})


if __name__ == "__main__":
    unittest.main()
