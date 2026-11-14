# Oasis V2

The paper engine is now connected to the hosted frontend through a scheduled Python worker. See [connected dashboard operation](CONNECTED_DASHBOARD.md) for architecture, controls, tests and operating limits.

The implementation remains paper-only. The legacy scheduled trader is retired in favor of the new worker. No live orders or account credentials are used by the connected dashboard.
