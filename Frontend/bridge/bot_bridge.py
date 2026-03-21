"""
bot_bridge — manages bot engine thread lifecycle and exposes shared state to GUI.
All potentially blocking operations run in daemon threads — the GUI never freezes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from services.live_trading_service import LiveTradingService
from services.backtest_service import BacktestService
from utils.config_loader import build_paths, load_all_configs
from utils.state import RuntimeState, StateStore


class BotBridge:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.store = StateStore()
        self._trading = LiveTradingService(project_root, self.store)
        self._backtest = BacktestService(project_root)

    # --- Bot lifecycle (all non-blocking) ---

    def start_bot(self) -> None:
        self._trading.start(force_login=False)

    def force_login(self) -> None:
        self._trading.start(force_login=True)

    def run_once(self) -> None:
        self._trading.run_once()

    def stop_bot(self) -> None:
        self._trading.stop()

    # --- Trading controls (safe to call from GUI thread) ---

    def pause_trading(self) -> None:
        self.store.update(trading_paused=True)
        engine = self._trading.engine
        if engine:
            engine.pause()

    def resume_trading(self) -> None:
        self.store.update(trading_paused=False)
        engine = self._trading.engine
        if engine:
            engine.resume()

    def manual_exit_position(self) -> bool:
        engine = self._trading.engine
        if engine:
            return engine.manual_exit_position()
        return False

    def cancel_working_order(self) -> bool:
        engine = self._trading.engine
        if engine:
            return engine.cancel_working_order()
        return False

    def modify_working_order_price(self, new_price: float) -> bool:
        engine = self._trading.engine
        if engine:
            return engine.modify_working_order_price(new_price)
        return False

    def set_position_sl(self, sl_percent: float) -> None:
        engine = self._trading.engine
        if engine:
            engine.set_exit_override("sl_percent", sl_percent)

    def clear_position_overrides(self) -> None:
        engine = self._trading.engine
        if engine:
            engine.clear_exit_overrides()

    # --- State read ---

    def get_state(self) -> RuntimeState:
        return self.store.read()

    def is_running(self) -> bool:
        return self._trading.is_running

    def get_runtime_mode(self) -> str:
        return self._trading.get_runtime_mode()

    def get_log_path(self) -> Path:
        return self._trading.get_log_path()

    def get_configs_dir(self) -> Path:
        return self.project_root / "Backend" / "configs"

    def service_health(self) -> dict:
        return self._trading.service_health()

    # --- Backtesting ---

    @property
    def backtest(self) -> BacktestService:
        return self._backtest
