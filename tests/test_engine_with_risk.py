import math

import pandas as pd

from backtesting.engine_with_risk import RiskBacktestEngine


def bar(
    timestamp,
    open_price,
    high,
    low,
    close,
    buy=False,
    sell=False,
    atr=2.0,
    segment_id=0,
    priority=None,
):
    row = {
        "timestamp": timestamp,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "BUY": buy,
        "SELL": sell,
        "ATR14": atr,
        "segment_id": segment_id,
    }
    if priority is not None:
        row["BUY_PRIORITY"] = priority
    return row


def make_market(rows):
    return pd.DataFrame(rows)


def make_engine(
    initial_capital=1000.0,
    max_open_positions=2,
    risk_per_trade=0.01,
    max_portfolio_risk=0.02,
):
    return RiskBacktestEngine(
        initial_capital=initial_capital,
        fee_rate=0.0,
        slippage_rate=0.0,
        max_open_positions=max_open_positions,
        risk_per_trade=risk_per_trade,
        max_portfolio_risk=max_portfolio_risk,
        atr_multiplier=2.5,
    )


def test_next_candle_execution():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 105, 107, 103, 106),
        bar("2026-01-01 08:00", 106, 108, 104, 107),
    ])

    result = make_engine().run({"BTCUSDT": data})
    assert len(result["trades"]) == 0
    assert "BTCUSDT" in result["open_positions"]
    position = result["open_positions"]["BTCUSDT"]
    assert position["entry_time"] == pd.Timestamp("2026-01-01 04:00", tz="UTC")
    assert math.isclose(position["entry_price"], 105.0)
    print("PASS: Next candle execution")


def test_initial_stop_and_one_percent_risk():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
        bar("2026-01-01 08:00", 100, 101, 99, 100),
    ])

    result = make_engine().run({"BTCUSDT": data})
    position = result["open_positions"]["BTCUSDT"]

    assert math.isclose(position["initial_stop"], 95.0)
    assert math.isclose(position["initial_risk"], 10.0, rel_tol=1e-6)
    print("PASS: Initial stop and 1% risk")


def test_normal_stop_execution():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
        bar("2026-01-01 08:00", 100, 101, 94, 96),
    ])

    result = make_engine().run({"BTCUSDT": data})
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert trade["exit_reason"] == "STOP_LOSS"
    assert math.isclose(trade["exit_price"], 95.0)
    print("PASS: Normal stop execution")


def test_gap_stop_execution():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
        bar("2026-01-01 08:00", 90, 92, 88, 91),
    ])

    result = make_engine().run({"BTCUSDT": data})
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert trade["exit_reason"] == "GAP_STOP"
    assert math.isclose(trade["exit_price"], 90.0)
    print("PASS: Gap stop execution")


def test_sell_signal_before_intrabar_stop():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100, sell=True),
        bar("2026-01-01 08:00", 100, 101, 94, 96),
    ])

    result = make_engine().run({"BTCUSDT": data})
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert trade["exit_reason"] == "SIGNAL_SELL"
    assert math.isclose(trade["exit_price"], 100.0)
    print("PASS: Sell signal before intrabar stop")


def test_trailing_stop_timing():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True, atr=2),
        bar("2026-01-01 04:00", 100, 121, 99, 120, atr=2),
        bar("2026-01-01 08:00", 120, 131, 119, 130, atr=2),
        bar("2026-01-01 12:00", 130, 131, 124, 126, atr=2),
    ])

    result = make_engine().run({"BTCUSDT": data})
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert math.isclose(trade["final_stop"], 125.0)
    assert trade["exit_reason"] == "STOP_LOSS"
    assert math.isclose(trade["exit_price"], 125.0)
    print("PASS: Trailing stop timing")


def test_portfolio_risk_limit():
    data_a = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
    ])
    data_b = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
    ])

    result = make_engine(
        max_open_positions=2,
        risk_per_trade=0.02,
        max_portfolio_risk=0.02,
    ).run({"BTCUSDT": data_a, "ETHUSDT": data_b})

    assert len(result["open_positions"]) <= 1
    total_risk = sum(
        p["risk_amount"] for p in result["open_positions"].values()
    )
    assert total_risk <= result["summary"]["final_equity"] * 0.02 + 1e-6
    print("PASS: Portfolio risk limit")


def test_invalid_atr_rejected():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True, atr=float("nan")),
        bar("2026-01-01 04:00", 100, 101, 99, 100, atr=2),
        bar("2026-01-01 08:00", 100, 101, 99, 100, atr=2),
    ])

    result = make_engine().run({"BTCUSDT": data})
    assert len(result["trades"]) == 0
    assert "BTCUSDT" not in result["open_positions"]
    print("PASS: Invalid ATR rejected")


def test_segment_boundary_protection():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True, segment_id=0),
        bar("2026-01-01 04:00", 100, 101, 99, 100, segment_id=1),
        bar("2026-01-01 08:00", 100, 101, 99, 100, segment_id=1),
    ])

    result = make_engine().run({"BTCUSDT": data})
    assert len(result["trades"]) == 0
    assert "BTCUSDT" not in result["open_positions"]
    print("PASS: Segment boundary protection")


def test_rotating_allocation():
    btc = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
    ])
    eth = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
    ])

    result = make_engine(
        initial_capital=1000,
        max_open_positions=1,
        risk_per_trade=0.01,
        max_portfolio_risk=0.02,
    ).run({"BTCUSDT": btc, "ETHUSDT": eth})

    assert len(result["open_positions"]) == 1
    assert next(iter(result["open_positions"])) == "BTCUSDT"
    print("PASS: Rotating allocation")


if __name__ == "__main__":
    print("=" * 60)
    print("MABOT - RISK ENGINE TESTS")
    print("=" * 60)

    test_next_candle_execution()
    test_initial_stop_and_one_percent_risk()
    test_normal_stop_execution()
    test_gap_stop_execution()
    test_sell_signal_before_intrabar_stop()
    test_trailing_stop_timing()
    test_portfolio_risk_limit()
    test_invalid_atr_rejected()
    test_segment_boundary_protection()
    test_rotating_allocation()

    print("=" * 60)
    print("ALL RISK ENGINE TESTS PASSED")
    print("=" * 60)


def test_engine_rejects_invalid_execution_costs():
    try:
        RiskBacktestEngine(fee_rate=1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid fee rate should be rejected")


def test_engine_rejects_non_boolean_signal_strings():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100),
        bar("2026-01-01 04:00", 100, 101, 99, 100),
    ])
    data["BUY"] = ["BUY", "NO"]
    try:
        make_engine().run({"BTCUSDT": data})
    except ValueError as exc:
        assert "BUY" in str(exc)
    else:
        raise AssertionError("Invalid signal values should be rejected")


def test_drawdown_includes_initial_capital_before_first_equity_record():
    data = make_market([
        bar("2026-01-01 00:00", 100, 101, 99, 100, buy=True),
        bar("2026-01-01 04:00", 100, 101, 90, 92),
    ])
    result = make_engine(initial_capital=1000).run({"BTCUSDT": data})
    assert math.isclose(result["summary"]["max_drawdown_pct"], -1.0, abs_tol=1e-6)
