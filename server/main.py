from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os

app = FastAPI(title="Project Indicator App API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "PROJECT INDICATOR APP", "version": "0.3.0"}

@app.get("/api/config/status")
def config_status():
    # Never expose secret values to the browser.
    return {
        "market": "XAUUSD",
        "provider": os.getenv("MARKET_DATA_PROVIDER", "not_configured"),
        "credentials_present": bool(os.getenv("MARKET_DATA_API_KEY")),
        "live_data": False,
        "message": "A verified live market-data provider has not been configured.",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/market/candles")
def candles(timeframe: str = "15m", limit: int = 300):
    allowed = {"1m", "5m", "15m", "30m", "1h", "4h", "1D"}
    if timeframe not in allowed:
        return {"status": "error", "message": "Unsupported timeframe", "data": []}
    return {
        "status": "not_configured",
        "symbol": "XAUUSD",
        "timeframe": timeframe,
        "data": [],
        "message": "No live or historical feed configured. No synthetic candles are returned.",
    }

from pydantic import BaseModel, Field
from alpha_signal import analyze_alpha_signal
from unified_decision import analyze_unified_decision
from institutional_footprint import analyze_institutional_footprint
from gold_report import build_gold_report

class Candle(BaseModel):
    time: str | int | float | None = None
    symbol: str = "XAUUSD"
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

class AlphaAnalysisRequest(BaseModel):
    candles: list[Candle] = Field(min_length=1, max_length=5000)
    settings: dict = Field(default_factory=dict)

@app.post("/api/analysis/alpha-signal")
def alpha_signal_analysis(payload: AlphaAnalysisRequest):
    candles = [item.model_dump() for item in payload.candles]
    return analyze_alpha_signal(candles, payload.settings)

@app.post("/api/analysis/unified-decision")
def unified_decision(payload: dict):
    """Conservative confluence gate for precomputed, confirmed engine outputs."""
    return analyze_unified_decision(payload)


class FootprintAnalysisRequest(BaseModel):
    candles: list[Candle] = Field(min_length=30, max_length=5000)
    settings: dict = Field(default_factory=dict)

class GoldReportRequest(BaseModel):
    timeframes: dict[str, list[Candle]]
    data_fresh: bool = False
    spread_acceptable: bool = False

@app.post("/api/analysis/institutional-footprint")
def institutional_footprint_analysis(payload: FootprintAnalysisRequest):
    """Candle-derived liquidity/absorption proxies; no hidden order-book claims."""
    candles = [item.model_dump() for item in payload.candles]
    return analyze_institutional_footprint(candles, payload.settings)

@app.post("/api/analysis/gold-report")
def gold_report_analysis(payload: GoldReportRequest):
    """Bengali dashboard can consume this multi-timeframe Gold Report AI contract."""
    timeframes = {
        tf: [item.model_dump() for item in rows]
        for tf, rows in payload.timeframes.items()
        if tf in {"4h", "1h", "15m", "5m"}
    }
    return build_gold_report(timeframes, data_fresh=payload.data_fresh, spread_acceptable=payload.spread_acceptable)
