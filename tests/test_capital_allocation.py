import pandas as pd

from backtesting.engine import BacktestEngine


def make_market(symbol):

    return pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2026-01-01 00:00",
            "2026-01-01 04:00",
            "2026-01-01 08:00",
            "2026-01-01 12:00",
        ], utc=True),

        "open": [100.0] * 4,
        "high": [101.0] * 4,
        "low": [99.0] * 4,
        "close": [100.0] * 4,

        "BUY": [True, False, True, False],
        "SELL": [False, True, False, False],

        "segment_id": [0, 0, 0, 0],
    })


def test_rotation():

    markets = {
        symbol: make_market(symbol)
        for symbol in [
            "BTCUSDT",
            "ETHUSDT",
            "XRPUSDT",
            "ZECUSDT",
        ]
    }

    engine = BacktestEngine(
        initial_capital=100,
        fee_rate=0,
        slippage_rate=0,
        max_open_positions=2,
    )

    result = engine.run(markets)

    positions = result["open_positions"]

    selected = set(positions.keys())

    print("\nFinal open positions:")
    for symbol in sorted(selected):
        print(symbol)

    expected = {"XRPUSDT", "ZECUSDT"}

    assert selected == expected, (
        f"Rotation failed. Expected {expected}, got {selected}"
    )

    assert len(positions) == 2

    print("\nPASS: Rotating allocation verified.")


if __name__ == "__main__":

    print("=" * 55)
    print("MABOT - ROTATING CAPITAL ALLOCATION TEST")
    print("=" * 55)

    test_rotation()

    print("\nALL TESTS PASSED")