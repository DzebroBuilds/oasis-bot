import React,{Component,useEffect,useState} from 'react';
import DitherVeil from './components/DitherVeil';
import './veil-core.css';

const SRC='https://images.unsplash.com/photo-1737071371043-761e02b1ef95?q=80&w=1400&auto=format&fit=crop';
class VeilBoundary extends Component {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<div className="veil-fallback"><img src={SRC} alt="OASIS visual core"/><p>Interactive rendering unavailable. Market controls remain available.</p></div>:this.props.children;}
}
export default function VeilCore({live,motion,analysis,current,left,observed,explanations,onSensor}) {
  const [enabled,setEnabled]=useState(true);
  const [command,setCommand]=useState(''),[reply,setReply]=useState(null),[supported,setSupported]=useState(null),[imageError,setImageError]=useState(false);
  useEffect(()=>{
    const canvas=document.createElement('canvas');
    try {const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');setSupported(Boolean(gl));gl?.getExtension('WEBGL_lose_context')?.loseContext();}catch{setSupported(false);}
  },[]);
  const respond=(input)=>{
    const text=input.trim().toLowerCase();
    let answer;
    if(/^(brief|briefing|status|explain|explain lean)$/.test(text)) answer=`Lean: ${analysis.lean}. Suggestion: ${analysis.suggestion}. ${analysis.confidence}. ${analysis.reasons.join(' ')}`;
    else if(/^(book|order book|depth)$/.test(text)){onSensor('book');answer=explanations.book;}
    else if(/^(trend|pulse|market pulse)$/.test(text)){onSensor('trend');answer=explanations.trend;}
    else if(/^(round|clock|time)$/.test(text)){onSensor('clock');answer=explanations.clock;}
    else if(/^(sources|news|context)$/.test(text)){onSensor('news');answer=explanations.news;document.getElementById('btc-news-title')?.scrollIntoView({behavior:motion?'smooth':'auto',block:'center'});}
    else answer='Available commands: briefing, book, trend, round, sources. This panel explains connected data; it is not a general-purpose chat model.';
    setReply({question:input,answer,at:Date.now(),slug:current?.slug||'No active round',observed});
    setCommand('');
  };
  const renderVeil=enabled&&motion&&supported!==false&&!imageError;
  return <div className="veil-console">
    <div className={`veil-stage ${live?'veil-connected':''} ${renderVeil?'veil-alive':''}`}>
      <div className="veil-visual" aria-hidden="true">
        <img className="veil-underlay" src={SRC} alt="" onError={()=>setImageError(true)}/>
        {renderVeil&&supported&&<VeilBoundary><DitherVeil src={SRC} pattern="floyd" pixelSize={2} inkColor="#120f17" paperColor="#f4f1ea" revealRadius={200} softness={0.6} linger={1} wander={true} clickBurst={true}/></VeilBoundary>}
      </div>
      <div className="veil-frame" aria-hidden="true"><span>OASIS // VISUAL CORE</span><span>{live?'TELEMETRY CONNECTED':'TELEMETRY WAITING'}</span></div>
      <div className="veil-identity"><span className="veil-kicker">O A S I S</span><strong>Intelligence, in view.</strong><p>{renderVeil?'Ambient visual core · responsive to your presence.':'Static core · interaction effects paused.'}</p></div>
      <div className="veil-state"><i/>{live?'Market data connected':'Waiting for fresh market data'}<span>{current?left+'s in round':'No active round'}</span></div>
      {imageError&&<p className="veil-error">Artwork could not load. Market analysis is still available.</p>}
    </div>
    <div className="veil-ambient-control"><span>Living wallpaper · ambient motion</span><button aria-pressed={!enabled} onClick={()=>setEnabled(v=>!v)}>{enabled?'Pause wallpaper':'Resume wallpaper'}</button></div>
    {!motion&&<p className="veil-note">Reduced motion uses static artwork. Enable motion with the Brain control to restore the effect.</p>}
    {supported===false&&<p className="veil-note">WebGL is unavailable; static artwork is shown.</p>}
    <div className="veil-command">
      <div className="veil-command-head"><span>OASIS COMMAND INTERFACE</span><small>Data briefings · no orders</small></div>
      <div className="veil-quick">{['Briefing','Book','Trend','Round','Sources'].map(item=><button key={item} onClick={()=>respond(item)}>{item}</button>)}</div>
      <form onSubmit={e=>{e.preventDefault();if(command.trim())respond(command);}}><label className="veil-sr" htmlFor="oasis-command">Ask OASIS for a briefing, book, trend, round or sources</label><span aria-hidden="true">›</span><input id="oasis-command" value={command} onChange={e=>setCommand(e.target.value)} placeholder="Try “briefing” or “trend”…" maxLength={160} autoComplete="off"/><button disabled={!command.trim()}>Send</button></form>
      <div className="veil-response" role="status" aria-live="polite">{reply?<><span>{reply.question} · {new Date(reply.at).toLocaleTimeString()}</span><p>{reply.answer}</p><small>{reply.slug} · {reply.observed?'Quote received '+new Date(reply.observed).toLocaleTimeString():'No quote available'}. Briefing snapshot; request again to update.{reply.slug!==current?.slug?' Round changed since this briefing.':''}</small></>:<p>Select a briefing to see what the available data says. Every response identifies its round and observation time.</p>}</div>
    </div>
  </div>;
}
