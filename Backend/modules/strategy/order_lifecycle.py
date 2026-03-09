"""
order_lifecycle — one-position order workflow with modify-on-reentry support.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from brokers.upstox.order_modify_v3 import modify_order_v3
from brokers.upstox.orders import get_order_status, place_order


@dataclass
class LifecycleResult:
    action: str
    success: bool
    message: str
    payload: Dict[str, Any]


class OrderLifecycleManager:
    def __init__(self, runtime_mode: str, order_cfg: Dict[str, Any], logger) -> None:
        self.runtime_mode = "live" if str(runtime_mode).lower() == "live" else "paper"
        self.order_cfg = order_cfg
        self.logger = logger

        self.working_order: Optional[Dict[str, Any]] = None
        self.active_position: Optional[Dict[str, Any]] = None
        self.last_closed_epoch: float = 0.0

    def has_active_position(self) -> bool:
        return self.active_position is not None

    def has_working_order(self) -> bool:
        return self.working_order is not None

    def handle_entry_signal(
        self,
        headers: Dict[str, str],
        selected_contract: Dict[str, Any],
        option_ltp: float,
    ) -> LifecycleResult:
        """
        Place new order or modify existing working order when signal repeats.
        """
        if self.active_position:
            return LifecycleResult("skip", False, "Active position already exists", {})

        contract = selected_contract["contract"]
        instrument_token = contract["instrument_key"]
        quantity = self._build_quantity(contract)
        order_type = str(self.order_cfg.get("order_type", "LIMIT")).upper()
        price = self._entry_price(option_ltp) if order_type != "MARKET" else None

        # Paper mode: fill immediately.
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
                "exit_reason": None,
                "exit_price": None,
                "exit_time_epoch": None,
            }
            return LifecycleResult("paper_fill", True, "Paper entry filled", dict(self.active_position))

        # Live mode.
        if self.working_order is None:
            placed = place_order(
                headers=headers,
                instrument_token=instrument_token,
                quantity=quantity,
                transaction_type="BUY",
                order_cfg=self.order_cfg,
                price=price,
                timeout=int(self.order_cfg.get("order_request_timeout_seconds", 10)),
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

        # Working order already exists: modify only if same instrument and configuration allows.
        if self.working_order["instrument_token"] != instrument_token:
            return LifecycleResult(
                "skip_modify",
                False,
                "Working order instrument differs; modify skipped",
                dict(self.working_order),
            )

        return self._maybe_modify_working_order(
            headers=headers,
            fresh_price=float(price if price is not None else option_ltp),
        )

    def poll_working_order(self, headers: Dict[str, str]) -> LifecycleResult:
        if self.runtime_mode != "live":
            return LifecycleResult("poll", True, "Paper mode", {})
        if not self.working_order:
            return LifecycleResult("poll", True, "No working order", {})

        order_id = self.working_order["order_id"]
        polled = get_order_status(
            headers=headers,
            order_id=order_id,
            timeout=int(self.order_cfg.get("order_status_timeout_seconds", 10)),
        )
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

        # OPEN/PENDING states.
        self.working_order["status"] = status.upper() if status else "OPEN"
        return LifecycleResult("poll", True, f"Working order status={self.working_order['status']}", dict(self.working_order))

    def mark_manual_exit(self, exit_price: float = 0.0, reason: str = "MANUAL_DETECTED") -> LifecycleResult:
        if not self.active_position:
            return LifecycleResult("manual_exit", False, "No active position", {})
        self.active_position["status"] = "CLOSED"
        self.active_position["exit_reason"] = reason
        self.active_position["exit_price"] = float(exit_price)
        self.active_position["exit_time_epoch"] = time.time()
        snapshot = dict(self.active_position)
        self.active_position = None
        self.last_closed_epoch = time.time()
        self.logger.info(f"Position closed by manual detection. reason={reason}")
        return LifecycleResult("manual_exit", True, "Position closed", snapshot)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "runtime_mode": self.runtime_mode,
            "working_order": dict(self.working_order) if self.working_order else None,
            "active_position": dict(self.active_position) if self.active_position else None,
            "last_closed_epoch": self.last_closed_epoch,
        }

    def _maybe_modify_working_order(self, headers: Dict[str, str], fresh_price: float) -> LifecycleResult:
        if self.runtime_mode != "live":
            return LifecycleResult("skip_modify", False, "Modify supported in live mode only", {})

        if not bool(self.order_cfg.get("modify_on_reentry_signal", True)):
            return LifecycleResult("skip_modify", False, "Modify on signal is disabled", dict(self.working_order))

        now = time.time()
        cooldown = int(self.order_cfg.get("modify_cooldown_seconds", 10))
        last_modified = float(self.working_order.get("last_modified_epoch", 0.0))
        if last_modified and now - last_modified < cooldown:
            return LifecycleResult("skip_modify", False, "Modify cooldown active", dict(self.working_order))

        old_price = float(self.working_order["price"])
        new_price = self._round_to_tick(fresh_price)
        if bool(self.order_cfg.get("only_improve_price", True)) and not (new_price < old_price):
            return LifecycleResult("skip_modify", False, "Price not improved for BUY order", dict(self.working_order))

        modified = modify_order_v3(
            headers=headers,
            order_id=self.working_order["order_id"],
            order_type=str(self.order_cfg.get("order_type", "LIMIT")).upper(),
            price=new_price,
            validity=str(self.order_cfg.get("validity", "DAY")),
            trigger_price=float(self.order_cfg.get("trigger_price", 0.0)),
            quantity=int(self.working_order["quantity"]),
            disclosed_quantity=int(self.order_cfg.get("disclosed_quantity", 0)),
            timeout=int(self.order_cfg.get("order_request_timeout_seconds", 10)),
        )
        if not modified["success"]:
            return LifecycleResult("modify_order", False, "Order modify failed", modified)

        self.working_order["price"] = new_price
        self.working_order["last_modified_epoch"] = now
        self.logger.info(
            f"Modified entry order {self.working_order['order_id']} price {old_price:.2f} -> {new_price:.2f}"
        )
        return LifecycleResult("modify_order", True, "Order modified", dict(self.working_order))

    def _build_quantity(self, contract: Dict[str, Any]) -> int:
        mode = str(self.order_cfg.get("quantity_mode", "lots")).lower()
        if mode == "qty":
            return max(1, int(self.order_cfg.get("quantity", 1)))
        lots = max(1, int(self.order_cfg.get("lots", 1)))
        lot_size = max(1, int(contract.get("lot_size", 1)))
        return lots * lot_size

    def _entry_price(self, option_ltp: float) -> float:
        source = str(self.order_cfg.get("entry_price_source", "ltp")).lower()
        if source == "ltp":
            return self._round_to_tick(option_ltp)
        # fallback
        return self._round_to_tick(option_ltp)

    def _round_to_tick(self, price: float) -> float:
        tick = float(self.order_cfg.get("tick_size", 0.05))
        if tick <= 0:
            return round(float(price), 2)
        return round(round(float(price) / tick) * tick, 2)
