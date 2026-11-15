import React from 'react';

export default function BitcoinContext({clock}) {
  const reviewed=Date.parse('2026-11-14T23:40:00Z');
  const old=clock-reviewed>86400000;
  return <section className="btc-analysis btc-news" aria-labelledby="btc-news-title">
    <p className="eyebrow">SOURCED CONTEXT / DAILY AND WEEKLY HORIZON</p>
    <h3 id="btc-news-title">Why Bitcoin may be moving</h3>
    <p>Research reviewed November 14, 2026 (UTC). {old?'OUTDATED CONTEXT — recheck the sources before using.':'Dated research snapshot; headlines do not refresh automatically.'}</p>
    <article><h4>ETF withdrawals may weigh on demand</h4>
      <p>The Block reported roughly $1.07 billion of weekly U.S. spot Bitcoin ETF outflows and seven consecutive withdrawal sessions. Reduced fund demand is a plausible source of broader pressure; it does not identify the cause of this five-minute round.</p>
      <a href="https://www.theblock.co/news/markets/2026-11-14-bitcoin-etfs-lose-1-billion-for-the-second-week-in-a-row-as-crypto-funds-except-one-continue-bleeding-440337" target="_blank" rel="noreferrer">The Block · November 14, 2026 ↗</a>
    </article>
    <article><h4>Leverage and risk aversion can amplify declines</h4>
      <p>Investing.com reported forced liquidations alongside ETF outflows and broader risk aversion. Forced selling can accelerate a decline; reversals can still occur. This is reported background, not evidence of current liquidation flow.</p>
      <a href="https://in.investing.com/news/cryptocurrency-news/bitcoin-slides-below-68000-as-anthropic-ipo-frenzy-drains-market-liquidity-5704546" target="_blank" rel="noreferrer">Investing.com · November 14, 2026 ↗</a>
    </article>
    <p><strong>What is still unknown:</strong> live BRTI relative to the target, spot momentum, current ETF flow and liquidation feeds. News describes possible drivers; this app cannot establish the cause of an individual move. These reports are not used to force an Up or Down suggestion.</p>
  </section>;
}
