import assert from 'node:assert/strict';
import {findRounds,roundWindow,bookQuote,bucketSlug,discoverRounds} from './btcRound.js';
const event={slug:'btc-updown-5m-2026-11-14-1200z',markets:[{slug:'btc-test'}]};
assert.equal(findRounds([event],Date.parse('2026-11-14T12:02:00Z')).current.slug,'btc-test');
assert.equal(findRounds([event],Date.parse('2026-11-14T12:05:00Z')).current,null);
assert.equal(findRounds([{...event,slug:'btc-updown-15m-2026-11-14-1200z'}],Date.parse('2026-11-14T12:02:00Z')).current,null);
assert.equal(roundWindow(event,{assetPriceTerms:{windowStart:'2026-11-14T12:00:00Z',windowEnd:'2026-11-14T12:15:00Z'}}),null);
const book={state:'MARKET_STATE_OPEN',offers:[{px:{value:'0.55',currency:'USD'},qty:'5'}],bids:[{px:{value:'0.50',currency:'USD'},qty:'8'}]};
assert.equal(bookQuote(book).ask.price,.55);
assert.equal(bookQuote(book).opposite.price,.5);
assert.equal(bookQuote({...book,offers:[{px:{value:'0.5',currency:'EUR'},qty:'5'}]}).ask,null);
console.log('BTC round selection, boundaries and book conversion checks passed');
const boundary=Date.parse('2026-11-14T12:05:00Z');
assert.equal(bucketSlug(boundary-1),'btc-updown-5m-2026-11-14-1200z');
assert.equal(bucketSlug(boundary),'btc-updown-5m-2026-11-14-1205z');
const rollover={...event,slug:bucketSlug(boundary),markets:[{slug:'new-round'}]};
const discovered=await discoverRounds(async path=>path.endsWith(rollover.slug)?{event:rollover}:{events:[event]},null,boundary);
assert.equal(discovered.current.slug,'new-round');
console.log('Direct lookup rollover checks passed');

const {analyzeRound}=await import('./btcRound.js');
const analysisInput={quote:bookQuote(book),stale:false,left:120,mapped:true,slug:'new-round',history:[]};
assert.equal(analyzeRound(analysisInput).lean,'Neutral');
const down={...analysisInput,quote:bookQuote({...book,offers:[{px:{value:'.4',currency:'USD'},qty:10}],bids:[{px:{value:'.39',currency:'USD'},qty:10}]})};
assert.equal(analyzeRound(down).lean,'Down');
assert.equal(analyzeRound({...analysisInput,quote:bookQuote({...book,bids:[{px:{value:'.54',currency:'USD'},qty:10}]})}).lean,'Up');
for(const invalid of [{stale:true},{mapped:false},{left:30},{quote:{...down.quote,spread:-.01}},{quote:{...down.quote,spread:.06}},{quote:{...down.quote,open:false}}]) {
  const result=analyzeRound({...down,...invalid});
  assert.equal(result.lean,'Unavailable');
  assert.equal(result.suggestion,'Wait');
}
assert.equal(analyzeRound(down).suggestion,'Wait');
console.log('Analysis freshness, mapping, spread and expiry gates passed');
