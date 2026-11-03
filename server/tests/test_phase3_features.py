import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from server.phase3_storage import Phase3Store
from server.risk_management import DEFAULT_RISK_SETTINGS, evaluate_risk, normalize_risk_settings

def buy_decision():
    return {"decision":"BUY","trade_plan":{"entry":[2000.0,2002.0],"stop_loss":1990.0,"targets":[2020.0,2040.0,2060.0]}}
def safe_quote():
    return {"acceptable":True,"spread_points":12.0}

class RiskManagementTests(unittest.TestCase):
    def test_settings_validation(self):
        settings=normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"account_balance":10000,"contract_size":100})
        self.assertEqual(settings["account_balance"],10000.0)
        with self.assertRaises(ValueError): normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"risk_percent":99})
        with self.assertRaises(ValueError): normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"contract_size":float("nan")})
    def test_contract_aware_position_size(self):
        settings=normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"account_balance":10000,"contract_size":100,"cooldown_minutes":0})
        result=evaluate_risk(buy_decision(),safe_quote(),settings,[])
        self.assertTrue(result["approved_for_alert"])
        self.assertEqual(result["position_size"]["risk_cash"],50.0)
        self.assertEqual(result["position_size"]["estimated_lots"],0.0455)
    def test_spread_and_reward_risk_gates(self):
        settings=normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"max_spread_points":10})
        result=evaluate_risk(buy_decision(),safe_quote(),settings,[])
        self.assertIn("USER_MAX_SPREAD_EXCEEDED",result["blocking_reasons"])
        poor=buy_decision();poor["trade_plan"]["targets"][0]=2008
        result=evaluate_risk(poor,safe_quote(),settings,[])
        self.assertIn("MINIMUM_REWARD_RISK_NOT_MET",result["blocking_reasons"])
    def test_daily_trades_open_limit_and_cooldown(self):
        now=datetime(2026,11,3,12,0,tzinfo=timezone.utc)
        settings=normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"max_trades_per_day":1,"max_open_trades":1,"cooldown_minutes":60})
        journal=[{"status":"OPEN","opened_at":(now-timedelta(minutes=10)).isoformat(),"created_at":(now-timedelta(minutes=10)).isoformat()}]
        result=evaluate_risk(buy_decision(),safe_quote(),settings,journal,now)
        self.assertFalse(result["approved_for_alert"])
        self.assertIn("MAX_TRADES_PER_DAY_REACHED",result["blocking_reasons"])
        self.assertIn("MAX_OPEN_TRADES_REACHED",result["blocking_reasons"])
        self.assertIn("TRADE_COOLDOWN_ACTIVE",result["blocking_reasons"])
    def test_daily_loss_gate(self):
        now=datetime(2026,11,3,12,0,tzinfo=timezone.utc)
        settings=normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"account_balance":1000,"cooldown_minutes":0,"max_trades_per_day":10})
        journal=[{"status":"CLOSED","opened_at":(now-timedelta(hours=2)).isoformat(),"closed_at":(now-timedelta(hours=1)).isoformat(),"pnl_money":-25.0}]
        result=evaluate_risk(buy_decision(),safe_quote(),settings,journal,now)
        self.assertIn("MAX_DAILY_LOSS_REACHED",result["blocking_reasons"])

class Phase3StorageTests(unittest.TestCase):
    def test_persistent_settings_alerts_and_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Phase3Store(str(Path(folder)/"phase3.sqlite"))
            settings=normalize_risk_settings({**DEFAULT_RISK_SETTINGS,"account_balance":5000})
            store.set_risk_settings(settings)
            self.assertEqual(store.get_risk_settings(DEFAULT_RISK_SETTINGS)["account_balance"],5000.0)
            event,created=store.create_signal_event({"signal_key":"1h-100-buy","direction":"BUY","candle_time":100,"reason_codes":["CONFIRMED"]})
            self.assertTrue(created)
            duplicate,created_again=store.create_signal_event({"signal_key":"1h-100-buy","direction":"BUY","candle_time":100,"reason_codes":["CONFIRMED"]})
            self.assertFalse(created_again);self.assertEqual(event["id"],duplicate["id"])
            trade=store.create_journal_entry({"direction":"BUY","entry_price":2001,"stop_loss":1990,"target_price":2020,"lots":0.01,"notes":"test"})
            self.assertEqual(len(store.list_journal_entries()),1)
            closed=store.close_journal_entry(trade["id"],2010,9.0)
            self.assertEqual(closed["status"],"CLOSED")
            self.assertIsNone(store.close_journal_entry(trade["id"],2011,10.0))
            self.assertEqual(len(store.list_signal_events()),1)

if __name__=="__main__": unittest.main()
