import tempfile
import unittest
from pathlib import Path

from server.phase5_paper import (
    PaperForwardStore,
    advance_open_trade,
    journal_view_from_paper_trades,
    normalize_paper_config,
    open_from_pending,
    performance_summary,
)


class Phase5ConfigTests(unittest.TestCase):
    def test_defaults_are_paused_and_costs_are_zero(self):
        state = normalize_paper_config({})
        self.assertFalse(state["enabled"])
        self.assertIsNone(state["max_spread_points"])
        self.assertEqual(state["slippage_points"], 0.0)
        self.assertEqual(state["commission_points_per_side"], 0.0)

    def test_rejects_missing_or_non_positive_spread_cap_for_active_config(self):
        state = normalize_paper_config({"enabled": True})
        self.assertIsNone(state["max_spread_points"])
        self.assertFalse(state["enabled"] is False)
        with self.assertRaises(ValueError):
            normalize_paper_config({"max_spread_points": 0})
        with self.assertRaises(ValueError):
            normalize_paper_config({"slippage_points": -1})
        with self.assertRaises(ValueError):
            normalize_paper_config({"commission_points_per_side": float("inf")})

    def test_preserves_runtime_state_when_changing_configuration(self):
        current = normalize_paper_config({"enabled": False, "max_spread_points": 30})
        current["pending_signal"] = {"side": "BUY"}
        current["last_processed_candle_time"] = 123
        updated = normalize_paper_config({"slippage_points": 2}, current)
        self.assertEqual(updated["max_spread_points"], 30)
        self.assertEqual(updated["pending_signal"], {"side": "BUY"})
        self.assertEqual(updated["last_processed_candle_time"], 123)


class Phase5StoreTests(unittest.TestCase):
    def test_persistent_state_events_and_duplicate_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PaperForwardStore(str(Path(directory) / "paper.sqlite3"))
            state = store.get_state()
            state["enabled"] = True
            store.save_state(state)
            self.assertTrue(store.get_state()["enabled"])
            self.assertTrue(store.claim_event(1700000000, {"source": "test"}))
            self.assertFalse(store.claim_event(1700000000, {"source": "duplicate"}))
            store.finish_event(1700000000, "WAIT", "PROCESSED", "", {"paper_only": True})
            events = store.list_events(10)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["status"], "PROCESSED")
            self.assertTrue(events[0]["payload"]["paper_only"])


class Phase5ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.pending = {
            "side": "BUY",
            "signal_time": 1700000000,
            "trade_plan": {
                "valid": True,
                "entry": [1999.0, 2001.0],
                "stop_loss": 1998.0,
                "targets": [2002.0, 2003.0, 2004.0],
            },
            "position_size": {"estimated_lots": 0.1},
        }

    def test_enters_only_on_next_bar_open_inside_entry_zone(self):
        trade, status = open_from_pending(
            self.pending,
            {"time": 1700003600, "open": 2000.0, "high": 2001.0, "low": 1999.0, "close": 2000.5},
            spread_points=10, point_size=0.01, slippage_points=1,
            commission_points_per_side=0.0,
        )
        self.assertEqual(status, "ENTRY_OPENED")
        self.assertEqual(trade["status"], "OPEN")
        self.assertEqual(trade["entry_price"], 2000.06)
        self.assertEqual(trade["lots"], 0.1)

    def test_does_not_chase_when_next_open_is_outside_zone(self):
        trade, status = open_from_pending(
            self.pending,
            {"time": 1700003600, "open": 2002.0, "high": 2003.0, "low": 2001.0, "close": 2002.5},
            spread_points=10, point_size=0.01, slippage_points=1,
            commission_points_per_side=0.0,
        )
        self.assertIsNone(trade)
        self.assertEqual(status, "ENTRY_ZONE_MISSED_NO_CHASE")

    def test_stop_first_when_stop_and_tp1_touch_same_bar(self):
        trade = {
            "id": "paper-test", "side": "BUY", "status": "OPEN",
            "entry_reference_price": 2000.0, "entry_price": 2000.06,
            "stop_loss": 1998.0, "tp1": 2002.0, "risk_unit": 2.0,
        }
        closed = advance_open_trade(
            trade,
            {"time": 1700003600, "open": 2000.0, "high": 2003.0, "low": 1997.0, "close": 2001.0},
            spread_points=10, point_size=0.01, slippage_points=1,
            commission_points_per_side=0,
        )
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(closed["exit_reason"], "STOP_FIRST")
        self.assertLess(closed["net_pnl_price"], 0)

    def test_costs_are_included_in_net_pnl(self):
        trade = {
            "id": "paper-test", "side": "BUY", "status": "OPEN",
            "entry_reference_price": 2000.0, "entry_price": 2000.06,
            "stop_loss": 1998.0, "tp1": 2002.0, "risk_unit": 2.0,
        }
        closed = advance_open_trade(
            trade,
            {"time": 1700003600, "open": 2000.0, "high": 2003.0, "low": 1999.0, "close": 2002.5},
            spread_points=10, point_size=0.01, slippage_points=1,
            commission_points_per_side=1,
        )
        self.assertEqual(closed["exit_reason"], "TP1")
        self.assertLess(closed["net_pnl_price"], closed["gross_pnl_price"])
        self.assertAlmostEqual(closed["pnl_r"], 0.89, places=2)

    def test_performance_metrics_and_risk_journal_adapter(self):
        trades = [
            {"id": "a", "side": "BUY", "status": "CLOSED", "entry_time": 100, "exit_time": 200,
             "net_pnl_price": 2.0, "pnl_r": 1.0, "lots": 0.1},
            {"id": "b", "side": "SELL", "status": "CLOSED", "entry_time": 300, "exit_time": 400,
             "net_pnl_price": -1.0, "pnl_r": -0.5, "lots": 0.1},
        ]
        summary = performance_summary(trades, 8, None)
        self.assertEqual(summary["trades_closed"], 2)
        self.assertEqual(summary["win_rate_pct"], 50.0)
        self.assertEqual(summary["profit_factor_R"], 2.0)
        self.assertEqual(summary["processed_events"], 8)
        journal = journal_view_from_paper_trades(trades, 100)
        self.assertAlmostEqual(journal[0]["pnl_money"], 20.0)


if __name__ == "__main__":
    unittest.main()
