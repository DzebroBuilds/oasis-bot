# Polymarket US market-data integration

The Python worker calls the public US gateway at https://gateway.polymarket.us.
It does not use the international Polymarket service, API keys, order endpoints,
balances, or private portfolio data. No SDK dependency is needed for public GETs.

The adapter follows the same endpoints as the official SDK: GET /v1/markets and
GET /v1/markets/{slug}/bbo. It samples up to 50 explicitly active, non-closed markets
and enriches up to ten best-bid/offer snapshots. Provider failure retains previous
data with its original timestamp and reports independent exchange health.

Source IDs are namespaced PMUS:<slug>. They cannot be routed through the Kalshi
paper signal handler. Polymarket US is read-only in this milestone.

The UI labels the underlying long outcome; its opposite ask is calculated as one
minus the long best bid. This is an indicative snapshot, not an executable quote
or arbitrage opportunity. Prices round upward to cents for the current paper-ledger
schema. USD validation and missing-data handling prevent foreign-currency values,
last-trade prices or missing depth from being passed off as current asks.

No automatic equivalent-market mapping is created. Similar names do not establish
identical outcomes, settlement sources, cutoff times, fees or payout conditions.
Those must be reviewed before any price comparison is treated as a strategy.

Official references:
- https://docs.polymarket.us/api-reference/introduction
- https://docs.polymarket.us/api-reference/markets/get-markets
- https://docs.polymarket.us/api-reference/markets/get-market-bbo
- https://github.com/Polymarket/polymarket-us-python
