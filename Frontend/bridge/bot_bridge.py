"""
bot_bridge — manages bot engine thread lifecycle and exposes shared state to GUI.
All potentially blocking operations run in daemon threads — the GUI never freezes.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from modules.state.runtime_state import RuntimeState, StateStore
from modules.strategy.engine import SantoshTradingEngine
from modules.utils.config_loader import build_paths, load_all_configs
from modules.utils.logger import setup_logger


class BotBridge:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.store = StateStore()
        self._engine: Optional[SantoshTradingEngine] = None
        self._thread: Optional[threading.Thread] = None
        paths = build_paths(project_root)
        self._logger = setup_logger("santosh_bot", paths.logs_dir)

    # --- Bot lifecycle (all non-blocking) ---

    def start_bot(self) -> None:
        """Initialise + run forever — fully in daemon thread, GUI never freezes."""
        if self._thread and self._thread.is_alive():
            return

        def _run():
            self.store.update(error_message="Initializing...")
            engine = self._build_engine(force_login=False)
            if not engine:
                return
            self._engine = engine
            engine.run_forever()

        self._thread = threading.Thread(target=_run, name="santosh-bot", daemon=True)
        self._thread.start()

    def force_login(self) -> None:
        """Force fresh OAuth login then run — non-blocking."""
        if self._thread and self._thread.is_alive():
            return

        def _run():
            self.store.update(error_message="Logging in...")
            engine = self._build_engine(force_login=True)
            if not engine:
                return
            self._engine = engine
            engine.run_forever()

        self._thread = threading.Thread(target=_run, name="santosh-bot-login", daemon=True)
        self._thread.start()

    def run_once(self) -> None:
        """Run single cycle — non-blocking."""
        if self._thread and self._thread.is_alive():
            return

        def _single():
            self.store.update(error_message="Running single cycle...")
            engine = self._build_engine(force_login=False)
            if not engine:
                return
            self._engine = engine
            try:
                engine.run_once()
                self.store.update(error_message="")
            except Exception as exc:
                self.store.update(error_message=str(exc))
            finally:
                engine.stop()

        self._thread = threading.Thread(target=_single, name="santosh-bot-once", daemon=True)
        self._thread.start()

    def stop_bot(self) -> None:
        if self._engine:
            self._engine.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self._engine = None
        self._thread = None

    # --- Trading controls (safe to call from GUI thread) ---

    def pause_trading(self) -> None:
        self.store.update(trading_paused=True)
        if self._engine:
            self._engine.pause()

    def resume_trading(self) -> None:
        self.store.update(trading_paused=False)
        if self._engine:
            self._engine.resume()

    def manual_exit_position(self) -> bool:
        if self._engine:
            return self._engine.manual_exit_position()
        return False

    def cancel_working_order(self) -> bool:
        if self._engine:
            return self._engine.cancel_working_order()
        return False

    def modify_working_order_price(self, new_price: float) -> bool:
        if self._engine:
            return self._engine.modify_working_order_price(new_price)
        return False

    def set_position_sl(self, sl_percent: float) -> None:
        if self._engine:
            self._engine.set_exit_override("sl_percent", sl_percent)

    def clear_position_overrides(self) -> None:
        if self._engine:
            self._engine.clear_exit_overrides()

    # --- State read ---

    def get_state(self) -> RuntimeState:
        return self.store.read()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_runtime_mode(self) -> str:
        if self._engine:
            return self._engine.system_cfg.get("runtime", {}).get("mode", "paper")
        try:
            paths = build_paths(self.project_root)
            cfg = load_all_configs(paths)
            return cfg["system"].get("runtime", {}).get("mode", "paper")
        except Exception:
            return "paper"

    def get_log_path(self) -> Path:
        return self.project_root / "Backend" / "data" / "logs" / "bot.log"

    # --- Internal ---

    def _build_engine(self, force_login: bool) -> Optional[SantoshTradingEngine]:
        try:
            paths = build_paths(self.project_root)
            config_bundle = load_all_configs(paths)
            level = config_bundle["system"].get("runtime", {}).get("log_level", "INFO")
            self._logger.setLevel(level)
            engine = SantoshTradingEngine(
                config_bundle=config_bundle,
                state_store=self.store,
                logger=self._logger,
            )
            if not engine.initialize(force_login=force_login):
                self.store.update(error_message="Engine initialization failed")
                return None
            self.store.update(error_message="")
            return engine
        except Exception as exc:
            self.store.update(error_message=f"Bridge error: {exc}")
            return None
