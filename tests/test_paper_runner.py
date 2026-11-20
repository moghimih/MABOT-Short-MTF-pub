import pandas as pd

from paper_trading.runner import PaperSignalRunner
from paper_trading.broker import PaperBroker


class FakeClient:
    def __init__(self, frame): self.frame = frame
    def fetch_closed_4h(self, symbol): return self.frame.copy()


def candles(n=220):
    start = 1_700_000_000
    close = [100.0] * n
    return pd.DataFrame({
        "timestamp": [start + i*14400 for i in range(n)],
        "open": close, "high": [101.0]*n, "low": [99.0]*n,
        "close": close, "volume": [10.0]*n,
    })


def test_runner_marks_no_signal_and_ignores_duplicate(tmp_path):
    db = tmp_path / "paper.sqlite"
    broker = PaperBroker(db, initial_cash=100, fee_rate=0.002, slippage_rate=0.0005)
    runner = PaperSignalRunner(db, client=FakeClient(candles()), broker=broker)
    first = runner.process_symbol("BTCUSDT", candles())
    second = runner.process_symbol("BTCUSDT", candles())
    assert first["action"] == "NO_SIGNAL"
    assert second["action"] == "DUPLICATE_IGNORED"
    assert broker.cash == 100


def test_runner_triggers_paper_stop_and_uses_gap_open(tmp_path):
    db = tmp_path / "stop.sqlite"
    broker = PaperBroker(db, initial_cash=100, fee_rate=0.0, slippage_rate=0.0)
    broker.buy("seed", "BTCUSDT", 100, 0.1, 95)
    frame = candles()
    frame.loc[frame.index[-1], "open"] = 90
    frame.loc[frame.index[-1], "low"] = 89
    frame.loc[frame.index[-1], "close"] = 91
    runner = PaperSignalRunner(db, client=FakeClient(frame), broker=broker)
    result = runner.process_symbol("BTCUSDT", frame)
    assert result["action"] == "PAPER_STOP"
    assert not broker.positions()
    assert broker.trades()[-1]["price"] == 90


class FailingClient:
    def __init__(self, failures):
        self.failures = dict(failures)
    def fetch_closed_4h(self, symbol):
        remaining = self.failures.get(symbol, 0)
        if remaining > 0:
            self.failures[symbol] = remaining - 1
            raise TimeoutError("simulated API timeout")
        return candles()


def test_runner_retries_and_isolates_symbol_failure(tmp_path):
    db = tmp_path / "isolation.sqlite"
    client = FailingClient({"BTCUSDT": 2})
    runner = PaperSignalRunner(db, client=client, retry_attempts=3)
    results = runner.run_once(["BTCUSDT", "ETHUSDT"])
    assert [r["action"] for r in results] == ["NO_SIGNAL", "NO_SIGNAL"]


def test_runner_opens_circuit_after_three_symbol_failures(tmp_path):
    db = tmp_path / "circuit.sqlite"
    client = FailingClient({"BTCUSDT": 3, "ETHUSDT": 3, "ZECUSDT": 3})
    runner = PaperSignalRunner(db, client=client, retry_attempts=1)
    results = runner.run_once(["BTCUSDT", "ETHUSDT", "ZECUSDT", "XRPUSDT"])
    assert results[-1]["action"] == "CIRCUIT_OPEN"
    assert len(results) == 4
