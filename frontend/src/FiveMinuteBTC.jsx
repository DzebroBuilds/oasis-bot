import React,{useEffect,useRef,useState} from 'react';
import {bookQuote,findRounds,publicJson,roundWindow} from './btcRound';
import './five-minute.css';

const price=p=>typeof p==='number'?`${(p*100).toFixed(2)}¢`:'Unavailable';
const usd=amount=>amount?.currency==='USD'&&Number.isFinite(Number(amount.value))?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(amount.value)):'Not supplied';
const time=t=>new Date(t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});

export default function FiveMinuteBTC() {
  const [rounds,setRounds]=useState({current:null,upcoming:[]});
  const [detail,setDetail]=useState(null);
  const [book,setBook]=useState(null);
  const [observed,setObserved]=useState(0);
  const [clock,setClock]=useState(Date.now());
  const [status,setStatus]=useState('Discovering the current BTC round…');
  const [watching,setWatching]=useState(true);
  const [history,setHistory]=useState([]);
  const activeSlug=useRef(null);
  useEffect(()=>{const tick=setInterval(()=>setClock(Date.now()),250);return()=>clearInterval(tick);},[]);
  useEffect(()=>{
    if(!watching) {setStatus('Live watch paused');return;}
    let stopped=false,timer;
    const controller=new AbortController();
    const poll=async()=>{
      try {
        const response=await publicJson('/v1/search?query=BTC%20Up%20or%20Down%205m&status=active&limit=50',controller.signal);
        if(!Array.isArray(response.events)) throw new Error('Unexpected discovery response');
        const next=findRounds(response.events);
        if(stopped) return;
        setRounds(next);
        if(next.current?.slug!==activeSlug.current) {
          activeSlug.current=next.current?.slug||null;
          setBook(null);setDetail(null);setObserved(0);setHistory([]);
        }
        if(!next.current) {setStatus('No current five-minute BTC contract returned by the US API');return;}
        const slug=next.current.slug;
        const [marketResponse,bookResponse]=await Promise.all([
          publicJson(`/v1/market/slug/${encodeURIComponent(slug)}`,controller.signal),
          publicJson(`/v1/markets/${encodeURIComponent(slug)}/book`,controller.signal)
        ]);
        if(stopped||activeSlug.current!==slug) return;
        const market=marketResponse.market;
        const schedule=market?roundWindow(next.current.event,market):null;
        if(!schedule||schedule.start>Date.now()||schedule.end<=Date.now()||market.closed===true) {
          setBook(null);setStatus('Round has closed or its timing could not be verified');return;
        }
        const current={...next.current,...schedule,market};
        setRounds({...next,current});
        setDetail(market);setBook(bookResponse.marketData||null);
        const at=Date.now();setObserved(at);
        const quote=bookQuote(bookResponse.marketData);
        setStatus(quote.open?'Public order book connected':'Market is not in open trading state');
        setHistory(old=>[...old,{at,slug,ask:quote.ask?.price??null,bid:quote.bid?.price??null}].slice(-30));
      } catch(error) {
        if(!stopped) setStatus('Live data unavailable. Last received quote is retained and will be marked stale.');
      } finally {if(!stopped) timer=setTimeout(poll,10000);}
    };
    poll();
    return()=>{stopped=true;controller.abort();clearTimeout(timer);};
  },[watching]);
  const current=rounds.current;
  const left=current?Math.max(0,Math.ceil((current.end-clock)/1000)):0;
  const age=observed?Math.max(0,(clock-observed)/1000):Infinity;
  const stale=age>12||!watching||!left;
  const quote=bookQuote(book);
  const longSide=(detail?.marketSides||[]).find(s=>s.long===true)?.description;
  const shortSide=(detail?.marketSides||[]).find(s=>s.long===false)?.description;
  const rules=detail?.description||current?.event?.description||'';
  const verifiedBenchmark=/BRTI|CF Benchmarks/i.test(rules);
  return <section className="btc-terminal" aria-labelledby="btc-title">
    <div className="btc-heading"><div><p className="eyebrow">POLYMARKET US / BTC / FIVE MINUTES</p><h2 id="btc-title">One round. A clearer view.</h2></div><button onClick={()=>setWatching(v=>!v)} aria-pressed={!watching}>{watching?'Pause live watch':'Resume live watch'}</button></div>
    <p className={`btc-status ${stale?'btc-stale':''}`} role="status">{status}{observed?` · Quote age ${Math.floor(age)}s${stale?' · STALE / NOT ACTIONABLE':''}`:''}</p>
    <div className="btc-round"><div><span>CURRENT ROUND</span><h3>{current?`${time(current.start)} – ${time(current.end)}`:'Waiting for an active round'}</h3><code>{current?.slug||'No expired contract will be substituted'}</code></div><div className="btc-countdown" aria-label="Time remaining">{current?`${Math.floor(left/60).toString().padStart(2,'0')}:${(left%60).toString().padStart(2,'0')}`:'--:--'}<small>{left?'remaining · device clock':'round closed / unavailable'}</small></div></div>
    <div className="btc-quotes"><article><span>{longSide||'Long outcome'} · best offer</span><strong>{price(quote.ask?.price)}</strong><small>{quote.ask?`${quote.ask.size} contracts at best offer`:'No resting offer received'}</small></article><article><span>{shortSide||'Opposite outcome'} · implied offer</span><strong>{price(quote.opposite?.price)}</strong><small>{quote.opposite?`${quote.opposite.size} contracts at opposing best bid`:'No opposing bid received'}</small></article><article><span>Long bid–ask spread</span><strong>{typeof quote.spread==='number'?`${(quote.spread*100).toFixed(2)}¢`:'Unavailable'}</strong><small>{stale?'Quote is stale':quote.open?'Open book snapshot':'Market not open'}</small></article></div>
    <div className="btc-context"><div><span>Price to beat</span><strong>{usd(detail?.assetPriceTerms?.priceToBeat)}</strong><small>Only the provider-supplied benchmark value is shown.</small></div><div><span>Settlement reference</span><strong>{verifiedBenchmark?'CF Benchmarks BRTI':'Read the published rules'}</strong><small>Exchange spot BTC prices are not substituted for settlement data.</small></div></div>
    <details className="btc-rules"><summary>Round rules and data source</summary><p>{rules||'Rules not yet returned by the public API.'}</p><p>Timing source: {current?.timeSource||'Unavailable'}. Prices refresh approximately every 10 seconds while this page is open. Requests can take longer during outages. This is polling, not a tick-by-tick stream.</p>{current&&<a href={`https://polymarket.us/event/${encodeURIComponent(current.event.slug)}`} target="_blank" rel="noreferrer">Open the official event ↗</a>}</details>
    <div className="btc-upcoming"><h3>Next rounds returned by the API</h3>{rounds.upcoming.length?rounds.upcoming.map(r=><p key={r.slug}>{time(r.start)} – {time(r.end)} <code>{r.slug}</code></p>):<p>No upcoming round has been returned yet. Discovery repeats automatically.</p>}</div>
    <details className="btc-rules"><summary>Recent observations ({history.length})</summary><div className="dashboard-table-wrap"><table><thead><tr><th>Received</th><th>Long bid</th><th>Long offer</th></tr></thead><tbody>{history.slice().reverse().map(h=><tr key={h.at}><td>{time(h.at)}</td><td>{price(h.bid)}</td><td>{price(h.ask)}</td></tr>)}</tbody></table></div></details>
    <p className="btc-limits">Read-only research view. No prediction signal, paper fill, or live order is generated from these quotes. Browser watching stops when the page closes; the Python recorder is a separate process.</p>
  </section>;
}
