from risk.portfolio_risk import check_portfolio_risk


def run_tests():

    print("=" * 55)
    print("MABOT - PORTFOLIO RISK TESTS")
    print("=" * 55)

    # Test 1: First position
    result = check_portfolio_risk(
        equity=100,
        open_positions=[],
        new_trade_risk=1,
    )

    assert result.allowed
    print("PASS: First position accepted")

    # Test 2: Two positions within 2% limit
    positions = [
        {"risk_amount": 1.0}
    ]

    result = check_portfolio_risk(
        equity=100,
        open_positions=positions,
        new_trade_risk=1.0,
    )

    assert result.allowed
    assert result.total_risk == 2.0
    print("PASS: Portfolio risk at limit")

    # Test 3: Reject risk above limit
    result = check_portfolio_risk(
        equity=100,
        open_positions=positions,
        new_trade_risk=1.5,
    )

    assert not result.allowed
    print("PASS: Excess portfolio risk rejected")

    # Test 4: Remaining risk
    assert result.remaining_risk == 1.0
    print("PASS: Remaining risk calculated")

    # Test 5: Invalid risk
    try:
        check_portfolio_risk(
            equity=100,
            open_positions=[],
            new_trade_risk=-1,
        )
    except ValueError:
        print("PASS: Invalid risk rejected")
    else:
        raise AssertionError("Negative risk was accepted")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run_tests()