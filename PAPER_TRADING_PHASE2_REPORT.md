# MABOT Paper Trading — Phase 2

## Delivered

Phase 2 adds a read-only Nobitex 4-hour candle client and a local paper signal runner.

- Fetches public OHLCV candles from the Nobitex UDF history endpoint; no API key is used.
- Filters out the currently forming candle, sorts timestamps, removes duplicate timestamps, validates OHLCV values and OHLC relationships.
- Rejects stale market data (default maximum age: 8 hours after the latest candle close).
- Rebuilds gap-aware segments and recalculates EMA200 separately inside each segment.
- Applies the existing Donchian BREAKOUT strategy without changing its parameters.
- Processes each `(symbol, candle_timestamp)` once using a SQLite primary key.
- Routes simulated fills only through the local SQLite `PaperBroker`.
- Simulates stop exits from candle OHLC; if a candle opens below the stop, uses the worse open as the reference price before adverse slippage.
- Continues to keep `LIVE_TRADING_ENABLED=False`.

## Run

From the project root, install requirements and run one cycle:

```bash
pip install -r requirements.txt
python -m paper_trading.runner --once
```

For continuous polling (the same closed candle is ignored on later polls):

```bash
python -m paper_trading.runner --interval 60
```

Default SQLite state is `results/mabot_paper.sqlite3`. Use `--db PATH` to select another path. The runner catches cycle errors and fails closed; it does not execute signals when data retrieval or validation fails.

## Safety boundary

This implementation contains no exchange order-placement, account-balance, withdrawal, or private authenticated trading calls. It is a paper simulator. It does not prove strategy profitability and should be observed before any separate decision about live trading. The stop fill is an OHLC-based approximation; real execution can be worse due to gaps, liquidity, spread, and market impact.

## Tests

Full project suite: **34 passed**.

New Phase 2 coverage includes closed-candle filtering, duplicate removal, stale-data rejection, gap-aware EMA warmup, duplicate signal suppression, and stop execution through an opening gap.

## Remaining before unattended deployment

- Verify the live endpoint response against current Nobitex behavior in the user's deployment environment.
- Add structured rotating logs, process supervision, alerting, and API backoff/circuit-breaker policy.
- Run a multi-day paper observation and reconcile candle timestamps and simulated fills.
- Add explicit portfolio-wide risk accounting and operational drawdown pause before unattended use.
