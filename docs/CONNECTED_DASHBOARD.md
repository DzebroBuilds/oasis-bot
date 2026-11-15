# Connected Oasis paper dashboard

The GitHub Pages frontend reads public JSON produced by Python on GitHub Actions.
It is a scheduled research dashboard, not an always-on trading API.

## Components

- `src/dashboard_runner.py`: unauthenticated Kalshi market-data client, bounded event
  scan, paper-signal ingestion, finalized-market settlement reconciliation, optional
  grounded Gemini research, and public dashboard export.
- `src/paper_engine.py`: transactional paper ledger, budgets, duplicate prevention,
  side-specific prices, conservative fee bounds and uncertainty deductions.
- `frontend/src/Dashboard.jsx`: scanner, portfolio, decisions, research and controls.
- `.github/workflows/dashboard.yml` on main: hourly/manual worker with serialized
  state writes. The source checkout is pinned to an approved feature-branch commit.
- `.github/workflows/pages.yml` on main: deploys a pinned frontend snapshot.
- `oasis-data` branch: public paper-only `ledger.json`, `paper-signals.json`, and
  `dashboard.json`. The worker fails if the ledger is missing/corrupt rather than
  silently resetting budget accounting.

## Operation

Open the site and use **Run / pause scanner**. This opens GitHub's authenticated
workflow controls. Choose **Run workflow**, branch **main**, and action `scan`,
`pause`, or `resume`. Scheduled runs occur hourly, subject to GitHub delays. Pause
is applied when the job executes, not immediately from the browser. Workflow
concurrency serializes jobs, so an in-flight run finishes before pause is applied.

The frontend reloads the published snapshot every minute. Refresh dashboard reloads
data; it does not start a scan. Stale/error states display explicitly. Provider
outages retain the previous market-data timestamp and prior snapshot.

The public feed contains no account balance, private portfolio, credentials, or
live orders. Do not add private data to this public repository or its ledger.

## Paper signals

By default the inbox is empty. No model probabilities are invented from market
prices, and there is no automatic strategy approval. A forecast may be submitted
through **Manage paper signals** using GitHub's authenticated editor. Its schema:

```json
[
  {
    "ticker": "ACTUAL-OPEN-MARKET-TICKER",
    "model_version": "your-reviewed-model-version",
    "probability_yes": 0.65,
    "uncertainty": 0.10,
    "fee_bound_cents": 3,
    "evidence": [
      {"url": "https://example.com/replace-with-source", "observed_at": "REPLACE_WITH_CURRENT_ISO_TIMESTAMP", "summary": "Replace with supporting evidence"}
    ]
  }
]
```

This example is not a recommendation or valid submission. Evidence must be fresh
when the job runs. Probability and uncertainty are uncalibrated unless independently
evaluated. Quotes, market rules and identity are fetched from Kalshi, not taken from
the submitted signal. Orderbook opposing bids supply side-specific ask liquidity.
Missing liquidity prevents a fill. Positions are simulated only; fee bounds are
caller-supplied, and assumed fills do not model queue position, latency or slippage.
Clear processed signals from the inbox to avoid reevaluating stale submissions;
the permanent market duplicate rule independently prevents a second entry.

## Optional AI research

Manual runs may enable `enable_research`. This uses the existing repository secret
`GEMINI_API_KEY`, with a maximum of three public markets per run. Default scheduled
runs do not use Gemini. Provider usage can incur charges. The model is selected by
`GEMINI_MODEL` (default `gemini-4-hydrogen`). Source-cited text is displayed as research,
never converted directly into an order. Missing keys, errors or missing citations
are explicit statuses. No API key is sent to the frontend or published in the feed.

The provider adapter is based on official public documentation; successful model
access, current billing and grounding-display terms must be verified before treating
this optional integration as production-ready. Paid provider calls are not part of CI.

## Validate locally

```powershell
python -m unittest discover -s src -p "test_*.py" -v
python -m compileall -q src
cd frontend
npm install --ignore-scripts
npm run build
```

Runtime Python worker uses only the standard library. The legacy agent and its
Gemini/Telegram/Firebase dependencies remain separate; the new workflow does not
invoke that agent or receive Kalshi trading credentials.

Official API references:
- https://docs.kalshi.com/getting_started/quick_start_market_data
- https://docs.kalshi.com/api-reference/market/get-markets
- https://docs.kalshi.com/api-reference/events/get-events
- https://ai.google.dev/gemini-api/docs/google-search
