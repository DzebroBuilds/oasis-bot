import React, { useCallback, useEffect, useMemo, useState } from 'react';
import './dashboard.css';

const FEED = 'https://raw.githubusercontent.com/DzebroBuilds/oasis-bot/oasis-data/dashboard.json';
const RUNS = 'https://github.com/DzebroBuilds/oasis-bot/actions/workflows/dashboard.yml';
const money = value => typeof value === 'number' ? new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(value/100) : '—';
const date = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Not yet available';
const label = value => String(value || '').replaceAll('_', ' ');
const quote = value => typeof value === 'number' ? `${value}¢` : 'Unavailable';

function validate(data) {
  if (data?.schema_version !== 1 || data.mode !== 'paper' || !data.stats || !data.limits || !data.health ||
      !['markets','positions','decisions','research'].every(key=>Array.isArray(data[key])) ||
      !Number.isFinite(Date.parse(data.generated_at))) throw new Error('Unsupported dashboard data');
  return data;
}

export default function Dashboard() {
  const [data,setData]=useState(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  const [tab,setTab]=useState('Markets');
  const [query,setQuery]=useState('');
  const [category,setCategory]=useState('All');
  const [clock,setClock]=useState(Date.now());
  const refresh=useCallback(async signal=>{
    setLoading(true);
    try {
      const response=await fetch(`${FEED}?t=${Date.now()}`,{cache:'no-store',signal});
      if(!response.ok) throw new Error('Data update unavailable');
      const next=validate(await response.json());
      setData(next); setError(''); setClock(Date.now());
    } catch(err) {
      if(err.name!=='AbortError') setError('Cannot reach the Python dashboard feed. Showing the last loaded snapshot, if available.');
    } finally { if(!signal?.aborted) setLoading(false); }
  },[]);
  useEffect(()=>{
    const controller=new AbortController();
    refresh(controller.signal);
    const timer=setInterval(()=>refresh(controller.signal),60000);
    const tick=setInterval(()=>setClock(Date.now()),30000);
    return ()=>{controller.abort();clearInterval(timer);clearInterval(tick);};
  },[refresh]);
  const categories=useMemo(()=>['All',...new Set((data?.markets||[]).map(m=>m.category))],[data]);
  const markets=useMemo(()=>(data?.markets||[]).filter(m=>(category==='All'||m.category===category)&&
    `${m.title} ${m.ticker}`.toLowerCase().includes(query.toLowerCase())),[data,category,query]);
  const marketAge=data?.health.market_data_at ? clock-Date.parse(data.health.market_data_at) : Infinity;
  const stale=marketAge>90*60000;
  const status=!data?'Waiting for Python':data.paused?'Scanner paused':data.health.status==='degraded'?'Update needs attention':stale?'Market data stale':'Python connected';

  return <div className="oasis-dashboard">
    <div className="section-heading"><div><p className="eyebrow">OASIS / PAPER OPERATIONS</p><h2>Your research workspace.</h2></div><span className={`connection ${stale||error?'warning':''}`}>{status}</span></div>
    <div className="dashboard-toolbar"><p>Python scan: {date(data?.generated_at)}<br/><span>Market snapshot: {date(data?.health.market_data_at)}</span></p><div><button onClick={()=>refresh()} disabled={loading}>{loading?'Loading…':'Refresh dashboard'}</button><a href={RUNS} target="_blank" rel="noreferrer">Run / pause scanner ↗</a></div></div>
    {error&&<p className="dashboard-alert" role="alert">{error}</p>}
    {data?.health.message&&<p className="dashboard-alert">{data.health.message}</p>}
    <p className="dashboard-context">Paper trading only. Updates are scheduled hourly and may be delayed by GitHub. Quotes are snapshots, not executable live prices.</p>
    <div className="dashboard-stats">
      <article><span>Markets in snapshot</span><strong>{data?data.markets.length:'—'}</strong><small>Bounded exchange sample</small></article>
      <article><span>Paper realized P&amp;L</span><strong>{money(data?.stats.pnl_cents)}</strong><small>{data?`${data.stats.settled} settled positions`:'Waiting for ledger'}</small></article>
      <article><span>Open paper exposure</span><strong>{money(data?.stats.exposure_cents)}</strong><small>{data?`${data.stats.open_positions} positions`:'Waiting for ledger'}</small></article>
      <article><span>Daily entry cost</span><strong>{money(data?.stats.spent_today_cents)}</strong><small>Cap {money(data?.limits.daily_cents)} · UTC day</small></article>
    </div>
    <nav className="dashboard-tabs" aria-label="Dashboard sections">{['Markets','Portfolio','Decisions','Research','Controls'].map(name=><button key={name} aria-pressed={tab===name} onClick={()=>setTab(name)}>{name}</button>)}</nav>
    <div className="dashboard-panel">
      {tab==='Markets'&&<>
        <div className="market-filters"><label>Find a market<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search title or ticker" /></label><label>Category<select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select></label></div>
        <p className="panel-note">{data?.scan_scope||'Waiting for the first Python scan.'} No model probability is implied by these prices.</p>
        <div className="dashboard-table-wrap"><table><thead><tr><th>Market</th><th>Category</th><th>YES ask</th><th>NO ask</th><th>Contracts traded</th><th>Closes</th></tr></thead><tbody>{markets.map(m=><tr key={m.ticker}><td><details><summary>{m.title}</summary><code>{m.ticker}</code><p>{m.rules||'Settlement rules unavailable in this snapshot.'}</p><small>Observed {date(m.quoted_at)}</small></details></td><td>{m.category}</td><td>{quote(m.yes_ask_cents)}</td><td>{quote(m.no_ask_cents)}</td><td>{m.volume.toLocaleString()}</td><td>{date(m.closes_at)}</td></tr>)}</tbody></table></div>
        {!markets.length&&<p className="dashboard-empty">{loading?'Loading the market snapshot…':data?'No markets match these filters.':'No snapshot has loaded. Check the scanner run in GitHub.'}</p>}
      </>}
      {tab==='Portfolio'&&<>
        <div className="panel-heading"><h3>Paper positions</h3><span>Brier score: {typeof data?.stats.brier_score==='number'?data.stats.brier_score.toFixed(4):'Awaiting settled forecasts'}</span></div>
        <div className="dashboard-table-wrap"><table><thead><tr><th>Market</th><th>Side</th><th>Contracts</th><th>Entry cost</th><th>Status</th><th>Realized P&amp;L</th></tr></thead><tbody>{data?.positions.map(p=><tr key={p.ticker}><td>{p.ticker}</td><td>{p.side.toUpperCase()}</td><td>{p.count}</td><td>{money(p.cost_cents)}</td><td>{p.status}</td><td>{money(p.pnl_cents)}</td></tr>)}</tbody></table></div>
        {!data?.positions.length&&<p className="dashboard-empty">No paper positions yet. A timestamped probability signal with evidence and a fee bound must pass the engine before a simulated entry can appear.</p>}
        <p className="panel-note">Paper fills assume execution at the supplied book price and size. P&amp;L includes the supplied conservative fee bound. It is not actual account performance.</p>
      </>}
      {tab==='Decisions'&&<>
        <h3>Why Oasis acted—or waited</h3><p className="panel-note">Latest 100 decisions. Rejections are expected when evidence or a validated probability estimate is missing.</p>
        <div className="dashboard-table-wrap"><table><thead><tr><th>Time</th><th>Market</th><th>Decision</th></tr></thead><tbody>{data?.decisions.map((d,i)=><tr key={`${d.at}-${i}`}><td>{date(d.at)}</td><td>{d.ticker}</td><td><span className="decision-reason">{label(d.reason)}</span></td></tr>)}</tbody></table></div>
        {!data?.decisions.length&&<p className="dashboard-empty">No recorded decisions yet.</p>}
      </>}
      {tab==='Research'&&<>
        <h3>Evidence before conviction</h3><p className="panel-note">Optional grounded Gemini research is available from Run workflow → enable_research. Maximum three public markets per manual run; provider usage may incur charges. Research does not enable orders.</p>
        {data?.research.map((r,i)=><article className="research-note" key={`${r.ticker}-${i}`}><h4>{r.ticker}</h4><small>{label(r.status)} · {date(r.at)}</small><p>{r.text||r.reason}</p><ul>{r.sources?.map((s,j)=><li key={j}><a href={s.url.startsWith('https://')?s.url:undefined} target="_blank" rel="noreferrer">{s.title}</a></li>)}</ul></article>)}
        {!data?.research.length&&<p className="dashboard-empty">No AI research in the latest scan. Scheduled scans do not call a paid AI provider.</p>}
      </>}
      {tab==='Controls'&&<>
        <h3>Controls &amp; operating limits</h3>
        <dl className="control-grid"><div><dt>Mode</dt><dd>Paper only · live orders blocked</dd></div><div><dt>Scanner</dt><dd>{data?.paused?'Paused':'Scheduled hourly'}</dd></div><div><dt>Per entry cap</dt><dd>{money(data?.limits.unit_cents)}</dd></div><div><dt>Per event exposure cap</dt><dd>{money(data?.limits.event_cents)}</dd></div><div><dt>Strategy</dt><dd>{data?.strategy_status||'Awaiting state'}</dd></div><div><dt>Hosting</dt><dd>GitHub Pages + Python Actions</dd></div></dl>
        <p className="panel-note">Run, pause, and resume require your GitHub sign-in. Open the workflow, choose Run workflow, then select the action. A pause takes effect when that job runs; an already running scan finishes first. Refreshing this page only reloads published data.</p>
        <div className="control-links"><a href={RUNS} target="_blank" rel="noreferrer">Open authenticated run controls ↗</a><a href="https://github.com/DzebroBuilds/oasis-bot/edit/oasis-data/paper-signals.json" target="_blank" rel="noreferrer">Manage paper signals ↗</a></div>
        <p className="panel-note">This is a public research dashboard. Keep personal account data, credentials, and private research out of the public paper ledger.</p>
      </>}
    </div>
    <p className="dashboard-bottom" role="status">{data?`${data.stats.decisions} recorded decisions · ${status}`:'Waiting for the Python dashboard feed.'}</p>
  </div>;
}
