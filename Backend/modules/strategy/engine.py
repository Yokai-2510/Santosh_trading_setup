"""
engine — thin cycle coordinator. All logic lives in sub-modules.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from brokers.upstox.market_data import get_ltp
from brokers.upstox.websocket_v3 import UpstoxMarketFeedV3
from modules.auth.login_manager import authenticate_upstox
from modules.data.candle_service import CandleService
from modules.data.instrument_filter import build_index_option_universe, load_cached_universe
from modules.data.live_candle_builder import LiveCandleBuilder
from modules.risk.risk_guard import is_entry_allowed
from modules.state.runtime_state import (
    PositionSnapshot,
    SignalSnapshot,
    StateStore,
    TradeRecord,
    WorkingOrderSnapshot,
)
from modules.strategy.entry_conditions import evaluate_entry_signal
from modules.strategy.exit_conditions import evaluate_exit
from modules.strategy.instrument_selection import select_entry_contract
from modules.strategy.order_lifecycle import OrderLifecycleManager
from modules.strategy.position_sync import detect_manual_exit
from modules.utils.market_hours import is_market_active


class SantoshTradingEngine:
    def __init__(
        self,
        config_bundle: Dict[str, Any],
        state_store: StateStore,
        logger,
    ) -> None:
        self.system_cfg = config_bundle["system"]
        self.strategy_cfg = config_bundle["strategy"]
        self.credentials_cfg = config_bundle["credentials"]
        self.paths = config_bundle["paths"]
        self.logger = logger
        self.store = state_store

        self.headers: Dict[str, str] = {}
        self.universe: Dict[str, Any] = {}
        self.running = False
        self.candle_service: Optional[CandleService] = None

        runtime_mode = self.system_cfg.get("runtime", {}).get("mode", "paper")
        self.lifecycle = OrderLifecycleManager(
            runtime_mode=runtime_mode,
            strategy_cfg=self.strategy_cfg,
            logger=logger,
        )
        self._last_manual_poll_epoch = 0.0
        self._last_signal_ok: Optional[bool] = None  # track changes to avoid log noise

        # Thread-safe exit overrides (set from GUI without restarting engine)
        self._exit_overrides: Dict[str, Any] = {}
        self._overrides_lock = threading.Lock()

        # Live market data (WebSocket + candle builder)
        self._live_builder: Optional[LiveCandleBuilder] = None
        self._ws_feed: Optional[UpstoxMarketFeedV3] = None

    # --- Initialization ---

    def initialize(self, force_login: bool = False) -> bool:
        ok, headers, message = authenticate_upstox(
            credentials_cfg=self.credentials_cfg,
            auth_cfg=self.system_cfg.get("auth", {}),
            token_cache_path=self.paths.token_cache,
            force_login=force_login,
        )
        if not ok:
            self.logger.error("Auth failed: %s", message)
            self.store.update(auth_ok=False, auth_message=message)
            return False

        self.headers = headers
        self.logger.info("Auth OK: %s", message)
        self.store.update(auth_ok=True, auth_message=message)

        timeouts = self.system_cfg.get("broker", {}).get("api_timeouts", {})
        self.candle_service = CandleService(
            headers=self.headers,
            timeout_seconds=int(timeouts.get("historical_seconds", 20)),
        )

        expiry_choice = self.strategy_cfg.get("instrument_selection", {}).get("expiry_choice", "current")
        self.universe = build_index_option_universe(
            headers=self.headers,
            cache_dir=self.paths.cache_dir,
            expiry_choice=expiry_choice,
            timeout_seconds=int(timeouts.get("master_contract_seconds", 60)),
        )
        if not self.universe.get("indices"):
            self.logger.error("Universe build returned no indices")
            return False

        self.logger.info("Universe ready | expiry=%s | indices=%s",
                         expiry_choice, ",".join(sorted(self.universe["indices"].keys())))

        self._start_live_feed()
        return True

    # --- Main loop ---

    def run_forever(self) -> None:
        self.running = True
        self.store.update(bot_running=True, error_message="")
        loop_seconds = int(self.system_cfg.get("runtime", {}).get("loop_interval_seconds", 5))
        self.logger.info("Engine started | mode=%s", self.lifecycle.runtime_mode)

        while self.running:
            try:
                self.run_once()
            except Exception as exc:
                self.logger.exception("Engine cycle error: %s", exc)
                self.store.update(error_message=str(exc))
            time.sleep(max(1, loop_seconds))

    def run_once(self) -> None:
        if not self.headers:
            raise RuntimeError("Engine not initialized")

        # 1. Market hours check
        ignore = bool(self.system_cfg.get("runtime", {}).get("ignore_market_hours", False))
        market_active = is_market_active(self.system_cfg.get("market", {}), ignore=ignore)
        self.store.update(market_active=market_active)

        # 2. Poll working (entry) order status
        if self.lifecycle.has_working_order():
            result = self.lifecycle.poll_working_order(self.headers)
            if result.action == "fill":
                self.logger.info("Entry filled: %s", result.message)

        # 3. Poll exit order status
        if self.lifecycle.has_exit_order():
            result = self.lifecycle.poll_exit_order(self.headers)
            if result.action == "close" and result.success:
                self.logger.info("Exit filled: %s", result.message)
                self._record_trade(result.payload)

        # 4. Evaluate exit conditions if position active
        if self.lifecycle.has_active_position() and not self.lifecycle.has_exit_order():
            self._evaluate_and_handle_exit()

        # 5. Poll manual exit
        self._poll_manual_exit_if_due()

        if not market_active:
            self._sync_state()
            return

        # 6. Trading paused?
        if self.store.read().trading_paused:
            self._sync_state()
            return

        # 7. Risk guard
        risk_cfg = self.system_cfg.get("risk", {})
        allowed, reason = is_entry_allowed(self.store, risk_cfg)
        if not allowed:
            self.logger.info("Risk guard blocked: %s", reason)
            self._sync_state()
            return

        # 8. Skip if position/order already active
        if self.lifecycle.has_active_position() or self.lifecycle.has_working_order() or self.lifecycle.has_exit_order():
            self._sync_state()
            return

        # 9. Re-entry cooldown
        reentry_wait = int(
            self.strategy_cfg.get("position_management", {}).get("reentry_wait_seconds_after_close", 30)
        )
        if self.lifecycle.last_closed_epoch and (time.time() - self.lifecycle.last_closed_epoch) < reentry_wait:
            self._sync_state()
            return

        # 10. Evaluate entry signal
        signal = self._evaluate_entry()
        if not signal.get("ok"):
            self._sync_state()
            return

        # 11. Resolve contract and handle entry
        self._handle_entry()
        self._sync_state()

    def stop(self) -> None:
        self.running = False
        self.store.update(bot_running=False)
        if self._ws_feed:
            self._ws_feed.stop()
            self._ws_feed = None

    # --- GUI-facing control methods ---

    def pause(self) -> None:
        self.store.update(trading_paused=True)

    def resume(self) -> None:
        self.store.update(trading_paused=False)

    def manual_exit_position(self) -> bool:
        if not self.lifecycle.has_active_position():
            return False
        result = self.lifecycle.mark_manual_exit(exit_price=0.0, reason="MANUAL_GUI")
        if result.success:
            self.logger.info("GUI manual exit executed")
            self._record_trade(result.payload)
        return result.success

    def cancel_working_order(self) -> bool:
        if not self.lifecycle.has_working_order():
            return False
        result = self.lifecycle.cancel_working_order(self.headers)
        if result.success:
            self.logger.info("GUI cancelled working order")
        return result.success

    def modify_working_order_price(self, new_price: float) -> bool:
        if not self.lifecycle.has_working_order():
            return False
        result = self.lifecycle.force_modify_working_order(self.headers, new_price)
        if result.success:
            self.logger.info("GUI modified working order price to %.2f", new_price)
        return result.success

    def set_exit_override(self, key: str, value: Any) -> None:
        with self._overrides_lock:
            self._exit_overrides[key] = value

    def clear_exit_overrides(self) -> None:
        with self._overrides_lock:
            self._exit_overrides.clear()

    # --- Step functions ---

    def _evaluate_entry(self) -> Dict[str, Any]:
        ins_cfg = self.strategy_cfg.get("instrument_selection", {})
        underlying = str(ins_cfg.get("underlying", "NIFTY")).upper()
        index_data = self._get_index_data(underlying)
        if not index_data:
            return {"ok": False, "reason": "No universe data"}

        spot_key = index_data.get("spot_instrument_key")
        timeframe = int(self.strategy_cfg.get("entry_conditions", {}).get("timeframe_minutes", 3))
        candles = self.candle_service.get_candles(spot_key, timeframe) if self.candle_service else []
        signal = evaluate_entry_signal(candles, self.strategy_cfg)

        # Log only when result changes
        if signal.get("ok") != self._last_signal_ok:
            self._last_signal_ok = signal.get("ok")
            self.logger.info("Signal changed → ok=%s | %s", signal.get("ok"), signal.get("checks"))

        self.store.update(
            last_signal=SignalSnapshot(
                ok=signal.get("ok", False),
                checks=signal.get("checks", {}),
                values=signal.get("values", {}),
                thresholds=self._build_thresholds(),
                evaluated_at_epoch=time.time(),
            )
        )
        return signal

    def _build_thresholds(self) -> Dict[str, str]:
        entry_cfg = self.strategy_cfg.get("entry_conditions", {})
        out: Dict[str, str] = {}
        rsi_cfg = entry_cfg.get("rsi", {})
        if rsi_cfg.get("enabled", True):
            op = rsi_cfg.get("operator", ">")
            out["rsi"] = f"{op} {rsi_cfg.get('threshold', 60.0)}"
        vol_cfg = entry_cfg.get("volume_vs_ema", {})
        if vol_cfg.get("enabled", True):
            out["volume_vs_ema"] = "Vol > EMA"
        adx_cfg = entry_cfg.get("adx", {})
        if adx_cfg.get("enabled", False):
            out["adx"] = f">= {adx_cfg.get('min_threshold', 20.0)}"
        return out

    def _handle_entry(self) -> None:
        ins_cfg = self.strategy_cfg.get("instrument_selection", {})
        underlying = str(ins_cfg.get("underlying", "NIFTY")).upper()
        index_data = self._get_index_data(underlying)
        if not index_data:
            return

        spot_key = index_data.get("spot_instrument_key")
        spot_map = get_ltp(self.headers, [spot_key])
        spot_ltp = float(spot_map.get(spot_key, 0.0))
        if spot_ltp <= 0:
            self.logger.warning("Invalid spot LTP for %s", spot_key)
            return

        contract_selection = select_entry_contract(self.universe, self.strategy_cfg, spot_ltp)
        if not contract_selection:
            self.logger.warning("No option contract resolved")
            return

        option_token = contract_selection["contract"]["instrument_key"]
        option_map = get_ltp(self.headers, [option_token])
        option_ltp = float(option_map.get(option_token, 0.0))
        if option_ltp <= 0:
            self.logger.warning("Invalid option LTP for %s", option_token)
            return

        action = self.lifecycle.handle_entry_signal(
            headers=self.headers,
            selected_contract=contract_selection,
            option_ltp=option_ltp,
        )
        if action.success:
            self.logger.info("Entry: %s | %s", action.action, action.message)
        else:
            self.logger.warning("Entry failed: %s", action.message)

    def _evaluate_and_handle_exit(self) -> None:
        pos = self.lifecycle.active_position
        if not pos:
            return

        instrument_token = pos["instrument_token"]
        ltp_map = get_ltp(self.headers, [instrument_token])
        current_ltp = float(ltp_map.get(instrument_token, 0.0))
        if current_ltp <= 0:
            return

        self.lifecycle.update_peak_ltp(current_ltp)

        # Build effective exit config — merge in any GUI overrides
        exit_cfg = dict(self.strategy_cfg.get("exit_conditions", {}))
        with self._overrides_lock:
            if "sl_percent" in self._exit_overrides:
                exit_cfg = dict(exit_cfg)
                exit_cfg["stoploss"] = dict(exit_cfg.get("stoploss", {}))
                exit_cfg["stoploss"]["enabled"] = True
                exit_cfg["stoploss"]["type"] = "percent"
                exit_cfg["stoploss"]["value"] = float(self._exit_overrides["sl_percent"])

        exit_signal = evaluate_exit(
            entry_price=float(pos["entry_price"]),
            current_ltp=current_ltp,
            peak_ltp=self.lifecycle.get_peak_ltp(),
            exit_cfg=exit_cfg,
        )
        if exit_signal:
            result = self.lifecycle.handle_exit_signal(self.headers, exit_signal)
            self.logger.info("Exit triggered: %s | %s", exit_signal.trigger, exit_signal.reason)
            if result.action == "close" and result.success:
                self._record_trade(result.payload)

    def _poll_manual_exit_if_due(self) -> None:
        cfg = self.strategy_cfg.get("position_management", {})
        if not bool(cfg.get("manual_exit_detection_enabled", True)):
            return
        interval = int(cfg.get("manual_exit_poll_interval_seconds", 1))
        now = time.time()
        if self._last_manual_poll_epoch and now - self._last_manual_poll_epoch < max(1, interval):
            return
        self._last_manual_poll_epoch = now

        timeouts = self.system_cfg.get("broker", {}).get("api_timeouts", {})
        result = detect_manual_exit(
            headers=self.headers,
            manager=self.lifecycle,
            timeout_seconds=int(timeouts.get("positions_seconds", 10)),
        )
        if result and result.success:
            self.logger.info("Manual exit detected: %s", result.message)
            self._record_trade(result.payload)

    def _record_trade(self, payload: Dict[str, Any]) -> None:
        entry_price = float(payload.get("entry_price", 0.0))
        exit_price = float(payload.get("exit_price", 0.0))
        quantity = int(payload.get("quantity", 0))
        pnl = (exit_price - entry_price) * quantity

        entry_epoch = float(payload.get("entry_time_epoch", 0.0))
        exit_epoch = float(payload.get("exit_time_epoch", 0.0))

        record = TradeRecord(
            symbol=payload.get("trading_symbol", ""),
            side="BUY",
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            exit_reason=payload.get("exit_reason", ""),
            entry_time=datetime.fromtimestamp(entry_epoch).strftime("%H:%M:%S") if entry_epoch else "",
            exit_time=datetime.fromtimestamp(exit_epoch).strftime("%H:%M:%S") if exit_epoch else "",
        )
        self.store.add_trade(record)
        self.store.update(last_closed_epoch=time.time())
        self.logger.info("Trade recorded: %s pnl=%.2f reason=%s", record.symbol, pnl, record.exit_reason)

    def _start_live_feed(self) -> None:
        """Start WebSocket subscription for the configured underlying instrument."""
        try:
            ins_cfg = self.strategy_cfg.get("instrument_selection", {})
            underlying = str(ins_cfg.get("underlying", "NIFTY")).upper()
            index_data = self.universe.get("indices", {}).get(underlying)
            if not index_data:
                self.logger.warning("LiveFeed: no universe entry for %s — skipping WebSocket", underlying)
                return

            spot_key = index_data.get("spot_instrument_key")
            if not spot_key:
                self.logger.warning("LiveFeed: no spot_instrument_key for %s", underlying)
                return

            access_token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not access_token:
                self.logger.warning("LiveFeed: cannot extract access token from headers")
                return

            self._live_builder = LiveCandleBuilder()
            self._ws_feed = UpstoxMarketFeedV3(
                access_token=access_token,
                instrument_keys=[spot_key],
                mode=UpstoxMarketFeedV3.MODE_FULL,
                on_feed=self._live_builder.on_feed,
                on_connect=lambda: self.logger.info("Market WebSocket connected | key=%s", spot_key),
                on_disconnect=lambda: self.logger.warning("Market WebSocket disconnected"),
            )
            self._ws_feed.start()

            if self.candle_service:
                self.candle_service.set_live_builder(self._live_builder)

            self.logger.info("LiveFeed started for %s", spot_key)
        except Exception as exc:
            self.logger.error("LiveFeed init failed: %s", exc)

    def _get_index_data(self, underlying: str) -> Optional[Dict[str, Any]]:
        index_data = self.universe.get("indices", {}).get(underlying)
        if not index_data:
            cached = load_cached_universe(self.paths.universe_cache)
            if cached:
                self.universe = cached
                index_data = self.universe.get("indices", {}).get(underlying)
        if not index_data:
            self.logger.warning("No universe data for underlying=%s", underlying)
        return index_data

    def _sync_state(self) -> None:
        pos = self.lifecycle.active_position
        wo = self.lifecycle.working_order

        active_snap = None
        if pos:
            ltp_map = get_ltp(self.headers, [pos["instrument_token"]])
            current_ltp = float(ltp_map.get(pos["instrument_token"], 0.0))
            unrealised = (current_ltp - float(pos["entry_price"])) * int(pos["quantity"]) if current_ltp > 0 else 0.0
            active_snap = PositionSnapshot(
                instrument_token=pos["instrument_token"],
                trading_symbol=pos.get("trading_symbol", ""),
                quantity=int(pos["quantity"]),
                entry_price=float(pos["entry_price"]),
                current_ltp=current_ltp,
                unrealised_pnl=unrealised,
                entry_time_epoch=float(pos.get("entry_time_epoch", 0.0)),
                peak_ltp=float(pos.get("peak_ltp", 0.0)),
                status=pos.get("status", "ACTIVE"),
            )

        working_snap = None
        if wo:
            working_snap = WorkingOrderSnapshot(
                order_id=wo.get("order_id", ""),
                instrument_token=wo.get("instrument_token", ""),
                trading_symbol=wo.get("trading_symbol", ""),
                price=float(wo.get("price", 0.0)),
                quantity=int(wo.get("quantity", 0)),
                status=wo.get("status", "OPEN"),
            )

        self.store.update(
            active_position=active_snap,
            working_order=working_snap,
            last_cycle_epoch=time.time(),
            cycle_count=self.store.read().cycle_count + 1,
        )
