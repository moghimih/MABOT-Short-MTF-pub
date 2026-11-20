from risk.stop_loss import (
    calculate_initial_stop,
    update_trailing_stop,
    is_stop_triggered,
)


def run_tests():
    print("=" * 55)
    print("MABOT - STOP LOSS TESTS")
    print("=" * 55)

    initial = calculate_initial_stop(100, 2, 2.5)
    assert initial == 95
    print("PASS: Initial ATR stop")

    moved = update_trailing_stop(95, 110, 2)
    assert moved.updated and moved.stop_price == 105
    print("PASS: Trailing stop moved upward")

    unchanged = update_trailing_stop(105, 108, 2)
    assert not unchanged.updated and unchanged.stop_price == 105
    print("PASS: Stop never moves backward")

    assert is_stop_triggered(104, 105)
    assert not is_stop_triggered(106, 105)
    print("PASS: Stop trigger detection")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run_tests()