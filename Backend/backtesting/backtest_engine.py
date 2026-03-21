"""backtest_engine — run strategy against historical data.

Reuses the same strategy logic (entry_conditions, exit_conditions, indicators)
used by the live engine, ensuring consistency between backtesting and live trading.

Usage:
    from backtesting.backtest_engine import BacktestEngine
    from backtesting.data_loader import load_from_csv
    from backtesting.report import generate_report, print_report

    candles = load_from_csv("historical_data.csv")
    engine = BacktestEngine(strategy_cfg)
    trades = engine.run(candles)
    report = generate_report(trades)
    print(print_report(report))
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from data.indicators import build_dataframe, evaluate_entry_indicators
from orders.position_manager import ClosedTrade, PositionData, PositionStatus
from strategy.exit_conditions import ExitSignal, evaluate_exit


class BacktestEngine:
    """
    Simulates trading strategy on historical candle data.

    Walk-forward approach:
      1. Iterate through candles one by one
      2. At each bar, evaluate entry/exit conditions using all prior bars
      3. Fill orders at the candle's close price (or configurable price)
      4. Track positions and generate closed trade list
    """

    def __init__(
        self,
        strategy_cfg: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.strategy_cfg = strategy_cfg
        self.logger = logger or logging.getLogger("backtest")

        self.entry_cfg = strategy_cfg.get("entry_conditions", {})
        self.exit_cfg = strategy_cfg.get("exit_conditions", {})
        self.min_candles = int(self.entry_cfg.get("min_candles_required", 60))

    def run(self, candles: List[dict]) -> List[ClosedTrade]:
        """
        Run backtest on candle data and return list of closed trades.

        Each candle dict must have: timestamp, open, high, low, close, volume
        """
        if not candles or len(candles) < self.min_candles:
            self.logger.warning("Insufficient candles for backtest: %d", len(candles))
            return []

        trades: List[ClosedTrade] = []
        position: Optional[_BacktestPosition] = None

        for i in range(self.min_candles, len(candles)):
            bar = candles[i]
            lookback = candles[:i + 1]

            bar_close = float(bar.get("close", 0))
            bar_high = float(bar.get("high", 0))
            bar_low = float(bar.get("low", 0))
            bar_ts = bar.get("timestamp", "")

            if bar_close <= 0:
                continue

            # --- If in position: evaluate exit ---
            if position is not None:
                position.peak_ltp = max(position.peak_ltp, bar_high)

                exit_signal = evaluate_exit(
                    entry_price=position.entry_price,
                    current_ltp=bar_close,
                    peak_ltp=position.peak_ltp,
                    exit_cfg=self.exit_cfg,
                    now=_parse_timestamp(bar_ts),
                )

                # Also check if low breached SL
                if exit_signal is None:
                    exit_signal = evaluate_exit(
                        entry_price=position.entry_price,
                        current_ltp=bar_low,
                        peak_ltp=position.peak_ltp,
                        exit_cfg=self.exit_cfg,
                        now=_parse_timestamp(bar_ts),
                    )

                if exit_signal:
                    trade = position.close(
                        exit_price=exit_signal.exit_price,
                        exit_reason=exit_signal.trigger,
                        exit_ts=bar_ts,
                    )
                    trades.append(trade)
                    position = None
                    self.logger.debug("Exit at bar %d: %s", i, exit_signal.trigger)
                continue

            # --- No position: evaluate entry ---
            signal = evaluate_entry_indicators(lookback, self.entry_cfg)
            if signal.get("ok"):
                position = _BacktestPosition(
                    entry_price=bar_close,
                    entry_quantity=1,  # normalized to 1 lot for backtesting
                    entry_ts=bar_ts,
                    peak_ltp=bar_close,
                )
                self.logger.debug("Entry at bar %d: price=%.2f", i, bar_close)

        # Close any open position at last bar
        if position is not None:
            last_bar = candles[-1]
            trade = position.close(
                exit_price=float(last_bar.get("close", 0)),
                exit_reason="END_OF_DATA",
                exit_ts=last_bar.get("timestamp", ""),
            )
            trades.append(trade)

        self.logger.info("Backtest complete: %d trades", len(trades))
        return trades


class _BacktestPosition:
    """Internal position tracker for backtesting."""

    def __init__(
        self,
        entry_price: float,
        entry_quantity: int,
        entry_ts: str,
        peak_ltp: float,
    ) -> None:
        self.entry_price = entry_price
        self.entry_quantity = entry_quantity
        self.entry_ts = entry_ts
        self.peak_ltp = peak_ltp

    def close(self, exit_price: float, exit_reason: str, exit_ts: str) -> ClosedTrade:
        pnl = (exit_price - self.entry_price) * self.entry_quantity
        entry_epoch = _ts_to_epoch(self.entry_ts)
        exit_epoch = _ts_to_epoch(exit_ts)

        return ClosedTrade(
            instrument_token="BACKTEST",
            trading_symbol="BACKTEST",
            underlying="",
            option_type="",
            strike=0.0,
            entry_order_id="BT",
            entry_price=self.entry_price,
            entry_quantity=self.entry_quantity,
            entry_time_epoch=entry_epoch,
            exit_order_id="BT",
            exit_price=exit_price,
            exit_time_epoch=exit_epoch,
            exit_reason=exit_reason,
            realised_pnl=pnl,
            peak_ltp=self.peak_ltp,
        )


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _ts_to_epoch(ts_str: str) -> float:
    dt = _parse_timestamp(ts_str)
    return dt.timestamp() if dt else 0.0
