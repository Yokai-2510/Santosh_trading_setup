"""
position_sync — manual exit detection by polling broker positions.
"""

from __future__ import annotations

from typing import Optional

from brokers.upstox.positions import get_positions
from modules.strategy.order_lifecycle import LifecycleResult, OrderLifecycleManager


def detect_manual_exit(
    headers: dict,
    manager: OrderLifecycleManager,
    timeout_seconds: int = 10,
) -> Optional[LifecycleResult]:
    if manager.runtime_mode != "live":
        return None
    if not manager.has_active_position():
        return None

    active = manager.active_position or {}
    instrument_token = active.get("instrument_token")
    if not instrument_token:
        return None

    positions = get_positions(headers=headers, timeout=timeout_seconds)
    if positions is None:
        return None

    matched = [row for row in positions if row.get("instrument_token") == instrument_token]
    if not matched:
        # No position entry found for our token -> treat as externally closed.
        return manager.mark_manual_exit(exit_price=0.0, reason="MANUAL_DETECTED_NOT_FOUND")

    net_quantity = sum(int(row.get("quantity", 0)) for row in matched)
    if net_quantity == 0:
        last_price = float(matched[0].get("last_price", 0.0))
        return manager.mark_manual_exit(exit_price=last_price, reason="MANUAL_DETECTED_QTY_ZERO")
    return None
