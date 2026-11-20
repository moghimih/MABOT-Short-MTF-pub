"""Small deterministic helpers for sizing paper spot positions."""
def quantity_for_risk(equity: float, entry_price: float, stop_price: float,
                      risk_fraction: float = 0.01) -> float:
    values = (equity, entry_price, stop_price, risk_fraction)
    if any(not isinstance(v, (int, float)) or not (0 < v < float("inf")) for v in values):
        raise ValueError("Sizing inputs must be positive finite numbers")
    if stop_price >= entry_price or risk_fraction >= 1:
        raise ValueError("Require stop < entry and risk_fraction < 1")
    return equity * risk_fraction / (entry_price - stop_price)
