import pandas as pd

from data.validator import validate_market_data


def valid_frame():
    return pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 04:00:00+00:00",
            "2026-01-01 08:00:00+00:00",
        ], utc=True),
        "open": [100.0, 101.0, 102.0],
        "high": [102.0, 103.0, 104.0],
        "low": [99.0, 100.0, 101.0],
        "close": [101.0, 102.0, 103.0],
        "volume": [10.0, 11.0, 12.0],
        "segment_id": [0, 0, 0],
        "bars_in_segment": [1, 2, 3],
    })


def test_valid_gap_aware_frame_passes():
    assert validate_market_data(valid_frame()) == []


def test_unmarked_time_gap_fails():
    frame = valid_frame()
    frame.loc[2, "timestamp"] = pd.Timestamp("2026-01-01 12:00:00+00:00")
    assert any("Time gap" in error for error in validate_market_data(frame))


def test_segment_counter_must_restart():
    frame = valid_frame()
    frame.loc[2, "segment_id"] = 1
    frame.loc[2, "bars_in_segment"] = 3
    assert any("bars_in_segment" in error for error in validate_market_data(frame))


def test_non_finite_prices_fail():
    frame = valid_frame()
    frame.loc[1, "high"] = float("inf")
    assert any("Non-finite" in error for error in validate_market_data(frame))
