# Oasis

Oasis is a paper-trading research dashboard for Kalshi, built with Python and React.

**Live frontend:** https://dzebrobuilds.github.io/oasis-bot/

The connected dashboard uses a scheduled Python worker on GitHub Actions and a
durable public paper ledger. It displays market snapshots, paper positions,
decisions, research and scanner status. GitHub sign-in protects run controls.

See [connected dashboard operation](docs/CONNECTED_DASHBOARD.md) for architecture,
run/pause controls, optional AI research, paper signals and verification commands.

Live order execution remains disabled in the V2 implementation. Paper fills and
uncalibrated forecasts are not actual investment performance. The legacy agent is
not used by the connected dashboard workflow.
