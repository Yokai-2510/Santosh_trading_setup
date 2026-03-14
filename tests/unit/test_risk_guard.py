"""
Tests for risk_guard — daily loss and trade count limits.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Backend"))

from modules.risk.risk_guard import is_entry_allowed
from modules.state.runtime_state import StateStore


def test_entry_allowed_when_risk_disabled():
    store = StateStore()
    allowed, _ = is_entry_allowed(store, {"enabled": False})
    assert allowed is True


def test_entry_blocked_daily_loss():
    store = StateStore()
    store.update(session_realised_pnl=-6000.0)
    allowed, reason = is_entry_allowed(store, {"enabled": True, "max_daily_loss": 5000.0, "max_trades_per_session": 10})
    assert allowed is False
    assert "loss" in reason.lower()


def test_entry_blocked_max_trades():
    store = StateStore()
    store.update(session_trade_count=10)
    allowed, reason = is_entry_allowed(store, {"enabled": True, "max_daily_loss": 5000.0, "max_trades_per_session": 10})
    assert allowed is False
    assert "trades" in reason.lower()


def test_entry_allowed_within_limits():
    store = StateStore()
    store.update(session_realised_pnl=-1000.0, session_trade_count=3)
    allowed, _ = is_entry_allowed(store, {"enabled": True, "max_daily_loss": 5000.0, "max_trades_per_session": 10})
    assert allowed is True
