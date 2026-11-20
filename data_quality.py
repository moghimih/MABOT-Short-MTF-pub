import pandas as pd
from pathlib import Path

files = list(Path(".").glob("*_history.csv"))

print("=" * 50)
print("MABOT - DATA QUALITY CHECK")
print("=" * 50)

for file in files:

    df = pd.read_csv(file)

    print(f"\nMARKET: {file.stem.upper()}")

    errors = []

    if df.empty:
        errors.append("No data")

    if df.isnull().any().any():
        errors.append("Missing values")

    if df["timestamp"].duplicated().any():
        errors.append("Duplicate timestamps")

    if not df["timestamp"].is_monotonic_increasing:
        errors.append("Timestamps not sorted")

    if (df["high"] < df["low"]).any():
        errors.append("High below Low")

    if (df["high"] < df["open"]).any():
        errors.append("High below Open")

    if (df["high"] < df["close"]).any():
        errors.append("High below Close")

    if (df["low"] > df["open"]).any():
        errors.append("Low above Open")

    if (df["low"] > df["close"]).any():
        errors.append("Low above Close")

    if (df["volume"] < 0).any():
        errors.append("Negative volume")

    gaps = (
        df["timestamp"].diff().dropna() != 3600
    ).sum()

    print("Candles:", len(df))
    print("Time gaps:", gaps)

    if errors:
        print("STATUS: FAILED")
        for error in errors:
            print(" -", error)
    else:
        print("STATUS: PASSED")

print("\nQUALITY CHECK FINISHED")