"""live_trading_service — high-level orchestrator for the live trading workflow.

Wraps TradingEngine lifecycle + background services (position polling, capital).
The GUI bridge delegates to this service instead of managing threads directly.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, Optional

from main.engine import TradingEngine
from services.service_registry import ServiceRegistry
from utils.config_loader import build_paths, load_all_configs
from utils.logger import setup_logger
from utils.state import StateStore


class LiveTradingService:
    """Wraps engine + background service lifecycle."""

    def __init__(self, project_root: Path, state_store: StateStore) -> None:
        self.project_root = project_root
        self.store = state_store
        self._engine: Optional[TradingEngine] = None
        self._thread: Optional[threading.Thread] = None
        self._registry: Optional[ServiceRegistry] = None
        paths = build_paths(project_root)
        self._logger = setup_logger("santosh_bot", paths.logs_dir)

    @property
    def engine(self) -> Optional[TradingEngine]:
        return self._engine

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, force_login: bool = False) -> None:
        if self.is_running:
            return

        def _run():
            self.store.update(error_message="Initializing...")
            engine = self._build_engine(force_login)
            if not engine:
                return
            self._engine = engine
            engine.run_forever()

        self._thread = threading.Thread(target=_run, name="santosh-bot", daemon=True)
        self._thread.start()

    def run_once(self, force_login: bool = False) -> None:
        if self.is_running:
            return

        def _single():
            self.store.update(error_message="Running single cycle...")
            engine = self._build_engine(force_login)
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

    def stop(self) -> None:
        if self._registry:
            self._registry.stop_all()
        if self._engine:
            self._engine.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self._engine = None
        self._thread = None
        self._registry = None

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
        return self.project_root / "Backend" / "data_store" / "logs" / "bot.log"

    def service_health(self) -> Dict[str, Any]:
        if self._registry:
            return self._registry.health_summary()
        return {}

    def _build_engine(self, force_login: bool) -> Optional[TradingEngine]:
        try:
            paths = build_paths(self.project_root)
            config_bundle = load_all_configs(paths)
            level = config_bundle["system"].get("runtime", {}).get("log_level", "INFO")
            self._logger.setLevel(level)
            engine = TradingEngine(
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
            self.store.update(error_message=f"Service error: {exc}")
            return None
