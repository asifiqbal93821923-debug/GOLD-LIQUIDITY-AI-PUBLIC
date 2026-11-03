import unittest
from unittest.mock import patch

from scripts.research_cost_policy import with_fail_closed_spread_gate
from scripts.optimize_alpha_settings import optimize_parameters
from scripts.calibrate_trade_plan import calibrate
from scripts.rolling_walk_forward_validation import run_rolling_walk_forward


def mock_backtest_report():
    return {
        "status": "ok",
        "trade_count": 20,
        "win_rate_pct": 55.0,
        "net_pnl_price": 12.0,
        "average_R": 0.6,
        "profit_factor": 1.6,
        "max_drawdown_price": 3.0,
        "accepted_signals": 20,
        "signals_evaluated": 25,
        "skipped_signals": 5,
        "trades": [{"net_R": 0.5, "net_pnl_price": 1.0}] * 20,
    }


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

    def test_optimizer_passes_fail_closed_gate_into_every_replay(self):
        partitions = {name: {"4h": [], "1h": [], "15m": []}
                      for name in ("train", "validation", "test")}
        with patch("scripts.optimize_alpha_settings.split_chronologically",
                   return_value={"status": "ok", "partitions": partitions, "bar_counts": {}}), \
             patch("scripts.optimize_alpha_settings.run_gold_mtf_backtest",
                   side_effect=[mock_backtest_report(), mock_backtest_report(),
                                mock_backtest_report()]) as replay:
            out = optimize_parameters({}, {"max_spread_points": 4.5}, count=1)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(replay.call_count, 3)
        for call in replay.call_args_list:
            self.assertTrue(call.kwargs["costs"]["require_spread_limit"])
            self.assertEqual(call.kwargs["costs"]["max_spread_points"], 4.5)

    def test_trade_plan_calibration_passes_same_gate_into_every_replay(self):
        partitions = {name: {"4h": [], "1h": [], "15m": []}
                      for name in ("train", "validation", "test")}
        with patch("scripts.calibrate_trade_plan.split_chronologically",
                   return_value={"status": "ok", "partitions": partitions,
                                 "bar_counts": {}, "boundary_epoch": {}}), \
             patch("scripts.calibrate_trade_plan.CANDIDATES",
                   [{"atr_period": 14, "swing_lookback": 15,
                     "stop_atr_buffer": 0.1, "entry_atr_half_width": 0.1,
                     "target_rr": [1.0, 2.0, 3.0]}]), \
             patch("scripts.calibrate_trade_plan.run_gold_mtf_backtest",
                   side_effect=[mock_backtest_report(), mock_backtest_report(),
                                mock_backtest_report()]) as replay:
            out = calibrate({}, {"max_spread_points": 3.0})
        self.assertEqual(out["status"], "ok")
        self.assertEqual(replay.call_count, 3)
        for call in replay.call_args_list:
            self.assertTrue(call.kwargs["costs"]["require_spread_limit"])
            self.assertEqual(call.kwargs["costs"]["max_spread_points"], 3.0)

    def test_walk_forward_passes_same_gate_to_train_oos_and_holdout(self):
        start = 1_600_000_000 - (1_600_000_000 % 14_400)

        def bars(count, step):
            return [{"time": start + i * step, "open": 2300.0, "high": 2301.0,
                     "low": 2299.0, "close": 2300.2, "volume": 10.0}
                    for i in range(count)]

        frames = {"4h": bars(625, 14_400), "1h": bars(2500, 3600),
                  "15m": bars(10_000, 900)}
        with patch("scripts.rolling_walk_forward_validation.validate_candles",
                   side_effect=lambda rows: rows), \
             patch("scripts.rolling_walk_forward_validation.run_gold_mtf_backtest",
                   side_effect=[mock_backtest_report() for _ in range(9)]) as replay:
            out = run_rolling_walk_forward(
                frames, folds=4, train_fraction=0.12, test_fraction=0.10,
                holdout_fraction=0.10, mode="rolling",
                costs={"max_spread_points": 2.5},
            )
        self.assertEqual(out["status"], "ok")
        self.assertEqual(replay.call_count, 9)
        for call in replay.call_args_list:
            self.assertTrue(call.kwargs["costs"]["require_spread_limit"])
            self.assertEqual(call.kwargs["costs"]["max_spread_points"], 2.5)


if __name__ == "__main__":
    unittest.main()
