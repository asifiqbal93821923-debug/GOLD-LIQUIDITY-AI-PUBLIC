import { useCallback, useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, ColorType } from 'lightweight-charts';
import { Activity, AlertTriangle, BarChart3, CandlestickChart, Clock3, Layers3, Radio, ShieldCheck, Target, Waves, Upload, RefreshCw } from 'lucide-react';

const timeframes=['3m','5m','15m','30m','1h','4h','1D'];
const labels={ '3m':'৩ মিনিট','5m':'৫ মিনিট','15m':'১৫ মিনিট','30m':'৩০ মিনিট','1h':'১ ঘণ্টা','4h':'৪ ঘণ্টা','1D':'১ দিন' };
const API='';

function parseCsv(text){
  const lines=text.replace(/^\uFEFF/,'').trim().split(/\r?\n/).filter(Boolean);
  if(lines.length<2) throw new Error('CSV-তে Header ও অন্তত একটি Candle থাকতে হবে।');
  const first=lines[0];
  const delimiter=[';',',','\t'].sort((a,b)=>first.split(b).length-first.split(a).length)[0];
  const headers=first.split(delimiter).map(x=>x.trim().replace(/^"|"$/g,'').toLowerCase());
  const idx=(...names)=>headers.findIndex(x=>names.includes(x));
  const ti=idx('time','timestamp','datetime'), di=idx('date');
  const oi=idx('open','o'), hi=idx('high','h'), li=idx('low','l'), ci=idx('close','c'), vi=idx('volume','vol','tick_volume','tick volume');
  if([oi,hi,li,ci].some(x=>x<0)||(ti<0&&di<0)) throw new Error('CSV Header দরকার: time বা date, open, high, low, close (volume ঐচ্ছিক)।');
  return lines.slice(1).map((line,n)=>{
    const a=line.split(delimiter).map(x=>x.trim().replace(/^"|"$/g,''));
    const rawTime=(di>=0&&ti>=0)?(a[di]+' '+a[ti]):a[ti>=0?ti:di];
    const numericTime=Number(rawTime);
    const parsedTime=rawTime&&Number.isFinite(numericTime)?numericTime:Date.parse(rawTime.replaceAll('.','-'))/1000;
    const candle={time:parsedTime,symbol:'XAUUSD',open:Number(a[oi]),high:Number(a[hi]),low:Number(a[li]),close:Number(a[ci])};
    if(vi>=0&&a[vi]!==''&&Number.isFinite(Number(a[vi]))) candle.volume=Number(a[vi]);
    if(!Number.isFinite(candle.time)||![candle.open,candle.high,candle.low,candle.close].every(Number.isFinite)) throw new Error('CSV Row '+(n+2)+'-এ ভুল মান আছে।');
    return candle;
  });
}

function ChartPanel({timeframe,setTimeframe,candles,loading,onReload,report,dataKind}){
  const host=useRef(null); const chartRef=useRef(null); const seriesRef=useRef(null); const priceLinesRef=useRef([]);
  useEffect(()=>{
    if(!host.current) return;
    const chart=createChart(host.current,{autoSize:true,
      layout:{background:{type:ColorType.Solid,color:'#0d1420'},textColor:'#91a0b5',attributionLogo:false},
      grid:{vertLines:{color:'#172232'},horzLines:{color:'#172232'}},
      rightPriceScale:{borderColor:'#263449'},timeScale:{borderColor:'#263449',timeVisible:true,secondsVisible:false},
      crosshair:{vertLine:{color:'#61748c'},horzLine:{color:'#61748c'}}});
    const series=chart.addSeries(CandlestickSeries,{upColor:'#21b78a',downColor:'#ed6675',
      borderUpColor:'#21b78a',borderDownColor:'#ed6675',wickUpColor:'#21b78a',wickDownColor:'#ed6675'});
    chartRef.current=chart; seriesRef.current=series;
    const resize=new ResizeObserver(()=>chart.timeScale().fitContent()); resize.observe(host.current);
    return ()=>{resize.disconnect();chart.remove();chartRef.current=null;seriesRef.current=null;};
  },[]);
  useEffect(()=>{
    if(!seriesRef.current) return;
    const data=candles.map(c=>({time:c.time,open:c.open,high:c.high,low:c.low,close:c.close}));
    try { seriesRef.current.setData(data); chartRef.current?.timeScale().fitContent(); } catch(e) { console.error('Chart data rejected',e); }
  },[candles]);
  useEffect(()=>{
    if(!seriesRef.current) return;
    priceLinesRef.current.forEach(line=>{try{seriesRef.current.removePriceLine(line);}catch(e){}});
    priceLinesRef.current=[];
    const smc=report && report.timeframes && report.timeframes['1h'] && report.timeframes['1h'].smc;
    if(!smc||smc.status!=='ok') return;
    const add=(price,title,color,lineStyle=2)=>{
      if(typeof price!=='number'||!Number.isFinite(price)) return;
      priceLinesRef.current.push(seriesRef.current.createPriceLine({price,title,color,lineWidth:1,lineStyle,axisLabelVisible:true}));
    };
    add(smc.swing_high && smc.swing_high.price,'1H Swing High','#e36c75');
    add(smc.swing_low && smc.swing_low.price,'1H Swing Low','#42b99b');
    (smc.active_fvgs||[]).slice(-4).forEach((z,i)=>{add(z.low,'1H FVG '+(i+1)+' L','#6f9fe8',1);add(z.high,'1H FVG '+(i+1)+' H','#6f9fe8',1);});
    (smc.order_block_candidates||[]).slice(-3).forEach((z,i)=>{const color=z.direction==='bullish'?'#36b995':'#d77b83';add(z.low,'1H OB '+(i+1)+' L',color,2);add(z.high,'1H OB '+(i+1)+' H',color,2);});
    (smc.equal_high_pools||[]).slice(-3).forEach((z,i)=>add(z.price,'1H EQH '+(i+1),'#d8ad69',1));
    (smc.equal_low_pools||[]).slice(-3).forEach((z,i)=>add(z.price,'1H EQL '+(i+1),'#d8ad69',1));
  },[report,candles]);
  return <section className="card chart-card">
    <div className="section-head"><div><span className="eyebrow">PRICE ACTION · XAUUSD</span><h2>Gold Spot <span className="muted">· Main Trading TF: 1H</span></h2></div>
      <span className={'data-pill '+(candles.length?'data-ready':'')}><i/> {candles.length?(dataKind==='mt5_bridge'?'MT5 BRIDGE':'HISTORICAL DATA'):'NO DATA'}</span></div>
    <div className="tf-row">{timeframes.map(t=><button key={t} className={timeframe===t?'tf active':'tf'} onClick={()=>setTimeframe(t)}>{t.toUpperCase()}</button>)}
      <button className="tf reload" onClick={onReload} disabled={loading}><RefreshCw size={13}/> Reload</button></div>
    <div ref={host} className="chart-host" aria-label="XAUUSD historical candlestick chart"/>
    {!candles.length&&<div className="chart-overlay"><CandlestickChart size={25}/><b>{loading?'Candle লোড হচ্ছে…':'এই Timeframe-এর Candle Data নেই'}</b><span>MT5 বা CSV থেকে Historical Candle Import করুন। কোনো Synthetic Price দেখানো হচ্ছে না।</span></div>}
    <div className="chart-foot">চার্ট: {labels[timeframe]} · {candles.length} candles · Historical import only — Live feed not connected</div>
  </section>;
}

export default function App(){
  const [api,setApi]=useState('checking');
  const [config,setConfig]=useState(null);
  const [tf,setTf]=useState('1h');
  const [candles,setCandles]=useState([]);
  const [dataKind,setDataKind]=useState('historical_import');
  const [counts,setCounts]=useState({});
  const [loading,setLoading]=useState(false);
  const [message,setMessage]=useState('');
  const [report,setReport]=useState(null);
  const [quoteInfo,setQuoteInfo]=useState(null);
  const [importing,setImporting]=useState(false);
  const fileRef=useRef(null);

  const loadCandles=useCallback(async (frame=tf)=>{
    setLoading(true); setMessage('');
    try{
      const res=await fetch(API+'/api/market/candles?timeframe='+encodeURIComponent(frame)+'&limit=3000');
      if(!res.ok) throw new Error('Candle API request failed: '+res.status);
      const data=await res.json(); const rows=data.data||[];
      setCandles(rows); setCounts(old=>({...old,[frame]:data.count||rows.length}));
      return rows;
    }catch(e){setMessage('ডেটা লোড করা যায়নি: '+e.message);setCandles([]);setDataKind('historical_import');return [];}
    finally{setLoading(false);}
  },[tf]);

  useEffect(()=>{fetch('/api/health').then(r=>r.ok?r.json():Promise.reject()).then(()=>setApi('online')).catch(()=>setApi('offline'));
    fetch('/api/config/status').then(r=>r.ok?r.json():null).then(setConfig).catch(()=>setConfig(null));},[]);
  useEffect(()=>{loadCandles(tf);},[tf,loadCandles]);

  const importFile=async file=>{
    if(!file)return;
    setImporting(true);setMessage('');
    try{
      const rows=parseCsv(await file.text());
      const res=await fetch('/api/market/candles/import',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({symbol:'XAUUSD',timeframe:tf,source:'CSV: '+file.name,candles:rows})});
      const result=await res.json();
      if(!res.ok) throw new Error(result.detail||result.message||'Import failed');
      setMessage('সফল: '+result.stored+'টি '+tf.toUpperCase()+' Candle সংরক্ষণ হয়েছে।');
      await loadCandles(tf);
    }catch(e){setMessage('Import Error: '+e.message);}
    finally{setImporting(false);if(fileRef.current)fileRef.current.value='';}
  };

  const runReport=async()=>{
    setMessage('');setReport(null);
    try{
      const frames={};let allFresh=true;
      for(const frame of ['4h','1h','15m']){
        const res=await fetch('/api/market/candles?timeframe='+frame+'&limit=1000');
        const d=await res.json();frames[frame]=d.data||[];if(d.live!==true) allFresh=false;
      }
      const quoteRes=await fetch('/api/market/quote');const quote=await quoteRes.json();setQuoteInfo(quote);
      const res=await fetch('/api/analysis/gold-report',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({timeframes:frames,data_fresh:allFresh,spread_acceptable:quote.acceptable===true})});
      const data=await res.json();if(!res.ok)throw new Error(data.detail||'Report failed');setReport(data);
    }catch(e){setMessage('Analysis Error: '+e.message);}
  };

  const decision=report?.decision||{};
  const plan=decision.trade_plan;
  return <main className="shell">
    <header className="topbar"><div className="brand"><div className="brand-mark"><BarChart3 size={21}/></div><div><b>PROJECT INDICATOR APP</b><small>GOLD MARKET INTELLIGENCE</small></div></div>
      <div className="top-status"><span className={'api-dot '+api}/><span>API {api.toUpperCase()}</span><span className="divider-v"/><span className="mode-label">1H PRIMARY TERMINAL</span></div></header>
    <section className="welcome"><div><span className="eyebrow">WORKSPACE · XAUUSD</span><h1>See the market.<br/><em>Understand the move.</em></h1>
      <p>৪H Macro · ১H Main Trading · ১৫M Setup · ৫M Optional Entry Confirmation</p></div>
      <div className="session-card"><span className="eyebrow">DATA STATUS</span><strong><Radio size={17}/> {config?.live_data?'LIVE FEED':'HISTORICAL MODE'}</strong>
        <small>{config?.message||'API status যাচাই হচ্ছে…'}</small></div></section>

    <section className="metric-grid">
      <article className="card metric"><div className="metric-top"><span>PRIMARY TIMEFRAME</span><Activity size={17}/></div><b>1 HOUR</b><small>Direction & trade plan source</small></article>
      <article className="card metric"><div className="metric-top"><span>4H MACRO</span><Waves size={17}/></div><b>CONTEXT FILTER</b><small>Higher timeframe confirmation</small></article>
      <article className="card metric"><div className="metric-top"><span>15M SETUP</span><Layers3 size={17}/></div><b>CONFIRMATION</b><small>Structure alignment required</small></article>
      <article className="card metric"><div className="metric-top"><span>5M ENTRY</span><Target size={17}/></div><b>OPTIONAL</b><small>Never owns trade direction</small></article>
    </section>

    <ChartPanel timeframe={tf} setTimeframe={setTf} candles={candles} loading={loading} onReload={()=>loadCandles(tf)} report={report} dataKind={dataKind}/>
    <section className="card import-card">
      <div className="section-head"><div><span className="eyebrow">HISTORICAL DATA IMPORT</span><h2>MT5 / CSV Candle Upload</h2></div><Upload size={19}/></div>
      <p>উপরের নির্বাচিত Timeframe-এ CSV Import হবে। Header: <code>time,open,high,low,close,volume</code>। Time Unix seconds/milliseconds অথবা ISO timestamp হতে পারে।</p>
      <div className="import-actions"><input ref={fileRef} type="file" accept=".csv,text/csv" onChange={e=>importFile(e.target.files?.[0])}/><span>{importing?'Import হচ্ছে…':(counts[tf]||0)+' saved candles · '+tf.toUpperCase()}</span></div>
      {message&&<div className="notice">{message}</div>}
    </section>

    <section className="card report-card">
      <div className="section-head"><div><span className="eyebrow">MULTI-TIMEFRAME DECISION ENGINE</span><h2>১ ঘণ্টার Gold Trade Report</h2></div><button className="action-btn" onClick={runReport}>Run Analysis</button></div>
      {!report?<div className="empty-state"><ShieldCheck size={22}/><b>Analysis চালানোর জন্য প্রস্তুত</b><span>4H, 1H ও 15M-এ অন্তত ৫০টি করে Candle থাকলে Engine পূর্ণ রিপোর্ট তৈরি করতে পারবে।</span></div>:
        <div className="report-result"><div className={'decision '+(decision.decision==='BUY'?'buy':decision.decision==='SELL'?'sell':'wait')}>{decision.decision||'WAIT'}</div>
          <div><b>Primary: 1H · 4H Macro · 15M Setup · 5M Optional</b><p>{decision.note||report.disclaimer}</p></div>
          <div className="reason-list"><b>Decision Reasons</b>{(decision.reason_codes||[]).map(x=><span key={x}>{x}</span>)}</div>
          {plan&&<div className="risk-grid"><span>Entry {plan.entry?.join(' – ')}</span><span>SL {plan.stop_loss}</span>{(plan.targets||[]).map((x,i)=><span key={i}>TP{i+1} {x}</span>)}</div>}
          <small>{report.disclaimer}</small>
        </div>}
    </section>

    <section className="lower-grid">
      <article className="card"><div className="section-head"><div><span className="eyebrow">ZONE RADAR</span><h2>Supply & Demand</h2></div><Layers3 size={19}/></div>
        <div className="empty-state"><AlertTriangle size={22}/><b>Initial 1H SMC Levels</b><span>1H swing high/low, FVG, OB candidates and EQH/EQL are drawn on the main price chart. Full shaded zones and replay validation remain pending.</span></div></article>
      <article className="card"><div className="section-head"><div><span className="eyebrow">DATA INTEGRITY</span><h2>Feed & Execution</h2></div><ShieldCheck size={19}/></div>
        <div className="empty-state"><Radio size={22}/><b>Live feed not connected</b><span>Historical CSV data is supported. {config?.live_data?'MT5 bridge is recently connected.':'Live MT5 bridge is not currently active.'} Spread: {quoteInfo?.spread_points??'—'} points / limit {quoteInfo?.max_spread_points??'not configured'}. Commission and slippage model remain pending.</span></div></article>
    </section>
    <footer><span><Clock3 size={13}/> BUILD 0.4.0 · 1H PRIMARY</span><span>Historical analysis only · No broker orders are placed</span></footer>
  </main>;
}
