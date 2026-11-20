import pandas as pd
from pathlib import Path

FILES = [
    "btcusdt_history_extended.csv",
    "ethusdt_history_extended.csv",
    "zecusdt_history_extended.csv",
    "xrpusdt_history_extended.csv"
]

print("=" * 55)
print("MABOT - EXTENDED DATA QUALITY CHECK")
print("=" * 55)

for filename in FILES:
    path = Path(filename)

    print(f"\nChecking: {filename}")

    if not path.exists():
        print("ERROR: File not found!")
        continue

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)

    checks = {
        "Rows": len(df),
        "Missing values": int(df.isnull().sum().sum()),
        "Duplicate timestamps": int(df["timestamp"].duplicated().sum()),
        "Sorted timestamps": bool(df["timestamp"].is_monotonic_increasing),
        "Time gaps": int(
            (df["timestamp"].diff().dropna() != pd.Timedelta(hours=1)).sum()
        ),
        "Negative volume": int((df["volume"] < 0).sum()),
        "Invalid OHLC": int(
            (
                (df["high"] < df["low"]) |
                (df["high"] < df["open"]) |
                (df["high"] < df["close"]) |
                (df["low"] > df["open"]) |
                (df["low"] > df["close"])
            ).sum()
        )
    }

    for key, value in checks.items():
        print(f"{key}: {value}")

    print("First candle:", df["timestamp"].iloc[0])
    print("Last candle:", df["timestamp"].iloc[-1])

    passed = (
        checks["Missing values"] == 0
        and checks["Duplicate timestamps"] == 0
        and checks["Sorted timestamps"]
        and checks["Time gaps"] == 0
        and checks["Negative volume"] == 0
        and checks["Invalid OHLC"] == 0
    )

    print("STATUS:", "PASSED" if passed else "FAILED")

print("\n" + "=" * 55)
print("QUALITY CHECK FINISHED")
print("=" * 55)