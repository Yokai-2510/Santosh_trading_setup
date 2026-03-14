"""
runtime_state — thread-safe shared state (SSOT) for the trading system.

Written by the bot engine thread. Read by the GUI thread.
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PositionSnapshot:
    instrument_token: str = ""
    trading_symbol: str = ""
    quantity: int = 0
    entry_price: float = 0.0
    current_ltp: float = 0.0
    unrealised_pnl: float = 0.0
    entry_time_epoch: float = 0.0
    peak_ltp: float = 0.0
    status: str = "ACTIVE"


@dataclass
class WorkingOrderSnapshot:
    order_id: str = ""
    instrument_token: str = ""
    trading_symbol: str = ""
    price: float = 0.0
    quantity: int = 0
    status: str = "OPEN"


@dataclass
class SignalSnapshot:
    ok: bool = False
    checks: Dict[str, bool] = field(default_factory=dict)
    values: Dict[str, float] = field(default_factory=dict)
    # Display: {"rsi": "> 60.0", "volume_vs_ema": "Vol > EMA", "adx": "> 20.0"}
    thresholds: Dict[str, str] = field(default_factory=dict)
    evaluated_at_epoch: float = 0.0


@dataclass
class TradeRecord:
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    entry_price: float = 0.0
    exit_price: float = 0.0
    pnl: float = 0.0
    exit_reason: str = ""
    entry_time: str = ""
    exit_time: str = ""


@dataclass
class RuntimeState:
    # Bot lifecycle
    bot_running: bool = False
    trading_paused: bool = False
    last_cycle_epoch: float = 0.0
    cycle_count: int = 0
    error_message: str = ""

    # Auth
    auth_ok: bool = False
    auth_message: str = ""

    # Market
    market_active: bool = False

    # Strategy state
    active_position: Optional[PositionSnapshot] = None
    working_order: Optional[WorkingOrderSnapshot] = None
    last_signal: Optional[SignalSnapshot] = None

    # Session stats
    session_realised_pnl: float = 0.0
    session_trade_count: int = 0
    last_closed_epoch: float = 0.0

    # Trade history (session only, not persisted)
    trade_history: List[TradeRecord] = field(default_factory=list)


class StateStore:
    """Thread-safe wrapper around RuntimeState."""

    def __init__(self) -> None:
        self._state = RuntimeState()
        self._lock = threading.Lock()

    def read(self) -> RuntimeState:
        with self._lock:
            return copy.deepcopy(self._state)

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)

    def add_trade(self, record: TradeRecord) -> None:
        with self._lock:
            self._state.trade_history.append(record)
            self._state.session_trade_count += 1
            self._state.session_realised_pnl += record.pnl
