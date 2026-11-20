# MABOT Paper Trading — Phase 3 Operational Safeguards

## Implemented

- Rotating operational log file with console output.
- Capped exponential retry for read-only market-data calls.
- Per-symbol error isolation: one symbol's data failure no longer automatically prevents later symbols from being checked.
- Fail-closed circuit breaker: three consecutive symbol failures halt the remainder of the current cycle.
- Configurable retry attempts and log path from the command line.
- Added tests for retry success/failure, rotating log output, symbol retry/isolation, and circuit-breaker behavior.

## Validation

Full project test suite: **39 passed**.

A one-cycle live public-endpoint probe was attempted from this execution environment. It failed before reaching the API because DNS resolution for `apiv2.nobitex.ir` was unavailable in the sandbox (`NameResolutionError`). This is an environment/network limitation, not evidence that Nobitex itself is down. Therefore, live endpoint connectivity remains unverified and must be checked from the user's deployment machine.

## Run

```bash
pip install -r requirements.txt
python -m paper_trading.runner --once
python -m paper_trading.runner --interval 60 --retry-attempts 3
```

Default state database: `results/mabot_paper.sqlite3`  
Default rotating log: `results/logs/paper_runner.log`

## Safety boundary

- Public market-data endpoint only; no API key.
- No exchange order-placement/account/private trading calls.
- `LIVE_TRADING_ENABLED=False` remains unchanged.
- All fills are local virtual fills through `PaperBroker`.

This is an operationally safer paper runner, not authorization or readiness for real-money execution. Before unattended observation, verify the endpoint from the deployment environment, confirm symbol mapping and timestamps, and monitor the paper database/logs.
