import unittest
from scripts.rolling_walk_forward_validation import run_rolling_walk_forward

def bars(n, step):
    return [{"time": 1600000000 + i * step, "open": 2300, "high": 2301,
             "low": 2299, "close": 2300.2, "volume": 10} for i in range(n)]

class RollingWalkForwardTests(unittest.TestCase):
    def test_refuses_insufficient_history(self):
        out = run_rolling_walk_forward({"4h": bars(100,14400), "1h": bars(100,3600),
                                        "15m": bars(100,900)}, folds=3)
        self.assertEqual(out["status"], "insufficient_history")

    def test_rejects_invalid_fold_configuration(self):
        with self.assertRaises(ValueError):
            run_rolling_walk_forward({}, folds=1)

if __name__ == "__main__":
    unittest.main()
