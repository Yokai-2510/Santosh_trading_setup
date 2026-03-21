"""backtest_service — orchestrates backtesting runs with progress callbacks.

Bridges the BacktestEngine with the GUI, running backtests in background threads.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from backtesting.backtest_engine import BacktestEngine
from backtesting.report import BacktestResult, generate_report
from utils.config_loader import build_paths, load_all_configs
from utils.logger import setup_logger


class BacktestService:
    """Runs backtests in background threads with progress callbacks."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._thread: Optional[threading.Thread] = None
        self._result: Optional[BacktestResult] = None
        self._running = False
        self._progress: float = 0.0
        self._status: str = "idle"

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def status(self) -> str:
        return self._status

    @property
    def result(self) -> Optional[BacktestResult]:
        return self._result

    def run(
        self,
        underlying: str,
        start_date: str,
        end_date: str,
        strategy_overrides: Optional[Dict[str, Any]] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> None:
        """Start a backtest run in a background thread."""
        if self.is_running:
            return

        self._result = None
        self._progress = 0.0
        self._status = "starting"

        def _run():
            try:
                self._running = True
                paths = build_paths(self.project_root)
                config_bundle = load_all_configs(paths)
                logger = setup_logger("backtest", paths.logs_dir, level="INFO")

                if strategy_overrides:
                    strategy = config_bundle["strategy"]
                    for key, value in strategy_overrides.items():
                        if isinstance(value, dict) and key in strategy:
                            strategy[key].update(value)
                        else:
                            strategy[key] = value

                engine = BacktestEngine(
                    config_bundle=config_bundle,
                    logger=logger,
                    on_progress=self._on_progress,
                )

                self._status = "running"
                trades = engine.run(
                    underlying=underlying,
                    start_date=start_date,
                    end_date=end_date,
                )
                self._result = generate_report(trades)
                self._status = "complete"
                self._progress = 100.0

                if on_complete:
                    on_complete(self._result)

            except Exception as exc:
                self._status = f"error: {exc}"
                if on_error:
                    on_error(str(exc))
            finally:
                self._running = False

        self._thread = threading.Thread(target=_run, name="backtest", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._status = "stopped"

    def _on_progress(self, pct: float, msg: str = "") -> None:
        self._progress = pct
        if msg:
            self._status = msg
