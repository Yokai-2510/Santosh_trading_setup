"""service_registry — central registry for all background services.

Provides start/stop lifecycle management and health status for:
- PositionPollingService
- CapitalService
- HealthCheckService
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional


class BackgroundService:
    """Base class for a polling background service."""

    def __init__(self, name: str, interval_seconds: float, logger) -> None:
        self.name = name
        self.interval = max(1.0, interval_seconds)
        self.logger = logger
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.last_run_epoch: float = 0.0
        self.last_error: str = ""
        self.run_count: int = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name=self.name, daemon=True)
        self._thread.start()
        self.logger.info("Service started: %s (interval=%.1fs)", self.name, self.interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def tick(self) -> None:
        """Override in subclass — called every interval."""
        raise NotImplementedError

    def _loop(self) -> None:
        while self._running:
            try:
                self.tick()
                self.last_run_epoch = time.time()
                self.run_count += 1
                self.last_error = ""
            except Exception as exc:
                self.last_error = str(exc)
                self.logger.error("Service %s error: %s", self.name, exc)
            time.sleep(self.interval)

    def status_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "alive": self.alive,
            "run_count": self.run_count,
            "last_run_epoch": self.last_run_epoch,
            "last_error": self.last_error,
        }


class PositionPollingService(BackgroundService):
    """Polls broker positions API to detect manual exits."""

    def __init__(self, poll_fn: Callable, logger, interval: float = 2.0) -> None:
        super().__init__("position-poller", interval, logger)
        self._poll_fn = poll_fn

    def tick(self) -> None:
        self._poll_fn()


class CapitalService(BackgroundService):
    """Polls broker funds/margin API for capital tracking."""

    def __init__(self, fetch_fn: Callable, on_update: Callable, logger, interval: float = 30.0) -> None:
        super().__init__("capital-tracker", interval, logger)
        self._fetch_fn = fetch_fn
        self._on_update = on_update

    def tick(self) -> None:
        data = self._fetch_fn()
        if data:
            self._on_update(data)


class HealthCheckService(BackgroundService):
    """Periodically checks system health (auth, websocket, services)."""

    def __init__(self, check_fn: Callable, on_update: Callable, logger, interval: float = 60.0) -> None:
        super().__init__("health-check", interval, logger)
        self._check_fn = check_fn
        self._on_update = on_update

    def tick(self) -> None:
        result = self._check_fn()
        if result:
            self._on_update(result)


class ServiceRegistry:
    """Manages lifecycle of all background services."""

    def __init__(self, logger) -> None:
        self.logger = logger
        self._services: Dict[str, BackgroundService] = {}

    def register(self, service: BackgroundService) -> None:
        self._services[service.name] = service

    def start_all(self) -> None:
        for svc in self._services.values():
            svc.start()

    def stop_all(self) -> None:
        for svc in self._services.values():
            svc.stop()
        self.logger.info("All services stopped")

    def get(self, name: str) -> Optional[BackgroundService]:
        return self._services.get(name)

    def health_summary(self) -> Dict[str, Any]:
        return {name: svc.status_dict() for name, svc in self._services.items()}
