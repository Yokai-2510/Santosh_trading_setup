"""
engine — orchestrates auth, data fetch, signal checks, and order lifecycle.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

from brokers.upstox.market_data import get_ltp
from modules.auth.login_manager import authenticate_upstox
from modules.data.candle_service import CandleService
from modules.data.instrument_filter import build_index_option_universe, load_cached_universe
from modules.strategy.entry_conditions import evaluate_entry_signal
from modules.strategy.instrument_selection import select_entry_contract
from modules.strategy.order_lifecycle import OrderLifecycleManager
from modules.strategy.position_sync import detect_manual_exit


class SantoshTradingEngine:
    def __init__(self, config_bundle: Dict[str, Any], logger) -> None:
        self.system_cfg = config_bundle["system"]
        self.strategy_cfg = config_bundle["strategy"]
        self.credentials_cfg = config_bundle["credentials"]
        self.paths = config_bundle["paths"]
        self.logger = logger

        self.headers: Dict[str, str] = {}
        self.universe: Dict[str, Any] = {}
        self.running = False

        self.candle_service: Optional[CandleService] = None
        runtime_mode = self.system_cfg.get("runtime", {}).get("mode", "paper")
        order_cfg = self.strategy_cfg.get("order_details", {})
        self.lifecycle = OrderLifecycleManager(runtime_mode=runtime_mode, order_cfg=order_cfg, logger=logger)
        self._last_manual_poll_epoch = 0.0

    def initialize(self, force_login: bool = False) -> bool:
        auth_cfg = self.system_cfg.get("auth", {})
        ok, headers, message = authenticate_upstox(
            credentials_cfg=self.credentials_cfg,
            auth_cfg=auth_cfg,
            token_cache_path=self.paths.token_cache,
            force_login=force_login,
        )
        if not ok:
            self.logger.error(message)
            return False

        self.headers = headers
        self.logger.info(message)
        self.candle_service = CandleService(
            headers=self.headers,
            timeout_seconds=int(
                self.system_cfg.get("broker", {})
                .get("api", {})
                .get("historical_request_timeout_seconds", 20)
            ),
        )

        expiry_choice = self.strategy_cfg.get("instrument_selection", {}).get("expiry_choice", "current")
        self.universe = build_index_option_universe(
            headers=self.headers,
            cache_dir=self.paths.cache_dir,
            expiry_choice=expiry_choice,
            timeout_seconds=int(
                self.system_cfg.get("broker", {})
                .get("api", {})
                .get("master_contract_timeout_seconds", 60)
            ),
        )
        if not self.universe.get("indices"):
            self.logger.error("Universe build returned no indices")
            return False

        self.logger.info(
            "Universe ready | expiry_choice=%s | indices=%s",
            expiry_choice,
            ",".join(sorted(self.universe["indices"].keys())),
        )
        return True

    def run_forever(self) -> None:
        self.running = True
        loop_seconds = int(self.system_cfg.get("runtime", {}).get("loop_interval_seconds", 5))
        self.logger.info("Engine started")

        while self.running:
            try:
                self.run_once()
            except Exception as exc:
                self.logger.exception("Engine cycle error: %s", exc)
            time.sleep(max(1, loop_seconds))

    def run_once(self) -> None:
        if not self.headers:
            raise RuntimeError("Engine not initialized")

        ignore_market_hours = bool(self.system_cfg.get("runtime", {}).get("ignore_market_hours", False))
        market_open = self.system_cfg.get("market", {}).get("market_open", "09:15:00")
        market_close = self.system_cfg.get("market", {}).get("market_close", "15:30:00")
        market_active = ignore_market_hours or _is_market_active(market_open, market_close)

        # Always poll working order / manual exits even outside market hours for state sync.
        if self.lifecycle.has_working_order():
            result = self.lifecycle.poll_working_order(self.headers)
            self.logger.debug("Order poll: %s | %s", result.action, result.message)

        self._poll_manual_exit_if_due()
        if not market_active:
            self.logger.info("Market inactive - skipping entry checks this cycle")
            return

        selected_index_cfg = self.strategy_cfg.get("instrument_selection", {})
        underlying = str(selected_index_cfg.get("underlying", "NIFTY")).upper()
        index_data = self.universe.get("indices", {}).get(underlying)
        if not index_data:
            # Retry from cache once before rebuilding.
            cached = load_cached_universe(self.paths.universe_cache)
            if cached:
                self.universe = cached
                index_data = self.universe.get("indices", {}).get(underlying)
        if not index_data:
            self.logger.warning("No universe data for underlying=%s", underlying)
            return

        spot_key = index_data.get("spot_instrument_key")
        spot_map = get_ltp(self.headers, [spot_key])
        spot_ltp = float(spot_map.get(spot_key, 0.0))
        if spot_ltp <= 0:
            self.logger.warning("Invalid spot LTP for %s", spot_key)
            return

        timeframe = int(self.strategy_cfg.get("entry_conditions", {}).get("timeframe_minutes", 3))
        candles = self.candle_service.get_candles(spot_key, timeframe) if self.candle_service else []
        signal = evaluate_entry_signal(candles, self.strategy_cfg)
        self.logger.info("Entry checks=%s values=%s", signal.get("checks"), signal.get("values"))
        if not signal.get("ok"):
            return

        contract_selection = select_entry_contract(self.universe, self.strategy_cfg, spot_ltp)
        if not contract_selection:
            self.logger.warning("No option contract resolved")
            return

        contract = contract_selection["contract"]
        option_token = contract["instrument_key"]
        option_map = get_ltp(self.headers, [option_token])
        option_ltp = float(option_map.get(option_token, 0.0))
        if option_ltp <= 0:
            self.logger.warning("Invalid option LTP for %s", option_token)
            return

        reentry_wait = int(
            self.strategy_cfg.get("position_management", {}).get("reentry_wait_seconds_after_close", 30)
        )
        if self.lifecycle.last_closed_epoch and (time.time() - self.lifecycle.last_closed_epoch) < reentry_wait:
            self.logger.info("Re-entry cooldown active")
            return

        action = self.lifecycle.handle_entry_signal(
            headers=self.headers,
            selected_contract=contract_selection,
            option_ltp=option_ltp,
        )
        self.logger.info("Lifecycle action=%s success=%s msg=%s", action.action, action.success, action.message)

    def stop(self) -> None:
        self.running = False

    def _poll_manual_exit_if_due(self) -> None:
        cfg = self.strategy_cfg.get("position_management", {})
        if not bool(cfg.get("manual_exit_detection_enabled", True)):
            return
        interval = int(cfg.get("manual_exit_poll_interval_seconds", 1))
        now = time.time()
        if self._last_manual_poll_epoch and now - self._last_manual_poll_epoch < max(1, interval):
            return
        self._last_manual_poll_epoch = now
        result = detect_manual_exit(
            headers=self.headers,
            manager=self.lifecycle,
            timeout_seconds=int(
                self.system_cfg.get("broker", {})
                .get("api", {})
                .get("positions_request_timeout_seconds", 10)
            ),
        )
        if result:
            self.logger.info("Manual exit sync: %s", result.message)


def _is_market_active(open_time: str, close_time: str) -> bool:
    now = datetime.now().time()
    open_parts = [int(x) for x in open_time.split(":")]
    close_parts = [int(x) for x in close_time.split(":")]
    start = now.replace(hour=open_parts[0], minute=open_parts[1], second=open_parts[2], microsecond=0)
    end = now.replace(hour=close_parts[0], minute=close_parts[1], second=close_parts[2], microsecond=0)
    return start <= now <= end
