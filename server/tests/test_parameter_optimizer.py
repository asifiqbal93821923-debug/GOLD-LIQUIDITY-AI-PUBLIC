import unittest

from scripts.optimize_alpha_settings import (
    parameter_candidates,
    robust_score,
    split_chronologically,
)


class ParameterOptimizerTests(unittest.TestCase):
    def test_candidate_generation_is_reproducible_and_includes_defaults(self):
        a = parameter_candidates(100, seed=7)
        b = parameter_candidates(100, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 100)
        self.assertEqual(a[0]["atr_period"], 14)
        self.assertEqual(a[0]["band_multiplier"], 3.0)

    def test_candidate_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            parameter_candidates(501)

    def test_robust_score_rejects_too_few_trades_and_negative_split(self):
        train = {"trade_count": 20, "net_pnl_price": 10, "average_R": 0.5,
                 "profit_factor": 1.5, "win_rate_pct": 55, "max_drawdown_price": 3}
        validation = dict(train, trade_count=4)
        self.assertIsNone(robust_score(train, validation, min_trades=10))
        validation = dict(train, net_pnl_price=-1)
        self.assertIsNone(robust_score(train, validation, min_trades=10))

    def test_split_blocks_short_history(self):
        frames = {
            "4h": [{"time": i * 14400, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1} for i in range(10)],
            "1h": [{"time": i * 3600, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1} for i in range(40)],
            "15m": [{"time": i * 900, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1} for i in range(160)],
        }
        result = split_chronologically(frames)
        self.assertEqual(result["status"], "insufficient_history")
        self.assertEqual(result["reason"], "EACH_TRAIN_VALIDATION_TEST_WINDOW_REQUIRES_CLOSED_BARS")


if __name__ == "__main__":
    unittest.main()
