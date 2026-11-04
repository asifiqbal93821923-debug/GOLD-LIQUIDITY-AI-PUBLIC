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
    from .phase5_paper import (PaperForwardStore, normalize_paper_config, journal_view_from_paper_trades, advance_open_trade, open_from_pending, performance_summary)
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
    from phase5_paper import (PaperForwardStore, normalize_paper_config, journal_view_from_paper_trades, advance_open_trade, open_from_pending, performance_summary)

app = FastAPI(title="Project Indicator App API", version="0.7.0")
app.add_middleware(CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,https://asifiqbal93821923-debug.github.io").split(",") if origin.strip()],
    allow_credentials=True, allow_methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["*"])

DATABASE_PATH = os.getenv("DATABASE_URL") or os.getenv("CANDLE_DB_PATH", "data/market_candles.sqlite3")
STORE = CandleStore(DATABASE_PATH)
PHASE3_STORE = Phase3Store(DATABASE_PATH)
PHASE5_STORE = PaperForwardStore(DATABASE_PATH)
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
    folds: int = Field(default=4, ge=2, le=4)


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

class Phase5PaperConfigRequest(BaseModel):
    enabled: bool
    max_spread_points: float | None = None
    slippage_points: float = Field(default=0, ge=0, le=100000)
    commission_points_per_side: float = Field(default=0, ge=0, le=100000)


def _paper_forward_readiness(state: dict | None = None, now: datetime | None = None) -> dict:
    state = state or PHASE5_STORE.get_state()
    now = now or datetime.now(timezone.utc)
    checks = {}
    blockers = []
    persistent = (
        STORE.backend == "postgresql"
        or os.getenv("PAPER_FORWARD_ALLOW_SQLITE", "").strip().lower() == "true"
        or not os.getenv("RENDER_SERVICE_ID")
    )
    checks["persistent_storage"] = {"ok": persistent, "backend": STORE.backend}
    if not persistent:
        blockers.append("PERSISTENT_DATABASE_REQUIRED: configure DATABASE_URL (PostgreSQL) or explicitly approve a persistent SQLite disk.")
    token_ok = bool(os.getenv("MARKET_INGEST_TOKEN"))
    checks["mt5_bridge_token"] = {"ok": token_ok}
    if not token_ok:
        blockers.append("MT5 bridge token is not configured on the server.")
    system_cap = _configured_max_spread_points()
    checks["server_spread_cap"] = {"ok": system_cap > 0, "max_spread_points": system_cap or None}
    if system_cap <= 0:
        blockers.append("MAX_SPREAD_POINTS must be set to a measured positive broker spread cap.")
    paper_cap = state.get("max_spread_points")
    checks["paper_spread_cap"] = {"ok": isinstance(paper_cap, (int, float)) and not isinstance(paper_cap, bool) and math.isfinite(float(paper_cap)) and float(paper_cap) > 0,
        "max_spread_points": paper_cap}
    if not checks["paper_spread_cap"]["ok"]:
        blockers.append("Configure a positive Phase 5 maximum spread cap before starting.")
    elif system_cap > 0 and float(paper_cap) > system_cap:
        blockers.append("Phase 5 spread cap cannot be wider than the server MAX_SPREAD_POINTS gate.")
    frame_checks = {}
    for tf in ("4h", "1h", "15m"):
        state_tf = _ingest_status(tf, now)
        count = STORE.count("XAUUSD", tf)
        ok = bool(state_tf.get("fresh")) and count >= 50
        frame_checks[tf] = {**state_tf, "closed_candle_count": count, "ok": ok}
        if not state_tf.get("fresh"):
            blockers.append(tf.upper() + " authenticated MT5 feed is not fresh.")
        if count < 50:
            blockers.append(tf.upper() + " requires at least 50 stored candles.")
    checks["timeframes"] = frame_checks
    quote = _quote_status(now)
    quote_ok = bool(quote.get("fresh") and quote.get("acceptable"))
    if quote_ok and checks["paper_spread_cap"]["ok"]:
        quote_ok = float(quote.get("spread_points", math.inf)) <= float(paper_cap)
    checks["broker_quote"] = {**quote, "ok": quote_ok}
    if not quote_ok:
        blockers.append("Fresh MT5 Bid/Ask quote is missing, stale, above spread cap, or server spread gate is closed.")
    return {"ready": not blockers, "checks": checks, "blockers": blockers,
            "checked_at": now.isoformat(), "paper_only": True}


def _paper_frames_asof(decision_time: int) -> dict[str, list[dict]]:
    seconds = {"4h": 14400, "1h": 3600, "15m": 900, "5m": 300}
    frames = {}
    for tf, period in seconds.items():
        rows = STORE.read("XAUUSD", tf, 1500)
        closed_by_decision = [row for row in rows if int(row["time"]) + period <= decision_time]
        if tf == "5m" and len(closed_by_decision) < 50:
            continue
        frames[tf] = closed_by_decision
    return frames


def _run_paper_forward_cycle() -> dict:
    """Process one new closed 1H candle after authenticated MT5 quote ingestion."""
    state = PHASE5_STORE.get_state()
    existing_trades = PHASE5_STORE.list_trades(1000)
    has_open = any(x.get("status") == "OPEN" for x in existing_trades)
    if not state.get("enabled") and not has_open and not state.get("pending_signal"):
        return {"status": "disabled", "processed": False}
    now = datetime.now(timezone.utc)
    readiness = _paper_forward_readiness(state, now)
    # An existing paper position is managed only when the feed and quote are safe.
    if not readiness["ready"]:
        state["last_cycle"] = {"status": "blocked", "blockers": readiness["blockers"], "checked_at": now.isoformat()}
        PHASE5_STORE.save_state(state)
        return {"status": "blocked", "processed": False, "blockers": readiness["blockers"]}
    latest = STORE.read("XAUUSD", "1h", 1)
    if not latest:
        return {"status": "no_1h_candle", "processed": False}
    candle = latest[-1]
    candle_time = int(candle["time"])
    decision_time = candle_time + TF_SECONDS["1h"]
    now_epoch = int(now.timestamp())
    if decision_time > now_epoch + 5 or now_epoch - decision_time > TF_SECONDS["1h"] + 180:
        return {"status": "1h_candle_not_fresh_or_not_closed", "processed": False}
    previous = state.get("last_processed_candle_time")
    if previous is not None and candle_time <= int(previous):
        return {"status": "duplicate_candle", "processed": False, "candle_time": candle_time}
    if not PHASE5_STORE.claim_event(candle_time, {"trigger": "authenticated_mt5_quote_bridge", "paper_only": True}):
        return {"status": "duplicate_event", "processed": False, "candle_time": candle_time}
    try:
        frames = _paper_frames_asof(decision_time)
        if any(len(frames.get(tf) or []) < 50 for tf in ("4h", "1h", "15m")):
            raise ValueError("At least 50 fully closed 4H, 1H and 15M candles must be available as of the 1H decision close.")
        quote_record = STORE.latest_quote("XAUUSD") or {}
        quote_state = _quote_status(now)
        spread_points = float(quote_state.get("spread_points", 0))
        point_size = float(quote_record.get("point", 0))
        if point_size <= 0 or not math.isfinite(point_size):
            raise ValueError("The MT5 quote point size is invalid.")
        paper_cap = float(state["max_spread_points"])
        if spread_points > paper_cap:
            raise ValueError("Current spread exceeds the Phase 5 paper spread cap.")
        costs = {
            "spread_points": spread_points,
            "point_size": point_size,
            "slippage_points": float(state.get("slippage_points", 0)),
            "commission_points_per_side": float(state.get("commission_points_per_side", 0)),
        }
        actions = []
        trades = PHASE5_STORE.list_trades(1000)
        # Manage existing paper positions using only the newly closed H1 OHLC bar.
        for trade in trades:
            if trade.get("status") != "OPEN":
                continue
            closed = advance_open_trade(
                trade, candle, spread_points=costs["spread_points"], point_size=point_size,
                slippage_points=costs["slippage_points"],
                commission_points_per_side=costs["commission_points_per_side"])
            if closed:
                PHASE5_STORE.save_trade(closed)
                actions.append({"action": "TRADE_CLOSED", "trade_id": closed["id"],
                                "reason": closed["exit_reason"], "net_pnl_price": closed["net_pnl_price"],
                                "pnl_R": closed["pnl_r"]})
        trades = PHASE5_STORE.list_trades(1000)
        state = PHASE5_STORE.get_state()
        pending = state.get("pending_signal")
        active_now = any(x.get("status") == "OPEN" for x in trades)
        if pending:
            if not state.get("enabled"):
                actions.append({"action": "PENDING_CANCELLED", "reason": "ENGINE_PAUSED"})
                state["pending_signal"] = None
            elif active_now:
                actions.append({"action": "PENDING_CANCELLED", "reason": "OPEN_POSITION_PRESENT"})
                state["pending_signal"] = None
            else:
                trade, result = open_from_pending(
                    pending, candle, spread_points=costs["spread_points"], point_size=point_size,
                    slippage_points=costs["slippage_points"],
                    commission_points_per_side=costs["commission_points_per_side"])
                if trade:
                    PHASE5_STORE.save_trade(trade)
                    actions.append({"action": "TRADE_OPENED", "trade_id": trade["id"],
                                    "entry_price": trade["entry_price"], "side": trade["side"]})
                else:
                    actions.append({"action": "PENDING_EXPIRED", "reason": result})
                state["pending_signal"] = None
        report = None
        decision = {"decision": "WAIT", "reason_codes": ["ENGINE_PAUSED"], "trade_plan": {}}
        risk = {"status": "not_evaluated", "approved_for_alert": False, "blocking_reasons": ["ENGINE_PAUSED"]}
        if state.get("enabled"):
            report = build_gold_report(frames, data_fresh=True, spread_acceptable=True)
            decision = report.get("decision") or decision
            risk_settings = PHASE3_STORE.get_risk_settings(DEFAULT_RISK_SETTINGS)
            trades = PHASE5_STORE.list_trades(1000)
            risk_journal = journal_view_from_paper_trades(trades, risk_settings.get("contract_size"))
            paper_quote = {**quote_state, "acceptable": True}
            risk = evaluate_risk(decision, paper_quote, risk_settings, risk_journal, now)
            side = str(decision.get("decision", "WAIT")).upper()
            plan = decision.get("trade_plan") or {}
            if side in {"BUY", "SELL"} and plan.get("valid") is not False and risk.get("approved_for_alert"):
                if not any(x.get("status") == "OPEN" for x in trades) and not state.get("pending_signal"):
                    state["pending_signal"] = {
                        "side": side, "signal_time": decision_time,
                        "trade_plan": plan, "position_size": risk.get("position_size"),
                        "reason_codes": decision.get("reason_codes", []),
                        "source_candle_time": candle_time, "paper_only": True,
                    }
                    actions.append({"action": "SIGNAL_QUEUED_FOR_NEXT_1H_OPEN", "side": side})
                else:
                    actions.append({"action": "SIGNAL_NOT_QUEUED", "reason": "POSITION_OR_PENDING_EXISTS"})
            elif side in {"BUY", "SELL"}:
                actions.append({"action": "SIGNAL_BLOCKED", "reasons": risk.get("blocking_reasons") or [plan.get("reason", "INVALID_PLAN")]})
            else:
                actions.append({"action": "WAIT", "reasons": decision.get("reason_codes", [])})
        state["last_processed_candle_time"] = candle_time
        state["last_cycle"] = {
            "status": "processed", "candle_time": candle_time, "decision_time": decision_time,
            "decision": decision.get("decision", "WAIT"),
            "risk_status": risk.get("status"), "actions": actions,
            "spread_points": spread_points, "checked_at": now.isoformat(),
            "paper_only": True, "broker_orders_sent": False,
        }
        PHASE5_STORE.save_state(state)
        payload = {"decision": decision, "risk_management": risk, "actions": actions,
                   "data_as_of": decision_time, "costs": costs, "paper_only": True,
                   "broker_orders_sent": False}
        PHASE5_STORE.finish_event(candle_time, decision.get("decision", "WAIT"),
                                  "PROCESSED", "", payload)
        return {"status": "processed", "processed": True, "candle_time": candle_time, "actions": actions}
    except Exception as exc:
        PHASE5_STORE.fail_event(candle_time, str(exc))
        state = PHASE5_STORE.get_state()
        state["last_processed_candle_time"] = candle_time
        state["last_cycle"] = {"status": "error", "candle_time": candle_time,
                               "reason": str(exc), "checked_at": now.isoformat()}
        PHASE5_STORE.save_state(state)
        return {"status": "error", "processed": True, "candle_time": candle_time, "reason": str(exc)}


@app.api_route("/", methods=["GET", "HEAD"])
def root_health():
    # Root health response for generic platform probes and browser checks.
    return {"status":"ok","app":"GOLD TERMINAL API","health":"/api/health"}

@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"status":"ok","app":"PROJECT INDICATOR APP","version":"0.7.0"}

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
    paper_cycle = _run_paper_forward_cycle()
    return {"status":"ok","source":"mt5_bridge","spread_points":(payload.ask-payload.bid)/payload.point,
      "paper_forward":paper_cycle,"paper_only":True}

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




@app.get("/api/paper-forward/status")
def paper_forward_status():
    state = PHASE5_STORE.get_state()
    readiness = _paper_forward_readiness(state)
    trades = PHASE5_STORE.list_trades(1000)
    events = PHASE5_STORE.list_events(20)
    summary = performance_summary(trades, PHASE5_STORE.count_events(), state.get("pending_signal"))
    return {
        "status": "ok", "phase": "PHASE_5",
        "config": {
            "enabled": state.get("enabled", False),
            "max_spread_points": state.get("max_spread_points"),
            "slippage_points": state.get("slippage_points", 0.0),
            "commission_points_per_side": state.get("commission_points_per_side", 0.0),
        },
        "engine": {"enabled": state.get("enabled", False), "mode": "CLOSED_CANDLE_FORWARD_PAPER",
                   "started_at": state.get("started_at"), "stopped_at": state.get("stopped_at"),
                   "last_cycle": state.get("last_cycle")},
        "readiness": readiness, "summary": summary,
        "recent_trades": trades[:10], "recent_events": events,
        "paper_only": True, "broker_orders_sent": False,
        "note": "Paper simulation only. Live MT5 feed and broker-cost evidence must be independently verified."
    }


@app.put("/api/paper-forward/config")
def save_paper_forward_config(payload: Phase5PaperConfigRequest):
    current = PHASE5_STORE.get_state()
    candidate = payload.model_dump()
    try:
        updated = normalize_paper_config(candidate, current)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    if updated.get("enabled"):
        readiness = _paper_forward_readiness(updated)
        if not readiness.get("ready"):
            raise HTTPException(409, "Phase 5 start blocked: " + " | ".join(readiness["blockers"]))
        if not current.get("enabled"):
            updated["started_at"] = datetime.now(timezone.utc).isoformat()
            updated["stopped_at"] = None
    else:
        if current.get("enabled"):
            updated["stopped_at"] = datetime.now(timezone.utc).isoformat()
        updated["pending_signal"] = None
    PHASE5_STORE.save_state(updated)
    return {"status": "ok", "config": updated, "readiness": _paper_forward_readiness(updated),
            "paper_only": True, "broker_orders_sent": False}


@app.get("/api/paper-forward/trades")
def paper_forward_trades(limit: int = 200):
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    return {"status": "ok", "trades": PHASE5_STORE.list_trades(limit), "paper_only": True}


@app.get("/api/paper-forward/events")
def paper_forward_events(limit: int = 100):
    if not 1 <= limit <= 500:
        raise HTTPException(400, "limit must be between 1 and 500")
    return {"status": "ok", "events": PHASE5_STORE.list_events(limit), "paper_only": True}


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
