def calculate_stop_exit(open_price, low_price, stop_price, slippage=0.0005):
    """
    Simulate stop execution for a long position.
    """

    if min(open_price, low_price, stop_price) <= 0:
        raise ValueError("Prices must be positive")

    if low_price >= stop_price:
        return None

    # Gap below stop: execute at open
    if open_price < stop_price:
        execution_price = open_price
        reason = "GAP_STOP"
    else:
        execution_price = stop_price
        reason = "STOP_LOSS"

    execution_price *= (1 - slippage)

    return {
        "execution_price": execution_price,
        "reason": reason,
    }


def run_tests():

    print("=" * 55)
    print("MABOT - STOP EXECUTION TESTS")
    print("=" * 55)

    # Normal stop hit
    result = calculate_stop_exit(
        open_price=100,
        low_price=94,
        stop_price=95,
    )

    assert result["reason"] == "STOP_LOSS"
    assert result["execution_price"] < 95

    print("PASS: Normal stop execution")

    # Gap below stop
    result = calculate_stop_exit(
        open_price=90,
        low_price=88,
        stop_price=95,
    )

    assert result["reason"] == "GAP_STOP"
    assert result["execution_price"] < 90

    print("PASS: Gap stop execution")

    # Stop not reached
    result = calculate_stop_exit(
        open_price=100,
        low_price=97,
        stop_price=95,
    )

    assert result is None

    print("PASS: No unnecessary exit")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run_tests()