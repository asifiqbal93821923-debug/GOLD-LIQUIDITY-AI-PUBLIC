import { useCallback, useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, ColorType } from 'lightweight-charts';
import { Activity, AlertTriangle, BarChart3, Bell, CandlestickChart, Clock3, Layers3, Radio, Save, Settings2, ShieldCheck, Target, Waves, Upload, RefreshCw } from 'lucide-react';

const timeframes=['3m','5m','15m','30m','1h','4h','1D'];
const labels={ '3m':'৩ মিনিট','5m':'৫ মিনিট','15m':'১৫ মিনিট','30m':'৩০ মিনিট','1h':'১ ঘণ্টা','4h':'৪ ঘণ্টা','1D':'১ দিন' };
let API_BASE=(import.meta.env.VITE_API_BASE_URL||'').trim();
while(API_BASE.endsWith('/')) API_BASE=API_BASE.slice(0,-1);
const apiUrl=path=>API_BASE+(path.startsWith('/')?path:'/'+path);
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
  const candidates=[];
  for(const file of ['market-history.json','market-snapshot.json']){
    try{
      const response=await fetch(import.meta.env.BASE_URL+'data/'+file,{cache:'no-store',headers:{Accept:'application/json'}});
      if(response.ok){
        const candidate=await response.json();
        if(Array.isArray(candidate.points)&&candidate.points.length)candidates.push({payload:candidate,source:file==='market-history.json'?'scheduled_history_archive':'scheduled_snapshot'});
      }
    }catch(_){}
  }
  try{
    const response=await fetch(FREE_INTRADAY_URL,{cache:'no-store',headers:{Accept:'application/json'}});
    if(response.ok)candidates.push({payload:await response.json(),source:'direct_public_api'});
  }catch(_){}
  let selected=null, lastIssue='কোনো Feed Source থেকে ডেটা পাওয়া যায়নি।';
  for(const candidate of candidates){
    const raw=Array.isArray(candidate.payload.points)?candidate.payload.points:[];
    const byTime=new Map();
    for(const point of raw){
      const time=Number(point?.t),price=Number(point?.p);
      if(Number.isSafeInteger(Math.floor(time))&&Number.isFinite(time)&&Number.isFinite(price)&&time>0&&price>0)byTime.set(Math.floor(time),price);
    }
    const clean=[...byTime.entries()].map(([time,price])=>({time,price})).sort((a,b)=>a.time-b.time);
    if(clean.length<3){lastIssue='Feed-এ অন্তত ৩টি valid sample নেই।';continue;}
    const latestAge=Date.now()/1000-clean[clean.length-1].time;
    if(latestAge<0||latestAge>900){lastIssue='Feed-এর সর্বশেষ sample stale বা future timestamp।';continue;}
    selected={payload:candidate.payload,clean,latestAge,source:candidate.source};break;
  }
  if(!selected)throw new Error(lastIssue+' Stale data ব্যবহার করা হয়নি।');
  const {payload,clean,latestAge,source}=selected;
  const bucket=FREE_BUCKET_SECONDS[frame];
  if(!bucket)throw new Error('এই timeframe-এর জন্য ফ্রি Feed সমর্থিত নয়।');
  const grouped=new Map();
  for(const p of clean){
    const start=Math.floor(p.time/bucket)*bucket;
    const row=grouped.get(start);
    if(!row)grouped.set(start,{time:start,open:p.price,high:p.price,low:p.price,close:p.price,volume:0});
    else{row.high=Math.max(row.high,p.price);row.low=Math.min(row.low,p.price);row.close=p.price;}
  }
  const rows=[...grouped.values()].sort((a,b)=>a.time-b.time);
  if(rows.length<2)throw new Error('এই Timeframe-এ যথেষ্ট sampled candle নেই।');
  return {rows,source:'free_public_sampled',sampleAge:Math.round(latestAge),state:payload.data_state?.status||'unknown',feedSource:source};
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
  const [quoteInfo,setQuoteInfo]=useState(null);
  const [importing,setImporting]=useState(false);
  const [riskSettings,setRiskSettings]=useState({account_balance:null,contract_size:null,risk_percent:0.5,max_daily_loss_percent:2,max_trades_per_day:3,max_open_trades:1,cooldown_minutes:60,min_reward_risk:1.0,max_spread_points:null});
  const [riskSaving,setRiskSaving]=useState(false);
  const [signalEvents,setSignalEvents]=useState([]);
  const [notificationPermission,setNotificationPermission]=useState(typeof window!=='undefined'&&'Notification' in window?Notification.permission:'unsupported');
  const [phase4Report,setPhase4Report]=useState(null);
  const [phase4Busy,setPhase4Busy]=useState(false);
  const [phase4Provider,setPhase4Provider]=useState('');
  const [phase4Timezone,setPhase4Timezone]=useState('UTC');
  const [phase4SameFeed,setPhase4SameFeed]=useState(false);
  const [phase4Costs,setPhase4Costs]=useState({point_size:0.01,spread_points:0,slippage_points:0,commission_points_per_side:0,max_spread_points:0});
  const [phase5Status,setPhase5Status]=useState(null);
  const [phase5Settings,setPhase5Settings]=useState({enabled:false,max_spread_points:'',slippage_points:0,commission_points_per_side:0});
  const [phase5Busy,setPhase5Busy]=useState(false);
  const phase5Loaded=useRef(false);
  const seenSignalIds=useRef(new Set());
  const firstAlertsLoad=useRef(false);
  const fileRef=useRef(null);

  const loadCandles=useCallback(async (frame=tf)=>{
    setLoading(true); setMessage('');
    try{
      let rows=[],kind='historical_import';
      try{
        const res=await fetch(apiUrl('/api/market/candles?timeframe='+encodeURIComponent(frame)+'&limit=3000'));
        if(res.ok){
          const data=await res.json();
          rows=data.data||[];
          kind=data.data_kind||'historical_import';
        }
      }catch(_){}
      if(!rows.length){
        const free=await loadFreePublicGoldCandles(frame);
        rows=free.rows;kind=free.source;
        setMessage('ফ্রি পাবলিক Gold Feed চলছে ('+({scheduled_history_archive:'GitHub Actions Historical Archive',scheduled_snapshot:'GitHub Actions Snapshot',direct_public_api:'Direct XAUS Fallback'}[free.feedSource]||free.feedSource)+'): সর্বশেষ sample '+free.sampleAge+' সেকেন্ড পুরোনো। ৫-মিনিটে সংগৃহীত indicative sample থেকে '+frame.toUpperCase()+' bar তৈরি। এটি XM Broker Tick/আসল OHLCV নয়; ট্রেড execution-এর জন্য ব্যবহার করবেন না।');
      }
      setCandles(rows);setDataKind(kind);setCounts(old=>({...old,[frame]:rows.length}));
      return rows;
    }catch(e){
      setMessage('ডেটা লোড করা যায়নি: '+e.message);setCandles([]);setDataKind('historical_import');return [];
    }finally{setLoading(false);}
  },[tf]);

  useEffect(()=>{fetch(apiUrl('/api/health')).then(r=>r.ok?r.json():Promise.reject()).then(()=>setApi('online')).catch(()=>setApi('offline'));
    fetch(apiUrl('/api/config/status')).then(r=>r.ok?r.json():null).then(setConfig).catch(()=>setConfig(null));},[]);
  useEffect(()=>{loadCandles(tf);},[tf,loadCandles]);


  const refreshPhase3Records=useCallback(async(notifyNew=false)=>{
    try{
      const [riskRes,alertsRes]=await Promise.all([
        fetch(apiUrl('/api/risk/settings')),
        fetch(apiUrl('/api/alerts?limit=30'))
      ]);
      if(riskRes.ok){const risk=await riskRes.json();if(risk.settings)setRiskSettings(risk.settings);}
      if(alertsRes.ok){
        const alerts=await alertsRes.json();
        const events=alerts.events||[];
        if(!firstAlertsLoad.current){
          events.forEach(event=>seenSignalIds.current.add(event.id));
          firstAlertsLoad.current=true;
        }else if(notifyNew&&typeof Notification!=='undefined'&&Notification.permission==='granted'){
          events.filter(event=>!seenSignalIds.current.has(event.id)).forEach(event=>{
            seenSignalIds.current.add(event.id);
            try{new Notification('GOLD TERMINAL · '+event.direction,{body:'XAUUSD '+event.direction+' · '+Number(event.price||0).toFixed(2)+' · 1H confirmed signal'});}catch(_){}
          });
        }
        events.forEach(event=>seenSignalIds.current.add(event.id));
        setSignalEvents(events);
      }
    }catch(_){}
  },[]);

  useEffect(()=>{refreshPhase3Records(false);},[refreshPhase3Records]);
  useEffect(()=>{
    loadPhase5Status();
    const timer=window.setInterval(loadPhase5Status,20000);
    return ()=>window.clearInterval(timer);
  },[loadPhase5Status]);


  useEffect(()=>{
    const timer=window.setInterval(()=>{
      loadCandles(tf);
      fetch(apiUrl('/api/config/status')).then(r=>r.ok?r.json():null).then(setConfig).catch(()=>{});
      fetch(apiUrl('/api/market/quote')).then(r=>r.ok?r.json():null).then(setQuoteInfo).catch(()=>{});
      refreshPhase3Records(true);
    },30000);
    return ()=>window.clearInterval(timer);
  },[tf,loadCandles,refreshPhase3Records]);

  const importFile=async file=>{
    if(!file)return;
    setImporting(true);setMessage('');
    try{
      const rows=parseCsv(await file.text());
      const res=await fetch(apiUrl('/api/market/candles/import'),{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({symbol:'XAUUSD',timeframe:tf,source:'CSV: '+file.name,candles:rows})});
      const result=await res.json();
      if(!res.ok) throw new Error(result.detail||result.message||'Import failed');
      setMessage('সফল: '+result.stored+'টি '+tf.toUpperCase()+' Candle সংরক্ষণ হয়েছে।');
      await loadCandles(tf);
      refreshPhase3Records(false);
    }catch(e){setMessage('Import Error: '+e.message);}
    finally{setImporting(false);if(fileRef.current)fileRef.current.value='';}
  };

  const runReport=async()=>{
    setMessage('');setReport(null);
    try{
      const frames={};let allFresh=true;
      for(const frame of ['4h','1h','15m']){
        const res=await fetch(apiUrl('/api/market/candles?timeframe='+frame+'&limit=1000'));
        const d=await res.json();frames[frame]=d.data||[];if(d.live!==true) allFresh=false;
      }
      const quoteRes=await fetch(apiUrl('/api/market/quote'));const quote=await quoteRes.json();setQuoteInfo(quote);
      const res=await fetch(apiUrl('/api/analysis/gold-report'),{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({timeframes:frames,data_fresh:allFresh,spread_acceptable:quote.acceptable===true})});
      const data=await res.json();if(!res.ok)throw new Error(data.detail||'Report failed');setReport(data);await refreshPhase3Records(true);
    }catch(e){setMessage('Analysis Error: '+e.message);}
  };


  const decision=report?.decision||{};
  const plan=decision.trade_plan;

  const runPhase4Validation=async()=>{
    setPhase4Busy(true);setPhase4Report(null);setMessage('');
    try{
      const frames={};
      for(const frame of ['4h','1h','15m','5m']){
        const res=await fetch(apiUrl('/api/market/candles?timeframe='+frame+'&limit=6000'));
        if(!res.ok)throw new Error(frame.toUpperCase()+' history fetch failed ('+res.status+').');
        const data=await res.json();frames[frame]=data.data||[];
      }
      const response=await fetch(apiUrl('/api/research/phase4-validation'),{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          timeframes:frames,
          metadata:{symbol:'XAUUSD',provider:phase4Provider,timezone:phase4Timezone,
            same_feed_confirmed:phase4SameFeed,source:'app historical store',
            attestation:'user supplied; not independently verified'},
          costs:{...phase4Costs,require_spread_limit:true},folds:4
        })
      });
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail||'Phase 4 validation failed.');
      setPhase4Report(data);
    }catch(error){setMessage('Phase 4 Validation: '+(error?.message||'Unknown error'));}
    finally{setPhase4Busy(false);}
  };

  const saveRiskProfile=async()=>{
    setRiskSaving(true);
    try{
      const res=await fetch(apiUrl('/api/risk/settings'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(riskSettings)});
      const data=await res.json();if(!res.ok)throw new Error(data.detail||'Risk settings save failed');
      setRiskSettings(data.settings);setMessage('Risk profile নিরাপদে সংরক্ষণ হয়েছে।');
    }catch(error){setMessage('Risk settings: '+error.message);}
    finally{setRiskSaving(false);}
  };

  const loadPhase5Status=useCallback(async()=>{
    try{
      const res=await fetch(apiUrl('/api/paper-forward/status'));
      const data=await res.json();
      if(!res.ok)throw new Error(data.detail||'Phase 5 status unavailable');
      setPhase5Status(data);
      if(!phase5Loaded.current&&data.config){
        setPhase5Settings({...data.config});
        phase5Loaded.current=true;
      }
    }catch(error){setPhase5Status(old=>old||{status:'offline',error:error.message});}
  },[]);

  const savePhase5Config=async(enabled)=>{
    setPhase5Busy(true);
    try{
      const payload={...phase5Settings,enabled,max_spread_points:phase5Settings.max_spread_points===''?null:Number(phase5Settings.max_spread_points)};
      const res=await fetch(apiUrl('/api/paper-forward/config'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data=await res.json();
      if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||'Phase 5 configuration failed'));
      setPhase5Settings({...data.config});
      await loadPhase5Status();
      setMessage(enabled?'Phase 5 Forward Paper Trading চালু হয়েছে।':'Phase 5 settings সংরক্ষিত; নতুন entry আপাতত বন্ধ।');
    }catch(error){setMessage('Phase 5: '+error.message);}
    finally{setPhase5Busy(false);}
  };

  const enableNotifications=async()=>{
    if(typeof Notification==='undefined'){setNotificationPermission('unsupported');return;}
    try{const permission=await Notification.requestPermission();setNotificationPermission(permission);}
    catch(_){setNotificationPermission('denied');}
  };

  useEffect(()=>{
    if(!config?.live_data)return;
    runReport();
    const timer=window.setInterval(()=>runReport(),60000);
    return ()=>window.clearInterval(timer);
  },[config?.live_data]);

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
          {report.risk_management&&<div className="phase3-gate">
            <b><ShieldCheck size={13}/> Risk Gate · {report.risk_management.status?.toUpperCase()}</b>
            {report.risk_management.reward_risk_to_tp1!=null&&<span>TP1 R:R {report.risk_management.reward_risk_to_tp1}</span>}
            {report.risk_management.position_size&&<span>Estimated size {report.risk_management.position_size.estimated_lots} lots</span>}
            {(report.risk_management.blocking_reasons||[]).map(reason=><span className="risk-block" key={reason}>{reason}</span>)}
            {(report.risk_management.warnings||[]).map(reason=><small key={reason}>{reason.replaceAll('_',' ')}</small>)}
          </div>}
          <small>{report.disclaimer}</small>
        </div>}
    </section>



    <section className="card phase3-card">
      <div className="section-head"><div><span className="eyebrow">TRADE PROTECTION</span><h2>Risk Management & Position Sizing</h2></div><ShieldCheck size={19}/></div>
      <div className="phase3-metrics">
        <div><small>LIVE SPREAD</small><b>{quoteInfo?.fresh?Number(quoteInfo.spread_points).toFixed(1)+' pts':'NOT LIVE'}</b></div>
      </div>
      {report?.risk_management&&<div className={'phase3-risk-state '+(report.risk_management.status==='approved'?'approved':'blocked')}>
        <b>{report.risk_management.status==='approved'?'Risk checks passed for this alert':'Risk checks: '+(report.risk_management.status||'not evaluated').toUpperCase()}</b>
        <span>{(report.risk_management.blocking_reasons||[]).length?(report.risk_management.blocking_reasons||[]).join(' · '):'Spread, reward/risk, daily limits and cooldown checked.'}</span>
        {report.risk_management.position_size&&<span>Risk budget: {report.risk_management.position_size.risk_cash} · estimated size {report.risk_management.position_size.estimated_lots} lots</span>}
      </div>}
      <details className="risk-settings">
        <summary><Settings2 size={14}/> Risk profile settings <small>Configure account and broker contract details</small></summary>
        <div className="risk-form">
          <label>Account balance<input type="number" min="0" step="100" placeholder="e.g. 10000" value={riskSettings.account_balance??''} onChange={e=>setRiskSettings(v=>({...v,account_balance:e.target.value===''?null:Number(e.target.value)}))}/></label>
          <label>Contract size (units / lot)<input type="number" min="0" step="1" placeholder="Broker specification" value={riskSettings.contract_size??''} onChange={e=>setRiskSettings(v=>({...v,contract_size:e.target.value===''?null:Number(e.target.value)}))}/></label>
          <label>Risk per trade (%)<input type="number" min="0.01" max="5" step="0.05" value={riskSettings.risk_percent} onChange={e=>setRiskSettings(v=>({...v,risk_percent:Number(e.target.value)}))}/></label>
          <label>Max daily loss (%)<input type="number" min="0.1" max="20" step="0.1" value={riskSettings.max_daily_loss_percent} onChange={e=>setRiskSettings(v=>({...v,max_daily_loss_percent:Number(e.target.value)}))}/></label>
          <label>Max trades / day<input type="number" min="1" max="50" step="1" value={riskSettings.max_trades_per_day} onChange={e=>setRiskSettings(v=>({...v,max_trades_per_day:Number(e.target.value)}))}/></label>
          <label>Max open trades<input type="number" min="1" max="20" step="1" value={riskSettings.max_open_trades} onChange={e=>setRiskSettings(v=>({...v,max_open_trades:Number(e.target.value)}))}/></label>
          <label>Cooldown (minutes)<input type="number" min="0" max="1440" step="5" value={riskSettings.cooldown_minutes} onChange={e=>setRiskSettings(v=>({...v,cooldown_minutes:Number(e.target.value)}))}/></label>
          <label>Minimum TP1 R:R<input type="number" min="0.1" max="10" step="0.1" value={riskSettings.min_reward_risk} onChange={e=>setRiskSettings(v=>({...v,min_reward_risk:Number(e.target.value)}))}/></label>
          <label>Extra max spread (points)<input type="number" min="0" step="1" placeholder="Optional stricter cap" value={riskSettings.max_spread_points??''} onChange={e=>setRiskSettings(v=>({...v,max_spread_points:e.target.value===''?null:Number(e.target.value)}))}/></label>
        </div>
        <div className="phase3-actions"><button className="action-btn" onClick={saveRiskProfile} disabled={riskSaving}><Save size={13}/>{riskSaving?'Saving…':'Save risk profile'}</button><small>Broker-এর contract size ও point value যাচাই করে বসাও। খালি রাখলে lot-size estimate দেখানো হবে না।</small></div>
      </details>
    </section>

    <section className="phase3-columns phase3-single">
      <article className="card phase3-card">
        <div className="section-head"><div><span className="eyebrow">CONFIRMED SIGNALS</span><h2>Alerts</h2></div>
          <button className="action-btn secondary" onClick={enableNotifications}><Bell size={13}/> {notificationPermission==='granted'?'Notifications ON':notificationPermission==='denied'?'Notifications blocked':'Enable notifications'}</button>
        </div>
        <p className="phase3-note">নতুন 1H BUY/SELL confirmation হলে একবার alert তৈরি হয়; একই direction বারবার এলে duplicate alert হয় না।</p>
        <div className="phase3-list">
          {signalEvents.slice(0,8).map(event=><div className="phase3-row" key={event.id}>
            <b className={event.direction==='BUY'?'positive':'negative'}>{event.direction} · XAUUSD</b>
            <span>{Number(event.price||0).toFixed(2)} · {new Date(Number(event.candle_time)*1000).toLocaleString()}</span>
            <small>Entry {event.entry_low??'—'} – {event.entry_high??'—'} · SL {event.stop_loss??'—'} · TP1 {event.target1??'—'}</small>
          </div>)}
          {!signalEvents.length&&<div className="phase3-empty">এখনও কোনো confirmed live signal নেই। Fresh MT5 candles, valid 1H setup ও acceptable spread দরকার।</div>}
        </div>
      </article>
          </section>


    <section className="card phase5-card">
      <div className="section-head"><div><span className="eyebrow">PHASE 5 · LIVE FORWARD OBSERVATION</span><h2>Continuous Paper Trading</h2></div>
        <span className={'phase5-state '+(phase5Status?.engine?.enabled?'running':'paused')}>{phase5Status?.engine?.enabled?'ENGINE ON':'ENGINE PAUSED'}</span>
      </div>
      <p className="phase5-intro">Authenticated MT5 feed থেকে প্রতিটি সম্পূর্ণ 1H candle একবার প্রসেস হবে। Confirmed signal পরের 1H candle-এর Open-এ Entry Zone-এর ভিতরে থাকলেই simulated entry হবে। Stop/TP1, spread, slippage, commission ও risk gate ledger-এ সংরক্ষিত থাকবে। এটি শুধুই PAPER — কোনো broker order পাঠায় না।</p>
      <div className="phase5-metrics">
        <div><small>PROCESSED 1H EVENTS</small><b>{phase5Status?.summary?.processed_events??'—'}</b></div>
        <div><small>CLOSED PAPER TRADES</small><b>{phase5Status?.summary?.trades_closed??'—'}</b></div>
        <div><small>OPEN POSITIONS</small><b>{phase5Status?.summary?.trades_open??'—'}</b></div>
        <div><small>WIN RATE</small><b>{phase5Status?.summary?.win_rate_pct==null?'—':phase5Status.summary.win_rate_pct+'%'}</b></div>
        <div><small>NET PNL · PRICE</small><b>{phase5Status?.summary?.net_pnl_price==null?'—':Number(phase5Status.summary.net_pnl_price).toFixed(2)}</b></div>
        <div><small>AVERAGE R</small><b>{phase5Status?.summary?.average_R==null?'—':Number(phase5Status.summary.average_R).toFixed(2)+'R'}</b></div>
      </div>
      <div className={'phase5-readiness '+(phase5Status?.readiness?.ready?'ready':'blocked')}>
        <b>{phase5Status?.readiness?.ready?'Feed / storage readiness passed':'Start gate: requirements not yet met'}</b>
        {(phase5Status?.readiness?.blockers||[]).map((item,i)=><span key={i}>{item}</span>)}
        {phase5Status?.readiness?.ready&&<small>Storage: {phase5Status.readiness.checks?.persistent_storage?.backend||'—'} · Server spread cap: {phase5Status.readiness.checks?.server_spread_cap?.max_spread_points??'—'} pts</small>}
      </div>
      <div className="phase5-form">
        <label>Paper max spread (points)<input type="number" min="0.1" step="0.1" value={phase5Settings.max_spread_points??''} onChange={e=>setPhase5Settings(v=>({...v,max_spread_points:e.target.value===''?'':Number(e.target.value)}))} placeholder="Measured broker cap"/></label>
        <label>Slippage (points / side)<input type="number" min="0" step="0.1" value={phase5Settings.slippage_points??0} onChange={e=>setPhase5Settings(v=>({...v,slippage_points:Number(e.target.value)}))}/></label>
        <label>Commission (points / side)<input type="number" min="0" step="0.1" value={phase5Settings.commission_points_per_side??0} onChange={e=>setPhase5Settings(v=>({...v,commission_points_per_side:Number(e.target.value)}))}/></label>
      </div>
      <div className="phase5-actions">
        <button className="action-btn secondary" onClick={()=>savePhase5Config(false)} disabled={phase5Busy}>Save paper settings</button>
        {!phase5Status?.engine?.enabled?
          <button className="action-btn" onClick={()=>savePhase5Config(true)} disabled={phase5Busy||!phase5Status?.readiness?.ready}>Start forward paper</button>:
          <button className="action-btn danger" onClick={()=>savePhase5Config(false)} disabled={phase5Busy}>Pause new entries</button>}
        <button className="action-btn secondary" onClick={loadPhase5Status} disabled={phase5Busy}><RefreshCw size={13}/> Refresh status</button>
      </div>
      <small className="phase5-note">Paused অবস্থায় নতুন signal/entry নেওয়া হয় না; existing paper position MT5 feed fresh থাকলে exit rules দিয়ে manage হবে। Feed বন্ধ বা stale হলে position management-ও pause হবে। Live observation period এখনো শুরু হয়েছে বলে ধরা হবে না—engine চালু হওয়ার পরে নতুন future 1H candle collect হতে হবে।</small>
      <div className="phase5-recent">
        <div className="phase5-subhead">Recent paper trades</div>
        {(phase5Status?.recent_trades||[]).slice(0,6).map(trade=><div className="phase5-trade" key={trade.id}>
          <b className={trade.side==='BUY'?'positive':'negative'}>{trade.side} · {trade.status}</b>
          <span>Entry {Number(trade.entry_price).toFixed(2)} · SL {Number(trade.stop_loss).toFixed(2)} · TP1 {Number(trade.tp1).toFixed(2)}</span>
          <small>{new Date(Number(trade.entry_time)*1000).toLocaleString()} · {trade.status==='CLOSED'?'Exit '+Number(trade.exit_price).toFixed(2)+' · '+trade.exit_reason+' · '+Number(trade.pnl_r).toFixed(2)+'R':'Open · awaiting stop / target'}</small>
        </div>)}
        {!(phase5Status?.recent_trades||[]).length&&<div className="phase5-empty">এখনও কোনো paper position নেই। Live MT5 feed ও readiness gate পূরণ হলে future 1H candle-এ event processing শুরু হবে।</div>}
      </div>
      {phase5Status?.engine?.last_cycle&&<div className="phase5-last">Last cycle: {phase5Status.engine.last_cycle.status} · {phase5Status.engine.last_cycle.checked_at||'—'} · {(phase5Status.engine.last_cycle.actions||[]).map(x=>x.action).join(' / ')}</div>}
    </section>

    <section className="card phase4-card">
      <div className="section-head"><div><span className="eyebrow">PHASE 4 · VALIDATION GATE</span><h2>Gold Strategy Validation</h2></div>
        <button className="action-btn" onClick={runPhase4Validation} disabled={phase4Busy}>{phase4Busy?'Validating…':'Run Full Validation'}</button>
      </div>
      <p className="phase4-intro">একই XAUUSD feed-এর 4H, 1H, 15M ও optional 5M candle দিয়ে data audit, causal multi-timeframe replay, base/conservative/adverse cost stress এবং chronological walk-forward + sealed holdout পরীক্ষা হবে। Pine parity ও live broker execution আলাদা certification gate।</p>
      <div className="phase4-form">
        <label>Data provider / broker<input value={phase4Provider} onChange={e=>setPhase4Provider(e.target.value)} placeholder="যেমন: MT5 · broker name"/></label>
        <label>Data timezone<input value={phase4Timezone} onChange={e=>setPhase4Timezone(e.target.value)} placeholder="UTC or Asia/Kolkata"/></label>
        <label>Point size<input type="number" min="0.000001" step="0.001" value={phase4Costs.point_size} onChange={e=>setPhase4Costs(v=>({...v,point_size:Number(e.target.value)}))}/></label>
        <label>Observed spread (points)<input type="number" min="0" step="0.1" value={phase4Costs.spread_points} onChange={e=>setPhase4Costs(v=>({...v,spread_points:Number(e.target.value)}))}/></label>
        <label>Observed max spread cap<input type="number" min="0" step="0.1" value={phase4Costs.max_spread_points} onChange={e=>setPhase4Costs(v=>({...v,max_spread_points:Number(e.target.value)}))}/></label>
        <label>Slippage (points)<input type="number" min="0" step="0.1" value={phase4Costs.slippage_points} onChange={e=>setPhase4Costs(v=>({...v,slippage_points:Number(e.target.value)}))}/></label>
        <label>Commission / side (points)<input type="number" min="0" step="0.1" value={phase4Costs.commission_points_per_side} onChange={e=>setPhase4Costs(v=>({...v,commission_points_per_side:Number(e.target.value)}))}/></label>
      </div>
      <label className="phase4-attest"><input type="checkbox" checked={phase4SameFeed} onChange={e=>setPhase4SameFeed(e.target.checked)}/> আমি নিশ্চিত করছি 4H / 1H / 15M / 5M ডেটা একই XAUUSD provider, symbol ও timezone থেকে এসেছে (এটি user attestation; স্বয়ংক্রিয় প্রমাণ নয়)।</label>
      <small className="phase4-warning">ব্যাংক/ব্রোকারের আসল spread, slippage, commission এবং point size বসাতে হবে। Max spread শূন্য থাকলে research entry fail-closed হবে। পরীক্ষার খরচ-মান broker evidence ছাড়া verified নয়।</small>
      {phase4Report&&<div className="phase4-results">
        <div className={'phase4-status '+(phase4Report.status==='complete_not_certified'?'pass':'blocked')}>
          <b>{phase4Report.status==='research_pass_not_certified'?'RESEARCH RUN COMPLETE · NOT CERTIFIED':(phase4Report.status||'BLOCKED').replaceAll('_',' ').toUpperCase()}</b>
          <span>Final certification: {phase4Report.final_certification||'NOT CERTIFIED'}</span>
        </div>
        <div className="phase4-subhead">Historical candle quality</div>
        <div className="phase4-audits">
          {Object.entries(phase4Report.data_audit||{}).map(([tf,audit])=><div key={tf}>
            <b>{tf.toUpperCase()}</b><span>{audit.status||'missing'} · {audit.valid_unique_rows??0} valid</span>
            <small>Closed {audit.closed_rows??0} · Duplicate {audit.duplicate_rows??0} · Invalid {audit.invalid_rows??0} · Gaps {audit.gap_count??0} · Forming {audit.forming_rows??0}</small>
          </div>)}
        </div>
        <div className="phase4-subhead">Baseline MTF replay (net after entered costs)</div>
        <div className="phase4-metrics">
          {Object.entries(phase4Report.baseline_replay||{}).filter(([k])=>['trade_count','win_rate_pct','net_pnl_price','average_R','profit_factor','max_drawdown_price','signals_evaluated','accepted_signals'].includes(k)).map(([k,v])=><span key={k}>{k.replaceAll('_',' ')}<b>{v??'—'}</b></span>)}
        </div>
        <div className="phase4-subhead">Execution-cost stress</div>
        <div className="phase4-scenarios">
          {Object.entries(phase4Report.execution_cost_scenarios?.scenario_reports||{}).map(([name,item])=><div key={name}>
            <b>{name.toUpperCase()}</b><span>Trades {item.metrics?.trade_count??'—'} · Net {item.metrics?.net_pnl_price??'—'}</span>
            <small>Win {item.metrics?.win_rate_pct??'—'}% · PF {item.metrics?.profit_factor??'—'} · DD {item.metrics?.max_drawdown_price??'—'}</small>
          </div>)}
        </div>
        <div className="phase4-subhead">Walk-forward / out-of-sample + sealed holdout</div>
        <div className="phase4-metrics">
          <span>WFO status<b>{phase4Report.walk_forward?.status??'—'}</b></span>
          <span>Folds<b>{phase4Report.walk_forward?.aggregate_oos?.completed_folds??0}/{phase4Report.walk_forward?.fold_count??4}</b></span>
          <span>OOS trades<b>{phase4Report.walk_forward?.aggregate_oos?.trade_count??'—'}</b></span>
          <span>OOS net PnL<b>{phase4Report.walk_forward?.aggregate_oos?.net_pnl_price??'—'}</b></span>
          <span>Holdout<b>{phase4Report.walk_forward?.sealed_holdout?.status??'—'}</b></span>
          <span>Holdout net<b>{phase4Report.walk_forward?.sealed_holdout?.metrics?.net_pnl_price??'—'}</b></span>
        </div>
        <div className="phase4-subhead">Unfinished external certification gates</div>
        <div className="phase4-blockers">{(phase4Report.blockers||[]).map((item,i)=><span key={i}>{item}</span>)}</div>
        <small className="phase4-warning">Historical research output, not a profitability promise. OHLCV-derived liquidity is not an institutional order book. No live/paper execution has been certified.</small>
      </div>}
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
      <article className="card"><div className="section-head"><div><span className="eyebrow">LIQUIDITY INTELLIGENCE · OHLCV ESTIMATE</span><h2>Institutional Footprint</h2></div><Waves size={19}/></div>
        {(()=>{
          const liq=report?.timeframes?.['1h']?.liquidity||{};
          const activity=liq.activity_proxies||{};
          const sweep=liq.liquidity_sweep||{};
          const score=liq.institutional_activity_score||{};
          const book=liq.order_book||{};
          const levels=liq.liquidity_heatmap?.levels||[];
          return <div className="liquidity-content">
            <div className="liquidity-score"><span>Activity proxy</span><b>{score.score??'—'} / 100</b><small>{score.confidence||'No sample'}</small></div>
            <div className="liquidity-metrics">
              <span>Relative volume <b>{activity.relative_volume??'—'}x</b></span>
              <span>Estimated delta <b>{activity.estimated_delta??'—'}</b></span>
              <span>Estimated CVD (20) <b>{activity.estimated_cvd_20_bars??'—'}</b></span>
              <span>Unusual volume <b>{activity.unusual_volume?'YES':'NO DATA'}</b></span>
            </div>
            <div className="liquidity-sweeps">
              <span className={sweep.buy_side_sweep_and_reclaim?'sweep-hit':''}>Buy-side sweep {sweep.buy_side_sweep_and_reclaim?'Detected':'—'}</span>
              <span className={sweep.sell_side_sweep_and_reclaim?'sweep-hit':''}>Sell-side sweep {sweep.sell_side_sweep_and_reclaim?'Detected':'—'}</span>
            </div>
            <div className="phase3-list">
              {levels.slice(-6).map((level,i)=><div className="phase3-row" key={level.side+'-'+i}>
                <b className={level.side==='buy_side'?'positive':'negative'}>{level.side==='buy_side'?'BUY-SIDE POOL':'SELL-SIDE POOL'} · {level.strength}</b>
                <span>{Number(level.price).toFixed(2)} · {level.touches} pivot touches</span>
              </div>)}
              {!levels.length&&<div className="phase3-empty">পর্যাপ্ত confirmed swing touch না থাকায় liquidity cluster তৈরি হয়নি।</div>}
            </div>
            <small className="zone-disclaimer">{book.status==='not_connected'?'Live exchange order book / MBO: not connected. ':''}Delta/CVD এবং activity score candle-close-location proxy, প্রকৃত bid/ask flow বা named institutional order নয়।</small>
          </div>;
        })()}
      </article>
      <article className="card"><div className="section-head"><div><span className="eyebrow">DATA INTEGRITY</span><h2>Feed & Execution</h2></div><ShieldCheck size={19}/></div>
        <div className="empty-state"><Radio size={22}/><b>{config?.live_data?'MT5 Bridge Connected':'Live feed not connected'}</b><span>Historical CSV data is supported. {config?.live_data?'MT5 bridge is recently connected.':'Live MT5 bridge is not currently active.'} Spread: {quoteInfo?.spread_points??'—'} points / limit {quoteInfo?.max_spread_points??'not configured'}. Backtest-এ spread, commission ও slippage assumptions দেওয়া যায়; broker-এর আসল fee schedule এখনও যাচাই করা হয়নি.</span></div>
        <div className="feed-health-list">{['4h','1h','15m'].map(tf=>{const health=config?.timeframe_health?.[tf];return <div key={tf}><b>{tf.toUpperCase()}</b><span className={health?.fresh?'healthy':'unhealthy'}>{health?.fresh?'FRESH':'STALE / NOT CONNECTED'}</span><small>{health?.last_candle_close_age_seconds!=null?Number(health.last_candle_close_age_seconds).toFixed(0)+'s since close':health?.reason||'No authenticated MT5 candle feed'}</small></div>})}</div>
      </article>
    </section>
    <footer><span><Clock3 size={13}/> BUILD 0.5.0 · RISK & ALERTS · 1H PRIMARY</span><span>Closed-candle analysis only · No broker orders are placed</span></footer>
  </main>;
}
