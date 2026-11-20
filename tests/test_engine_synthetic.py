import pandas as pd

from backtesting.engine import BacktestEngine


def make_data(symbol, rows):
    df = pd.DataFrame(rows)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], utc=True
    )

    df["segment_id"] = 0

    return df


def test_next_candle_execution():
    data = make_data("BTCUSDT", [
        {
            "timestamp": "2026-01-01 00:00",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "BUY": True,
            "SELL": False,
        },
        {
            "timestamp": "2026-01-01 04:00",
            "open": 110,
            "high": 112,
            "low": 109,
            "close": 111,
            "BUY": False,
            "SELL": False,
        },
    ])

    engine = BacktestEngine(
        initial_capital=100,
        fee_rate=0,
        slippage_rate=0,
        max_open_positions=1,
    )

    result = engine.run({"BTCUSDT": data})

    assert len(result["trades"]) == 0
    assert len(result["open_positions"]) == 1

    position = result["open_positions"]["BTCUSDT"]

    assert position["entry_price"] == 110

    print("PASS: Next candle execution")


def test_fee_and_slippage():
    data = make_data("BTCUSDT", [
        {
            "timestamp": "2026-01-01 00:00",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "BUY": True,
            "SELL": False,
        },
        {
            "timestamp": "2026-01-01 04:00",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "BUY": False,
            "SELL": True,
        },
        {
            "timestamp": "2026-01-01 08:00",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "BUY": False,
            "SELL": False,
        },
    ])

    engine = BacktestEngine(
        initial_capital=100,
        fee_rate=0.002,
        slippage_rate=0.0005,
        max_open_positions=1,
    )

    result = engine.run({"BTCUSDT": data})

    assert len(result["trades"]) == 1

    trade = result["trades"].iloc[0]

    assert trade["entry_price"] > 100
    assert trade["exit_price"] < 100
    assert trade["net_pnl"] < 0

    print("PASS: Fee and slippage")


def test_position_limit():
    btc = make_data("BTCUSDT", [
        {
            "timestamp": "2026-01-01 00:00",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "BUY": True,
            "SELL": False,
        },
        {
            "timestamp": "2026-01-01 04:00",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "BUY": False,
            "SELL": False,
        },
    ])

    eth = btc.copy()
    eth["BUY"] = [True, False]

    engine = BacktestEngine(
        initial_capital=100,
        fee_rate=0,
        slippage_rate=0,
        max_open_positions=1,
    )

    result = engine.run({
        "BTCUSDT": btc,
        "ETHUSDT": eth,
    })

    assert len(result["open_positions"]) <= 1

    print("PASS: Maximum open positions")


if __name__ == "__main__":
    print("=" * 55)
    print("MABOT - SYNTHETIC ENGINE TESTS")
    print("=" * 55)

    test_next_candle_execution()
    test_fee_and_slippage()
    test_position_limit()

    print("\nALL TESTS PASSED")