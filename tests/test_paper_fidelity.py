"""Paper runner fidelity: same logic as the validated backtest, and robust to downtime."""
import contextlib
import io
from pathlib import Path

import pandas as pd
import pytest

from paper_trading.broker import PaperBroker
from paper_trading.runner import PaperSignalRunner

ROOT = Path(__file__).resolve().parent.parent
STEP = 4 * 3600
COLS = ["timestamp", "open", "high", "low", "close", "volume"]


def flat(n=240, price=100.0, start=1_700_000_000):
    return pd.DataFrame({"timestamp": [start + i * STEP for i in range(n)], "open": price,
                         "high": price * 1.01, "low": price * 0.99, "close": price, "volume": 10.0})


def test_equity_values_each_position_at_its_own_price(tmp_path):
    db = tmp_path / "p.sqlite"
    broker = PaperBroker(db, 100.0, 0.0, 0.0, 2)
    runner = PaperSignalRunner(db, broker=broker, client=object())
    broker.buy("e1", "ETHUSDT", 1800.0, 0.02, 1700.0)       # 36 USD in ETH, 64 cash
    runner._set_mark("ETHUSDT", 1800.0)
    runner._set_mark("BTCUSDT", 64000.0)                      # another symbol's price must not leak in
    assert runner._equity() == pytest.approx(100.0)


def test_catch_up_applies_a_stop_hit_during_downtime(tmp_path):
    db = tmp_path / "c.sqlite"
    broker = PaperBroker(db, 100.0, 0.0, 0.0, 2)
    runner = PaperSignalRunner(db, broker=broker, client=object())
    frame = flat()
    runner.process_symbol("BTCUSDT", frame.iloc[:230])         # observing from candle 229
    broker.buy("seed", "BTCUSDT", 100.0, 0.1, 95.0)
    later = frame.copy()
    later.loc[232, ["open", "high", "low", "close"]] = [96.0, 96.5, 90.0, 92.0]   # crash 3 candles ago
    later.loc[233:, ["open", "high", "low", "close"]] = 92.0                       # price stays low
    later.loc[233:, "high"], later.loc[233:, "low"] = 92.5, 91.5
    result = runner.process_symbol("BTCUSDT", later)           # runner "wakes up" at candle 239
    assert not broker.positions(), "stop hit while offline must not be skipped"
    assert broker.trades()[-1]["side"] == "SELL" and broker.trades()[-1]["price"] == pytest.approx(95.0)
    assert result["timestamp"] == int(later.timestamp.iloc[-1])


def test_trailing_stop_moves_up_only(tmp_path):
    db = tmp_path / "t.sqlite"
    broker = PaperBroker(db, 100.0, 0.0, 0.0, 2)
    runner = PaperSignalRunner(db, broker=broker, client=object())
    frame = flat()
    runner.process_symbol("BTCUSDT", frame.iloc[:230])
    broker.buy("seed", "BTCUSDT", 100.0, 0.1, 80.0)
    up = frame.copy()
    up.loc[230:, ["open", "high", "low", "close"]] = [109.0, 111.0, 108.0, 110.0]
    runner.process_symbol("BTCUSDT", up.iloc[:232])
    raised = broker.positions()["BTCUSDT"]["stop_price"]
    assert raised > 80.0
    with pytest.raises(ValueError):
        broker.update_stop("BTCUSDT", raised - 1)


@pytest.mark.skipif(not (ROOT / "btcusdt_4h_native_gap_aware.csv").exists(), reason="data files not present")
def test_paper_replay_matches_risk_backtest_engine(tmp_path):
    from backtesting.engine_with_risk import RiskBacktestEngine
    from indicators.engine import calculate_all_indicators
    from strategies.breakout import BreakoutStrategy

    symbols = ["BTCUSDT", "ETHUSDT", "ZECUSDT", "XRPUSDT"]
    raw = {s: pd.read_csv(ROOT / f"{s.lower()}_4h_native_gap_aware.csv") for s in symbols}
    ticks = sorted(set.intersection(*[set(df.timestamp) for df in raw.values()]))[-350:]

    class Replay:
        now = 0
        def fetch_closed_4h(self, symbol):
            d = raw[symbol]
            return d[d.timestamp <= self.now][COLS].tail(300).reset_index(drop=True)

    client = Replay()
    db = tmp_path / "r.sqlite"
    broker = PaperBroker(db, 100.0, 0.002, 0.0005, 2)
    runner = PaperSignalRunner(db, client=client, broker=broker, retry_attempts=1)
    for i, t in enumerate(ticks):
        if i % 2:                                              # poll every other candle: catch-up must cover
            continue
        client.now = t
        runner.run_once(symbols)
    client.now = ticks[-1]
    runner.run_once(symbols)

    sig = {}
    for s in symbols:
        df = raw[s].copy()
        df["timestamp"] = pd.to_datetime(df.timestamp, unit="s", utc=True)
        enriched = calculate_all_indicators(df)
        x = BreakoutStrategy().generate_signals(enriched).copy()
        for c in ("timestamp", "open", "high", "low", "close", "ATR14", "segment_id"):
            if c not in x.columns:
                x[c] = enriched[c].to_numpy()
        sig[s] = x[x.timestamp >= pd.to_datetime(ticks[0], unit="s", utc=True)].reset_index(drop=True)
    with contextlib.redirect_stdout(io.StringIO()):
        engine = RiskBacktestEngine().run(sig)
    eng_entries = {(r.symbol, int(pd.Timestamp(r.entry_time).timestamp())) for r in engine["trades"].itertuples()}
    paper_entries = {(e["symbol"], int(e["event_id"].split(":")[1]) + STEP)
                     for e in broker.trades() if e["side"] == "BUY"}
    assert len(eng_entries) >= 5                               # the scenario must really trade
    assert abs(len(paper_entries) - len(eng_entries)) <= 1
    assert len(paper_entries & eng_entries) >= 0.85 * len(eng_entries)


def test_report_summarises_round_trips(tmp_path):
    from paper_trading.report import build_report
    db = tmp_path / "rep.sqlite"
    broker = PaperBroker(db, 100.0, 0.0, 0.0, 2)
    runner = PaperSignalRunner(db, broker=broker, client=object())
    broker.buy("BTCUSDT:1:BUY", "BTCUSDT", 100.0, 0.5, 90.0)
    broker.sell("BTCUSDT:2:SELL", "BTCUSDT", 110.0)
    runner._set_mark("BTCUSDT", 110.0)
    runner._snapshot(2)
    r = build_report(str(db))
    assert r["trades"] == 1 and r["net_pnl"] == pytest.approx(5.0) and r["equity"] == pytest.approx(105.0)
