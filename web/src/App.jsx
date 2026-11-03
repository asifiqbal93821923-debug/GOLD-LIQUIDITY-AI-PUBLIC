import { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, ColorType } from 'lightweight-charts';
import { Activity, AlertTriangle, BarChart3, CandlestickChart, Clock3, Layers3, Radio, ShieldCheck, Target, Waves } from 'lucide-react';

const timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1D'];
const panels = [
  { label: 'MARKET BIAS', value: 'WAITING FOR DATA', detail: 'Trend engine not connected', icon: Activity },
  { label: 'MOMENTUM', value: 'UNAVAILABLE', detail: 'Requires live candles', icon: Waves },
  { label: 'MARKET STRUCTURE', value: 'NOT ANALYZED', detail: 'Pine Script logic pending', icon: Layers3 },
  { label: 'LIQUIDITY', value: 'NOT ANALYZED', detail: 'No order-flow claims without data', icon: Target },
];

function ChartPanel() {
  const host = useRef(null);
  const [tf, setTf] = useState('15m');
  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: '#0d1420' }, textColor: '#91a0b5', attributionLogo: false },
      grid: { vertLines: { color: '#172232' }, horzLines: { color: '#172232' } },
      rightPriceScale: { borderColor: '#263449' },
      timeScale: { borderColor: '#263449', timeVisible: true, secondsVisible: false },
      crosshair: { vertLine: { color: '#61748c' }, horzLine: { color: '#61748c' } },
    });
    chart.addSeries(CandlestickSeries, {
      upColor: '#21b78a', downColor: '#ed6675', borderUpColor: '#21b78a',
      borderDownColor: '#ed6675', wickUpColor: '#21b78a', wickDownColor: '#ed6675',
    });
    const resize = new ResizeObserver(() => chart.timeScale().fitContent());
    resize.observe(host.current);
    return () => { resize.disconnect(); chart.remove(); };
  }, []);
  return <section className="card chart-card">
    <div className="section-head"><div><span className="eyebrow">PRICE ACTION</span><h2>XAU / USD <span className="muted">· Gold Spot</span></h2></div><span className="data-pill"><i /> DATA NOT CONNECTED</span></div>
    <div className="tf-row">{timeframes.map(t => <button key={t} className={tf === t ? 'tf active' : 'tf'} onClick={() => setTf(t)}>{t}</button>)}</div>
    <div className="chart-empty"><div className="chart-icon"><CandlestickChart size={25}/></div><b>Waiting for a verified Gold price feed</b><span>Chart timeframe: {tf.toUpperCase()} · No simulated prices are displayed as live market data.</span></div>
    <div ref={host} className="chart-host" aria-label="XAUUSD candlestick chart awaiting data" />
  </section>;
}

export default function App() {
  const [api, setApi] = useState('checking');
  useEffect(() => {
    fetch('/api/health').then(r => r.ok ? r.json() : Promise.reject()).then(() => setApi('online')).catch(() => setApi('offline'));
  }, []);
  return <main className="shell">
    <header className="topbar"><div className="brand"><div className="brand-mark"><BarChart3 size={21}/></div><div><b>PROJECT INDICATOR APP</b><small>GOLD MARKET INTELLIGENCE</small></div></div><div className="top-status"><span className={'api-dot ' + api}/><span>API {api.toUpperCase()}</span><span className="divider-v"/><span className="mode-label">ANALYSIS TERMINAL</span></div></header>
    <section className="welcome"><div><span className="eyebrow">WORKSPACE · XAUUSD</span><h1>See the market.<br/><em>Understand the move.</em></h1><p>One workspace for price action, market structure, liquidity and disciplined trade planning.</p></div><div className="session-card"><span className="eyebrow">SYSTEM STATUS</span><strong><Radio size={17}/> INITIAL SETUP</strong><small>Waiting for data provider and first Pine Script.</small></div></section>
    <section className="metric-grid">{panels.map(p => {const Icon=p.icon; return <article className="card metric" key={p.label}><div className="metric-top"><span>{p.label}</span><Icon size={17}/></div><b>{p.value}</b><small>{p.detail}</small></article>;})}</section>
    <ChartPanel />
    <section className="lower-grid">
      <article className="card"><div className="section-head"><div><span className="eyebrow">TRADE PLANNER</span><h2>Entry & Risk Plan</h2></div><Target size={19}/></div><div className="empty-state"><ShieldCheck size={22}/><b>No trade setup yet</b><span>Signals will appear only after the source-code logic and market-data feed are validated.</span></div></article>
      <article className="card"><div className="section-head"><div><span className="eyebrow">ZONE RADAR</span><h2>Supply & Demand</h2></div><Layers3 size={19}/></div><div className="empty-state"><AlertTriangle size={22}/><b>Zones not calculated</b><span>Support, resistance, supply and demand will be drawn from verified candle data.</span></div></article>
    </section>
    <footer><span><Clock3 size={13}/> BUILD 0.1.0 · FOUNDATION</span><span>Educational analysis only · No broker orders are placed</span></footer>
  </main>;
}