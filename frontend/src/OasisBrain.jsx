import React,{useState} from 'react';
import VeilCore from './VeilCore';

const cents=n=>Number.isFinite(n)?(n*100).toFixed(1)+'¢':'—';
const stamp=n=>new Date(n).toLocaleTimeString();
const nodes=[['book','Order book',80,75],['trend','Quote trend',80,225],['clock','Round clock',300,35],['rules','Settlement',520,75],['news','News context',520,225]];
export default function OasisBrain({analysis,quote,history,current,stale,left,observed,watching}) {
  const [sensor,setSensor]=useState('book'),[sample,setSample]=useState(null),[range,setRange]=useState(30),[motion,setMotion]=useState(true);
  const rows=history.filter(h=>h.slug===current?.slug&&Number.isFinite(h.bid)&&Number.isFinite(h.ask)).slice(-range);
  const selected=rows.length?rows[Math.min(sample??rows.length-1,rows.length-1)]:null;
  const mids=rows.map(h=>(h.bid+h.ask)/2);
  const coords=mids.map((p,i)=>[(i/Math.max(1,mids.length-1))*560+20,145-p*120]);
  const points=coords.map(p=>p.join(',')).join(' ');
  const bidSize=quote.bid?.size||0,askSize=quote.ask?.size||0;
  const depth=bidSize+askSize?bidSize/(bidSize+askSize)*100:50;
  const live=!stale&&quote.open;
  const explanations={
    book:`Up bid ${cents(quote.bid?.price)} / offer ${cents(quote.ask?.price)}. Spread ${cents(quote.spread)}. Displayed depth covers only the best price level; it is not total buying/selling pressure.`,
    trend:rows.length>1?`${rows.length} two-sided observations of this round. Up midpoint moved ${((mids.at(-1)-mids[0])*100).toFixed(1)} cents. This tracks contract sentiment, not underlying BTC price.`:'Waiting for at least two valid two-sided quotes to compare.',
    clock:current?`${left} seconds remain. The lean is suppressed in the final 30 seconds; the schedule uses your device clock.`:'Waiting for a verified active round.',
    rules:'The published rules and Yes/No sides must confirm the Up/Down mapping. The provider BRTI target is shown below. Live BRTI momentum is not connected.',
    news:'Dated, linked research provides daily/weekly context below. It has zero weight in the direction calculation and does not refresh automatically.'
  };
  return <section className={`oasis-brain ${live?'is-live':''} ${motion?'':'reduce-motion'}`} aria-labelledby="brain-title">
    <header className="brain-head"><div><p className="eyebrow">OASIS / MARKET INTELLIGENCE</p><h3 id="brain-title">The OASIS Brain<span>BTC · 5 MIN</span></h3><p>A transparent view of what the market is telling us.</p></div><span className="brain-live"><i/>{!watching?'WATCH PAUSED':live?'RECEIVING DATA':'WAITING FOR DATA'}</span></header>
    <div className="brain-layout"><div className="brain-network">
      <VeilCore live={live} motion={motion} analysis={analysis} current={current} left={left} observed={observed} explanations={explanations} onSensor={setSensor}/>
      <div className="brain-sensors" aria-label="Explore analysis inputs">{nodes.map(([id,label])=><button key={id} aria-pressed={sensor===id} onClick={()=>setSensor(id)}>{label}</button>)}</div>
      <p className="brain-explanation" role="status">{explanations[sensor]}</p>
    </div><aside className="brain-verdict"><span>MARKET PRICING LEAN</span><strong>{analysis.lean}</strong><p>{analysis.confidence}</p><div>Trade suggestion <b>{analysis.suggestion}</b></div><small>Market sentiment only. An independent predictive edge has not been established.</small><small>{observed?'Last quote '+stamp(observed):'Awaiting a quote'}</small></aside></div>
    <div className="brain-chart-head"><div><h4>Market pulse</h4><p>Up contract midpoint · current round only</p></div><label>Observations <select value={range} onChange={e=>{setRange(Number(e.target.value));setSample(null);}}><option value={10}>Last 10</option><option value={30}>Last 30</option></select></label></div>
    <div className="brain-chart">
      <svg viewBox="0 0 600 170" role="img" aria-label="Up contract midpoint history from 0 to 100 cents"><path d="M20 85 H580" stroke="#5b506d" strokeDasharray="4 5"/><text x="24" y="79">50¢</text>{coords.length>1&&<polyline points={points} fill="none" stroke="#bca1ff" strokeWidth="3"/>}{coords.map(([x,y],i)=><circle key={i} cx={x} cy={y} r={selected===rows[i]?5:2} fill={selected===rows[i]?'#7af2d0':'#bca1ff'}/>)}</svg>
      {!rows.length&&<p className="brain-empty">Waiting for two-sided quotes. Missing prices are never filled in.</p>}
    </div>
    <div className="brain-replay"><span>Inspect snapshots</span><button disabled={rows.length<2||(sample!==null&&sample===0)} onClick={()=>setSample(v=>Math.max(0,(v??rows.length-1)-1))}>Previous</button><button disabled={sample===null||sample>=rows.length-1} onClick={()=>setSample(v=>Math.min(rows.length-1,(v??rows.length-1)+1))}>Next</button><button onClick={()=>setSample(null)} aria-pressed={sample===null}>Follow latest</button></div>
    <div className="brain-snapshot">{selected?<><span>{stamp(selected.at)} · {sample===null?'LATEST':'HISTORICAL SNAPSHOT'}</span><b>Up bid {cents(selected.bid)}</b><b>Up offer {cents(selected.ask)}</b><b>Midpoint {cents((selected.bid+selected.ask)/2)}</b></>:<span>No complete snapshot yet.</span>}</div>
    <div className="brain-depth"><span>Best-level Up bid depth: {bidSize.toLocaleString()} contracts</span><span>Best-level Up offer depth: {askSize.toLocaleString()} contracts</span><div aria-label="Relative contract quantities at best bid and offer"><i style={{width:depth+'%'}}/></div><small>Resting quantities can change or disappear. This is not a probability or trade signal.</small></div>
    <footer><span>READ-ONLY ANALYSIS · No orders placed</span><button aria-pressed={!motion} onClick={()=>setMotion(v=>!v)}>{motion?'Reduce motion':'Enable motion'}</button></footer>
  </section>;
}
