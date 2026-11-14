import React, { useEffect, useState } from 'react';
import SoftAurora from './components/SoftAurora';

export default function App() {
  const [reduceMotion, setReduceMotion] = useState(true);
  const [animationPaused, setAnimationPaused] = useState(false);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduceMotion(preference.matches);
    update();
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);

  return (
    <main>
      <section className="hero" aria-labelledby="hero-title">
        <div className="aurora-layer" aria-hidden="true" style={{ width: '100%', height: '600px', position: 'relative' }}>
          <SoftAurora
            speed={reduceMotion || animationPaused ? 0 : 0.6}
            scale={1.5}
            brightness={1}
            color1="#f7f7f7"
            color2="#e100ff"
            bandHeight={0.5}
            bandSpread={1}
            enableMouseInteraction={!reduceMotion && !animationPaused}
            mouseInfluence={0.25}
            intro={!reduceMotion && !animationPaused}
            clickPulse={!reduceMotion && !animationPaused}
          />
        </div>
        <div className="hero-content">
          <header>
            <a className="brand" href="#top" aria-label="Oasis home"><span className="brand-icon">O</span> OASIS<span className="brand-ai"> / AI</span></a>
            <span className="mode"><span /> PAPER RESEARCH</span>
          </header>
          <div className="hero-copy" id="top">
            <p className="eyebrow">THE OASIS COMMAND CENTER</p>
            <h1 id="hero-title">Clarity in<br />a world of uncertainty.</h1>
            <p className="intro">Research the evidence. Evaluate the edge.<br />Build conviction through measured results.</p>
            <a className="primary" href="#workspace">Explore your workspace <span aria-hidden="true">↘</span></a>
          </div>
          <div className="hero-bottom"><span>RESEARCH / EVALUATE / REFINE</span><button type="button" onClick={() => setAnimationPaused(v => !v)} aria-pressed={animationPaused}>{animationPaused ? 'Resume background' : 'Pause background'}</button></div>
        </div>
      </section>
      <section id="workspace" className="workspace" aria-labelledby="workspace-title">
        <div className="section-heading"><div><p className="eyebrow">YOUR NEXT MOVE</p><h2 id="workspace-title">A foundation for better decisions.</h2></div><span className="connection">Backend not connected</span></div>
        <div className="cards">
          <article><span className="number">01 / RESEARCH</span><h3>Market intelligence</h3><p>Inspect market rules, timestamped evidence, and probability estimates in one place.</p><span className="planned">Planned integration</span></article>
          <article><span className="number">02 / SIMULATE</span><h3>Paper portfolio</h3><p>Follow simulated positions and evaluate results after costs and uncertainty.</p><span className="planned">Planned integration</span></article>
          <article><span className="number">03 / CONTROL</span><h3>Risk & activity</h3><p>Review spending limits, exposure, and the reasoning behind every decision.</p><span className="planned">Planned integration</span></article>
        </div>
        <footer><span>OasisWebAndAI</span><span>Frontend preview · No live trading</span></footer>
      </section>
    </main>
  );
}
