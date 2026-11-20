# Multi-timeframe launcher update

The Windows `START_HERE.bat` launcher now asks for a timeframe at startup:
- `1h` uses Nobitex resolution `60`
- `4h` uses Nobitex resolution `240`
- `1d` uses Nobitex resolution `D`

Each timeframe writes to its own SQLite paper-account database, heartbeat file, log, and dashboard port:
- 1h: `results/paper_1h.sqlite3`, port 8081
- 4h: `results/paper_4h.sqlite3`, port 8082
- 1d: `results/paper_1d.sqlite3`, port 8083

To compare timeframes simultaneously, start `START_HERE.bat` in separate CMD windows and choose a different timeframe in each. Do not run two copies of the same timeframe against the same database.

The strategy and risk parameters are unchanged. This only generalizes candle retrieval and candle-gap handling. The 1h and 1d variants have not yet had separate historical backtests or forward validation. Each needs at least 201 closed candles for EMA200 warm-up; in particular, 1d needs about 201 days of usable data before its EMA200-based signals become active.

Paper-only safety remains unchanged: public market data, simulated fills, no exchange order methods, no API keys, and no real orders.
