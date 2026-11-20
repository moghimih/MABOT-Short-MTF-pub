"""Audit native Nobitex 4h/1d candle CSVs without modifying them."""
from pathlib import Path
import pandas as pd

FILES = {
    "BTC 4h": ("btcusdt_4h_native.csv", 4 * 60 * 60),
    "ETH 4h": ("ethusdt_4h_native.csv", 4 * 60 * 60),
    "ZEC 4h": ("zecusdt_4h_native.csv", 4 * 60 * 60),
    "XRP 4h": ("xrpusdt_4h_native.csv", 4 * 60 * 60),
    "BTC 1d": ("btcusdt_1d_native.csv", 24 * 60 * 60),
    "ETH 1d": ("ethusdt_1d_native.csv", 24 * 60 * 60),
    "ZEC 1d": ("zecusdt_1d_native.csv", 24 * 60 * 60),
    "XRP 1d": ("xrpusdt_1d_native.csv", 24 * 60 * 60),
}

REQUIRED = ["open", "high", "low", "close", "volume"]

print("=" * 76)
print("MABOT - NATIVE TIMEFRAME GAP AUDIT")
print("READ-ONLY: CSV FILES WILL NOT BE MODIFIED")
print("=" * 76)

for label, (filename, interval_seconds) in FILES.items():
    path = Path(filename)
    print(f"\n{label} | {filename}")
    print("-" * 76)

    if not path.exists():
        print("FILE NOT FOUND")
        continue

    df = pd.read_csv(path)
    missing_columns = [c for c in ["timestamp", *REQUIRED] if c not in df.columns]
    if missing_columns:
        print("MISSING COLUMNS:", ", ".join(missing_columns))
        continue

    # Native downloader stores Unix timestamps in seconds.
    ts_num = pd.to_numeric(df["timestamp"], errors="coerce")
    if ts_num.isna().any():
        print("INVALID TIMESTAMP VALUES:", int(ts_num.isna().sum()))
        continue

    ts = pd.to_datetime(ts_num, unit="s", utc=True)
    diffs = ts.diff().dropna()
    expected = pd.Timedelta(seconds=interval_seconds)
    bad = diffs[diffs != expected]

    duplicate_count = int(ts.duplicated().sum())
    sorted_ok = bool(ts.is_monotonic_increasing)
    missing_values = int(df[[*REQUIRED]].isna().sum().sum())

    numeric = df[REQUIRED].apply(pd.to_numeric, errors="coerce")
    numeric_errors = int(numeric.isna().sum().sum())
    invalid_ohlc = int((
        (numeric["high"] < numeric["low"]) |
        (numeric["high"] < numeric["open"]) |
        (numeric["high"] < numeric["close"]) |
        (numeric["low"] > numeric["open"]) |
        (numeric["low"] > numeric["close"])
    ).sum())
    negative_volume = int((numeric["volume"] < 0).sum())

    print("Rows:", len(df))
    print("First:", ts.iloc[0] if len(ts) else "n/a")
    print("Last: ", ts.iloc[-1] if len(ts) else "n/a")
    print("Sorted:", sorted_ok)
    print("Duplicate timestamps:", duplicate_count)
    print("Missing OHLCV cells:", missing_values)
    print("Non-numeric OHLCV cells:", numeric_errors)
    print("Invalid OHLC rows:", invalid_ohlc)
    print("Negative volume rows:", negative_volume)
    print("Irregular time transitions:", len(bad))

    if len(bad):
        print("GAP DETAILS (previous candle -> next candle):")
        for next_index, delta in bad.items():
            prev_index = next_index - 1
            prev_time = ts.iloc[prev_index]
            next_time = ts.iloc[next_index]
            delta_seconds = delta.total_seconds()
            ratio = delta_seconds / interval_seconds
            whole_steps = round(ratio)
            if whole_steps >= 1 and abs(ratio - whole_steps) < 1e-9:
                missing_intervals = whole_steps - 1
                detail = f"approximately {missing_intervals} missing candle(s)"
            else:
                detail = "interval is not an integer multiple of expected timeframe"
            print(
                f"  {prev_time} -> {next_time} | "
                f"delta={delta} | {detail}"
            )
    else:
        print("No irregular transitions detected.")

print("\n" + "=" * 76)
print("AUDIT FINISHED - NO FILES CHANGED")
print("=" * 76)
