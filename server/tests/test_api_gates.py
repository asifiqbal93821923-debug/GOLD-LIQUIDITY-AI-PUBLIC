import os
import tempfile
from datetime import datetime, timezone
import unittest
from pathlib import Path
from unittest.mock import patch
from server import main as api
from server.market_data import CandleStore

def sample(n=160):
    rows=[]; price=2300.0
    for i in range(n):
        drift=0.32 if (i//20)%2==0 else -0.25
        op=price; close=price+drift+((i%5)-2)*0.03
        rows.append({"time":1760000000+i*3600,"symbol":"XAUUSD","open":op,
          "high":max(op,close)+0.22,"low":min(op,close)-0.20,"close":close,"volume":100+i%11})
        price=close
    return rows

class ServerTradeGateTests(unittest.TestCase):
    def payload(self, data_fresh=True, spread_acceptable=True):
        frames={tf:[api.Candle(**row) for row in sample()] for tf in ("4h","1h","15m")}
        return api.GoldReportRequest(timeframes=frames,data_fresh=data_fresh,spread_acceptable=spread_acceptable)

    def test_client_cannot_claim_freshness_or_spread_without_server_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MAX_SPREAD_POINTS":"50"}):
                out=api.gold_report_analysis(self.payload(True,True))
                codes=out["decision"]["reason_codes"]
                self.assertIn("DATA_NOT_FRESH_OR_COMPLETE",codes)
                self.assertIn("SPREAD_NOT_ACCEPTABLE",codes)

    def test_stale_broker_tick_keeps_spread_gate_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            for tf in ("4h","1h","15m"):
                store.upsert("XAUUSD",tf,sample(),"mt5_bridge")
            store.upsert_quote("XAUUSD",2350.10,2350.20,0.01,
                int(datetime.now(timezone.utc).timestamp())-600,"mt5_bridge")
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MAX_SPREAD_POINTS":"20"}):
                out=api.gold_report_analysis(self.payload(False,False))
                self.assertIn("SPREAD_NOT_ACCEPTABLE",out["decision"]["reason_codes"])

    def test_future_tick_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            for tf in ("4h","1h","15m"):
                store.upsert("XAUUSD",tf,sample(),"mt5_bridge")
            store.upsert_quote("XAUUSD",2350.10,2350.20,0.01,
                int(datetime.now(timezone.utc).timestamp())+600,"mt5_bridge")
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MAX_SPREAD_POINTS":"20"}):
                self.assertFalse(api.get_market_quote()["fresh"])
                out=api.gold_report_analysis(self.payload())
                self.assertIn("SPREAD_NOT_ACCEPTABLE",out["decision"]["reason_codes"])

    def test_recent_mt5_bars_and_quote_open_server_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            for tf in ("4h","1h","15m"):
                store.upsert("XAUUSD",tf,sample(),"mt5_bridge")
            store.upsert_quote("XAUUSD",2350.10,2350.20,0.01,int(datetime.now(timezone.utc).timestamp()),"mt5_bridge")
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MAX_SPREAD_POINTS":"20"}):
                out=api.gold_report_analysis(self.payload(False,False))
                codes=out["decision"]["reason_codes"]
                self.assertNotIn("DATA_NOT_FRESH_OR_COMPLETE",codes)
                self.assertNotIn("SPREAD_NOT_ACCEPTABLE",codes)

if __name__=="__main__": unittest.main()
