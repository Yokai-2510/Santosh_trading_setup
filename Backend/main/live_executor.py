"""live_executor — real broker order execution for live trading mode.

All orders go through the Upstox broker API.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from brokers.upstox.order_modify_v3 import modify_order_v3
from brokers.upstox.orders import cancel_order as broker_cancel_order
from brokers.upstox.orders import get_order_status, place_order
from brokers.upstox.positions import get_positions
from main.paper_executor import OrderResult
from orders.order_builder import OrderParams


class LiveExecutor:
    """Real broker executor — orders go to Upstox API."""

    def __init__(
        self,
        strategy_cfg: Dict[str, Any],
        headers: Dict[str, str],
        logger,
    ) -> None:
        self.strategy_cfg = strategy_cfg
        self.headers = headers
        self.logger = logger
        self.order_cfg = strategy_cfg.get("order_execution", {})

    def update_headers(self, headers: Dict[str, str]) -> None:
        """Update auth headers (e.g., after token refresh)."""
        self.headers = headers

    def place_entry_order(self, order_params: OrderParams) -> OrderResult:
        """Place a BUY order via broker API."""
        timeout = int(self.order_cfg.get("order_request_timeout_seconds", 10))
        order_cfg_dict = {
            "product": order_params.product,
            "validity": order_params.validity,
            "order_type": order_params.order_type,
            "disclosed_quantity": order_params.disclosed_quantity,
            "trigger_price": order_params.trigger_price,
            "is_amo": order_params.is_amo,
        }

        placed = place_order(
            headers=self.headers,
            instrument_token=order_params.instrument_token,
            quantity=order_params.quantity,
            transaction_type="BUY",
            order_cfg=order_cfg_dict,
            price=order_params.price,
            timeout=timeout,
        )

        if not placed["success"]:
            return OrderResult(
                success=False,
                order_id="",
                fill_price=0.0,
                fill_quantity=0,
                message=f"Order placement failed: {placed.get('response', {})}",
                status="REJECTED",
            )

        order_id = placed.get("order_id", "")
        self.logger.info("Entry order placed: %s", order_id)
        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=0.0,
            fill_quantity=0,
            message="Entry order placed",
            status="OPEN",
        )

    def place_exit_order(
        self,
        instrument_token: str,
        quantity: int,
        exit_price: float,
        exit_order_type: str,
    ) -> OrderResult:
        """Place a SELL order via broker API."""
        timeout = int(self.order_cfg.get("order_request_timeout_seconds", 10))
        order_cfg_dict = {
            "product": self.order_cfg.get("product", "D"),
            "validity": self.order_cfg.get("validity", "DAY"),
            "order_type": exit_order_type,
            "disclosed_quantity": int(self.order_cfg.get("disclosed_quantity", 0)),
            "trigger_price": 0.0,
            "is_amo": False,
        }

        price = exit_price if exit_order_type == "LIMIT" else None

        placed = place_order(
            headers=self.headers,
            instrument_token=instrument_token,
            quantity=quantity,
            transaction_type="SELL",
            order_cfg=order_cfg_dict,
            price=price,
            timeout=timeout,
        )

        if not placed["success"]:
            return OrderResult(
                success=False,
                order_id="",
                fill_price=0.0,
                fill_quantity=0,
                message=f"Exit order failed: {placed.get('response', {})}",
                status="REJECTED",
            )

        order_id = placed.get("order_id", "")
        self.logger.info("Exit order placed: %s", order_id)
        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=0.0,
            fill_quantity=0,
            message="Exit order placed",
            status="OPEN",
        )

    def poll_order(self, order_id: str) -> OrderResult:
        """Poll broker for order status."""
        polled = get_order_status(headers=self.headers, order_id=order_id)
        if not polled["success"]:
            return OrderResult(
                success=False,
                order_id=order_id,
                fill_price=0.0,
                fill_quantity=0,
                message="Order status poll failed",
                status="UNKNOWN",
            )

        data = polled.get("data", {})
        status = str(data.get("status", "")).strip().lower()

        if status in {"complete", "filled"}:
            fill_price = float(data.get("average_price", 0.0))
            fill_qty = int(data.get("filled_quantity", 0))
            return OrderResult(
                success=True,
                order_id=order_id,
                fill_price=fill_price,
                fill_quantity=fill_qty,
                message="Order filled",
                status="FILLED",
            )

        if status in {"rejected", "cancelled", "canceled"}:
            return OrderResult(
                success=False,
                order_id=order_id,
                fill_price=0.0,
                fill_quantity=0,
                message=f"Order ended: {status}",
                status=status.upper(),
            )

        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=0.0,
            fill_quantity=0,
            message=f"Order status: {status}",
            status=status.upper() if status else "OPEN",
        )

    def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an open order."""
        result = broker_cancel_order(headers=self.headers, order_id=order_id)
        return OrderResult(
            success=result.get("success", False),
            order_id=order_id,
            fill_price=0.0,
            fill_quantity=0,
            message="Order cancelled" if result.get("success") else "Cancel failed",
            status="CANCELLED" if result.get("success") else "OPEN",
        )

    def modify_order(
        self, order_id: str, new_price: float, quantity: int
    ) -> OrderResult:
        """Modify order price."""
        modified = modify_order_v3(
            headers=self.headers,
            order_id=order_id,
            order_type=str(self.order_cfg.get("order_type", "LIMIT")).upper(),
            price=new_price,
            validity=str(self.order_cfg.get("validity", "DAY")),
            trigger_price=float(self.order_cfg.get("trigger_price", 0.0)),
            quantity=quantity,
            disclosed_quantity=int(self.order_cfg.get("disclosed_quantity", 0)),
        )

        if not modified["success"]:
            return OrderResult(
                success=False,
                order_id=order_id,
                fill_price=0.0,
                fill_quantity=0,
                message="Order modify failed",
                status="OPEN",
            )

        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=new_price,
            fill_quantity=quantity,
            message=f"Order price → {new_price:.2f}",
            status="OPEN",
        )

    def detect_manual_exit(self, instrument_token: str) -> Optional[float]:
        """Poll broker positions to detect manual exit. Returns exit price or None."""
        timeout = int(
            self.strategy_cfg.get("broker", {}).get("api_timeouts", {}).get("positions_seconds", 10)
        )
        positions = get_positions(headers=self.headers, timeout=timeout)
        if positions is None:
            return None

        matched = [row for row in positions if row.get("instrument_token") == instrument_token]
        if not matched:
            return 0.0  # position not found = manually exited

        net_quantity = sum(int(row.get("quantity", 0)) for row in matched)
        if net_quantity == 0:
            return float(matched[0].get("last_price", 0.0))

        return None
