from dataclasses import dataclass
import math


@dataclass
class PositionSize:
    quantity: float
    entry_price: float
    stop_price: float
    risk_budget: float
    estimated_risk: float
    position_cost: float
    valid: bool
    reason: str = ""


def calculate_position_size(
    equity,
    available_cash,
    entry_price,
    atr,
    risk_pct=0.01,
    atr_multiplier=2.5,
    fee_rate=0.002,
    slippage_rate=0.0005,
    max_allocation=None,
):
    values = [
        equity,
        available_cash,
        entry_price,
        atr,
        risk_pct,
        atr_multiplier,
        fee_rate,
        slippage_rate,
    ]

    if any(
        value is None
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("Inputs must be finite numbers")

    if equity <= 0:
        raise ValueError("Equity must be positive")

    if available_cash < 0:
        raise ValueError("Available cash cannot be negative")

    if available_cash == 0:
        return PositionSize(
            0, 0, 0, 0, 0, 0, False,
            "Insufficient cash"
        )

    if entry_price <= 0 or atr <= 0:
        raise ValueError("Invalid price or ATR")

    if not 0 < risk_pct <= 1:
        raise ValueError("Invalid risk percentage")

    if atr_multiplier <= 0:
        raise ValueError("Invalid ATR multiplier")

    if not 0 <= fee_rate < 1:
        raise ValueError("Invalid fee rate")

    if not 0 <= slippage_rate < 1:
        raise ValueError("Invalid slippage rate")

    if max_allocation is not None:

        if not math.isfinite(max_allocation):
            raise ValueError("Invalid allocation limit")

        if max_allocation <= 0:
            raise ValueError("Invalid allocation limit")

        available_cash = min(
            available_cash,
            max_allocation,
        )

    # Actual estimated entry price including slippage
    actual_entry = (
        entry_price * (1 + slippage_rate)
    )

    # Stop distance is measured from actual entry
    stop_price = (
        actual_entry - atr * atr_multiplier
    )

    if stop_price <= 0:
        return PositionSize(
            0, actual_entry, stop_price,
            equity * risk_pct, 0, 0, False,
            "Stop price is invalid"
        )

    # Estimated stop execution including slippage
    actual_exit = (
        stop_price * (1 - slippage_rate)
    )

    entry_fee_per_unit = (
        actual_entry * fee_rate
    )

    exit_fee_per_unit = (
        actual_exit * fee_rate
    )

    risk_per_unit = (
        actual_entry
        - actual_exit
        + entry_fee_per_unit
        + exit_fee_per_unit
    )

    if risk_per_unit <= 0:
        raise ValueError("Invalid risk per unit")

    risk_budget = equity * risk_pct

    quantity_by_risk = (
        risk_budget / risk_per_unit
    )

    cash_per_unit = (
        actual_entry * (1 + fee_rate)
    )

    quantity_by_cash = (
        available_cash / cash_per_unit
    )

    quantity = min(
        quantity_by_risk,
        quantity_by_cash,
    )

    position_cost = (
        quantity * cash_per_unit
    )

    estimated_risk = (
        quantity * risk_per_unit
    )

    if quantity <= 0:
        return PositionSize(
            0, actual_entry, stop_price,
            risk_budget, 0, 0, False,
            "Calculated quantity is zero"
        )

    return PositionSize(
        quantity=quantity,
        entry_price=actual_entry,
        stop_price=stop_price,
        risk_budget=risk_budget,
        estimated_risk=estimated_risk,
        position_cost=position_cost,
        valid=True,
        reason="OK",
    )