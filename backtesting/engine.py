import math
import pandas as pd

from config.settings import (
    INITIAL_CAPITAL,
    FEE_RATE,
    SLIPPAGE_RATE,
    MAX_OPEN_POSITIONS,
)


class BacktestEngine:

    def __init__(
        self,
        initial_capital=INITIAL_CAPITAL,
        fee_rate=FEE_RATE,
        slippage_rate=SLIPPAGE_RATE,
        max_open_positions=MAX_OPEN_POSITIONS,
    ):

        if initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        if not 0 <= fee_rate < 1:
            raise ValueError("Invalid fee rate")

        if not 0 <= slippage_rate < 1:
            raise ValueError("Invalid slippage rate")

        if max_open_positions < 1:
            raise ValueError("Invalid position limit")

        self.initial_capital = float(initial_capital)
        self.fee_rate = float(fee_rate)
        self.slippage_rate = float(slippage_rate)
        self.max_open_positions = int(max_open_positions)

    def _validate_market(self, symbol, df):

        required = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "BUY",
            "SELL",
        }

        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                f"{symbol}: Missing columns: {missing}"
            )

        data = df.copy()

        data["timestamp"] = pd.to_datetime(
            data["timestamp"],
            utc=True,
            errors="coerce",
        )

        if data["timestamp"].isna().any():
            raise ValueError(
                f"{symbol}: Invalid timestamps"
            )

        data = data.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        if data["timestamp"].duplicated().any():
            raise ValueError(
                f"{symbol}: Duplicate timestamps"
            )

        prices = ["open", "high", "low", "close"]

        for column in prices:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        if data[prices].isna().any().any():
            raise ValueError(
                f"{symbol}: Invalid OHLC values"
            )

        if not all(
            (data[column] > 0).all()
            for column in prices
        ):
            raise ValueError(
                f"{symbol}: Prices must be positive"
            )

        invalid_ohlc = (
            (data["high"] < data["low"])
            | (data["high"] < data["open"])
            | (data["high"] < data["close"])
            | (data["low"] > data["open"])
            | (data["low"] > data["close"])
        )

        if invalid_ohlc.any():
            raise ValueError(
                f"{symbol}: Invalid OHLC structure"
            )

        for column in ["BUY", "SELL"]:
            if data[column].isna().any():
                raise ValueError(
                    f"{symbol}: Missing {column} signals"
                )

            if not data[column].isin([True, False]).all():
                raise ValueError(
                    f"{symbol}: {column} must be boolean"
                )

            data[column] = data[column].astype(bool)

        if "segment_id" not in data.columns:
            data["segment_id"] = 0

        if "BUY_PRIORITY" in data.columns:
            data["BUY_PRIORITY"] = pd.to_numeric(
                data["BUY_PRIORITY"],
                errors="coerce",
            )

        return data

    def run(self, signals_by_symbol):

        if not signals_by_symbol:
            raise ValueError("No market data supplied")

        cash = self.initial_capital

        positions = {}
        last_prices = {}

        trades = []
        equity_history = []

        events = {}

        # Validate and prepare all markets
        for symbol, df in signals_by_symbol.items():

            data = self._validate_market(symbol, df)

            for i in range(len(data)):

                row = data.iloc[i]
                timestamp = row["timestamp"]

                events.setdefault(timestamp, []).append({
                    "symbol": symbol,
                    "index": i,
                    "row": row,
                    "data": data,
                })

        # Stable rotating tie-breaker
        rotation_cursor = 0

        # Process timestamps chronologically
        for timestamp in sorted(events):

            current_events = sorted(
                events[timestamp],
                key=lambda x: x["symbol"],
            )

            executable = []

            for event in current_events:

                i = event["index"]
                data = event["data"]

                if i == 0:
                    continue

                previous = data.iloc[i - 1]
                current = event["row"]

                # Prevent signals crossing data gaps
                if (
                    previous["segment_id"]
                    != current["segment_id"]
                ):
                    continue

                executable.append({
                    "symbol": event["symbol"],
                    "previous": previous,
                    "current": current,
                })

            # ------------------------------------------------
            # 1. Execute SELL orders first
            # ------------------------------------------------

            for event in executable:

                symbol = event["symbol"]
                previous = event["previous"]
                current = event["current"]

                if not bool(previous["SELL"]):
                    continue

                if symbol not in positions:
                    continue

                execution_price = (
                    float(current["open"])
                    * (1 - self.slippage_rate)
                )

                position = positions.pop(symbol)

                quantity = position["quantity"]

                gross_proceeds = (
                    quantity * execution_price
                )

                exit_fee = (
                    gross_proceeds * self.fee_rate
                )

                net_proceeds = (
                    gross_proceeds - exit_fee
                )

                cash += net_proceeds

                pnl = (
                    net_proceeds
                    - position["entry_cost"]
                )

                trades.append({
                    "symbol": symbol,
                    "entry_time": position["entry_time"],
                    "exit_time": timestamp,
                    "entry_price": position["entry_price"],
                    "exit_price": execution_price,
                    "quantity": quantity,
                    "entry_fee": position["entry_fee"],
                    "exit_fee": exit_fee,
                    "total_fees": (
                        position["entry_fee"] + exit_fee
                    ),
                    "net_pnl": pnl,
                    "return_pct": (
                        pnl / position["entry_cost"]
                    ) * 100,
                })

            # ------------------------------------------------
            # 2. Collect BUY candidates
            # ------------------------------------------------

            candidates = []

            for event in executable:

                symbol = event["symbol"]
                previous = event["previous"]

                if not bool(previous["BUY"]):
                    continue

                if bool(previous["SELL"]):
                    continue

                if symbol in positions:
                    continue

                priority = None

                if "BUY_PRIORITY" in previous.index:
                    value = previous["BUY_PRIORITY"]

                    if pd.notna(value):
                        priority = float(value)

                candidates.append({
                    "symbol": symbol,
                    "current": event["current"],
                    "priority": priority,
                })

            # ------------------------------------------------
            # 3. Select candidates without fixed alphabetical
            #    preference across successive opportunities
            # ------------------------------------------------

            candidates.sort(
                key=lambda x: x["symbol"]
            )

            if candidates:

                count = len(candidates)

                offset = rotation_cursor % count

                rotated = (
                    candidates[offset:]
                    + candidates[:offset]
                )

                # Explicit BUY_PRIORITY takes precedence.
                # Equal or missing priorities use rotation.
                rotated.sort(
                    key=lambda x: (
                        x["priority"] is not None,
                        x["priority"]
                        if x["priority"] is not None
                        else 0,
                    ),
                    reverse=True,
                )

                free_slots = (
                    self.max_open_positions
                    - len(positions)
                )

                selected = rotated[:free_slots]

                if selected:
                    rotation_cursor += len(selected)

                # ------------------------------------------------
                # 4. Allocate capital equally across selected
                # ------------------------------------------------

                if selected and cash > 0:

                    budget_per_position = (
                        cash / len(selected)
                    )

                    for candidate in selected:

                        symbol = candidate["symbol"]
                        current = candidate["current"]

                        execution_price = (
                            float(current["open"])
                            * (1 + self.slippage_rate)
                        )

                        quantity = (
                            budget_per_position
                            / (
                                execution_price
                                * (1 + self.fee_rate)
                            )
                        )

                        gross_cost = (
                            quantity * execution_price
                        )

                        entry_fee = (
                            gross_cost * self.fee_rate
                        )

                        total_cost = (
                            gross_cost + entry_fee
                        )

                        if total_cost > cash + 1e-10:
                            continue

                        cash -= total_cost

                        positions[symbol] = {
                            "entry_time": timestamp,
                            "entry_price": execution_price,
                            "quantity": quantity,
                            "entry_fee": entry_fee,
                            "entry_cost": total_cost,
                        }

            # ------------------------------------------------
            # 5. Update market prices
            # ------------------------------------------------

            for event in current_events:

                symbol = event["symbol"]

                last_prices[symbol] = float(
                    event["row"]["close"]
                )

            # ------------------------------------------------
            # 6. Calculate portfolio equity
            # ------------------------------------------------

            positions_value = sum(
                position["quantity"]
                * last_prices[symbol]
                for symbol, position in positions.items()
                if symbol in last_prices
            )

            equity = cash + positions_value

            equity_history.append({
                "timestamp": timestamp,
                "cash": cash,
                "positions_value": positions_value,
                "open_positions": len(positions),
                "equity": equity,
            })

            # Cash must never become materially negative
            if cash < -1e-8:
                raise RuntimeError(
                    "Negative cash balance detected"
                )

        # ----------------------------------------------------
        # Performance calculations
        # ----------------------------------------------------

        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity_history)

        if not equity_df.empty:

            peak = equity_df["equity"].cummax()

            drawdown = (
                equity_df["equity"] / peak - 1
            )

            max_drawdown = float(
                drawdown.min() * 100
            )

            final_equity = float(
                equity_df["equity"].iloc[-1]
            )

        else:

            final_equity = self.initial_capital
            max_drawdown = 0.0

        if not trades_df.empty:

            wins = trades_df[
                trades_df["net_pnl"] > 0
            ]

            losses = trades_df[
                trades_df["net_pnl"] < 0
            ]

            gross_profit = float(
                wins["net_pnl"].sum()
            )

            gross_loss = abs(
                float(losses["net_pnl"].sum())
            )

            if gross_loss > 0:
                profit_factor = (
                    gross_profit / gross_loss
                )
            elif gross_profit > 0:
                profit_factor = float("inf")
            else:
                profit_factor = 0.0

            win_rate = (
                len(wins) / len(trades_df)
            ) * 100

        else:

            gross_profit = 0.0
            gross_loss = 0.0
            profit_factor = 0.0
            win_rate = 0.0

        summary = {
            "initial_capital": self.initial_capital,
            "final_equity": final_equity,
            "total_return_pct": (
                final_equity / self.initial_capital - 1
            ) * 100,
            "max_drawdown_pct": max_drawdown,
            "closed_trades": len(trades_df),
            "win_rate_pct": win_rate,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "open_positions": len(positions),
            "remaining_cash": cash,
        }

        return {
            "summary": summary,
            "trades": trades_df,
            "equity_curve": equity_df,
            "open_positions": positions,
        }