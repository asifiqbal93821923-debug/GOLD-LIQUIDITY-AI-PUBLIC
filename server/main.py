from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import hmac
import math
from pydantic import BaseModel, Field
from typing import Literal
import os

try:
    from .alpha_signal import analyze_alpha_signal
    from .unified_decision import analyze_unified_decision
    from .institutional_footprint import analyze_institutional_footprint
    from .gold_report import build_gold_report
    from .market_data import CandleStore, validate_candles, to_epoch_seconds
    from .phase3_storage import Phase3Store
    from .risk_management import DEFAULT_RISK_SETTINGS, normalize_risk_settings, evaluate_risk
    from .backtest import run_alpha_1h_backtest
    from .multitimeframe_backtest import run_gold_mtf_backtest
    from .data_audit import audit_candle_history
    from .phase4_validation import run_phase4_validation
except ImportError:
    from alpha_signal import analyze_alpha_signal
    from unified_decision import analyze_unified_decision
    from institutional_footprint import analyze_institutional_footprint
    from gold_report import build_gold_report
    from market_data import CandleStore, validate_candles, to_epoch_seconds
    from phase3_storage import Phase3Store
    from risk_management import DEFAULT_RISK_SETTINGS, normalize_risk_settings, evaluate_risk
    from backtest import run_alpha_1h_backtest
    from multitimeframe_backtest import run_gold_mtf_backtest
    from data_audit import audit_candle_history
    from phase4_validation import run_phase4_validation

app = FastAPI(title="Project Indicator App API", version="0.6.0")
app.add_middleware(CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,https://asifiqbal93821923-debug.github.io").split(",") if origin.strip()],
    allow_credentials=True, allow_methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["*"])

DATABASE_PATH = os.getenv("DATABASE_URL") or os.getenv("CANDLE_DB_PATH", "data/market_candles.sqlite3")
STORE = CandleStore(DATABASE_PATH)
PHASE3_STORE = Phase3Store(DATABASE_PATH)
TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1D"}

TF_SECONDS={"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,"1D":86400}

def _ingest_status(tf: str, now: datetime | None=None) -> dict:
    now=now or datetime.now(timezone.utc)
    ingest=STORE.latest_ingest("XAUUSD",tf)
    if not ingest or ingest.get("source")!="mt5_bridge":
        return {"fresh":False,"reason":"NO_MT5_CANDLE_INGEST"}
    try:
        received_at=datetime.fromisoformat(ingest["updated_at"])
        receive_age=(now-received_at).total_seconds()
        latest=STORE.read("XAUUSD",tf,1)
        if not latest:
            return {"fresh":False,"reason":"NO_CLOSED_CANDLES"}
        bar_open=int(latest[-1]["time"])
        bar_close=bar_open+TF_SECONDS[tf]
        bar_age=now.timestamp()-bar_close
        # A candle must have closed, and the most recent closed candle must be
        # no older than one full timeframe plus the bridge grace window.
        fresh=bool(0<=receive_age<=180 and -5<=bar_age<=TF_SECONDS[tf]+180)
        return {"fresh":fresh,"receive_age_seconds":round(receive_age,1),
          "last_candle_open":bar_open,"last_candle_close":bar_close,
          "last_candle_close_age_seconds":round(bar_age,1),
          "reason":None if fresh else "STALE_OR_UNCLOSED_LAST_CANDLE"}
    except (TypeError,ValueError,KeyError):
        return {"fresh":False,"reason":"INVALID_INGEST_TIMESTAMP"}

def _fresh_ingest(tf: str, now: datetime | None=None) -> bool:
    return _ingest_status(tf,now)["fresh"]

def _configured_max_spread_points() -> float:
    """Return a finite positive broker-calibrated limit; fail closed otherwise."""
    try:
        value=float(os.getenv("MAX_SPREAD_POINTS","0"))
    except (TypeError,ValueError):
        return 0.0
    return value if math.isfinite(value) and value>0 else 0.0


def _quote_status(now: datetime | None=None) -> dict:
    now=now or datetime.now(timezone.utc)
    quote=STORE.latest_quote("XAUUSD")
    if not quote or quote.get("source")!="mt5_bridge":
        return {"fresh":False,"acceptable":False,"reason":"NO_AUTHENTICATED_MT5_QUOTE"}
    try:
        receive_age=(now-datetime.fromisoformat(quote["updated_at"])).total_seconds()
        tick_age=now.timestamp()-float(quote["quote_time"])
        spread=float(quote["spread_points"])
        threshold=_configured_max_spread_points()
        if not math.isfinite(spread) or spread<0:
            raise ValueError("Invalid stored spread")
        fresh=bool(0<=receive_age<=180 and -5<=tick_age<=180)
        acceptable=bool(fresh and threshold>0 and spread<=threshold)
        if not fresh:
            reason="STALE_QUOTE"
        elif threshold<=0:
            reason="SPREAD_LIMIT_NOT_CONFIGURED"
        elif spread>threshold:
            reason="SPREAD_LIMIT_EXCEEDED"
        else:
            reason=None
        return {"fresh":fresh,"acceptable":acceptable,"spread_points":round(spread,2),
          "max_spread_points":threshold or None,"quote_age_seconds":round(tick_age,1),
          "reason":reason}
    except (TypeError,ValueError,KeyError):
        return {"fresh":False,"acceptable":False,"reason":"INVALID_QUOTE_TIMESTAMP_OR_SPREAD"}


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

class BacktestRequest(BaseModel):
    candles: list[Candle] = Field(min_length=50, max_length=5000)
    settings: dict = Field(default_factory=dict)
    costs: dict = Field(default_factory=dict)

class GoldBacktestRequest(BaseModel):
    timeframes: dict[str, list[Candle]]
    settings: dict = Field(default_factory=dict)
    costs: dict = Field(default_factory=dict)

class HistoryAuditRequest(BaseModel):
    timeframes: dict[str, list[Candle]]

class Phase4ValidationRequest(BaseModel):
    timeframes: dict[str, list[Candle]]
    costs: dict = Field(default_factory=dict)
    settings: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    folds: int = Field(default=4, ge=2, le=8)


class QuoteBridgeRequest(BaseModel):
    symbol: str = "XAUUSD"
    time: str | int | float
    bid: float
    ask: float
    point: float

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

class JournalCreateRequest(BaseModel):
    direction: Literal["BUY", "SELL"]
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    target_price: float = Field(gt=0)
    lots: float = Field(gt=0, le=1000)
    notes: str = Field(default="", max_length=500)

class JournalCloseRequest(BaseModel):
    exit_price: float = Field(gt=0)
    pnl_money: float

@app.api_route("/", methods=["GET", "HEAD"])
def root_health():
    # Root health response for generic platform probes and browser checks.
    return {"status":"ok","app":"GOLD TERMINAL API","health":"/api/health"}

@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"status":"ok","app":"PROJECT INDICATOR APP","version":"0.6.0"}

@app.get("/api/config/status")
def config_status():
    provider=os.getenv("MARKET_DATA_PROVIDER","not_configured")
    now=datetime.now(timezone.utc)
    bars={tf:_ingest_status(tf,now) for tf in ("4h","1h","15m")}
    quote=_quote_status(now)
    live=all(x["fresh"] for x in bars.values()) and quote["fresh"]
    latest=STORE.latest_ingest("XAUUSD")
    return {"market":"XAUUSD","provider":provider,
      "credentials_present":bool(os.getenv("MARKET_DATA_API_KEY")),
      "bridge_token_configured":bool(os.getenv("MARKET_INGEST_TOKEN")),
      "live_data":live,"fresh_closed_timeframes":{tf:x["fresh"] for tf,x in bars.items()},
      "timeframe_health":bars,"quote":quote,
      "spread_acceptable":quote["acceptable"],"last_ingest":latest,"historical_store":STORE.backend,
      "message":"Fresh MT5 candles and broker quote are being received." if live else "Historical data is available; one or more MT5 candle timeframes or the actual broker tick is stale/missing.",
      "checked_at":now.isoformat()}

@app.get("/api/market/candles")
def get_candles(timeframe: str="1h", limit: int=1000, symbol: str="XAUUSD"):
    if timeframe not in TIMEFRAMES: raise HTTPException(400,"Unsupported timeframe")
    if not 1<=limit<=100000: raise HTTPException(400,"limit must be between 1 and 100000")
    rows=STORE.read(symbol.upper(),timeframe,limit)
    ingest=STORE.latest_ingest(symbol.upper(),timeframe)
    live=False
    if ingest and ingest.get("source")=="mt5_bridge":
        live=_fresh_ingest(timeframe)
    return {"status":"ok" if rows else "not_available","symbol":symbol.upper(),
      "timeframe":timeframe,"count":len(rows),"data":rows,
      "data_kind":"mt5_bridge" if live else "historical_import","source":ingest.get("source") if ingest else None,
      "last_updated_at":ingest.get("updated_at") if ingest else None,"live":live,
      "message":"Recent closed candles from authenticated MT5 bridge." if live else "Stored historical candles; live bridge is not currently fresh." if rows else "No candles imported for this symbol/timeframe."}

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
    now=datetime.now(timezone.utc).timestamp()
    latest=normalized[-1]["time"]
    period=TF_SECONDS[payload.timeframe]
    close_time=latest+period
    if close_time>now+5:
        raise HTTPException(422,"Latest MT5 candle is not closed yet or has a future timestamp.")
    if now-close_time>period+180:
        raise HTTPException(422,"Latest MT5 closed candle is stale; refresh broker history before sending.")
    count=STORE.upsert("XAUUSD",payload.timeframe,normalized,"mt5_bridge")
    return {"status":"ok","source":"mt5_bridge","timeframe":payload.timeframe,
      "received":len(rows),"stored":count,"live":True,
      "note":"EA should resend closed bars on its timer; freshness is based on server receive time."}


@app.post("/api/market/quote/bridge")
def mt5_quote_bridge(payload: QuoteBridgeRequest, x_bridge_token: str | None = Header(default=None, alias="X-Bridge-Token")):
    expected=os.getenv("MARKET_INGEST_TOKEN")
    if not expected:
        raise HTTPException(503,"Server MT5 bridge token is not configured.")
    if not x_bridge_token or not hmac.compare_digest(x_bridge_token,expected):
        raise HTTPException(401,"Invalid bridge token.")
    if (payload.symbol.upper()!="XAUUSD" or not all(math.isfinite(x) for x in (payload.bid,payload.ask,payload.point))
        or payload.bid<=0 or payload.ask<payload.bid or payload.point<=0):
        raise HTTPException(422,"Invalid XAUUSD quote or point size.")
    try: quote_time=to_epoch_seconds(payload.time)
    except ValueError as exc: raise HTTPException(422,str(exc))
    STORE.upsert_quote("XAUUSD",payload.bid,payload.ask,payload.point,quote_time,"mt5_bridge")
    return {"status":"ok","source":"mt5_bridge","spread_points":(payload.ask-payload.bid)/payload.point}

@app.get("/api/market/quote")
def get_market_quote(symbol: str="XAUUSD"):
    if symbol.upper()!="XAUUSD":
        return {"status":"not_available","acceptable":False,"message":"Only XAUUSD is enabled."}
    quote=STORE.latest_quote("XAUUSD")
    if not quote: return {"status":"not_available","acceptable":False,"fresh":False,"message":"No broker bid/ask quote received."}
    state=_quote_status()
    return {"status":"ok","symbol":"XAUUSD","bid":quote["bid"],"ask":quote["ask"],
      "spread_points":state.get("spread_points"),"max_spread_points":state.get("max_spread_points"),
      "fresh":state["fresh"],"acceptable":state["acceptable"],"quote_age_seconds":state.get("quote_age_seconds"),
      "source":quote["source"],"updated_at":quote["updated_at"],"reason":state.get("reason"),
      "message":"Spread within configured limit." if state["acceptable"] else "Spread gate closed: actual tick stale or MAX_SPREAD_POINTS not configured/exceeded."}



@app.get("/api/risk/settings")
def get_risk_settings():
    settings = PHASE3_STORE.get_risk_settings(DEFAULT_RISK_SETTINGS)
    return {"status": "ok", "settings": settings,
      "note": "Risk profile is used for analysis gates and estimates only; no orders are sent."}


@app.put("/api/risk/settings")
def save_risk_settings(payload: dict):
    try:
        settings = normalize_risk_settings(payload)
        PHASE3_STORE.set_risk_settings(settings)
        return {"status": "ok", "settings": settings}
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/alerts")
def get_signal_alerts(limit: int = 50):
    if not 1 <= limit <= 200:
        raise HTTPException(400, "limit must be between 1 and 200")
    return {"status": "ok", "events": PHASE3_STORE.list_signal_events(limit)}


@app.get("/api/journal")
def get_trade_journal(limit: int = 50):
    if not 1 <= limit <= 500:
        raise HTTPException(400, "limit must be between 1 and 500")
    entries = PHASE3_STORE.list_journal_entries(limit)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    opened_today = 0
    realized_today = 0.0
    open_trades = 0
    for trade in PHASE3_STORE.list_journal_entries(500):
        try:
            opened = datetime.fromisoformat((trade.get("opened_at") or trade.get("created_at")).replace("Z", "+00:00"))
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            if opened.astimezone(timezone.utc) >= day_start:
                opened_today += 1
        except (AttributeError, TypeError, ValueError):
            pass
        if trade.get("status") == "OPEN":
            open_trades += 1
        try:
            closed = datetime.fromisoformat((trade.get("closed_at") or "").replace("Z", "+00:00"))
            if closed.tzinfo is None:
                closed = closed.replace(tzinfo=timezone.utc)
            pnl = float(trade.get("pnl_money"))
            if closed.astimezone(timezone.utc) >= day_start and math.isfinite(pnl):
                realized_today += pnl
        except (AttributeError, TypeError, ValueError):
            pass
    return {"status": "ok", "entries": entries, "summary": {
        "opened_today_utc": opened_today, "open_trades": open_trades,
        "realized_pnl_today_utc": round(realized_today, 2)}, "timezone": "UTC"}


@app.post("/api/journal")
def create_trade_journal_entry(payload: JournalCreateRequest):
    values = payload.model_dump()
    if payload.direction == "BUY" and not payload.stop_loss < payload.entry_price < payload.target_price:
        raise HTTPException(422, "BUY journal levels must satisfy SL < entry < target.")
    if payload.direction == "SELL" and not payload.stop_loss > payload.entry_price > payload.target_price:
        raise HTTPException(422, "SELL journal levels must satisfy SL > entry > target.")
    try:
        return {"status": "ok", "entry": PHASE3_STORE.create_journal_entry(values)}
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc))


@app.post("/api/journal/{entry_id}/close")
def close_trade_journal_entry(entry_id: str, payload: JournalCloseRequest):
    if not math.isfinite(payload.exit_price) or not math.isfinite(payload.pnl_money):
        raise HTTPException(422, "Exit price and realized PnL must be finite.")
    entry = PHASE3_STORE.close_journal_entry(entry_id, payload.exit_price, payload.pnl_money)
    if entry is None:
        raise HTTPException(404, "Open journal trade not found; it may already be closed.")
    return {"status": "ok", "entry": entry}


@app.post("/api/market/history/audit")
def market_history_audit(payload: HistoryAuditRequest):
    now=int(datetime.now(timezone.utc).timestamp())
    reports={}
    for tf, rows in payload.timeframes.items():
        if tf not in {"4h","1h","15m","5m"}:
            reports[tf]={"status":"unsupported_timeframe"}
            continue
        if len(rows)>100000:
            raise HTTPException(413,"Maximum 100000 candles per timeframe for data audit.")
        reports[tf]=audit_candle_history([x.model_dump() for x in rows],tf,now)
    return {"status":"ok","symbol":"XAUUSD","checked_at":datetime.now(timezone.utc).isoformat(),
      "reports":reports,"note":"Audit only; no candles are synthesized or modified."}

@app.post("/api/backtest/gold-mtf")
def gold_mtf_backtest(payload: GoldBacktestRequest):
    selected={tf:rows for tf,rows in payload.timeframes.items() if tf in {"4h","1h","15m","5m"}}
    if any(len(rows)>5000 for rows in selected.values()):
        raise HTTPException(413,"Maximum 5000 candles per timeframe for research replay.")
    timeframes={tf:[x.model_dump() for x in rows] for tf,rows in selected.items()}
    return run_gold_mtf_backtest(timeframes,costs=payload.costs,settings=payload.settings)

@app.post("/api/research/phase4-validation")
def phase4_validation(payload: Phase4ValidationRequest):
    selected={tf:rows for tf,rows in payload.timeframes.items() if tf in {"4h","1h","15m","5m"}}
    if any(len(rows)>6000 for rows in selected.values()):
        raise HTTPException(413,"Maximum 6000 candles per timeframe for Phase 4 validation.")
    timeframes={tf:[x.model_dump() for x in rows] for tf,rows in selected.items()}
    return run_phase4_validation(timeframes,costs=payload.costs,
        settings=payload.settings,metadata=payload.metadata,folds=payload.folds)


@app.post("/api/backtest/alpha-1h")
def alpha_1h_backtest(payload: BacktestRequest):
    """Research replay of 1H Alpha flips; not the full multi-timeframe strategy."""
    return run_alpha_1h_backtest([x.model_dump() for x in payload.candles],
      settings=payload.settings,costs=payload.costs)

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
    # Never trust browser-supplied freshness/spread booleans for the final trade gate.
    now=datetime.now(timezone.utc)
    fresh=all(_fresh_ingest(tf,now) for tf in ("4h","1h","15m"))
    spread_ok=_quote_status(now)["acceptable"]
    report = build_gold_report(timeframes,data_fresh=fresh,spread_acceptable=spread_ok)
    risk_settings = PHASE3_STORE.get_risk_settings(DEFAULT_RISK_SETTINGS)
    journal = PHASE3_STORE.list_journal_entries(500)
    quote = _quote_status(now)
    risk = evaluate_risk(report.get("decision", {}), quote, risk_settings, journal, now)
    report["risk_management"] = risk

    direction = report.get("decision", {}).get("decision")
    last_1h = (timeframes.get("1h") or [])[-1] if timeframes.get("1h") else None
    previous_state = PHASE3_STORE.get_setting("last_signal_state:XAUUSD", "WAIT")
    if direction in {"BUY", "SELL"} and risk.get("approved_for_alert") and last_1h:
        plan = report.get("decision", {}).get("trade_plan") or {}
        entry = plan.get("entry") or []
        targets = plan.get("targets") or []
        candle_time = int(last_1h["time"])
        if direction != previous_state:
            event, created = PHASE3_STORE.create_signal_event({
                "signal_key": f"XAUUSD:1H:{candle_time}:{direction}",
                "symbol": "XAUUSD", "direction": direction, "candle_time": candle_time,
                "price": float(last_1h["close"]),
                "entry_low": entry[0] if len(entry) == 2 else None,
                "entry_high": entry[1] if len(entry) == 2 else None,
                "stop_loss": plan.get("stop_loss"),
                "target1": targets[0] if len(targets) > 0 else None,
                "target2": targets[1] if len(targets) > 1 else None,
                "target3": targets[2] if len(targets) > 2 else None,
                "reason_codes": report.get("decision", {}).get("reason_codes", []),
            })
            report["alert_event"] = {"created": created, "event": event}
        PHASE3_STORE.set_setting("last_signal_state:XAUUSD", direction)
    else:
        PHASE3_STORE.set_setting("last_signal_state:XAUUSD", "WAIT")
    return report
