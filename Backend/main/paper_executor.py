"""paper_executor — simulated order execution for paper trading mode.

All orders fill instantly at the requested price. No broker calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from orders.order_builder import OrderParams


@dataclass
class OrderResult:
    """Outcome of an order operation."""
    success: bool
    order_id: str
    fill_price: float
    fill_quantity: int
    message: str
    status: str         # FILLED, REJECTED, CANCELLED, OPEN, PENDING


class PaperExecutor:
    """Simulated executor — all orders fill instantly."""

    def __init__(self, strategy_cfg: Dict[str, Any], logger) -> None:
        self.strategy_cfg = strategy_cfg
        self.logger = logger
        self._order_counter = 0

    def place_entry_order(self, order_params: OrderParams) -> OrderResult:
        """Instant fill at the given price."""
        self._order_counter += 1
        order_id = f"PAPER_ENTRY_{self._order_counter}"
        fill_price = float(order_params.price if order_params.price is not None else 0.0)

        self.logger.info(
            "Paper entry filled: %s @ %.2f qty=%d",
            order_params.trading_symbol, fill_price, order_params.quantity,
        )
        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=fill_price,
            fill_quantity=order_params.quantity,
            message="Paper entry filled",
            status="FILLED",
        )

    def place_exit_order(
        self,
        instrument_token: str,
        quantity: int,
        exit_price: float,
        exit_order_type: str,
    ) -> OrderResult:
        """Instant fill at exit price."""
        self._order_counter += 1
        order_id = f"PAPER_EXIT_{self._order_counter}"

        self.logger.info(
            "Paper exit filled: %s @ %.2f qty=%d",
            instrument_token, exit_price, quantity,
        )
        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=exit_price,
            fill_quantity=quantity,
            message="Paper exit filled",
            status="FILLED",
        )

    def poll_order(self, order_id: str) -> OrderResult:
        """Paper orders are always already filled."""
        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=0.0,
            fill_quantity=0,
            message="Paper order always filled",
            status="FILLED",
        )

    def cancel_order(self, order_id: str) -> OrderResult:
        """Always succeeds."""
        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=0.0,
            fill_quantity=0,
            message="Paper order cancelled",
            status="CANCELLED",
        )

    def modify_order(
        self, order_id: str, new_price: float, quantity: int
    ) -> OrderResult:
        """Always succeeds — just logs."""
        self.logger.info("Paper order %s price modified to %.2f", order_id, new_price)
        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=new_price,
            fill_quantity=quantity,
            message=f"Paper order price → {new_price:.2f}",
            status="OPEN",
        )

    def detect_manual_exit(self, instrument_token: str) -> Optional[float]:
        """No manual exit detection in paper mode."""
        return None
