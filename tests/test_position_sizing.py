from risk.position_sizing import calculate_position_size


def test_basic_position_sizing():

    result = calculate_position_size(
        equity=100,
        available_cash=100,
        entry_price=100,
        atr=2,
        risk_pct=0.01,
        atr_multiplier=2.5,
        fee_rate=0.002,
        slippage_rate=0.0005,
    )

    assert result.valid
    assert result.quantity > 0
    assert result.stop_price < result.entry_price

    assert result.estimated_risk <= result.risk_budget

    print("PASS: Risk limit respected")

    print("Quantity:", result.quantity)
    print("Stop:", result.stop_price)
    print("Risk budget:", result.risk_budget)
    print("Estimated risk:", result.estimated_risk)
    print("Position cost:", result.position_cost)


def test_insufficient_cash():

    result = calculate_position_size(
        equity=100,
        available_cash=0,
        entry_price=100,
        atr=2,
    )

    assert not result.valid

    print("PASS: Insufficient cash handled")


def test_invalid_atr():

    try:
        calculate_position_size(
            equity=100,
            available_cash=100,
            entry_price=100,
            atr=0,
        )

    except ValueError:
        print("PASS: Invalid ATR rejected")
        return

    raise AssertionError("Invalid ATR was accepted")


if __name__ == "__main__":

    print("=" * 55)
    print("MABOT - POSITION SIZING TESTS")
    print("=" * 55)

    test_basic_position_sizing()
    test_insufficient_cash()
    test_invalid_atr()

    print("\nALL TESTS PASSED")