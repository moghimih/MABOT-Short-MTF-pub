import pandas as pd

from strategies.base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    name = "DONCHIAN_BREAKOUT"

    ENTRY_PERIOD = 20
    EXIT_PERIOD = 10

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:

        required = {
            "high",
            "low",
            "close",
            "EMA200",
            "bars_in_segment",
        }

        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                f"{self.name}: Missing columns: {missing}"
            )

        result = df.copy()

        # کانال فقط از کندل‌های بسته‌شده قبلی ساخته می‌شود.
        result["ENTRY_CHANNEL"] = (
            result.groupby("segment_id")["high"]
            .transform(
                lambda s: s.shift(1).rolling(
                    self.ENTRY_PERIOD,
                    min_periods=self.ENTRY_PERIOD
                ).max()
            )
        )

        result["EXIT_CHANNEL"] = (
            result.groupby("segment_id")["low"]
            .transform(
                lambda s: s.shift(1).rolling(
                    self.EXIT_PERIOD,
                    min_periods=self.EXIT_PERIOD
                ).min()
            )
        )

        ready = (
            (result["bars_in_segment"] >= 200)
            & result["EMA200"].notna()
            & result["ENTRY_CHANNEL"].notna()
            & result["EXIT_CHANNEL"].notna()
        )

        result["BUY"] = (
            ready
            & (result["close"] > result["ENTRY_CHANNEL"])
            & (result["close"] > result["EMA200"])
        ).fillna(False).astype(bool)

        result["SELL"] = (
            result["close"] < result["EXIT_CHANNEL"]
        ).fillna(False).astype(bool)

        self.validate_output(result)

        return result