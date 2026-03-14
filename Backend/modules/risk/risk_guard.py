"""
risk_guard — pre-entry risk checks.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from modules.state.runtime_state import StateStore


def is_entry_allowed(
    store: StateStore,
    risk_cfg: Dict[str, Any],
) -> Tuple[bool, str]:
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
