from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os

app = FastAPI(title="Project Indicator App API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "PROJECT INDICATOR APP", "version": "0.1.0"}

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