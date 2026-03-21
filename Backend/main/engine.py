"""engine — core trading cycle orchestrator.

Clean execution flow:
  1. check_pre_conditions()    — market hours, paused, cooldown, risk, data readiness
  2. evaluate_entry_signal()   — RSI, Volume, MACD, ADX indicator gate
  3. prepare_order()           — instrument selection + order params (qty, price, tick)
  4. execute_entry_order()     — paper or live executor
  5. evaluate_exit()           — SL, Target, Trailing SL, Time-based
  6. execute_exit_order()      — paper or live executor
  7. cleanup_position()        — record trade, reset state, update flags

Paper vs live mode is handled by swapping the executor.
Strategy logic is pure (no broker calls) — reusable by backtesting.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional, Union

from brokers.upstox.market_data import get_ltp
from brokers.upstox.websocket_v3 import UpstoxMarketFeedV3
from data.candle_service import CandleService
from data.instrument_filter import build_index_option_universe, load_cached_universe
from data.live_candle_builder import LiveCandleBuilder
from main.live_executor import LiveExecutor
from main.paper_executor import OrderResult, PaperExecutor
from orders.order_builder import prepare_entry_order, round_to_tick
from orders.position_manager import PositionManager, PositionStatus
from strategy.entry_conditions import evaluate_entry_signal
from strategy.exit_conditions import ExitSignal, evaluate_exit
from strategy.instrument_selection import select_entry_contract
from strategy.pre_checks import check_pre_conditions
from utils.login_manager import authenticate_upstox
from utils.market_hours import is_market_active
from utils.state import (
    PositionSnapshot,
    SignalSnapshot,
    StateStore,
    TradeRecord,
    WorkingOrderSnapshot,
)


class TradingEngine:
    """Core orchestrator for the Santosh trading strategy."""

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

        # Position manager (SSOT)
        self.pos_mgr = PositionManager(logger)

        # Executor (set during initialize based on mode)
        runtime_mode = self.system_cfg.get("runtime", {}).get("mode", "paper")
        self.mode = "live" if str(runtime_mode).lower() == "live" else "paper"
        self.executor: Union[PaperExecutor, LiveExecutor, None] = None

        # Order modify config
        self.modify_cfg = self.strategy_cfg.get("order_modify", {})

        # Track signal changes to avoid log noise
        self._last_signal_ok: Optional[bool] = None
        self._last_candles: list = []
        self._last_manual_poll_epoch = 0.0

        # Thread-safe exit overrides (set from GUI)
        self._exit_overrides: Dict[str, Any] = {}
        self._overrides_lock = threading.Lock()

        # Live market feed
        self._live_builder: Optional[LiveCandleBuilder] = None
        self._ws_feed: Optional[UpstoxMarketFeedV3] = None

    # ===================================================================
    # INITIALIZATION
    # ===================================================================

    def initialize(self, force_login: bool = False) -> bool:
        """Authenticate, build universe, start live feed, create executor."""
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

        # Candle service
        timeouts = self.system_cfg.get("broker", {}).get("api_timeouts", {})
        self.candle_service = CandleService(
            headers=self.headers,
            timeout_seconds=int(timeouts.get("historical_seconds", 20)),
        )

        # Universe (instrument download + filter)
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

        self.logger.info(
            "Universe ready | expiry=%s | indices=%s",
            expiry_choice, ",".join(sorted(self.universe["indices"].keys())),
        )

        # Executor
        if self.mode == "live":
            self.executor = LiveExecutor(self.strategy_cfg, self.headers, self.logger)
        else:
            self.executor = PaperExecutor(self.strategy_cfg, self.logger)

        # Live WebSocket feed
        self._start_live_feed()
        return True

    # ===================================================================
    # MAIN LOOP
    # ===================================================================

    def run_forever(self) -> None:
        self.running = True
        self.store.update(bot_running=True, error_message="")
        loop_seconds = int(self.system_cfg.get("runtime", {}).get("loop_interval_seconds", 5))
        self.logger.info("Engine started | mode=%s", self.mode)

        while self.running:
            try:
                self.run_once()
            except Exception as exc:
                self.logger.exception("Engine cycle error: %s", exc)
                self.store.update(error_message=str(exc))
            time.sleep(max(1, loop_seconds))

    def run_once(self) -> None:
        """
        Single engine cycle — runs EVERY loop iteration regardless of position state.

        The cycle has two halves that run every time:
          A. OBSERVE  — always runs: market status, candle fetch, indicator evaluation
          B. ACT      — state-dependent: poll orders, evaluate exits, place entries

        This ensures the signal panel always shows live indicator values,
        even when a position is active or an order is pending.
        """
        if not self.headers:
            raise RuntimeError("Engine not initialized")

        # ==============================================================
        # A. OBSERVE — runs every cycle regardless of position state
        # ==============================================================

        # A1. Market status
        ignore = bool(self.system_cfg.get("runtime", {}).get("ignore_market_hours", False))
        market_active = is_market_active(self.system_cfg.get("market", {}), ignore=ignore)
        self.store.update(market_active=market_active)

        # A2. Fetch candles and evaluate indicators (always, for GUI display)
        signal = self._evaluate_signal()

        # ==============================================================
        # B. ACT — depends on current position state
        # ==============================================================

        # B1. Poll pending orders
        if self.pos_mgr.is_pending_entry():
            self._poll_entry_order()

        if self.pos_mgr.is_pending_exit():
            self._poll_exit_order()

        # B2. Cleanup closed positions
        if self.pos_mgr.is_closed():
            self._cleanup_position()

        # B3. If ACTIVE, evaluate exit conditions
        if self.pos_mgr.is_active():
            self._evaluate_and_handle_exit()
            self._poll_manual_exit_if_due()

        # B4. If IDLE + market active + signal OK → try entry
        if self.pos_mgr.is_idle() and market_active:
            self._try_entry(signal)

        # Always sync state to GUI
        self._sync_state()

    def stop(self) -> None:
        self.running = False
        self.store.update(bot_running=False)
        if self._ws_feed:
            self._ws_feed.stop()
            self._ws_feed = None

    # ===================================================================
    # A2. SIGNAL EVALUATION — runs every cycle
    # ===================================================================

    def _evaluate_signal(self) -> Dict[str, Any]:
        """
        Fetch candles and evaluate entry indicators EVERY cycle.

        This runs regardless of position state so the GUI signal panel
        always shows live RSI, Volume, ADX values.
        Returns the signal dict for use by _try_entry().
        """
        spot_key = self._get_spot_key()
        if not spot_key:
            return {"ok": False, "reason": "No spot key"}

        timeframe = int(self.strategy_cfg.get("entry_conditions", {}).get("timeframe_minutes", 3))
        self._last_candles = (
            self.candle_service.get_candles(spot_key, timeframe)
            if self.candle_service else []
        )

        signal = evaluate_entry_signal(self._last_candles, self.strategy_cfg)

        # Log only when result changes
        if signal.get("ok") != self._last_signal_ok:
            self._last_signal_ok = signal.get("ok")
            self.logger.info("Signal changed → ok=%s | %s", signal.get("ok"), signal.get("checks"))

        # Always push to GUI state store
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

    # ===================================================================
    # B4. ENTRY — only when IDLE + market open + signal OK
    # ===================================================================

    def _try_entry(self, signal: Dict[str, Any]) -> None:
        """Check pre-conditions and execute entry if signal is OK."""
        # Pre-checks (paused, cooldown, risk, data readiness)
        pre_ok, pre_reason = check_pre_conditions(
            store=self.store,
            system_cfg=self.system_cfg,
            strategy_cfg=self.strategy_cfg,
            last_closed_epoch=self.pos_mgr.last_closed_epoch,
            has_active_position=not self.pos_mgr.is_idle(),
            has_working_order=self.pos_mgr.is_pending_entry(),
            has_exit_order=self.pos_mgr.is_pending_exit(),
            candle_count=len(getattr(self, "_last_candles", [])),
        )
        if not pre_ok:
            return

        if not signal.get("ok"):
            return

        # Prepare order (instrument selection + order params) and execute
        self._prepare_and_execute_entry()

    def _prepare_and_execute_entry(self) -> None:
        """Select instrument, get LTPs, build order params, execute."""
        ins_cfg = self.strategy_cfg.get("instrument_selection", {})
        underlying = str(ins_cfg.get("underlying", "NIFTY")).upper()
        index_data = self._get_index_data(underlying)
        if not index_data:
            return

        # Get spot LTP
        spot_key = index_data.get("spot_instrument_key")
        spot_map = get_ltp(self.headers, [spot_key])
        spot_ltp = float(spot_map.get(spot_key, 0.0))
        if spot_ltp <= 0:
            self.logger.warning("Invalid spot LTP for %s", spot_key)
            return

        # Select contract (ATM/ITM/OTM)
        contract_selection = select_entry_contract(self.universe, self.strategy_cfg, spot_ltp)
        if not contract_selection:
            self.logger.warning("No option contract resolved")
            return

        # Get option LTP
        option_token = contract_selection["contract"]["instrument_key"]
        option_map = get_ltp(self.headers, [option_token])
        option_ltp = float(option_map.get(option_token, 0.0))
        if option_ltp <= 0:
            self.logger.warning("Invalid option LTP for %s", option_token)
            return

        # Build order params
        order_params = prepare_entry_order(contract_selection, option_ltp, self.strategy_cfg)
        if not order_params:
            self.logger.warning("Order preparation failed")
            return

        # Step 4: Execute entry order
        result = self.executor.place_entry_order(order_params)

        if result.success:
            if result.status == "FILLED":
                # Paper mode: instant fill
                self.pos_mgr.on_entry_placed(
                    order_id=result.order_id,
                    instrument_token=order_params.instrument_token,
                    trading_symbol=order_params.trading_symbol,
                    quantity=order_params.quantity,
                    price=result.fill_price,
                    underlying=order_params.underlying,
                    expiry=order_params.expiry,
                    option_type=order_params.option_type,
                    strike=order_params.strike,
                    lot_size=order_params.lot_size,
                    tick_size=order_params.tick_size,
                )
                self.pos_mgr.on_entry_filled(
                    fill_price=result.fill_price,
                    fill_quantity=result.fill_quantity,
                    order_id=result.order_id,
                )
            else:
                # Live mode: order placed, waiting for fill
                self.pos_mgr.on_entry_placed(
                    order_id=result.order_id,
                    instrument_token=order_params.instrument_token,
                    trading_symbol=order_params.trading_symbol,
                    quantity=order_params.quantity,
                    price=float(order_params.price or option_ltp),
                    underlying=order_params.underlying,
                    expiry=order_params.expiry,
                    option_type=order_params.option_type,
                    strike=order_params.strike,
                    lot_size=order_params.lot_size,
                    tick_size=order_params.tick_size,
                )
        else:
            self.logger.warning("Entry order failed: %s", result.message)

    # ===================================================================
    # STEP 5-6: EXIT EVALUATION + EXECUTION
    # ===================================================================

    def _evaluate_and_handle_exit(self) -> None:
        """Evaluate exit conditions and execute if triggered."""
        pos = self.pos_mgr.position
        if pos.status != PositionStatus.ACTIVE:
            return

        # Get current LTP
        ltp_map = get_ltp(self.headers, [pos.instrument_token])
        current_ltp = float(ltp_map.get(pos.instrument_token, 0.0))
        if current_ltp <= 0:
            return

        # Update tracking
        self.pos_mgr.update_ltp(current_ltp)

        # Build effective exit config (merge GUI overrides)
        exit_cfg = dict(self.strategy_cfg.get("exit_conditions", {}))
        with self._overrides_lock:
            if "sl_percent" in self._exit_overrides:
                exit_cfg = dict(exit_cfg)
                exit_cfg["stoploss"] = dict(exit_cfg.get("stoploss", {}))
                exit_cfg["stoploss"]["enabled"] = True
                exit_cfg["stoploss"]["type"] = "percent"
                exit_cfg["stoploss"]["value"] = float(self._exit_overrides["sl_percent"])

        # Evaluate exit
        exit_signal = evaluate_exit(
            entry_price=pos.entry_price,
            current_ltp=current_ltp,
            peak_ltp=pos.peak_ltp,
            exit_cfg=exit_cfg,
        )

        if exit_signal:
            self._execute_exit(exit_signal, current_ltp)

    def _execute_exit(self, exit_signal: ExitSignal, current_ltp: float) -> None:
        """Execute the exit order (paper or live)."""
        pos = self.pos_mgr.position
        self.logger.info("Exit triggered: %s | %s", exit_signal.trigger, exit_signal.reason)

        result = self.executor.place_exit_order(
            instrument_token=pos.instrument_token,
            quantity=pos.entry_quantity,
            exit_price=exit_signal.exit_price,
            exit_order_type=exit_signal.order_type,
        )

        if result.success:
            if result.status == "FILLED":
                # Paper mode: instant close
                self.pos_mgr.on_manual_exit(
                    exit_price=result.fill_price,
                    reason=exit_signal.trigger,
                )
            else:
                # Live mode: exit order placed, waiting
                self.pos_mgr.on_exit_placed(
                    order_id=result.order_id,
                    reason=exit_signal.trigger,
                )
        else:
            self.logger.warning("Exit order failed: %s", result.message)

    # ===================================================================
    # ORDER POLLING
    # ===================================================================

    def _poll_entry_order(self) -> None:
        """Poll working entry order status."""
        if self.mode == "paper":
            return  # Paper fills instantly

        order_id = self.pos_mgr.position.working_order_id
        if not order_id:
            return

        result = self.executor.poll_order(order_id)

        if result.status == "FILLED":
            fill_price = result.fill_price or self.pos_mgr.position.working_order_price
            fill_qty = result.fill_quantity or self.pos_mgr.position.entry_quantity
            self.pos_mgr.on_entry_filled(fill_price, fill_qty, order_id)
        elif result.status in {"REJECTED", "CANCELLED", "CANCELED"}:
            self.pos_mgr.on_entry_rejected(result.message)

    def _poll_exit_order(self) -> None:
        """Poll exit order status."""
        if self.mode == "paper":
            return

        order_id = self.pos_mgr.position.exit_order_id
        if not order_id:
            return

        result = self.executor.poll_order(order_id)

        if result.status == "FILLED":
            self.pos_mgr.on_exit_filled(result.fill_price)
        elif result.status in {"REJECTED", "CANCELLED", "CANCELED"}:
            self.pos_mgr.on_exit_rejected(result.message)

    def _poll_manual_exit_if_due(self) -> None:
        """Detect manual exit via broker position polling."""
        if self.mode == "paper":
            return

        cfg = self.strategy_cfg.get("position_management", {})
        if not bool(cfg.get("manual_exit_detection_enabled", True)):
            return

        interval = int(cfg.get("manual_exit_poll_interval_seconds", 1))
        now = time.time()
        if self._last_manual_poll_epoch and now - self._last_manual_poll_epoch < max(1, interval):
            return
        self._last_manual_poll_epoch = now

        exit_price = self.executor.detect_manual_exit(self.pos_mgr.position.instrument_token)
        if exit_price is not None:
            reason = "MANUAL_DETECTED_NOT_FOUND" if exit_price == 0.0 else "MANUAL_DETECTED_QTY_ZERO"
            self.pos_mgr.on_manual_exit(exit_price=exit_price, reason=reason)

    # ===================================================================
    # STEP 7: CLEANUP
    # ===================================================================

    def _cleanup_position(self) -> None:
        """Record trade, reset position state, update flags."""
        trade = self.pos_mgr.cleanup()
        if not trade:
            return

        record = TradeRecord(
            symbol=trade.trading_symbol,
            side="BUY",
            quantity=trade.entry_quantity,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            pnl=trade.realised_pnl,
            exit_reason=trade.exit_reason,
            entry_time=(
                datetime.fromtimestamp(trade.entry_time_epoch).strftime("%H:%M:%S")
                if trade.entry_time_epoch else ""
            ),
            exit_time=(
                datetime.fromtimestamp(trade.exit_time_epoch).strftime("%H:%M:%S")
                if trade.exit_time_epoch else ""
            ),
        )
        self.store.add_trade(record)
        self.store.update(last_closed_epoch=time.time())
        self.logger.info(
            "Trade recorded: %s pnl=%.2f reason=%s",
            record.symbol, trade.realised_pnl, record.exit_reason,
        )

        # Clear exit overrides after position close
        self.clear_exit_overrides()

    # ===================================================================
    # GUI-FACING CONTROL METHODS
    # ===================================================================

    def pause(self) -> None:
        self.store.update(trading_paused=True)

    def resume(self) -> None:
        self.store.update(trading_paused=False)

    def manual_exit_position(self) -> bool:
        if not self.pos_mgr.is_active():
            return False
        self.pos_mgr.on_manual_exit(exit_price=0.0, reason="MANUAL_GUI")
        self.logger.info("GUI manual exit executed")
        return True

    def cancel_working_order(self) -> bool:
        if not self.pos_mgr.is_pending_entry():
            return False
        order_id = self.pos_mgr.position.working_order_id
        result = self.executor.cancel_order(order_id)
        if result.success:
            self.pos_mgr.on_entry_cancelled()
            self.logger.info("GUI cancelled working order")
        return result.success

    def modify_working_order_price(self, new_price: float) -> bool:
        if not self.pos_mgr.is_pending_entry():
            return False
        order_id = self.pos_mgr.position.working_order_id
        tick_size = self.pos_mgr.position.tick_size
        new_price = round_to_tick(new_price, tick_size)
        result = self.executor.modify_order(
            order_id, new_price, self.pos_mgr.position.entry_quantity,
        )
        if result.success:
            self.pos_mgr.on_entry_modified(new_price)
            self.logger.info("GUI modified working order price to %.2f", new_price)
        return result.success

    def set_exit_override(self, key: str, value: Any) -> None:
        with self._overrides_lock:
            self._exit_overrides[key] = value

    def clear_exit_overrides(self) -> None:
        with self._overrides_lock:
            self._exit_overrides.clear()

    # ===================================================================
    # INTERNAL HELPERS
    # ===================================================================

    def _get_spot_key(self) -> Optional[str]:
        ins_cfg = self.strategy_cfg.get("instrument_selection", {})
        underlying = str(ins_cfg.get("underlying", "NIFTY")).upper()
        index_data = self._get_index_data(underlying)
        return index_data.get("spot_instrument_key") if index_data else None

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

    def _start_live_feed(self) -> None:
        """Start WebSocket subscription for the configured underlying."""
        try:
            ins_cfg = self.strategy_cfg.get("instrument_selection", {})
            underlying = str(ins_cfg.get("underlying", "NIFTY")).upper()
            index_data = self.universe.get("indices", {}).get(underlying)
            if not index_data:
                self.logger.warning("LiveFeed: no universe entry for %s", underlying)
                return

            spot_key = index_data.get("spot_instrument_key")
            if not spot_key:
                self.logger.warning("LiveFeed: no spot_instrument_key for %s", underlying)
                return

            access_token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not access_token:
                self.logger.warning("LiveFeed: cannot extract access token")
                return

            self._live_builder = LiveCandleBuilder()
            self._ws_feed = UpstoxMarketFeedV3(
                access_token=access_token,
                instrument_keys=[spot_key],
                mode=UpstoxMarketFeedV3.MODE_FULL,
                on_feed=self._live_builder.on_feed,
                on_connect=lambda: self.logger.info("WebSocket connected | key=%s", spot_key),
                on_disconnect=lambda: self.logger.warning("WebSocket disconnected"),
            )
            self._ws_feed.start()

            if self.candle_service:
                self.candle_service.set_live_builder(self._live_builder)

            self.logger.info("LiveFeed started for %s", spot_key)
        except Exception as exc:
            self.logger.error("LiveFeed init failed: %s", exc)

    def _sync_state(self) -> None:
        """Sync position manager state to the GUI state store."""
        pos = self.pos_mgr.position

        # Active position snapshot
        active_snap = None
        if pos.status in (PositionStatus.ACTIVE, PositionStatus.PENDING_EXIT):
            active_snap = PositionSnapshot(
                instrument_token=pos.instrument_token,
                trading_symbol=pos.trading_symbol,
                quantity=pos.entry_quantity,
                entry_price=pos.entry_price,
                current_ltp=pos.current_ltp,
                unrealised_pnl=pos.unrealised_pnl,
                entry_time_epoch=pos.entry_time_epoch,
                peak_ltp=pos.peak_ltp,
                status=pos.status.value,
            )

        # Working order snapshot
        working_snap = None
        if pos.status == PositionStatus.PENDING_ENTRY and pos.working_order_id:
            working_snap = WorkingOrderSnapshot(
                order_id=pos.working_order_id,
                instrument_token=pos.instrument_token,
                trading_symbol=pos.trading_symbol,
                price=pos.working_order_price,
                quantity=pos.entry_quantity,
                status=pos.working_order_status or "OPEN",
            )

        self.store.update(
            active_position=active_snap,
            working_order=working_snap,
            last_cycle_epoch=time.time(),
            cycle_count=self.store.read().cycle_count + 1,
        )
