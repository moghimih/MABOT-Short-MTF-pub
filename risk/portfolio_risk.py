from dataclasses import dataclass
import math


@dataclass
class PortfolioRiskResult:
    allowed: bool
    current_risk: float
    new_risk: float
    total_risk: float
    risk_limit: float
    remaining_risk: float
    remaining_after_trade: float
    reason: str


def check_portfolio_risk(
    equity,
    open_positions,
    new_trade_risk,
    max_portfolio_risk=0.02,
):
    values = [
        equity,
        new_trade_risk,
        max_portfolio_risk,
    ]

    if any(
        not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("Inputs must be finite numbers")

    if equity <= 0:
        raise ValueError("Equity must be positive")

    if new_trade_risk < 0:
        raise ValueError("New trade risk cannot be negative")

    if not 0 < max_portfolio_risk <= 1:
        raise ValueError("Invalid portfolio risk limit")

    current_risk = 0.0

    for position in open_positions:

        risk = position.get("risk_amount")

        if (
            risk is None
            or not isinstance(risk, (int, float))
            or not math.isfinite(risk)
            or risk < 0
        ):
            raise ValueError("Invalid position risk")

        current_risk += risk

    risk_limit = equity * max_portfolio_risk

    total_risk = current_risk + new_trade_risk

    remaining_risk = max(
        0.0,
        risk_limit - current_risk,
    )

    remaining_after_trade = max(
        0.0,
        risk_limit - total_risk,
    )

    allowed = (
        total_risk <= risk_limit + 1e-9
    )

    return PortfolioRiskResult(
        allowed=allowed,
        current_risk=current_risk,
        new_risk=new_trade_risk,
        total_risk=total_risk,
        risk_limit=risk_limit,
        remaining_risk=remaining_risk,
        remaining_after_trade=remaining_after_trade,
        reason=(
            "OK"
            if allowed
            else "PORTFOLIO_RISK_LIMIT_EXCEEDED"
        ),
    )