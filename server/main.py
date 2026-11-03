from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import hmac
from pydantic import BaseModel, Field
from typing import Literal
import os

try:
    from .alpha_signal import analyze_alpha_signal
    from .unified_decision import analyze_unified_decision
    from .institutional_footprint import analyze_institutional_footprint
    from .gold_report import build_gold_report
    from .market_data import CandleStore, validate_candles
except ImportError:
    from alpha_signal import analyze_alpha_signal
    from unified_decision import analyze_unified_decision
    from institutional_footprint import analyze_institutional_footprint
    from gold_report import build_gold_report
    from market_data import CandleStore, validate_candles

app = FastAPI(title="Project Indicator App API", version="0.4.0")
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

STORE = CandleStore(os.getenv("CANDLE_DB_PATH", "data/market_candles.sqlite3"))
TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1D"}

class Candle(BaseModel):
    time: str | int | float
    symbol: str = "XAUUSD"
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

class CandleImportRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str
    source: str = "user_import"
    candles: list[Candle] = Field(min_length=1, max_length=100000)

class AlphaAnalysisRequest(BaseModel):
    candles: list[Candle] = Field(min_length=1, max_length=5000)
    settings: dict = Field(default_factory=dict)

class FootprintAnalysisRequest(BaseModel):
    candles: list[Candle] = Field(min_length=30, max_length=5000)
    settings: dict = Field(default_factory=dict)

class GoldReportRequest(BaseModel):
    timeframes: dict[str, list[Candle]]
    data_fresh: bool = False
    spread_acceptable: bool = False

@app.get("/api/health")
def health():
    return {"status":"ok","app":"PROJECT INDICATOR APP","version":"0.4.0"}

@app.get("/api/config/status")
def config_status():
    provider=os.getenv("MARKET_DATA_PROVIDER","not_configured")
    latest=STORE.latest_ingest("XAUUSD")
    live=False
    if latest and latest.get("source")=="mt5_bridge":
        try:
            updated=datetime.fromisoformat(latest["updated_at"])
            live=(datetime.now(timezone.utc)-updated).total_seconds()<=180
        except (TypeError,ValueError):
            live=False
    return {"market":"XAUUSD","provider":provider,
      "credentials_present":bool(os.getenv("MARKET_DATA_API_KEY")),
      "bridge_token_configured":bool(os.getenv("MARKET_INGEST_TOKEN")),
      "live_data":live,"last_ingest":latest,"historical_store":"sqlite",
      "message":"MT5 bridge is sending recent candles." if live else "Historical imports are available; live MT5 bridge is not currently sending fresh candles.",
      "checked_at":datetime.now(timezone.utc).isoformat()}

@app.get("/api/market/candles")
def get_candles(timeframe: str="1h", limit: int=1000, symbol: str="XAUUSD"):
    if timeframe not in TIMEFRAMES: raise HTTPException(400,"Unsupported timeframe")
    if not 1<=limit<=100000: raise HTTPException(400,"limit must be between 1 and 100000")
    rows=STORE.read(symbol.upper(),timeframe,limit)
    return {"status":"ok" if rows else "not_available","symbol":symbol.upper(),
      "timeframe":timeframe,"count":len(rows),"data":rows,
      "data_kind":"historical_import","live":False,
      "message":"Stored historical candles; not a live price feed." if rows else "No candles imported for this symbol/timeframe."}

@app.post("/api/market/candles/import")
def import_candles(payload: CandleImportRequest):
    if payload.timeframe not in TIMEFRAMES: raise HTTPException(400,"Unsupported timeframe")
    if payload.symbol.upper()!="XAUUSD": raise HTTPException(400,"Only XAUUSD is enabled in this build")
    rows=[c.model_dump() for c in payload.candles]
    try: normalized=validate_candles(rows)
    except ValueError as exc: raise HTTPException(422,str(exc))
    count=STORE.upsert(payload.symbol.upper(),payload.timeframe,normalized,payload.source[:80])
    return {"status":"ok","symbol":payload.symbol.upper(),"timeframe":payload.timeframe,
      "received":len(rows),"stored":count,"source":payload.source[:80],
      "data_kind":"historical_import","live":False}


@app.post("/api/market/candles/bridge")
def mt5_candle_bridge(payload: CandleImportRequest, x_bridge_token: str | None = Header(default=None, alias="X-Bridge-Token")):
    """Authenticated MT5 Expert Advisor ingestion endpoint; closed candles only."""
    expected=os.getenv("MARKET_INGEST_TOKEN")
    if not expected:
        raise HTTPException(503,"Server MT5 bridge token is not configured.")
    if not x_bridge_token or not hmac.compare_digest(x_bridge_token,expected):
        raise HTTPException(401,"Invalid bridge token.")
    if payload.timeframe not in TIMEFRAMES:
        raise HTTPException(400,"Unsupported timeframe")
    if payload.symbol.upper()!="XAUUSD":
        raise HTTPException(400,"Only XAUUSD is enabled in this build")
    rows=[x.model_dump() for x in payload.candles]
    try: normalized=validate_candles(rows)
    except ValueError as exc: raise HTTPException(422,str(exc))
    count=STORE.upsert("XAUUSD",payload.timeframe,normalized,"mt5_bridge")
    return {"status":"ok","source":"mt5_bridge","timeframe":payload.timeframe,
      "received":len(rows),"stored":count,"live":True,
      "note":"EA should resend closed bars on its timer; freshness is based on server receive time."}

@app.post("/api/analysis/alpha-signal")
def alpha_signal_analysis(payload: AlphaAnalysisRequest):
    return analyze_alpha_signal([x.model_dump() for x in payload.candles],payload.settings)

@app.post("/api/analysis/unified-decision")
def unified_decision(payload: dict):
    return analyze_unified_decision(payload)

@app.post("/api/analysis/institutional-footprint")
def institutional_footprint_analysis(payload: FootprintAnalysisRequest):
    return analyze_institutional_footprint([x.model_dump() for x in payload.candles],payload.settings)

@app.post("/api/analysis/gold-report")
def gold_report_analysis(payload: GoldReportRequest):
    timeframes={tf:[x.model_dump() for x in rows] for tf,rows in payload.timeframes.items()
      if tf in {"4h","1h","15m","5m"}}
    return build_gold_report(timeframes,data_fresh=payload.data_fresh,
      spread_acceptable=payload.spread_acceptable)
