from risk.stop_execution import calculate_stop_exit


def run_tests():

    print("=" * 55)
    print("MABOT - STOP EXECUTION MODULE")
    print("=" * 55)

    # Normal stop
    result = calculate_stop_exit(
        open_price=100,
        low_price=94,
        stop_price=95,
    )

    assert result.triggered
    assert result.reason == "STOP_LOSS"
    assert result.execution_price < 95

    print("PASS: Normal stop")

    # Gap stop
    result = calculate_stop_exit(
        open_price=90,
        low_price=88,
        stop_price=95,
    )

    assert result.triggered
    assert result.reason == "GAP_STOP"
    assert result.execution_price < 90

    print("PASS: Gap stop")

    # Exact touch
    result = calculate_stop_exit(
        open_price=100,
        low_price=95,
        stop_price=95,
    )

    assert result.triggered

    print("PASS: Exact stop touch")

    # No trigger
    result = calculate_stop_exit(
        open_price=100,
        low_price=97,
        stop_price=95,
    )

    assert not result.triggered

    print("PASS: No stop trigger")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run_tests()