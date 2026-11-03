import os
import tempfile
from datetime import datetime, timezone
import unittest
import time
from pathlib import Path
from unittest.mock import patch
from server import main as api
from server.market_data import CandleStore

def sample(n=160,timeframe="1h"):
    seconds={"4h":14400,"1h":3600,"15m":900}[timeframe]
    latest=(int(time.time())//seconds)*seconds-seconds
    rows=[]; price=2300.0
    for i in range(n):
        drift=0.32 if (i//20)%2==0 else -0.25
        op=price; close=price+drift+((i%5)-2)*0.03
        rows.append({"time":latest-(n-1-i)*seconds,"symbol":"XAUUSD","open":op,
          "high":max(op,close)+0.22,"low":min(op,close)-0.20,"close":close,"volume":100+i%11})
        price=close
    return rows

class ServerTradeGateTests(unittest.TestCase):
    def payload(self, data_fresh=True, spread_acceptable=True):
        frames={tf:[api.Candle(**row) for row in sample(timeframe=tf)] for tf in ("4h","1h","15m")}
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
                store.upsert("XAUUSD",tf,sample(timeframe=tf),"mt5_bridge")
            store.upsert_quote("XAUUSD",2350.10,2350.20,0.01,
                int(datetime.now(timezone.utc).timestamp())-600,"mt5_bridge")
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MAX_SPREAD_POINTS":"20"}):
                out=api.gold_report_analysis(self.payload(False,False))
                self.assertIn("SPREAD_NOT_ACCEPTABLE",out["decision"]["reason_codes"])

    def test_future_tick_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            for tf in ("4h","1h","15m"):
                store.upsert("XAUUSD",tf,sample(timeframe=tf),"mt5_bridge")
            store.upsert_quote("XAUUSD",2350.10,2350.20,0.01,
                int(datetime.now(timezone.utc).timestamp())+600,"mt5_bridge")
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MAX_SPREAD_POINTS":"20"}):
                self.assertFalse(api.get_market_quote()["fresh"])
                out=api.gold_report_analysis(self.payload())
                self.assertIn("SPREAD_NOT_ACCEPTABLE",out["decision"]["reason_codes"])

    def test_recent_upload_of_stale_closed_bars_does_not_open_live_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            for tf in ("4h","1h","15m"):
                rows=sample(timeframe=tf)
                if tf=="1h":
                    # Age the entire uploaded series; shifting only the final
                    # row makes the penultimate row the newest stored candle.
                    for row in rows:
                        row["time"]-=7200
                store.upsert("XAUUSD",tf,rows,"mt5_bridge")
            with patch.object(api,"STORE",store):
                self.assertFalse(api._fresh_ingest("1h"))
                self.assertTrue(api._fresh_ingest("4h"))
                self.assertTrue(api._fresh_ingest("15m"))

    def test_bridge_rejects_unclosed_or_future_latest_candle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            now=int(time.time())
            payload=api.CandleImportRequest(timeframe="1h",candles=[
                api.Candle(time=now,open=2300,high=2301,low=2299,close=2300.5)
            ])
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MARKET_INGEST_TOKEN":"test-secret-token"}):
                with self.assertRaises(api.HTTPException) as raised:
                    api.mt5_candle_bridge(payload,"test-secret-token")
                self.assertEqual(raised.exception.status_code,422)

    def test_bridge_rejects_stale_latest_closed_candle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            now=int(time.time())
            payload=api.CandleImportRequest(timeframe="1h",candles=[
                api.Candle(time=now-3*3600,open=2300,high=2301,low=2299,close=2300.5)
            ])
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MARKET_INGEST_TOKEN":"test-secret-token"}):
                with self.assertRaises(api.HTTPException) as raised:
                    api.mt5_candle_bridge(payload,"test-secret-token")
                self.assertEqual(raised.exception.status_code,422)

    def test_recent_mt5_bars_and_quote_open_server_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CandleStore(str(Path(tmp)/"candles.db"))
            for tf in ("4h","1h","15m"):
                store.upsert("XAUUSD",tf,sample(timeframe=tf),"mt5_bridge")
            store.upsert_quote("XAUUSD",2350.10,2350.20,0.01,int(datetime.now(timezone.utc).timestamp()),"mt5_bridge")
            with patch.object(api,"STORE",store), patch.dict(os.environ,{"MAX_SPREAD_POINTS":"20"}):
                out=api.gold_report_analysis(self.payload(False,False))
                codes=out["decision"]["reason_codes"]
                self.assertNotIn("DATA_NOT_FRESH_OR_COMPLETE",codes)
                self.assertNotIn("SPREAD_NOT_ACCEPTABLE",codes)

if __name__=="__main__": unittest.main()
