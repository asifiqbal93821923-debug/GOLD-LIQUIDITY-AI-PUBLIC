import { useCallback, useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, ColorType } from 'lightweight-charts';
import { Activity, AlertTriangle, BarChart3, CandlestickChart, Clock3, Layers3, Radio, ShieldCheck, Target, Waves, Upload, RefreshCw } from 'lucide-react';

const timeframes=['3m','5m','15m','30m','1h','4h','1D'];
const labels={ '3m':'৩ মিনিট','5m':'৫ মিনিট','15m':'১৫ মিনিট','30m':'৩০ মিনিট','1h':'১ ঘণ্টা','4h':'৪ ঘণ্টা','1D':'১ দিন' };
const API='';
const ZONE_COLORS={bullish:'#27bd91',bearish:'#e16f7a'};

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


const FREE_INTRADAY_URL='https://xaus.com/api/v1/intraday?symbol=xau&hours=48';
const FREE_BUCKET_SECONDS={'5m':300,'15m':900,'30m':1800,'1h':3600,'4h':14400,'1D':86400};
async function loadFreePublicGoldCandles(frame){
  if(frame==='3m') throw new Error('ফ্রি পাবলিক Feed ৩ মিনিটের ডেটা দেয় না। ৫M বা ১৫M বেছে নিন।');
  // Prefer the cumulative scheduled archive, then the latest snapshot, then direct XAUS.
  let payload=null, snapshotSource='scheduled_history_archive';
  for(const file of ['market-history.json','market-snapshot.json']){
    try{
      const response=await fetch(import.meta.env.BASE_URL+'data/'+file,{cache:'no-store',headers:{Accept:'application/json'}});
      if(response.ok){
        const candidate=await response.json();
        if(Array.isArray(candidate.points)&&candidate.points.length){payload=candidate;break;}
      }
    }catch(_){}
  }
  if(!payload){
    snapshotSource='direct_public_api';
    const response=await fetch(FREE_INTRADAY_URL,{headers:{Accept:'application/json'}});
    if(!response.ok) throw new Error('ফ্রি Gold Feed unavailable: HTTP '+response.status);
    payload=await response.json();
  }
  const points=Array.isArray(payload.points)?payload.points:[];
  const clean=points.map(p=>({time:Number(p.t),price:Number(p.p)}))
    .filter(p=>Number.isFinite(p.time)&&Number.isFinite(p.price)&&p.price>0)
    .sort((a,b)=>a.time-b.time);
  if(clean.length<3) throw new Error('ফ্রি Feed-এ পর্যাপ্ত sampled price নেই।');
  const latestAge=Date.now()/1000-clean[clean.length-1].time;
  if(latestAge<0||latestAge>900) throw new Error('ফ্রি Feed-এর সর্বশেষ sample ১৫ মিনিটের বেশি পুরোনো; stale data দেখানো বন্ধ রাখা হয়েছে।');
  const bucket=FREE_BUCKET_SECONDS[frame];
  if(!bucket) throw new Error('এই timeframe-এর জন্য ফ্রি Feed সমর্থিত নয়।');
  const grouped=new Map();
  for(const p of clean){
    const start=Math.floor(p.time/bucket)*bucket;
    const row=grouped.get(start);
    if(!row) grouped.set(start,{time:start,open:p.price,high:p.price,low:p.price,close:p.price,volume:0});
    else {row.high=Math.max(row.high,p.price);row.low=Math.min(row.low,p.price);row.close=p.price;}
  }
  const rows=[...grouped.values()].sort((a,b)=>a.time-b.time);
  return {rows,source:'free_public_sampled',sampleAge:Math.round(latestAge),state:payload.data_state?.status||'unknown',feedSource:snapshotSource};
}

function ChartPanel({timeframe,setTimeframe,candles,loading,onReload,report,dataKind}){
  const host=useRef(null); const chartRef=useRef(null); const seriesRef=useRef(null); const priceLinesRef=useRef([]); const [zoneRects,setZoneRects]=useState([]); const [chartError,setChartError]=useState('');
  useEffect(()=>{
    if(!host.current) return;
    let chart=null, stopResize=()=>{};
    try {
      const width=Math.max(280,host.current.clientWidth||320);
      const height=Math.max(180,host.current.clientHeight||240);
      chart=createChart(host.current,{width,height,
        layout:{background:{type:ColorType.Solid,color:'#0d1420'},textColor:'#91a0b5',attributionLogo:false},
        grid:{vertLines:{color:'#172232'},horzLines:{color:'#172232'}},
        rightPriceScale:{borderColor:'#263449'},timeScale:{borderColor:'#263449',timeVisible:true,secondsVisible:false},
        crosshair:{vertLine:{color:'#61748c'},horzLine:{color:'#61748c'}}});
      const series=chart.addSeries(CandlestickSeries,{upColor:'#21b78a',downColor:'#ed6675',
        borderUpColor:'#21b78a',borderDownColor:'#ed6675',wickUpColor:'#21b78a',wickDownColor:'#ed6675'});
      chartRef.current=chart; seriesRef.current=series;
      const resize=()=>{if(!chart||!host.current)return;chart.applyOptions({width:Math.max(280,host.current.clientWidth||320),height:Math.max(180,host.current.clientHeight||240)});chart.timeScale().fitContent();};
      if(typeof ResizeObserver!=='undefined'){const observer=new ResizeObserver(resize);observer.observe(host.current);stopResize=()=>observer.disconnect();}
      else {window.addEventListener('resize',resize);stopResize=()=>window.removeEventListener('resize',resize);}
      resize();
    } catch(error) {
      console.error('Chart initialization failed:',error);
      setChartError(error?.message||'Chart initialization failed');
      try{chart?.remove();}catch(_){}
      chartRef.current=null;seriesRef.current=null;
    }
    return ()=>{stopResize();try{chart?.remove();}catch(_){}chartRef.current=null;seriesRef.current=null;};
  },[]);
  useEffect(()=>{
    if(!seriesRef.current) return;
    const data=candles.map(c=>({time:c.time,open:c.open,high:c.high,low:c.low,close:c.close}));
    try { seriesRef.current.setData(data); chartRef.current?.timeScale().fitContent(); } catch(e) { console.error('Chart data rejected',e); }
  },[candles]);
  useEffect(()=>{
    const chart=chartRef.current, series=seriesRef.current, el=host.current;
    if(!chart||!series||!el) return;
    const ts=chart.timeScale();
    const specs=[];
    for(const tf of ['4h','1h','15m']){
      const smc=report?.timeframes?.[tf]?.smc;
      (smc?.zones||[]).filter(z=>z.status==='active'&&Number.isFinite(z.start_time)&&z.high>z.low)
        .slice(-5).forEach((z,i)=>specs.push({...z,timeframe:tf,id:tf+'-'+z.zone_type+'-'+i}));
    }
    const update=()=>{
      const width=el.clientWidth, height=el.clientHeight;
      const first=candles[0]?.time, last=candles[candles.length-1]?.time;
      const next=specs.map(z=>{
        if(first==null||last==null||z.start_time>last) return null;
        const rawX=ts.timeToCoordinate(z.start_time);
        const x=rawX==null?(z.start_time<first?0:null):Math.max(0,rawX);
        const y1=series.priceToCoordinate(z.high), y2=series.priceToCoordinate(z.low);
        if(x==null||y1==null||y2==null||y2<0||y1>height) return null;
        const color=ZONE_COLORS[z.direction]||'#8da0b8';
        return {id:z.id,left:x,top:Math.max(0,Math.min(y1,y2)),width:Math.max(0,width-x-64),
          height:Math.max(2,Math.min(height,Math.max(y1,y2))-Math.max(0,Math.min(y1,y2))),
          color,label:(z.timeframe.toUpperCase()+' '+(z.zone_type==='fvg'?'FVG':'OB')+' '+(z.direction==='bullish'?'DEMAND':'SUPPLY'))};
      }).filter(Boolean);
      setZoneRects(next);
    };
    update();
    let stopResize=()=>{};
    if(typeof ResizeObserver!=='undefined'){const observer=new ResizeObserver(update);observer.observe(el);stopResize=()=>observer.disconnect();}
    else {window.addEventListener('resize',update);stopResize=()=>window.removeEventListener('resize',update);}
    ts.subscribeVisibleLogicalRangeChange(update);
    return ()=>{stopResize();ts.unsubscribeVisibleLogicalRangeChange(update);};
  },[report,candles]);
  useEffect(()=>{
    if(!seriesRef.current) return;
    priceLinesRef.current.forEach(line=>{try{seriesRef.current.removePriceLine(line);}catch(e){}});
    priceLinesRef.current=[];
    const frames=report && report.timeframes;
    const smc=frames && frames['1h'] && frames['1h'].smc;
    const macro=frames && frames['4h'] && frames['4h'].smc;
    const add=(price,title,color,lineStyle=2)=>{
      if(typeof price!=='number'||!Number.isFinite(price)) return;
      priceLinesRef.current.push(seriesRef.current.createPriceLine({price,title,color,lineWidth:1,lineStyle,axisLabelVisible:true}));
    };
    if(macro&&macro.status==='ok'){
      add(macro.swing_high&&macro.swing_high.price,'4H Macro High','#c88b55',2);
      add(macro.swing_low&&macro.swing_low.price,'4H Macro Low','#66a6a0',2);
    }
    if(!smc||smc.status!=='ok') return;
    add(smc.swing_high && smc.swing_high.price,'1H Swing High','#e36c75');
    add(smc.swing_low && smc.swing_low.price,'1H Swing Low','#42b99b');
    (smc.active_fvgs||[]).slice(-4).forEach((z,i)=>{add(z.low,'1H FVG '+(i+1)+' L','#6f9fe8',1);add(z.high,'1H FVG '+(i+1)+' H','#6f9fe8',1);});
    (smc.order_block_candidates||[]).slice(-3).forEach((z,i)=>{const color=z.direction==='bullish'?'#36b995':'#d77b83';add(z.low,'1H OB '+(i+1)+' L',color,2);add(z.high,'1H OB '+(i+1)+' H',color,2);});
    (smc.equal_high_pools||[]).slice(-3).forEach((z,i)=>add(z.price,'1H EQH '+(i+1),'#d8ad69',1));
    (smc.equal_low_pools||[]).slice(-3).forEach((z,i)=>add(z.price,'1H EQL '+(i+1),'#d8ad69',1));
  },[report,candles]);
  return <section className="card chart-card">
    <div className="section-head"><div><span className="eyebrow">PRICE ACTION · XAUUSD</span><h2>Gold Spot <span className="muted">· Main Trading TF: 1H</span></h2></div>
      <span className={'data-pill '+(candles.length?'data-ready':'')}><i/> {candles.length?(dataKind==='mt5_bridge'?'MT5 BRIDGE':dataKind==='free_public_sampled'?'FREE PUBLIC · SAMPLED':'HISTORICAL DATA'):'NO DATA'}</span></div>
    <div className="tf-row">{timeframes.map(t=><button key={t} className={timeframe===t?'tf active':'tf'} onClick={()=>setTimeframe(t)}>{t.toUpperCase()}</button>)}
      <button className="tf reload" onClick={onReload} disabled={loading}><RefreshCw size={13}/> Reload</button></div>
    <div ref={host} className="chart-host" aria-label="XAUUSD historical candlestick chart">
      <div className="zone-overlay">{zoneRects.map(z=><div key={z.id} className="zone-rect" style={{left:z.left,top:z.top,width:z.width,height:z.height,borderColor:z.color,background:z.color+'22'}}>
        <span style={{color:z.color}}>{z.label}</span></div>)}</div>
    </div>
    {chartError&&<div className="chart-overlay"><AlertTriangle size={22}/><b>চার্ট মডিউল শুরু করা যায়নি</b><span>{chartError}</span></div>}
    {!candles.length&&!chartError&&<div className="chart-overlay"><CandlestickChart size={25}/><b>{loading?'Candle লোড হচ্ছে…':'এই Timeframe-এর Candle Data নেই'}</b><span>MT5 বা CSV থেকে Historical Candle Import করুন। কোনো Synthetic Price দেখানো হচ্ছে না।</span></div>}
    <div className="chart-foot">চার্ট: {labels[timeframe]} · {candles.length} candles · {dataKind==='mt5_bridge'?'Recent MT5 closed candles':dataKind==='free_public_sampled'?'XAUS public 5-minute samples aggregated to '+timeframe.toUpperCase()+' (indicative, not XM ticks)':'Historical import only'} · Active candle-derived zones: {zoneRects.length}</div>
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
  const [backtest,setBacktest]=useState(null);
  const [backtestBusy,setBacktestBusy]=useState(false);
  const [mtfBacktest,setMtfBacktest]=useState(null);
  const [mtfBusy,setMtfBusy]=useState(false);
  const [costs,setCosts]=useState({point_size:0.01,spread_points:20,slippage_points:5,commission_points_per_side:0});
  const [quoteInfo,setQuoteInfo]=useState(null);
  const [importing,setImporting]=useState(false);
  const fileRef=useRef(null);

  const loadCandles=useCallback(async (frame=tf)=>{
    setLoading(true); setMessage('');
    try{
      let rows=[],kind='historical_import';
      try{
        const res=await fetch(API+'/api/market/candles?timeframe='+encodeURIComponent(frame)+'&limit=3000');
        if(res.ok){
          const data=await res.json();
          rows=data.data||[];
          kind=data.data_kind||'historical_import';
        }
      }catch(_){}
      if(!rows.length){
        const free=await loadFreePublicGoldCandles(frame);
        rows=free.rows;kind=free.source;
        setMessage('ফ্রি পাবলিক Gold Feed চলছে ('+(free.feedSource==='scheduled_snapshot'?'GitHub Actions snapshot':'direct XAUS fallback')+'): ৫-মিনিটে সংগৃহীত sample থেকে '+frame.toUpperCase()+' bar তৈরি। এটি XM Broker Tick/আসল OHLCV নয়; ট্রেড execution-এর জন্য ব্যবহার করবেন না।');
      }
      setCandles(rows);setDataKind(kind);setCounts(old=>({...old,[frame]:rows.length}));
      return rows;
    }catch(e){
      setMessage('ডেটা লোড করা যায়নি: '+e.message);setCandles([]);setDataKind('historical_import');return [];
    }finally{setLoading(false);}
  },[tf]);

  useEffect(()=>{fetch('/api/health').then(r=>r.ok?r.json():Promise.reject()).then(()=>setApi('online')).catch(()=>setApi('offline'));
    fetch('/api/config/status').then(r=>r.ok?r.json():null).then(setConfig).catch(()=>setConfig(null));},[]);
  useEffect(()=>{loadCandles(tf);},[tf,loadCandles]);


  useEffect(()=>{
    const timer=window.setInterval(()=>{
      loadCandles(tf);
      fetch('/api/config/status').then(r=>r.ok?r.json():null).then(setConfig).catch(()=>{});
      fetch('/api/market/quote').then(r=>r.ok?r.json():null).then(setQuoteInfo).catch(()=>{});
    },30000);
    return ()=>window.clearInterval(timer);
  },[tf,loadCandles]);

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


  const runBacktest=async()=>{
    setBacktest(null);setMessage('');
    try{
      const res=await fetch('/api/market/candles?timeframe=1h&limit=5000');
      const d=await res.json();
      if((d.data||[]).length<50) throw new Error('Backtest-এর জন্য অন্তত ৫০টি ১H Candle Import করুন।');
      const result=await fetch('/api/backtest/alpha-1h',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({candles:d.data,costs})});
      const data=await result.json();if(!result.ok)throw new Error(data.detail||'Backtest failed');
      setBacktest(data);
    }catch(e){setMessage('Backtest Error: '+e.message);}
  };



  const runMtfBacktest=async()=>{
    setMtfBusy(true);setMtfBacktest(null);setMessage('');
    try{
      const frames={};
      for(const frame of ['4h','1h','15m','5m']){
        const res=await fetch('/api/market/candles?timeframe='+frame+'&limit=3000');
        const d=await res.json();frames[frame]=d.data||[];
      }
      for(const frame of ['4h','1h','15m']) if(frames[frame].length<50) throw new Error(frame.toUpperCase()+'-এ অন্তত ৫০টি Candle দরকার।');
      if(frames['5m'].length<30) delete frames['5m'];
      const res=await fetch('/api/backtest/gold-mtf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({timeframes:frames,costs})});
      const data=await res.json();if(!res.ok)throw new Error(data.detail||data.reason||'MTF backtest failed');setMtfBacktest(data);
    }catch(e){setMessage('MTF Backtest Error: '+e.message);}
    finally{setMtfBusy(false);}
  };

  const decision=report?.decision||{};
  const plan=decision.trade_plan;
  return <main className="shell">
    <header className="topbar"><div className="brand"><div className="brand-mark"><BarChart3 size={21}/></div><div><b>PROJECT INDICATOR APP</b><small>GOLD MARKET INTELLIGENCE</small></div></div>
      <div className="top-status"><span className={'api-dot '+api}/><span>API {api.toUpperCase()}</span><span className="divider-v"/><span className="mode-label">1H PRIMARY TERMINAL</span></div></header>
    <section className="welcome"><div><span className="eyebrow">WORKSPACE · XAUUSD</span><h1>See the market.<br/><em>Understand the move.</em></h1>
      <p>৪H Macro · ১H Main Trading · ১৫M Setup · ৫M Optional Entry Confirmation</p></div>
      <div className="session-card"><span className="eyebrow">DATA STATUS</span><strong><Radio size={17}/> {config?.live_data?'LIVE MT5':dataKind==='free_public_sampled'?'FREE PUBLIC SAMPLE':'HISTORICAL MODE'}</strong>
        <small>{dataKind==='free_public_sampled'?'XAUS-এর ৫-মিনিট sampled XAU spot; XM quote নয়, indicative only.':config?.message||'API status যাচাই হচ্ছে…'}</small></div></section>

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



    <section className="card report-card">
      <div className="section-head"><div><span className="eyebrow">HISTORICAL REPLAY · 1H ONLY</span><h2>Alpha Signal Research Backtest</h2></div><div className="backtest-actions"><button className="action-btn" onClick={runBacktest}>Run 1H Alpha</button><button className="action-btn secondary" onClick={runMtfBacktest} disabled={mtfBusy}>{mtfBusy?"Replay…":"Run Full MTF Replay"}</button></div></div>
      <p className="backtest-note">এটি শুধু Alpha Signal Engine-এর ১H flip replay; সম্পূর্ণ 4H/1H/15M Gold Report strategy নয়। Broker-এর প্রকৃত execution cost বসাও।</p>
      <div className="cost-inputs">
        <label>Point Size<input type="number" min="0.000001" step="0.001" value={costs.point_size} onChange={e=>setCosts(v=>({...v,point_size:Number(e.target.value)}))}/></label>
        <label>Spread (points)<input type="number" min="0" step="1" value={costs.spread_points} onChange={e=>setCosts(v=>({...v,spread_points:Number(e.target.value)}))}/></label>
        <label>Slippage (points)<input type="number" min="0" step="1" value={costs.slippage_points} onChange={e=>setCosts(v=>({...v,slippage_points:Number(e.target.value)}))}/></label>
        <label>Commission / side (points)<input type="number" min="0" step="1" value={costs.commission_points_per_side} onChange={e=>setCosts(v=>({...v,commission_points_per_side:Number(e.target.value)}))}/></label>
      </div>
      {!backtest?<div className="empty-state"><Activity size={22}/><b>১H Alpha Flip Replay</b><span>অন্তত ৫০টি ১H Historical Candle Import করে Backtest চালাও।</span></div>:
        <div className="backtest-result"><div className="backtest-grid">
          <span>Trades <b>{backtest.trade_count}</b></span><span>Win Rate <b>{backtest.win_rate_pct}%</b></span><span>Net PnL <b>{backtest.net_pnl_price}</b></span><span>Average R <b>{backtest.average_R}</b></span><span>Profit Factor <b>{backtest.profit_factor??'—'}</b></span><span>Max Drawdown <b>{backtest.max_drawdown_price}</b></span>
        </div><small>{backtest.scope_warning||backtest.reason||backtest.execution_model}</small></div>}
      <div className="mtf-backtest">
        <b>FULL GOLD REPORT · 4H / 1H / 15M · OPTIONAL 5M</b>
        {!mtfBacktest?<small>৪H Macro, ১H Primary, ১৫M Setup এবং থাকলে ৫M refinement ধরে causal historical replay চালাও।</small>:
          <><div className="backtest-grid"><span>Trades <b>{mtfBacktest.trade_count}</b></span><span>Win Rate <b>{mtfBacktest.win_rate_pct}%</b></span><span>Net PnL <b>{mtfBacktest.net_pnl_price}</b></span><span>Average R <b>{mtfBacktest.average_R}</b></span><span>Profit Factor <b>{mtfBacktest.profit_factor??'—'}</b></span><span>Max DD <b>{mtfBacktest.max_drawdown_price}</b></span></div><small>Evaluated {mtfBacktest.signals_evaluated} · Accepted {mtfBacktest.accepted_signals} · Veto reasons: {JSON.stringify(mtfBacktest.veto_counts||{})}</small><small>{mtfBacktest.scope_warning}</small></>}
      </div>
    </section>

    <section className="lower-grid">
      <article className="card"><div className="section-head"><div><span className="eyebrow">ZONE RADAR</span><h2>Supply & Demand</h2></div><Layers3 size={19}/></div>
        <div className="zone-radar-list">{['4h','1h','15m'].flatMap(frame=>(report?.timeframes?.[frame]?.smc?.zones||[]).slice(-4).map((z,i)=>
          <div className="zone-radar-row" key={frame+'-'+i+'-'+z.zone_type+'-'+z.direction}>
            <b>{frame.toUpperCase()} · {z.zone_type==='fvg'?'FVG':'ORDER BLOCK'}</b>
            <span>{z.direction==='bullish'?'DEMAND':'SUPPLY'} · {z.status?.toUpperCase()}</span>
            <small>{Number(z.low).toFixed(2)} – {Number(z.high).toFixed(2)} {z.start_time?('· '+new Date(z.start_time*1000).toLocaleString()):'· timestamp unavailable'}</small>
          </div>))}
          {!report&&<div className="empty-state"><AlertTriangle size={22}/><b>Analysis চালালে জোন দেখা যাবে</b><span>4H macro, 1H primary এবং 15M setup থেকে candle-derived FVG ও Order Block zone তৈরি হবে।</span></div>}
          {report&&!['4h','1h','15m'].some(frame=>(report?.timeframes?.[frame]?.smc?.zones||[]).length>0)&&<div className="empty-state"><AlertTriangle size={22}/><b>কোনো confirmed zone নেই</b><span>পর্যাপ্ত valid candle বা confirmed structure না থাকলে জোন দেখানো হবে না।</span></div>}
        </div><small className="zone-disclaimer">জোনগুলো OHLCV candle-derived proxy; আসল institutional pending orders নয়। শুধু ACTIVE জোন চার্টে shaded overlay হিসেবে দেখানো হয়।</small></article>
      <article className="card"><div className="section-head"><div><span className="eyebrow">DATA INTEGRITY</span><h2>Feed & Execution</h2></div><ShieldCheck size={19}/></div>
        <div className="empty-state"><Radio size={22}/><b>{config?.live_data?'MT5 Bridge Connected':'Live feed not connected'}</b><span>Historical CSV data is supported. {config?.live_data?'MT5 bridge is recently connected.':'Live MT5 bridge is not currently active.'} Spread: {quoteInfo?.spread_points??'—'} points / limit {quoteInfo?.max_spread_points??'not configured'}. Backtest-এ spread, commission ও slippage assumptions দেওয়া যায়; broker-এর আসল fee schedule এখনও যাচাই করা হয়নি.</span></div></article>
    </section>
    <footer><span><Clock3 size={13}/> BUILD 0.4.0 · 1H PRIMARY</span><span>Closed-candle analysis only · No broker orders are placed</span></footer>
  </main>;
}
