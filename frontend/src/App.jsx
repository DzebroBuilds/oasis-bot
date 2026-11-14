import React, { useEffect, useState } from 'react';
import FiveMinuteBTC from './FiveMinuteBTC';
import Dashboard from './Dashboard';
import SoftAurora from './components/SoftAurora';
import ProfileCard from './components/ProfileCard';
import portraitUrl from './assets/profile-placeholder.svg';
import iconUrl from './assets/iconpattern.svg';

export default function App() {
  const [reduceMotion, setReduceMotion] = useState(true);
  const [animationPaused, setAnimationPaused] = useState(false);
  const [contactNotice, setContactNotice] = useState(false);
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
        <FiveMinuteBTC />
        <Dashboard />
        <section className="profile-preview" aria-labelledby="profile-preview-title">
          <div className="profile-preview-copy">
            <p className="eyebrow">PROFILE / COMPONENT PREVIEW</p>
            <h2 id="profile-preview-title">A personal touch.</h2>
            <p>A holographic profile card with cursor-driven tilt, glare, and depth.</p>
            <p className="profile-preview-note">Sample profile and placeholder artwork. Replace these with your own details and portrait.</p>
            <p className="profile-contact-notice" role="status">{contactNotice ? 'Contact clicked — preview only. No message was sent.' : ''}</p>
          </div>
          <div className="profile-preview-card">
            <ProfileCard
              name="Javi A. Torres"
              title="Software Engineer"
              handle="javicodes"
              status="Online"
              contactText="Contact"
              avatarUrl={portraitUrl}
              iconUrl={iconUrl}
              holo={0.8}
              glare={0.5}
              tiltStrength={12}
              parallax={8}
              radius={16}
              enableTilt={true}
              intro={true}
              showUserInfo={true}
              enableMobileTilt={false}
              theme="dark"
              onContactClick={() => {
                console.log('Contact clicked');
                setContactNotice(true);
              }}
            />
          </div>
        </section>
        <footer><span>OasisWebAndAI</span><span>Paper research dashboard · No live trading</span></footer>
      </section>
    </main>
  );
}


