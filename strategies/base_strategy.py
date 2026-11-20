from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):

    name = "BASE_STRATEGY"

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate entry and exit signals.

        Required output columns:
            BUY
            SELL
        """
        pass

    def validate_output(self, df: pd.DataFrame):

        required = {"BUY", "SELL"}

        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                f"{self.name}: Missing signal columns: {missing}"
            )

        if df["BUY"].isna().any():
            raise ValueError("BUY contains missing values")

        if df["SELL"].isna().any():
            raise ValueError("SELL contains missing values")

        if not pd.api.types.is_bool_dtype(df["BUY"]):
            raise TypeError("BUY must be boolean")

        if not pd.api.types.is_bool_dtype(df["SELL"]):
            raise TypeError("SELL must be boolean")

        return True