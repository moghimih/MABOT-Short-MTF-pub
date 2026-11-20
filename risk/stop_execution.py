from dataclasses import dataclass
import math


@dataclass
class StopExecutionResult:
    triggered: bool
    execution_price: float
    reason: str


def calculate_stop_exit(
    open_price,
    low_price,
    stop_price,
    slippage=0.0005,
):
    values = [
        open_price,
        low_price,
        stop_price,
        slippage,
    ]

    if any(
        not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("Inputs must be finite numbers")

    if min(open_price, low_price, stop_price) <= 0:
        raise ValueError("Prices must be positive")

    if not 0 <= slippage < 1:
        raise ValueError("Invalid slippage")

    # Stop not reached
    if low_price > stop_price:
        return StopExecutionResult(
            False, 0.0, "NOT_TRIGGERED"
        )

    # Gap below stop
    if open_price <= stop_price:
        raw_execution = open_price
        reason = "GAP_STOP"

    else:
        raw_execution = stop_price
        reason = "STOP_LOSS"

    execution_price = (
        raw_execution * (1 - slippage)
    )

    return StopExecutionResult(
        triggered=True,
        execution_price=execution_price,
        reason=reason,
    )