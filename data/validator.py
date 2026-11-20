"""Validation helpers for native OHLCV market data."""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "segment_id", "bars_in_segment",
]


def validate_market_data(
    df,
    symbol="UNKNOWN",
    expected_interval=pd.Timedelta(hours=4),
):
    """Return a list of data-quality errors (empty means valid).

    A time gap larger than the expected candle interval must begin a new
    segment. Segment counters must restart at 1 and increase without skips.
    """
    errors = []
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        return [f"Missing columns: {missing}"]
    if df.empty:
        return ["Dataset is empty"]

    data = df.copy()
    try:
        data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="raise")
    except Exception as exc:
        return [f"Invalid timestamps: {exc}"]

    if data["timestamp"].isna().any():
        errors.append("Missing timestamps detected")
    if data["timestamp"].duplicated().any():
        errors.append("Duplicate timestamps detected")
    if not data["timestamp"].is_monotonic_increasing:
        errors.append("Timestamps are not sorted")

    numeric_columns = ["open", "high", "low", "close", "volume", "segment_id", "bars_in_segment"]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
        if data[column].isna().any():
            errors.append(f"Missing or non-numeric values in {column}")
        elif not np.isfinite(data[column].to_numpy(dtype=float)).all():
            errors.append(f"Non-finite values in {column}")

    if data[numeric_columns].isna().any().any():
        return errors

    prices = data[["open", "high", "low", "close"]]
    if (prices <= 0).any().any():
        errors.append("Non-positive OHLC prices detected")
    invalid_ohlc = (
        (data["high"] < data["low"]) |
        (data["high"] < data["open"]) |
        (data["high"] < data["close"]) |
        (data["low"] > data["open"]) |
        (data["low"] > data["close"])
    )
    if invalid_ohlc.any():
        errors.append("Invalid OHLC values")
    if (data["volume"] < 0).any():
        errors.append("Negative volume detected")

    if (data["bars_in_segment"] < 1).any() or not np.equal(
        data["bars_in_segment"], np.floor(data["bars_in_segment"])
    ).all():
        errors.append("Invalid bars_in_segment values")
    if not np.equal(data["segment_id"], np.floor(data["segment_id"])).all():
        errors.append("segment_id must contain integers")

    # A segment may not disappear and then reappear later.
    segment_changes = data["segment_id"].ne(data["segment_id"].shift()).fillna(True)
    ordered_segments = data.loc[segment_changes, "segment_id"].tolist()
    if len(ordered_segments) != len(set(ordered_segments)):
        errors.append("A segment_id reappears after another segment")

    expected_counters = data.groupby("segment_id", sort=False).cumcount() + 1
    if not np.array_equal(data["bars_in_segment"].to_numpy(), expected_counters.to_numpy()):
        errors.append("bars_in_segment does not count consecutively from 1 within each segment")

    if expected_interval is not None and len(data) > 1:
        deltas = data["timestamp"].diff()
        same_segment = data["segment_id"].eq(data["segment_id"].shift())
        invalid_within_segment = same_segment & deltas.ne(expected_interval)
        if invalid_within_segment.any():
            errors.append("Time gap or irregular interval found inside a segment")
        gap_without_new_segment = (~same_segment) & deltas.le(expected_interval)
        if gap_without_new_segment.any():
            # Segment resets at a normal interval are allowed (e.g. explicit reset).
            pass
        unsegmented_gap = deltas.gt(expected_interval) & same_segment
        if unsegmented_gap.any():
            errors.append("Time gap is not marked by a new segment_id")

    return errors


def print_validation_report(df, symbol="UNKNOWN", expected_interval=pd.Timedelta(hours=4)):
    errors = validate_market_data(df, symbol, expected_interval)
    print("=" * 55)
    print(f"DATA VALIDATION: {symbol}")
    print("=" * 55)
    print(f"Rows: {len(df)}")
    if errors:
        print("STATUS: FAILED")
        for error in errors:
            print(f"[ERROR] {error}")
    else:
        print("STATUS: PASSED")
        print("No data quality problems detected.")
    print("=" * 55)
    return not errors
