# BTC five-minute workspace

The default workspace now opens with a Polymarket US five-minute BTC view. It
discovers rounds through the public search API and reads current market details
and order books approximately every ten seconds while the page remains open.
Requests are serialized, cancelled on unmount, and time out after eight seconds.
The view rolls to the next discovered round and marks quotes older than twelve
seconds stale. Device clock accuracy affects the displayed countdown.

Only exact BTC five-minute event slugs and 300-second windows are selected.
Provider window fields take priority; missing windows fall back to the published
UTC event-slug schedule, explicitly labeled as such. Closed and expired rounds
are never represented as current. Long/opposite outcomes use provider side
descriptions when supplied. Missing quotes/depth remain unavailable.

The displayed target price comes only from the provider's assetPriceTerms.priceToBeat.
No exchange spot price or language-model estimate is substituted for BRTI data.
Read the actual contract rules: beginning/end benchmark averaging and payout rules
matter. The application is not a tick-level feed or a verified latency-sensitive
execution system. There are no BTC paper fills or live orders in this milestone.

## Unattended recorder

```powershell
python src/five_minute.py --db btc-five-minute.sqlite3 --interval 10
```

The Python process continuously discovers the active round and persists public
book observations to SQLite. `--once` records one observation; `--snapshot` prints
one public snapshot. It receives no trading keys and has no order endpoints.
Run it on an always-on host with persistent storage to collect while the browser
is closed. The code is included, but this process is not hosted by GitHub Pages.
The existing hourly dashboard job supplies general research snapshots only.

## Verification

```powershell
python -m unittest discover -s src -p "test_*.py" -v
cd frontend
node src/btcRound.test.mjs
npm run build
```

Official endpoints: https://docs.polymarket.us/api-reference/search/search and
https://docs.polymarket.us/api-reference/markets/get-market-book.
