export const POLY_US = 'https://gateway.polymarket.us';
export function bucketSlug(now=Date.now()) {
  const stamp=new Date(Math.floor(now/300000)*300000).toISOString();
  return `btc-updown-5m-${stamp.slice(0,10)}-${stamp.slice(11,16).replace(':','')}z`;
}

export async function discoverRounds(fetchJson=publicJson,signal,now=Date.now()) {
  const results=await Promise.allSettled([
    fetchJson(`/v1/events/slug/${bucketSlug(now)}`,signal),
    fetchJson(`/v1/events/slug/${bucketSlug(now+300000)}`,signal),
    fetchJson('/v1/search?query=BTC%20Up%20or%20Down%205m&status=active&limit=50',signal)
  ]);
  const events=new Map();
  for(const result of results) {
    if(result.status!=='fulfilled') continue;
    const value=result.value;
    for(const event of [value.event,...(Array.isArray(value.events)?value.events:[])]) {
      if(event?.slug&&!events.has(event.slug)) events.set(event.slug,event);
    }
  }
  if(!events.size&&results.every(r=>r.status==='rejected')) throw new Error('Discovery unavailable');
  return findRounds([...events.values()],now);
}
const roundPattern = /^btc-updown-5m-(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})z$/;

export function roundWindow(event, market) {
  const terms=market.assetPriceTerms||{};
  let start=terms.windowStart||event.startTime;
  let end=terms.windowEnd||event.endTime;
  let source='provider fields';
  if(!start||!end) {
    const match=roundPattern.exec(event.slug||'');
    if(!match) return null;
    start=`${match[1]}T${match[2]}:${match[3]}:00Z`;
    end=new Date(Date.parse(start)+300000).toISOString();
    source='published event slug';
  }
  const a=Date.parse(start),b=Date.parse(end);
  return Number.isFinite(a)&&b-a===300000?{start:a,end:b,timeSource:source}:null;
}

export function findRounds(events,now=Date.now()) {
  const found=[];
  for(const event of events||[]) {
    if(!roundPattern.test(event.slug||'')||event.closed===true) continue;
    for(const market of event.markets||[]) {
      if(!/^[A-Za-z0-9_.-]{1,250}$/.test(market.slug||'')||market.closed===true) continue;
      const times=roundWindow(event,market);
      if(times&&times.end>now&&times.start<=now+900000) found.push({...times,event,market,slug:market.slug});
    }
  }
  found.sort((a,b)=>a.start-b.start);
  return {current:found.find(r=>r.start<=now&&now<r.end)||null,upcoming:found.filter(r=>r.start>now).slice(0,3)};
}

function price(level) {
  const amount=level?.px;
  const p=Number(amount?.value);
  const qty=Number(level?.qty);
  return amount?.currency==='USD'&&Number.isFinite(p)&&p>0&&p<1&&Number.isFinite(qty)&&qty>0?{price:p,size:qty}:null;
}

export function bookQuote(book) {
  const offers=(book?.offers||[]).map(price).filter(Boolean).sort((a,b)=>a.price-b.price);
  const bids=(book?.bids||[]).map(price).filter(Boolean).sort((a,b)=>b.price-a.price);
  const ask=offers[0]||null,bid=bids[0]||null;
  return {ask,bid,opposite:bid?{price:1-bid.price,size:bid.size}:null,
    spread:ask&&bid?ask.price-bid.price:null,open:book?.state==='MARKET_STATE_OPEN'};
}

export async function publicJson(path,signal) {
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),8000);
  const cancel=()=>controller.abort();
  signal?.addEventListener('abort',cancel,{once:true});
  if(signal?.aborted) controller.abort();
  try {
    const result=await fetch(POLY_US+path,{signal:controller.signal,cache:'no-store'});
    if(!result.ok) throw new Error(`Public data unavailable (${result.status})`);
    return await result.json();
  } finally {clearTimeout(timeout);signal?.removeEventListener('abort',cancel);}
}

export function analyzeRound({quote,stale,left,mapped,history=[],slug}) {
  const base={lean:'Unavailable',suggestion:'Wait',confidence:'Not rated',mid:null,reasons:[]};
  if(stale||!quote.open) return {...base,reasons:['Quotes are stale, paused, expired, or the market is not open.']};
  if(!mapped) return {...base,reasons:['Up/Down outcome mapping could not be verified from the published rules and sides.']};
  if(!quote.bid||!quote.ask||quote.spread<0||quote.spread>0.05+1e-9)
    return {...base,reasons:['A valid two-sided book with a spread of at most 5 cents is required.']};
  const mid=(quote.bid.price+quote.ask.price)/2;
  const lean=quote.bid.price>0.5?'Up':quote.ask.price<0.5?'Down':'Neutral';
  const observations=history.filter(h=>h.slug===slug&&Number.isFinite(h.bid)&&Number.isFinite(h.ask));
  const first=observations[0],last=observations.at(-1);
  const change=observations.length>=3?(last.bid+last.ask-first.bid-first.ask)/2:null;
  const reasons=[
    `Up bid/offer: ${(quote.bid.price*100).toFixed(1)} / ${(quote.ask.price*100).toFixed(1)} cents; midpoint ${(mid*100).toFixed(1)} cents.`,
    lean==='Neutral'?'The bid/offer interval includes 50 cents; there is no clear market favorite.':`The two-sided market pricing favors ${lean}; this is market sentiment, not an independently calculated win probability.`,
    change===null?'Collecting at least three observations for quote trend.':`Up midpoint changed ${(change*100).toFixed(1)} cents across ${observations.length} observations of this round. This is contract-price movement, not BTC momentum.`,
    left<=30?'Fewer than 30 seconds remain: settlement and request delays dominate.':'Live BRTI momentum, an independently tested forecast, and fees are not available here; no positive trading edge is established.'
  ];
  return {...base,lean: left<=30?'Unavailable':lean,confidence:'Low · market pricing only',mid,reasons};
}
