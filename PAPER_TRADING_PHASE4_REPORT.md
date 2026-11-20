# MABOT Paper Trading — Phase 4: review and fixes (2026-11-19)

Phase 3's runner (retries, logging, circuit breaker) worked, but its **trading logic did not match the validated backtest**, so its results could not be compared with the research. Replaying the real 4h data (last 900 candles, 4 symbols):

| Version | Trades | Return | Max DD |
|---|---|---|---|
| Risk backtest engine (reference) | 34 | +1.90% | -12.77% |
| Phase 3 runner, polled every candle | 31 | +5.58% | -10.60% |
| Phase 3 runner, polled every 3rd candle | 15 | +11.57% | -5.91% |
| **Fixed runner, polled every candle** | **34** | +2.89% | -12.59% |
| **Fixed runner, polled every 3rd candle** | **34** (identical) | +2.89% | -11.20% (sampled less often) |

## Bugs found and fixed
1. **Equity used one symbol's price for all positions.** While processing BTC (64 000), an ETH position of 0.02 was valued at 1 280 USD, so equity was inflated about 13x and risk sizing was meaningless. Now each holding is valued at its own last close (`marks` table).
2. **Downtime skipped candles.** Only the latest candle was processed, so stops and signals during an outage were lost and results became optimistic. Now every unprocessed closed candle is processed once, in time order across symbols (first run observes from the latest candle only).
3. **Different risk rules from the backtest.** The runner used a fixed Donchian-channel stop, no trailing, no portfolio-risk cap and a "50% of cash" size cap. Now it uses the engine's rules: ATR x 2.5 initial stop, up-only trailing stop, 1% equity risk with fees and slippage, 2% portfolio-risk cap (`risk/` modules shared with the engine).
4. EMA200/ATR14 now come from the project's `calculate_all_indicators` (signals were already identical: 0 mismatches on all four symbols).

## Added
- `PaperBroker.update_stop` (stops only move up), `equity_snapshots` table, `python -m paper_trading.report`.
- 5 new tests: per-symbol valuation, stop hit during downtime, trailing stop, replay parity against `RiskBacktestEngine` (same trade count within 1, >=85% identical entries), report. Suite: 44 tests.

## Known differences from the backtest (by design)
- Fills use the signal candle's close plus slippage (the live-like proxy of the next open); the backtest fills at the next open. Entries matched 33 of 34 in the replay.
- When two symbols signal on the same candle and only one slot is free, the runner takes them in `SYMBOLS` order; the engine rotates priority.

## Still not verified
- Live Nobitex responses (no network in the review environment). Run `python -m paper_trading.runner --once` on your PC and check that candle timestamps, prices and the symbol names (`BTCUSDT`, ...) look right.
- Polling every 60 s refetches 300 candles per symbol; `--interval 900` is enough for 4h candles.
