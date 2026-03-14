"""
Tests for exit_conditions — SL, target, trailing, time-based.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Backend"))

from modules.strategy.exit_conditions import evaluate_exit


def _base_exit_cfg(**overrides):
    cfg = {
        "stoploss": {"enabled": True, "type": "percent", "value": 30.0, "order_type": "SL-M"},
        "target": {"enabled": False, "type": "percent", "value": 50.0, "order_type": "LIMIT"},
        "trailing_sl": {"enabled": False, "activate_at_percent": 20.0, "trail_by_percent": 10.0},
        "time_based_exit": {"enabled": False, "exit_at_time": "15:15:00"},
    }
    cfg.update(overrides)
    return cfg


# --- Stop-Loss ---

def test_sl_percent_triggered():
    cfg = _base_exit_cfg()
    result = evaluate_exit(entry_price=100.0, current_ltp=65.0, peak_ltp=110.0, exit_cfg=cfg)
    assert result is not None
    assert result.trigger == "SL"


def test_sl_percent_not_triggered():
    cfg = _base_exit_cfg()
    result = evaluate_exit(entry_price=100.0, current_ltp=75.0, peak_ltp=110.0, exit_cfg=cfg)
    assert result is None


def test_sl_points_triggered():
    cfg = _base_exit_cfg(stoploss={"enabled": True, "type": "points", "value": 20.0, "order_type": "SL-M"})
    result = evaluate_exit(entry_price=100.0, current_ltp=79.0, peak_ltp=100.0, exit_cfg=cfg)
    assert result is not None
    assert result.trigger == "SL"


def test_sl_fixed_price_triggered():
    cfg = _base_exit_cfg(stoploss={"enabled": True, "type": "fixed_price", "value": 70.0, "order_type": "SL-M"})
    result = evaluate_exit(entry_price=100.0, current_ltp=68.0, peak_ltp=100.0, exit_cfg=cfg)
    assert result is not None
    assert result.trigger == "SL"


# --- Target ---

def test_target_percent_triggered():
    cfg = _base_exit_cfg(
        stoploss={"enabled": False},
        target={"enabled": True, "type": "percent", "value": 50.0, "order_type": "LIMIT"},
    )
    result = evaluate_exit(entry_price=100.0, current_ltp=152.0, peak_ltp=152.0, exit_cfg=cfg)
    assert result is not None
    assert result.trigger == "TARGET"


def test_target_not_triggered():
    cfg = _base_exit_cfg(
        stoploss={"enabled": False},
        target={"enabled": True, "type": "percent", "value": 50.0, "order_type": "LIMIT"},
    )
    result = evaluate_exit(entry_price=100.0, current_ltp=130.0, peak_ltp=130.0, exit_cfg=cfg)
    assert result is None


# --- Trailing SL ---

def test_trailing_sl_triggers_after_peak():
    cfg = _base_exit_cfg(
        stoploss={"enabled": False},
        trailing_sl={"enabled": True, "activate_at_percent": 20.0, "trail_by_percent": 10.0},
    )
    # Entry=100, peak=130 (activated at 120), trail=130*0.9=117, ltp=116 -> trigger
    result = evaluate_exit(entry_price=100.0, current_ltp=116.0, peak_ltp=130.0, exit_cfg=cfg)
    assert result is not None
    assert result.trigger == "TRAILING_SL"


def test_trailing_sl_not_activated_yet():
    cfg = _base_exit_cfg(
        stoploss={"enabled": False},
        trailing_sl={"enabled": True, "activate_at_percent": 20.0, "trail_by_percent": 10.0},
    )
    # Entry=100, peak=115 (not yet 120), so not activated
    result = evaluate_exit(entry_price=100.0, current_ltp=110.0, peak_ltp=115.0, exit_cfg=cfg)
    assert result is None


# --- Time-based exit ---

def test_time_exit_fires():
    cfg = _base_exit_cfg(
        stoploss={"enabled": False},
        time_based_exit={"enabled": True, "exit_at_time": "15:15:00"},
    )
    now = datetime(2025, 7, 1, 15, 16, 0)
    result = evaluate_exit(entry_price=100.0, current_ltp=105.0, peak_ltp=105.0, exit_cfg=cfg, now=now)
    assert result is not None
    assert result.trigger == "TIME"


def test_time_exit_before_time():
    cfg = _base_exit_cfg(
        stoploss={"enabled": False},
        time_based_exit={"enabled": True, "exit_at_time": "15:15:00"},
    )
    now = datetime(2025, 7, 1, 15, 14, 0)
    result = evaluate_exit(entry_price=100.0, current_ltp=105.0, peak_ltp=105.0, exit_cfg=cfg, now=now)
    assert result is None


def test_time_exit_highest_priority():
    """Time exit should fire even when SL is also triggered."""
    cfg = _base_exit_cfg(
        stoploss={"enabled": True, "type": "percent", "value": 30.0, "order_type": "SL-M"},
        time_based_exit={"enabled": True, "exit_at_time": "15:15:00"},
    )
    now = datetime(2025, 7, 1, 15, 20, 0)
    result = evaluate_exit(entry_price=100.0, current_ltp=60.0, peak_ltp=100.0, exit_cfg=cfg, now=now)
    assert result is not None
    assert result.trigger == "TIME"


# --- Edge cases ---

def test_no_exit_when_all_disabled():
    cfg = _base_exit_cfg(stoploss={"enabled": False})
    result = evaluate_exit(entry_price=100.0, current_ltp=50.0, peak_ltp=100.0, exit_cfg=cfg)
    assert result is None


def test_zero_entry_price_returns_none():
    cfg = _base_exit_cfg()
    result = evaluate_exit(entry_price=0.0, current_ltp=50.0, peak_ltp=100.0, exit_cfg=cfg)
    assert result is None
