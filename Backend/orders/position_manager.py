"""position_manager — comprehensive SSOT for position lifecycle.

Tracks the full lifecycle: IDLE → PENDING_ENTRY → ACTIVE → PENDING_EXIT → CLOSED → (cleanup) → IDLE

Each state transition is an explicit method call. The position data is organized
into sections (instrument, entry, tracking, exit) for clarity.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PositionStatus(str, Enum):
    IDLE = "IDLE"
    PENDING_ENTRY = "PENDING_ENTRY"
    ACTIVE = "ACTIVE"
    PENDING_EXIT = "PENDING_EXIT"
    CLOSED = "CLOSED"


@dataclass
class PositionData:
    """Complete SSOT schema for a single trading position.

    Organized into logical sections:
      - Status: current lifecycle state
      - Instrument: what is being traded
      - Entry: how the position was entered
      - Tracking: live P&L and peak tracking
      - Exit: how the position was closed
      - Orders: working order and exit order details
    """
    # -- Status --
    status: PositionStatus = PositionStatus.IDLE

    # -- Instrument --
    instrument_token: str = ""
    trading_symbol: str = ""
    underlying: str = ""
    expiry: str = ""
    option_type: str = ""
    strike: float = 0.0
    lot_size: int = 0
    tick_size: float = 0.05

    # -- Entry --
    entry_order_id: str = ""
    entry_price: float = 0.0
    entry_quantity: int = 0
    entry_time_epoch: float = 0.0

    # -- Live Tracking --
    current_ltp: float = 0.0
    peak_ltp: float = 0.0
    unrealised_pnl: float = 0.0

    # -- Exit --
    exit_order_id: str = ""
    exit_price: float = 0.0
    exit_time_epoch: float = 0.0
    exit_reason: str = ""
    realised_pnl: float = 0.0

    # -- Working Order (entry) --
    working_order_id: str = ""
    working_order_price: float = 0.0
    working_order_status: str = ""
    working_order_created_epoch: float = 0.0
    working_order_modified_epoch: float = 0.0


@dataclass
class ClosedTrade:
    """Snapshot of a completed trade for history recording."""
    instrument_token: str = ""
    trading_symbol: str = ""
    underlying: str = ""
    option_type: str = ""
    strike: float = 0.0
    entry_order_id: str = ""
    entry_price: float = 0.0
    entry_quantity: int = 0
    entry_time_epoch: float = 0.0
    exit_order_id: str = ""
    exit_price: float = 0.0
    exit_time_epoch: float = 0.0
    exit_reason: str = ""
    realised_pnl: float = 0.0
    peak_ltp: float = 0.0


class PositionManager:
    """
    Manages the complete lifecycle of a single trading position.

    State transitions:
        IDLE → PENDING_ENTRY   (on_entry_placed)
        PENDING_ENTRY → ACTIVE (on_entry_filled)
        PENDING_ENTRY → IDLE   (on_entry_cancelled / on_entry_rejected)
        ACTIVE → PENDING_EXIT  (on_exit_placed)
        ACTIVE → CLOSED        (on_manual_exit / on_paper_exit)
        PENDING_EXIT → CLOSED  (on_exit_filled)
        PENDING_EXIT → ACTIVE  (on_exit_rejected — falls back to active)
        CLOSED → IDLE          (cleanup)
    """

    def __init__(self, logger) -> None:
        self.position = PositionData()
        self.last_closed_epoch: float = 0.0
        self.trade_history: List[ClosedTrade] = []
        self.logger = logger

    # -- Status queries --

    def is_idle(self) -> bool:
        return self.position.status == PositionStatus.IDLE

    def is_pending_entry(self) -> bool:
        return self.position.status == PositionStatus.PENDING_ENTRY

    def is_active(self) -> bool:
        return self.position.status == PositionStatus.ACTIVE

    def is_pending_exit(self) -> bool:
        return self.position.status == PositionStatus.PENDING_EXIT

    def is_closed(self) -> bool:
        return self.position.status == PositionStatus.CLOSED

    # -- Entry transitions --

    def on_entry_placed(
        self,
        order_id: str,
        instrument_token: str,
        trading_symbol: str,
        quantity: int,
        price: float,
        underlying: str = "",
        expiry: str = "",
        option_type: str = "",
        strike: float = 0.0,
        lot_size: int = 0,
        tick_size: float = 0.05,
    ) -> None:
        """Transition IDLE → PENDING_ENTRY."""
        self.position = PositionData(
            status=PositionStatus.PENDING_ENTRY,
            instrument_token=instrument_token,
            trading_symbol=trading_symbol,
            underlying=underlying,
            expiry=expiry,
            option_type=option_type,
            strike=strike,
            lot_size=lot_size,
            tick_size=tick_size,
            entry_quantity=quantity,
            working_order_id=order_id,
            working_order_price=price,
            working_order_status="OPEN",
            working_order_created_epoch=time.time(),
        )
        self.logger.info(
            "Entry order placed: %s %s @ %.2f qty=%d",
            order_id, trading_symbol, price, quantity,
        )

    def on_entry_filled(self, fill_price: float, fill_quantity: int, order_id: str = "") -> None:
        """Transition PENDING_ENTRY → ACTIVE (or direct fill in paper mode)."""
        self.position.status = PositionStatus.ACTIVE
        self.position.entry_order_id = order_id or self.position.working_order_id
        self.position.entry_price = fill_price
        self.position.entry_quantity = fill_quantity
        self.position.entry_time_epoch = time.time()
        self.position.peak_ltp = fill_price
        self.position.current_ltp = fill_price
        self.position.unrealised_pnl = 0.0
        # Clear working order fields
        self.position.working_order_id = ""
        self.position.working_order_price = 0.0
        self.position.working_order_status = ""
        self.logger.info(
            "Entry filled: %s @ %.2f qty=%d",
            self.position.trading_symbol, fill_price, fill_quantity,
        )

    def on_entry_cancelled(self) -> None:
        """Transition PENDING_ENTRY → IDLE."""
        symbol = self.position.trading_symbol
        self.position = PositionData()
        self.logger.info("Entry cancelled: %s", symbol)

    def on_entry_rejected(self, reason: str = "") -> None:
        """Transition PENDING_ENTRY → IDLE."""
        symbol = self.position.trading_symbol
        self.position = PositionData()
        self.logger.warning("Entry rejected: %s reason=%s", symbol, reason)

    def on_entry_modified(self, new_price: float) -> None:
        """Update working order price (PENDING_ENTRY stays)."""
        old_price = self.position.working_order_price
        self.position.working_order_price = new_price
        self.position.working_order_modified_epoch = time.time()
        self.logger.info(
            "Entry modified: %s %.2f → %.2f",
            self.position.trading_symbol, old_price, new_price,
        )

    # -- Exit transitions --

    def on_exit_placed(self, order_id: str, reason: str) -> None:
        """Transition ACTIVE → PENDING_EXIT."""
        self.position.status = PositionStatus.PENDING_EXIT
        self.position.exit_order_id = order_id
        self.position.exit_reason = reason
        self.logger.info(
            "Exit order placed: %s reason=%s",
            self.position.trading_symbol, reason,
        )

    def on_exit_filled(self, exit_price: float) -> None:
        """Transition PENDING_EXIT → CLOSED."""
        self.position.status = PositionStatus.CLOSED
        self.position.exit_price = exit_price
        self.position.exit_time_epoch = time.time()
        self.position.realised_pnl = (
            (exit_price - self.position.entry_price) * self.position.entry_quantity
        )
        self.logger.info(
            "Exit filled: %s @ %.2f pnl=%.2f",
            self.position.trading_symbol, exit_price, self.position.realised_pnl,
        )

    def on_exit_rejected(self, reason: str = "") -> None:
        """Transition PENDING_EXIT → ACTIVE (fallback)."""
        self.position.status = PositionStatus.ACTIVE
        self.position.exit_order_id = ""
        self.position.exit_reason = ""
        self.logger.warning(
            "Exit rejected: %s reason=%s — falling back to ACTIVE",
            self.position.trading_symbol, reason,
        )

    def on_manual_exit(self, exit_price: float = 0.0, reason: str = "MANUAL") -> None:
        """Transition ACTIVE → CLOSED (manual/paper exit)."""
        self.position.status = PositionStatus.CLOSED
        self.position.exit_price = exit_price
        self.position.exit_time_epoch = time.time()
        self.position.exit_reason = reason
        if exit_price > 0 and self.position.entry_price > 0:
            self.position.realised_pnl = (
                (exit_price - self.position.entry_price) * self.position.entry_quantity
            )
        self.logger.info(
            "Manual exit: %s @ %.2f reason=%s",
            self.position.trading_symbol, exit_price, reason,
        )

    # -- Live tracking --

    def update_ltp(self, ltp: float) -> None:
        """Update current LTP and peak tracking for active positions."""
        if self.position.status == PositionStatus.ACTIVE and ltp > 0:
            self.position.current_ltp = ltp
            self.position.peak_ltp = max(self.position.peak_ltp, ltp)
            self.position.unrealised_pnl = (
                (ltp - self.position.entry_price) * self.position.entry_quantity
            )

    # -- Cleanup --

    def cleanup(self) -> Optional[ClosedTrade]:
        """
        Transition CLOSED → IDLE.

        Returns the closed trade data for recording, then resets position to IDLE.
        """
        if self.position.status != PositionStatus.CLOSED:
            return None

        trade = ClosedTrade(
            instrument_token=self.position.instrument_token,
            trading_symbol=self.position.trading_symbol,
            underlying=self.position.underlying,
            option_type=self.position.option_type,
            strike=self.position.strike,
            entry_order_id=self.position.entry_order_id,
            entry_price=self.position.entry_price,
            entry_quantity=self.position.entry_quantity,
            entry_time_epoch=self.position.entry_time_epoch,
            exit_order_id=self.position.exit_order_id,
            exit_price=self.position.exit_price,
            exit_time_epoch=self.position.exit_time_epoch,
            exit_reason=self.position.exit_reason,
            realised_pnl=self.position.realised_pnl,
            peak_ltp=self.position.peak_ltp,
        )

        self.trade_history.append(trade)
        self.last_closed_epoch = time.time()
        self.position = PositionData()

        self.logger.info(
            "Position cleaned up: %s pnl=%.2f reason=%s",
            trade.trading_symbol, trade.realised_pnl, trade.exit_reason,
        )
        return trade

    # -- Snapshot for state sync --

    def get_snapshot(self) -> PositionData:
        """Return a deep copy of current position data."""
        return copy.deepcopy(self.position)

    def get_working_order_dict(self) -> Optional[Dict[str, Any]]:
        """Return working order info as dict (for state sync), or None if no working order."""
        if not self.position.working_order_id:
            return None
        return {
            "order_id": self.position.working_order_id,
            "instrument_token": self.position.instrument_token,
            "trading_symbol": self.position.trading_symbol,
            "price": self.position.working_order_price,
            "quantity": self.position.entry_quantity,
            "status": self.position.working_order_status,
        }

    def get_active_position_dict(self) -> Optional[Dict[str, Any]]:
        """Return active position info as dict (for state sync), or None."""
        if self.position.status not in (PositionStatus.ACTIVE, PositionStatus.PENDING_EXIT):
            return None
        return {
            "instrument_token": self.position.instrument_token,
            "trading_symbol": self.position.trading_symbol,
            "quantity": self.position.entry_quantity,
            "entry_price": self.position.entry_price,
            "entry_time_epoch": self.position.entry_time_epoch,
            "current_ltp": self.position.current_ltp,
            "peak_ltp": self.position.peak_ltp,
            "unrealised_pnl": self.position.unrealised_pnl,
            "status": self.position.status.value,
        }
