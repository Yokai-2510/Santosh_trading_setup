"""pre_checks — pre-entry gate conditions.

These are hard blockers evaluated BEFORE indicator-based entry signals.
Pure functions — no broker calls. Reusable by backtesting.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

from utils.market_hours import is_market_active
from utils.state import StateStore


def check_pre_conditions(
    store: StateStore,
    system_cfg: Dict[str, Any],
    strategy_cfg: Dict[str, Any],
    last_closed_epoch: float,
    has_active_position: bool,
    has_working_order: bool,
    has_exit_order: bool,
    candle_count: int,
) -> Tuple[bool, str]:
    """
    Evaluate all pre-entry gates. Returns (allowed, reason).

    Checks (in order):
      1. Market hours
      2. Trading not paused
      3. No active position / working order / exit order
      4. Re-entry cooldown
      5. Risk guard (daily loss + max trades)
      6. Sufficient candle data
    """
    # 1. Market hours
    ignore_hours = bool(system_cfg.get("runtime", {}).get("ignore_market_hours", False))
    if not is_market_active(system_cfg.get("market", {}), ignore=ignore_hours):
        return False, "Market closed"

    # 2. Trading paused
    state = store.read()
    if state.trading_paused:
        return False, "Trading paused"

    # 3. Already in a position or order
    if has_active_position or has_working_order or has_exit_order:
        return False, "Position or order already active"

    # 4. Re-entry cooldown
    reentry_wait = int(
        strategy_cfg.get("position_management", {}).get("reentry_wait_seconds_after_close", 30)
    )
    if last_closed_epoch and (time.time() - last_closed_epoch) < reentry_wait:
        return False, f"Re-entry cooldown ({reentry_wait}s)"

    # 5. Risk guard
    risk_cfg = system_cfg.get("risk", {})
    risk_ok, risk_reason = check_risk_limits(store, risk_cfg)
    if not risk_ok:
        return False, risk_reason

    # 6. Sufficient candle data
    min_candles = int(strategy_cfg.get("entry_conditions", {}).get("min_candles_required", 60))
    if candle_count < min_candles:
        return False, f"Insufficient candles: {candle_count} < {min_candles}"

    return True, "Pre-checks passed"


def check_risk_limits(
    store: StateStore,
    risk_cfg: Dict[str, Any],
) -> Tuple[bool, str]:
    """Check daily loss limit and max trades per session."""
    if not risk_cfg.get("enabled", False):
        return True, "Risk checks disabled"

    state = store.read()

    max_loss = float(risk_cfg.get("max_daily_loss", 5000.0))
    if state.session_realised_pnl <= -abs(max_loss):
        return False, f"Daily loss limit reached: {state.session_realised_pnl:.2f}"

    max_trades = int(risk_cfg.get("max_trades_per_session", 10))
    if state.session_trade_count >= max_trades:
        return False, f"Max trades per session reached: {state.session_trade_count}"

    return True, "Risk checks passed"
