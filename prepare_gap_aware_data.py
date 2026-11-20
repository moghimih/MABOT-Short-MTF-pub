"""MABOT - Prepare gap-aware native Nobitex candles.

Reads the original native 4h/1d CSV files and writes NEW derived CSV files.
Original files are never modified. No missing candles are fabricated or filled.

Each continuous run of candles receives a segment_id. Indicator calculations
must be restarted separately inside each segment. `ema200_ready` is True only
from the 200th candle in a segment onward.

Run from the MABOT project folder:
    python prepare_gap_aware_data.py
"""
from pathlib import Path
import pandas as pd

FILES = {
    ("BTC", "4h"): "btcusdt_4h_native.csv",
    ("ETH", "4h"): "ethusdt_4h_native.csv",
    ("ZEC", "4h"): "zecusdt_4h_native.csv",
    ("XRP", "4h"): "xrpusdt_4h_native.csv",
    ("BTC", "1d"): "btcusdt_1d_native.csv",
    ("ETH", "1d"): "ethusdt_1d_native.csv",
    ("ZEC", "1d"): "zecusdt_1d_native.csv",
    ("XRP", "1d"): "xrpusdt_1d_native.csv",
}

EXPECTED = {"4h": pd.Timedelta(hours=4), "1d": pd.Timedelta(days=1)}
WARMUP_BARS = 200


def load_timestamp(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        # Nobitex UDF history timestamps are Unix seconds.
        return pd.to_datetime(series, unit="s", utc=True, errors="coerce")
    return pd.to_datetime(series, utc=True, errors="coerce")


def process_file(symbol: str, timeframe: str, filename: str) -> bool:
    path = Path(filename)
    print(f"\n{symbol} {timeframe} | {filename}")
    print("-" * 70)

    if not path.exists():
        print("MISSING FILE - skipped")
        return False

    df = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        print("ERROR - missing columns:", ", ".join(sorted(missing_cols)))
        return False

    # Parse into a temporary UTC column, retaining the original timestamp
    # representation in the output for compatibility with existing MABOT code.
    df["_timestamp_utc"] = load_timestamp(df["timestamp"])
    if df["_timestamp_utc"].isna().any():
        print("ERROR - invalid timestamps found; file not written")
        return False

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[["open", "high", "low", "close", "volume"]].isna().any().any():
        print("ERROR - invalid OHLCV values found; file not written")
        return False

    df = df.sort_values("_timestamp_utc").reset_index(drop=True)
    duplicate_count = int(df["_timestamp_utc"].duplicated().sum())
    if duplicate_count:
        print(f"ERROR - {duplicate_count} duplicate timestamps; file not written")
        return False

    delta = df["_timestamp_utc"].diff()
    expected = EXPECTED[timeframe]
    break_mask = delta.notna() & (delta != expected)
    df["segment_id"] = break_mask.cumsum().astype(int)
    df["bars_in_segment"] = df.groupby("segment_id").cumcount() + 1
    df["ema200_ready"] = df["bars_in_segment"] >= WARMUP_BARS

    gaps = df.loc[break_mask, ["_timestamp_utc"]].copy()

    print("Rows:", len(df))
    print("Continuous segments:", df["segment_id"].nunique())
    print("Gap/discontinuity transitions:", len(gaps))

    if len(gaps):
        print("Detected transitions:")
        for idx in gaps.index:
            prev_ts = df.loc[idx - 1, "_timestamp_utc"]
            next_ts = df.loc[idx, "_timestamp_utc"]
            delta_value = next_ts - prev_ts
            approx_missing = max(0, int(delta_value / expected) - 1)
            print(
                f"  {prev_ts} -> {next_ts} | delta={delta_value} | "
                f"approximately {approx_missing} missing {timeframe} candle(s)"
            )
    else:
        print("No discontinuities detected.")

    print("Segment summary:")
    for segment_id, part in df.groupby("segment_id", sort=True):
        ready_count = int(part["ema200_ready"].sum())
        print(
            f"  segment {segment_id}: {len(part)} candles | "
            f"{part['_timestamp_utc'].iloc[0]} -> {part['_timestamp_utc'].iloc[-1]} | "
            f"EMA200-ready candles: {ready_count}"
        )

    output = path.with_name(path.stem + "_gap_aware.csv")
    # Keep the original timestamp column unchanged so existing scripts that
    # use Unix seconds with unit="s" remain compatible. Drop only temp column.
    df = df.drop(columns=["_timestamp_utc"])
    df.to_csv(output, index=False)
    print("Saved:", output.name)
    return True


def main() -> None:
    print("=" * 72)
    print("MABOT - GAP-AWARE DATA PREPARATION")
    print("Original CSV files are read-only; no candles are fabricated.")
    print("=" * 72)

    success = 0
    for (symbol, timeframe), filename in FILES.items():
        success += int(process_file(symbol, timeframe, filename))

    print("\n" + "=" * 72)
    print(f"Finished: {success}/{len(FILES)} files processed")
    print("Derived files use segment_id and bars_in_segment.")
    print("Restart indicators at every new segment; do not carry EMA/RSI/ATR across gaps.")
    print("REAL TRADING: DISABLED")
    print("=" * 72)


if __name__ == "__main__":
    main()
