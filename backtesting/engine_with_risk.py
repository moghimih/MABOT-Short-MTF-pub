import math
import numpy as np
import pandas as pd

from config.settings import (
    INITIAL_CAPITAL,
    FEE_RATE,
    SLIPPAGE_RATE,
    MAX_OPEN_POSITIONS,
    MAX_RISK_PER_TRADE,
    MAX_PORTFOLIO_RISK,
)

from risk.position_sizing import calculate_position_size
from risk.portfolio_risk import check_portfolio_risk
from risk.stop_loss import update_trailing_stop
from risk.stop_execution import calculate_stop_exit


class RiskBacktestEngine:
    """
    Risk-managed spot backtester.

    Signals are read from the previous completed candle and executed at the
    current candle open. Stops are checked against current OHLC data.
    Trailing stops calculated from a candle close become active on the next
    candle, avoiding look-ahead bias.
    """

    def __init__(
        self,
        initial_capital=INITIAL_CAPITAL,
        fee_rate=FEE_RATE,
        slippage_rate=SLIPPAGE_RATE,
        max_open_positions=MAX_OPEN_POSITIONS,
        risk_per_trade=MAX_RISK_PER_TRADE,
        max_portfolio_risk=MAX_PORTFOLIO_RISK,
        atr_multiplier=2.5,
    ):
        self.initial_capital = float(initial_capital)
        self.fee_rate = float(fee_rate)
        self.slippage_rate = float(slippage_rate)
        if int(max_open_positions) != max_open_positions:
            raise ValueError("max_open_positions must be an integer")
        self.max_open_positions = int(max_open_positions)
        self.risk_per_trade = float(risk_per_trade)
        self.max_portfolio_risk = float(max_portfolio_risk)
        self.atr_multiplier = float(atr_multiplier)

        if not all(math.isfinite(value) for value in (
            self.initial_capital, self.fee_rate, self.slippage_rate,
            self.risk_per_trade, self.max_portfolio_risk, self.atr_multiplier,
        )):
            raise ValueError("Engine parameters must be finite numbers")
        if not 0 <= self.fee_rate < 1:
            raise ValueError("fee_rate must be in [0, 1)")
        if not 0 <= self.slippage_rate < 1:
            raise ValueError("slippage_rate must be in [0, 1)")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1")
        if not 0 < self.risk_per_trade <= 1:
            raise ValueError("risk_per_trade must be in (0, 1]")
        if not 0 < self.max_portfolio_risk <= 1:
            raise ValueError("max_portfolio_risk must be in (0, 1]")
        if self.atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be positive")

    @staticmethod
    def _validate_market(symbol, frame):
        required = {
            "timestamp", "open", "high", "low", "close",
            "BUY", "SELL", "ATR14",
        }
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(
                f"{symbol}: missing required columns: {sorted(missing)}"
            )

        data = frame.copy()
        data["timestamp"] = pd.to_datetime(
            data["timestamp"], utc=True, errors="raise"
        )
        if data["timestamp"].isna().any():
            raise ValueError(f"{symbol}: missing timestamps")
        data = data.sort_values("timestamp").reset_index(drop=True)

        if data["timestamp"].duplicated().any():
            raise ValueError(f"{symbol}: duplicate timestamps")

        for column in ["open", "high", "low", "close", "ATR14"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        prices = data[["open", "high", "low", "close"]]
        if (
            prices.isna().any().any()
            or not np.isfinite(prices.to_numpy(dtype=float)).all()
            or (prices <= 0).any().any()
        ):
            raise ValueError(f"{symbol}: invalid OHLC values")

        if (data["high"] < data[["open", "close", "low"]].max(axis=1)).any():
            raise ValueError(f"{symbol}: invalid high values")
        if (data["low"] > data[["open", "close", "high"]].min(axis=1)).any():
            raise ValueError(f"{symbol}: invalid low values")

        for signal in ("BUY", "SELL"):
            values = data[signal]
            if values.isna().any():
                raise ValueError(f"{symbol}: {signal} contains missing values")
            if pd.api.types.is_bool_dtype(values):
                data[signal] = values.astype(bool)
            elif pd.api.types.is_numeric_dtype(values) and values.isin([0, 1]).all():
                data[signal] = values.astype(bool)
            else:
                normalized = values.astype(str).str.strip().str.lower()
                if not normalized.isin(["true", "false", "1", "0"]).all():
                    raise ValueError(f"{symbol}: {signal} must contain boolean values")
                data[signal] = normalized.isin(["true", "1"])

        if data["ATR14"].dropna().lt(0).any():
            raise ValueError(f"{symbol}: ATR14 cannot be negative")

        if "segment_id" not in data.columns:
            data["segment_id"] = 0
        if data["segment_id"].isna().any():
            raise ValueError(f"{symbol}: segment_id contains missing values")
        if "BUY_PRIORITY" in data.columns:
            data["BUY_PRIORITY"] = pd.to_numeric(
                data["BUY_PRIORITY"], errors="coerce"
            )

        return data

    def _equity_at_open(self, cash, positions, open_prices, last_prices):
        equity = cash
        for symbol, position in positions.items():
            mark = open_prices.get(
                symbol, last_prices.get(symbol, position["entry_price"])
            )
            equity += position["quantity"] * mark
        return equity

    def _refresh_position_risk(self, position):
        stop_exit = position["stop_price"] * (1 - self.slippage_rate)
        entry = position["entry_price"]
        loss_per_unit = max(
            0.0,
            entry - stop_exit
            + entry * self.fee_rate
            + stop_exit * self.fee_rate,
        )
        position["risk_amount"] = (
            position["quantity"] * loss_per_unit
        )

    def _close_position(
        self, symbol, position, execution_price, timestamp,
        reason, cash, trades,
    ):
        quantity = position["quantity"]
        exit_fee = quantity * execution_price * self.fee_rate
        proceeds = quantity * execution_price - exit_fee
        cash += proceeds

        net_pnl = proceeds - position["entry_cost"]
        gross_pnl = (
            quantity * (execution_price - position["entry_price"])
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
            "entry_cost": position["entry_cost"],
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "return_pct": (
                net_pnl / position["entry_cost"] * 100
                if position["entry_cost"] else 0.0
            ),
            "initial_stop": position["initial_stop"],
            "final_stop": position["stop_price"],
            "exit_reason": reason,
            "bars_held": position["bars_held"],
            "risk_at_entry": position["initial_risk"],
        })
        return cash

    def run(self, markets):
        if not markets:
            raise ValueError("markets cannot be empty")

        validated = {
            symbol: self._validate_market(symbol, frame)
            for symbol, frame in markets.items()
        }

        rows_by_time = {}
        for symbol, frame in validated.items():
            for index, row in frame.iterrows():
                timestamp = row["timestamp"]
                rows_by_time.setdefault(timestamp, {})[symbol] = (
                    index, row
                )

        timestamps = sorted(rows_by_time)
        cash = self.initial_capital
        positions = {}
        last_prices = {}
        trades = []
        equity_records = []
        rotation_cursor = 0
        symbols = sorted(validated)

        for timestamp in timestamps:
            current = rows_by_time[timestamp]
            open_prices = {
                symbol: float(item[1]["open"])
                for symbol, item in current.items()
            }

            closed_this_bar = set()
            opened_this_bar = set()

            # 1) Count the candle for positions that existed at its open.
            # New positions opened below remain at bars_held == 0.
            existing_at_bar_start = set(positions)
            for symbol in existing_at_bar_start:
                if symbol in current:
                    positions[symbol]["bars_held"] += 1

            # 2) Gap stops: only exits observable at the candle open.
            for symbol in list(positions):
                if symbol not in current:
                    continue

                _, bar = current[symbol]
                position = positions[symbol]
                open_price = float(bar["open"])

                if open_price <= float(position["stop_price"]):
                    stop_result = calculate_stop_exit(
                        open_price=open_price,
                        low_price=open_price,
                        stop_price=float(position["stop_price"]),
                        slippage=self.slippage_rate,
                    )

                    if stop_result.triggered:
                        cash = self._close_position(
                            symbol, position, stop_result.execution_price,
                            timestamp, stop_result.reason, cash, trades,
                        )
                        del positions[symbol]
                        closed_this_bar.add(symbol)

            # 3) Signal exits execute at the current candle open.
            for symbol in list(positions):
                if symbol not in current:
                    continue

                index, bar = current[symbol]
                frame = validated[symbol]
                if index == 0:
                    continue

                previous = frame.iloc[index - 1]
                same_segment = (
                    previous["segment_id"] == bar["segment_id"]
                )

                if same_segment and bool(previous["SELL"]):
                    execution = (
                        float(bar["open"]) * (1 - self.slippage_rate)
                    )
                    cash = self._close_position(
                        symbol, positions[symbol], execution,
                        timestamp, "SIGNAL_SELL", cash, trades,
                    )
                    del positions[symbol]
                    closed_this_bar.add(symbol)

            # 4) Select and execute BUY signals at the candle open.
            # A symbol closed on this timestamp cannot be re-entered.
            candidates = []
            for symbol, (index, bar) in current.items():
                if index == 0 or symbol in positions:
                    continue
                if symbol in closed_this_bar:
                    continue

                frame = validated[symbol]
                previous = frame.iloc[index - 1]
                if previous["segment_id"] != bar["segment_id"]:
                    continue
                if not bool(previous["BUY"]):
                    continue

                priority = (
                    bar.get("BUY_PRIORITY")
                    if "BUY_PRIORITY" in bar.index else None
                )
                candidates.append((symbol, index, bar, priority))

            if symbols:
                rotation_order = (
                    symbols[rotation_cursor:] + symbols[:rotation_cursor]
                )
            else:
                rotation_order = []

            rotation_rank = {
                symbol: rank
                for rank, symbol in enumerate(rotation_order)
            }

            candidates.sort(
                key=lambda item: (
                    item[3] is not None and pd.notna(item[3]),
                    float(item[3])
                    if item[3] is not None and pd.notna(item[3])
                    else 0.0,
                    -rotation_rank.get(item[0], len(symbols)),
                ),
                reverse=True,
            )

            for symbol, index, bar, _priority in candidates:
                if len(positions) >= self.max_open_positions:
                    break
                if symbol in positions or symbol in closed_this_bar:
                    continue

                previous = validated[symbol].iloc[index - 1]
                atr = previous["ATR14"]
                if (
                    pd.isna(atr)
                    or not math.isfinite(float(atr))
                    or float(atr) <= 0
                ):
                    continue

                equity = self._equity_at_open(
                    cash, positions, open_prices, last_prices
                )
                sizing = calculate_position_size(
                    equity=equity,
                    available_cash=cash,
                    entry_price=float(bar["open"]),
                    atr=float(atr),
                    risk_pct=self.risk_per_trade,
                    atr_multiplier=self.atr_multiplier,
                    fee_rate=self.fee_rate,
                    slippage_rate=self.slippage_rate,
                )

                if not sizing.valid or sizing.quantity <= 0:
                    continue

                portfolio_check = check_portfolio_risk(
                    equity=equity,
                    open_positions=list(positions.values()),
                    new_trade_risk=sizing.estimated_risk,
                    max_portfolio_risk=self.max_portfolio_risk,
                )
                if not portfolio_check.allowed:
                    continue

                entry_price = sizing.entry_price
                quantity = sizing.quantity
                entry_fee = quantity * entry_price * self.fee_rate
                entry_cost = quantity * entry_price + entry_fee

                # Defensive cash check against floating point rounding.
                if entry_cost > cash + 1e-9:
                    continue

                cash -= entry_cost
                position = {
                    "symbol": symbol,
                    "entry_time": timestamp,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "entry_fee": entry_fee,
                    "entry_cost": entry_cost,
                    "stop_price": sizing.stop_price,
                    "initial_stop": sizing.stop_price,
                    "risk_amount": sizing.estimated_risk,
                    "initial_risk": sizing.estimated_risk,
                    "bars_held": 0,
                }
                positions[symbol] = position
                opened_this_bar.add(symbol)

                if symbols:
                    rotation_cursor = (
                        symbols.index(symbol) + 1
                    ) % len(symbols)

            # 5) Intrabar stops are evaluated after all open-time orders.
            # This includes new positions: they enter at open and can be
            # stopped later in the same candle.
            for symbol in list(positions):
                if symbol not in current:
                    continue

                _, bar = current[symbol]
                position = positions[symbol]
                stop_result = calculate_stop_exit(
                    open_price=float(bar["open"]),
                    low_price=float(bar["low"]),
                    stop_price=float(position["stop_price"]),
                    slippage=self.slippage_rate,
                )

                if stop_result.triggered:
                    reason = (
                        "SAME_BAR_" + stop_result.reason
                        if symbol in opened_this_bar
                        else stop_result.reason
                    )
                    cash = self._close_position(
                        symbol, position, stop_result.execution_price,
                        timestamp, reason, cash, trades,
                    )
                    del positions[symbol]
                    closed_this_bar.add(symbol)

            # 6) Update trailing stops from the completed close.
            # The updated stop is active from the next available candle.
            for symbol in list(positions):
                if symbol not in current or symbol in opened_this_bar:
                    continue

                index, bar = current[symbol]
                if index == 0:
                    continue

                previous = validated[symbol].iloc[index - 1]
                if previous["segment_id"] != bar["segment_id"]:
                    continue

                atr_now = bar["ATR14"]
                if (
                    pd.isna(atr_now)
                    or not math.isfinite(float(atr_now))
                    or float(atr_now) <= 0
                ):
                    continue

                position = positions[symbol]
                update = update_trailing_stop(
                    current_stop=float(position["stop_price"]),
                    current_price=float(bar["close"]),
                    atr=float(atr_now),
                    multiplier=self.atr_multiplier,
                )
                position["stop_price"] = update.stop_price
                self._refresh_position_risk(position)

            # 7) Mark all markets at the current completed close.
            for symbol, (_index, bar) in current.items():
                last_prices[symbol] = float(bar["close"])

            equity = cash
            for symbol, position in positions.items():
                mark = last_prices.get(
                    symbol, position["entry_price"]
                )
                equity += position["quantity"] * mark

            equity_records.append({
                "timestamp": timestamp,
                "cash": cash,
                "equity": equity,
                "open_positions": len(positions),
            })

        trades_frame = pd.DataFrame(trades)
        equity_frame = pd.DataFrame(equity_records)

        if not equity_frame.empty:
            # The initial account balance is the first high-water mark even
            # when the first recorded candle already contains a loss.
            peak = equity_frame["equity"].cummax().clip(
                lower=self.initial_capital
            )
            drawdown = equity_frame["equity"] / peak - 1
            max_drawdown = float(drawdown.min())
            final_equity = float(equity_frame["equity"].iloc[-1])
        else:
            max_drawdown = 0.0
            final_equity = self.initial_capital

        if not trades_frame.empty:
            wins = trades_frame[trades_frame["net_pnl"] > 0]
            losses = trades_frame[trades_frame["net_pnl"] < 0]
            gross_profit = float(wins["net_pnl"].sum())
            gross_loss = abs(float(losses["net_pnl"].sum()))
            profit_factor = (
                gross_profit / gross_loss if gross_loss > 0
                else (float("inf") if gross_profit > 0 else 0.0)
            )
            win_rate = float(
                (trades_frame["net_pnl"] > 0).mean()
            )
        else:
            profit_factor = 0.0
            win_rate = 0.0

        summary = {
            "initial_capital": self.initial_capital,
            "final_equity": final_equity,
            "total_return_pct": (
                (final_equity / self.initial_capital - 1) * 100
            ),
            "max_drawdown_pct": max_drawdown * 100,
            "total_trades": len(trades_frame),
            "win_rate_pct": win_rate * 100,
            "profit_factor": profit_factor,
            "open_positions": len(positions),
            "cash": cash,
        }

        return {
            "summary": summary,
            "trades": trades_frame,
            "equity_curve": equity_frame,
            "open_positions": positions,
        }


# Backwards-friendly class alias for explicit imports.
BacktestEngineWithRisk = RiskBacktestEngine
