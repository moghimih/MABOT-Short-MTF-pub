import pandas as pd

from data.loader import load_market_data
from indicators.engine import calculate_all_indicators
from adx_4h_research import load_data, add_indicators


FILES = {
    "BTCUSDT": "btcusdt_4h_native_gap_aware.csv",
    "ETHUSDT": "ethusdt_4h_native_gap_aware.csv",
    "ZECUSDT": "zecusdt_4h_native_gap_aware.csv",
    "XRPUSDT": "xrpusdt_4h_native_gap_aware.csv",
}

COLUMNS = {
    "EMA20": ("EMA20", "EMA20"),
    "EMA50": ("EMA50", "EMA50"),
    "RSI14": ("RSI14", "RSI14"),
    "ATR14": ("ATR14", "ATR14"),
    "PLUS_DI14": ("PLUS_DI14", "PLUS_DI"),
    "MINUS_DI14": ("MINUS_DI14", "MINUS_DI"),
    "ADX14": ("ADX14", "ADX"),
}

TOLERANCE = 1e-8

all_passed = True


for symbol, filename in FILES.items():

    print("\n" + "=" * 70)
    print(f"COMPARING: {symbol}")
    print("=" * 70)

    # OLD ENGINE
    old_data = load_data(filename)
    old = add_indicators(old_data)

    # NEW MODULAR ENGINE
    new_data = load_market_data(symbol)
    new = calculate_all_indicators(new_data)

    # Match rows
    merged = old.merge(
        new,
        on=["timestamp", "segment_id"],
        suffixes=("_old", "_new"),
        validate="one_to_one"
    )

    print(f"Old rows:     {len(old)}")
    print(f"New rows:     {len(new)}")
    print(f"Matched rows: {len(merged)}")

    if len(old) != len(new) or len(merged) != len(old):
        print("[FAIL] Row count mismatch")
        all_passed = False
        continue

    # Compare indicators
    for indicator, (old_col, new_col) in COLUMNS.items():

        if old_col in ["EMA20", "EMA50", "RSI14", "ATR14"]:
            old_col = old_col + "_old"
            new_col = new_col + "_new"

        a = merged[old_col]
        b = merged[new_col]

        valid = a.notna() & b.notna()

        if valid.sum() == 0:
            print(f"{indicator:12} NO COMPARABLE VALUES")
            all_passed = False
            continue

        diff = (a[valid] - b[valid]).abs()

        max_diff = diff.max()
        mean_diff = diff.mean()
        different = int((diff > TOLERANCE).sum())

        passed = max_diff <= TOLERANCE

        if not passed:
            all_passed = False

        status = "PASS" if passed else "FAIL"

        print(
            f"{indicator:12} "
            f"max_diff={max_diff:.12f} "
            f"mean_diff={mean_diff:.12f} "
            f"different={different} "
            f"[{status}]"
        )

    # Compare signal columns
    signal_pairs = [
        ("BUY_BASELINE", "BUY_BASELINE"),
        ("BUY_ADX", "BUY_BASELINE"),
        ("SELL_SIGNAL", "SELL_SIGNAL"),
    ]

    print("\nSIGNAL COMPARISON:")

    for old_signal, new_signal in signal_pairs:

        if old_signal not in merged.columns:
            print(f"{old_signal}: OLD COLUMN MISSING")
            all_passed = False
            continue

        if new_signal not in merged.columns:
            print(f"{new_signal}: NEW COLUMN MISSING")
            all_passed = False
            continue

        # New engine currently calculates indicators only.
        # Signal comparison is deferred until strategy modules exist.
        print(f"{old_signal}: NOT TESTED (strategy module pending)")


print("\n" + "=" * 70)

if all_passed:
    print("INDICATOR NUMERICAL COMPARISON: PASSED")
else:
    print("INDICATOR NUMERICAL COMPARISON: FAILED")

print("=" * 70)