"""
order_lifecycle — one-position order workflow with entry, modify, and exit support.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from brokers.upstox.order_modify_v3 import modify_order_v3
from brokers.upstox.orders import get_order_status, place_order
from modules.strategy.exit_conditions import ExitSignal


@dataclass
class LifecycleResult:
    action: str
    success: bool
    message: str
    payload: Dict[str, Any]


class OrderLifecycleManager:
    def __init__(self, runtime_mode: str, strategy_cfg: Dict[str, Any], logger) -> None:
        self.runtime_mode = "live" if str(runtime_mode).lower() == "live" else "paper"
        self.strategy_cfg = strategy_cfg
        self.order_cfg = strategy_cfg.get("order_execution", {})
        self.modify_cfg = strategy_cfg.get("order_modify", {})
        self.instrument_cfg = strategy_cfg.get("instrument_selection", {})
        self.logger = logger

        self.working_order: Optional[Dict[str, Any]] = None
        self.active_position: Optional[Dict[str, Any]] = None
        self.exit_order: Optional[Dict[str, Any]] = None
        self.last_closed_epoch: float = 0.0

    def has_active_position(self) -> bool:
        return self.active_position is not None

    def has_working_order(self) -> bool:
        return self.working_order is not None

    def has_exit_order(self) -> bool:
        return self.exit_order is not None

    # --- Peak LTP tracking for trailing SL ---

    def update_peak_ltp(self, current_ltp: float) -> None:
        if self.active_position and current_ltp > 0:
            old_peak = float(self.active_position.get("peak_ltp", 0.0))
            self.active_position["peak_ltp"] = max(old_peak, current_ltp)

    def get_peak_ltp(self) -> float:
        if self.active_position:
            return float(self.active_position.get("peak_ltp", 0.0))
        return 0.0

    # --- Entry ---

    def handle_entry_signal(
        self,
        headers: Dict[str, str],
        selected_contract: Dict[str, Any],
        option_ltp: float,
    ) -> LifecycleResult:
        if self.active_position:
            return LifecycleResult("skip", False, "Active position already exists", {})

        contract = selected_contract["contract"]
        instrument_token = contract["instrument_key"]
        quantity = self._build_quantity(contract)
        order_type = str(self.order_cfg.get("order_type", "LIMIT")).upper()
        price = self._entry_price(option_ltp) if order_type != "MARKET" else None

        # Paper mode: fill immediately
        if self.runtime_mode == "paper":
            fill_price = float(price if price is not None else option_ltp)
            self.active_position = {
                "instrument_token": instrument_token,
                "trading_symbol": contract.get("trading_symbol", ""),
                "quantity": quantity,
                "entry_price": fill_price,
                "entry_time_epoch": time.time(),
                "entry_order_id": "PAPER_ORDER",
                "status": "ACTIVE",
                "peak_ltp": fill_price,
                "exit_reason": None,
                "exit_price": None,
                "exit_time_epoch": None,
            }
            return LifecycleResult("paper_fill", True, "Paper entry filled", dict(self.active_position))

        # Live mode: new order or modify existing
        if self.working_order is None:
            return self._place_entry_order(headers, instrument_token, contract, quantity, price, option_ltp)

        if self.working_order["instrument_token"] != instrument_token:
            return LifecycleResult("skip_modify", False, "Working order instrument differs", dict(self.working_order))

        return self._maybe_modify_working_order(
            headers=headers,
            fresh_price=float(price if price is not None else option_ltp),
        )

    def _place_entry_order(
        self, headers, instrument_token, contract, quantity, price, option_ltp
    ) -> LifecycleResult:
        timeout = int(self.order_cfg.get("order_request_timeout_seconds", 10))
        placed = place_order(
            headers=headers,
            instrument_token=instrument_token,
            quantity=quantity,
            transaction_type="BUY",
            order_cfg=self.order_cfg,
            price=price,
            timeout=timeout,
        )
        if not placed["success"]:
            return LifecycleResult("place_order", False, "Order placement failed", placed)

        self.working_order = {
            "order_id": placed["order_id"],
            "instrument_token": instrument_token,
            "trading_symbol": contract.get("trading_symbol", ""),
            "quantity": quantity,
            "price": float(price if price is not None else option_ltp),
            "status": "OPEN",
            "created_at_epoch": time.time(),
            "last_modified_epoch": 0.0,
        }
        self.logger.info(f"Placed entry order {placed['order_id']} @ {self.working_order['price']:.2f}")
        return LifecycleResult("place_order", True, "Entry order placed", dict(self.working_order))

    # --- Poll working (entry) order ---

    def poll_working_order(self, headers: Dict[str, str]) -> LifecycleResult:
        if self.runtime_mode != "live":
            return LifecycleResult("poll", True, "Paper mode", {})
        if not self.working_order:
            return LifecycleResult("poll", True, "No working order", {})

        order_id = self.working_order["order_id"]
        polled = get_order_status(headers=headers, order_id=order_id)
        if not polled["success"]:
            return LifecycleResult("poll", False, "Order status polling failed", polled)

        data = polled.get("data", {})
        status = str(data.get("status", "")).strip().lower()

        if status in {"complete", "filled"}:
            fill_price = float(data.get("average_price") or self.working_order["price"])
            self.active_position = {
                "instrument_token": self.working_order["instrument_token"],
                "trading_symbol": self.working_order["trading_symbol"],
                "quantity": int(data.get("filled_quantity") or self.working_order["quantity"]),
                "entry_price": fill_price,
                "entry_time_epoch": time.time(),
                "entry_order_id": order_id,
                "status": "ACTIVE",
                "peak_ltp": fill_price,
                "exit_reason": None,
                "exit_price": None,
                "exit_time_epoch": None,
            }
            self.working_order = None
            self.logger.info(f"Entry filled for {self.active_position['trading_symbol']} @ {fill_price:.2f}")
            return LifecycleResult("fill", True, "Entry order filled", dict(self.active_position))

        if status in {"rejected", "cancelled", "canceled"}:
            snapshot = dict(self.working_order)
            self.working_order = None
            self.logger.warning(f"Working order {order_id} ended with status={status}")
            return LifecycleResult("closed_working", False, f"Working order ended with {status}", snapshot)

        self.working_order["status"] = status.upper() if status else "OPEN"
        return LifecycleResult("poll", True, f"Working order status={self.working_order['status']}", dict(self.working_order))

    # --- Exit ---

    def handle_exit_signal(
        self,
        headers: Dict[str, str],
        exit_signal: ExitSignal,
    ) -> LifecycleResult:
        if not self.active_position:
            return LifecycleResult("skip_exit", False, "No active position", {})

        # Paper mode: close immediately
        if self.runtime_mode == "paper":
            return self._close_position(
                exit_price=exit_signal.exit_price,
                reason=exit_signal.trigger,
            )

        # Live mode: place exit (SELL) order
        instrument_token = self.active_position["instrument_token"]
        quantity = int(self.active_position["quantity"])
        exit_order_cfg = dict(self.order_cfg)
        exit_order_cfg["order_type"] = exit_signal.order_type

        placed = place_order(
            headers=headers,
            instrument_token=instrument_token,
            quantity=quantity,
            transaction_type="SELL",
            order_cfg=exit_order_cfg,
            price=exit_signal.exit_price if exit_signal.order_type == "LIMIT" else None,
            timeout=int(self.order_cfg.get("order_request_timeout_seconds", 10)),
        )
        if not placed["success"]:
            return LifecycleResult("exit_order", False, "Exit order placement failed", placed)

        self.exit_order = {
            "order_id": placed["order_id"],
            "instrument_token": instrument_token,
            "trigger": exit_signal.trigger,
            "reason": exit_signal.reason,
            "status": "OPEN",
        }
        self.logger.info(f"Placed exit order {placed['order_id']} trigger={exit_signal.trigger}")
        return LifecycleResult("exit_order", True, "Exit order placed", dict(self.exit_order))

    def poll_exit_order(self, headers: Dict[str, str]) -> LifecycleResult:
        if not self.exit_order:
            return LifecycleResult("poll_exit", True, "No exit order", {})

        order_id = self.exit_order["order_id"]
        polled = get_order_status(headers=headers, order_id=order_id)
        if not polled["success"]:
            return LifecycleResult("poll_exit", False, "Exit order status poll failed", polled)

        data = polled.get("data", {})
        status = str(data.get("status", "")).strip().lower()

        if status in {"complete", "filled"}:
            fill_price = float(data.get("average_price") or 0.0)
            trigger = self.exit_order.get("trigger", "UNKNOWN")
            self.exit_order = None
            return self._close_position(exit_price=fill_price, reason=trigger)

        if status in {"rejected", "cancelled", "canceled"}:
            snapshot = dict(self.exit_order)
            self.exit_order = None
            self.logger.warning(f"Exit order {order_id} ended with status={status}")
            return LifecycleResult("exit_order_failed", False, f"Exit order {status}", snapshot)

        return LifecycleResult("poll_exit", True, f"Exit order status={status}", dict(self.exit_order))

    # --- GUI-driven controls ---

    def cancel_working_order(self, headers: Dict[str, str]) -> LifecycleResult:
        if not self.working_order:
            return LifecycleResult("cancel", False, "No working order", {})
        if self.runtime_mode == "paper":
            snapshot = dict(self.working_order)
            self.working_order = None
            return LifecycleResult("cancel", True, "Paper order cancelled", snapshot)
        from brokers.upstox.orders import cancel_order
        result = cancel_order(headers=headers, order_id=self.working_order["order_id"])
        if result.get("success"):
            snapshot = dict(self.working_order)
            self.working_order = None
            return LifecycleResult("cancel", True, "Order cancelled", snapshot)
        return LifecycleResult("cancel", False, "Cancel failed", result)

    def force_modify_working_order(self, headers: Dict[str, str], new_price: float) -> LifecycleResult:
        """GUI-initiated modify — bypasses cooldown and improve-price checks."""
        if not self.working_order:
            return LifecycleResult("modify_order", False, "No working order", {})
        if self.runtime_mode == "paper":
            old = float(self.working_order["price"])
            self.working_order["price"] = self._round_to_tick(new_price)
            self.working_order["last_modified_epoch"] = time.time()
            return LifecycleResult("modify_order", True, f"Paper order price updated {old:.2f} → {new_price:.2f}", dict(self.working_order))
        new_price = self._round_to_tick(new_price)
        modified = modify_order_v3(
            headers=headers,
            order_id=self.working_order["order_id"],
            order_type=str(self.order_cfg.get("order_type", "LIMIT")).upper(),
            price=new_price,
            validity=str(self.order_cfg.get("validity", "DAY")),
            trigger_price=float(self.order_cfg.get("trigger_price", 0.0)),
            quantity=int(self.working_order["quantity"]),
            disclosed_quantity=int(self.order_cfg.get("disclosed_quantity", 0)),
        )
        if not modified["success"]:
            return LifecycleResult("modify_order", False, "Forced modify failed", modified)
        self.working_order["price"] = new_price
        self.working_order["last_modified_epoch"] = time.time()
        return LifecycleResult("modify_order", True, f"Order price → {new_price:.2f}", dict(self.working_order))

    # --- Manual exit ---

    def mark_manual_exit(self, exit_price: float = 0.0, reason: str = "MANUAL_DETECTED") -> LifecycleResult:
        if not self.active_position:
            return LifecycleResult("manual_exit", False, "No active position", {})
        return self._close_position(exit_price=exit_price, reason=reason)

    # --- Internal ---

    def _close_position(self, exit_price: float, reason: str) -> LifecycleResult:
        if not self.active_position:
            return LifecycleResult("close", False, "No active position", {})

        self.active_position["status"] = "CLOSED"
        self.active_position["exit_reason"] = reason
        self.active_position["exit_price"] = float(exit_price)
        self.active_position["exit_time_epoch"] = time.time()
        snapshot = dict(self.active_position)
        self.active_position = None
        self.last_closed_epoch = time.time()
        self.logger.info(f"Position closed: reason={reason} exit_price={exit_price:.2f}")
        return LifecycleResult("close", True, "Position closed", snapshot)

    def _maybe_modify_working_order(self, headers: Dict[str, str], fresh_price: float) -> LifecycleResult:
        if self.runtime_mode != "live":
            return LifecycleResult("skip_modify", False, "Modify in live mode only", {})

        if not bool(self.modify_cfg.get("modify_on_reentry_signal", True)):
            return LifecycleResult("skip_modify", False, "Modify on signal disabled", dict(self.working_order))

        now = time.time()
        cooldown = int(self.modify_cfg.get("modify_cooldown_seconds", 10))
        last_modified = float(self.working_order.get("last_modified_epoch", 0.0))
        if last_modified and now - last_modified < cooldown:
            return LifecycleResult("skip_modify", False, "Modify cooldown active", dict(self.working_order))

        old_price = float(self.working_order["price"])
        new_price = self._round_to_tick(fresh_price)
        if bool(self.modify_cfg.get("only_improve_price", True)) and not (new_price < old_price):
            return LifecycleResult("skip_modify", False, "Price not improved", dict(self.working_order))

        modified = modify_order_v3(
            headers=headers,
            order_id=self.working_order["order_id"],
            order_type=str(self.order_cfg.get("order_type", "LIMIT")).upper(),
            price=new_price,
            validity=str(self.order_cfg.get("validity", "DAY")),
            trigger_price=float(self.order_cfg.get("trigger_price", 0.0)),
            quantity=int(self.working_order["quantity"]),
            disclosed_quantity=int(self.order_cfg.get("disclosed_quantity", 0)),
        )
        if not modified["success"]:
            return LifecycleResult("modify_order", False, "Order modify failed", modified)

        self.working_order["price"] = new_price
        self.working_order["last_modified_epoch"] = now
        self.logger.info(f"Modified order {self.working_order['order_id']} price {old_price:.2f} -> {new_price:.2f}")
        return LifecycleResult("modify_order", True, "Order modified", dict(self.working_order))

    def _build_quantity(self, contract: Dict[str, Any]) -> int:
        mode = str(self.instrument_cfg.get("quantity_mode", "lots")).lower()
        if mode == "qty":
            return max(1, int(self.instrument_cfg.get("quantity", 1)))
        lots = max(1, int(self.instrument_cfg.get("lots", 1)))
        lot_size = max(1, int(contract.get("lot_size", 1)))
        return lots * lot_size

    def _entry_price(self, option_ltp: float) -> float:
        return self._round_to_tick(option_ltp)

    def _round_to_tick(self, price: float) -> float:
        tick = float(self.order_cfg.get("tick_size", 0.05))
        if tick <= 0:
            return round(float(price), 2)
        return round(round(float(price) / tick) * tick, 2)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "runtime_mode": self.runtime_mode,
            "working_order": dict(self.working_order) if self.working_order else None,
            "active_position": dict(self.active_position) if self.active_position else None,
            "exit_order": dict(self.exit_order) if self.exit_order else None,
            "last_closed_epoch": self.last_closed_epoch,
        }
