import pandas as pd

from strategies.base_strategy import BaseStrategy


class ADXStrategy(BaseStrategy):
    name = "EMA_RSI_ADX"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:

        required = {
            "EMA20",
            "EMA50",
            "RSI14",
            "ADX",
            "PLUS_DI",
            "MINUS_DI",
            "bars_in_segment",
        }

        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                f"{self.name}: Missing columns: {missing}"
            )

        result = df.copy()

        valid_indicators = result[
            [
                "EMA20",
                "EMA50",
                "RSI14",
                "ADX",
                "PLUS_DI",
                "MINUS_DI",
            ]
        ].notna().all(axis=1)

        ready = (
            (result["bars_in_segment"] >= 200)
            & valid_indicators
        )

        base_buy = (
            (result["EMA20"] > result["EMA50"])
            & (result["RSI14"] > 50)
        )

        result["BUY"] = (
            ready
            & base_buy
            & (result["ADX"] >= 20)
            & (result["PLUS_DI"] > result["MINUS_DI"])
        ).fillna(False).astype(bool)

        result["SELL"] = (
            (result["EMA20"] < result["EMA50"])
            | (result["RSI14"] < 45)
        ).fillna(False).astype(bool)

        self.validate_output(result)

        return result