from dataclasses import dataclass
import math


@dataclass
class StopLossResult:
    stop_price: float
    updated: bool
    reason: str


def _positive_finite(**values):
    for name, value in values.items():
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number")


def calculate_initial_stop(entry_price, atr, multiplier=2.5):
    _positive_finite(entry_price=entry_price, atr=atr, multiplier=multiplier)
    stop = entry_price - (atr * multiplier)
    if stop <= 0:
        raise ValueError("Stop price must be positive")
    return stop


def update_trailing_stop(current_stop, current_price, atr, multiplier=2.5):
    _positive_finite(
        current_stop=current_stop,
        current_price=current_price,
        atr=atr,
        multiplier=multiplier,
    )
    proposed_stop = current_price - (atr * multiplier)
    if proposed_stop > current_stop:
        return StopLossResult(proposed_stop, True, "STOP_MOVED_UP")
    return StopLossResult(current_stop, False, "STOP_UNCHANGED")


def is_stop_triggered(current_price, stop_price):
    _positive_finite(current_price=current_price, stop_price=stop_price)
    return current_price <= stop_price
