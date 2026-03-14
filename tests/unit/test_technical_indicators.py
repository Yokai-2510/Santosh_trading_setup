"""
Tests for technical indicator calculations and entry gate.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Backend"))

from modules.indicators.technical_indicators import evaluate_entry_indicators
from tests.fixtures.sample_candles import make_rising_candles, make_flat_candles, make_dropping_candles


def _entry_cfg(**overrides):
    cfg = {
        "min_candles_required": 60,
        "rsi": {"enabled": True, "period": 14, "operator": ">", "threshold": 60.0},
        "volume_vs_ema": {"enabled": True, "ema_period": 20},
        "macd": {"enabled": False},
        "adx": {"enabled": False},
    }
    cfg.update(overrides)
    return cfg


def test_rising_candles_pass_rsi():
    candles = make_rising_candles(80)
    result = evaluate_entry_indicators(candles, _entry_cfg())
    assert result["checks"].get("rsi") is True
    assert result["values"]["rsi"] > 60.0


def test_flat_candles_fail_rsi():
    candles = make_flat_candles(80)
    result = evaluate_entry_indicators(candles, _entry_cfg())
    assert result["checks"].get("rsi") is False


def test_dropping_candles_fail_rsi_above():
    candles = make_dropping_candles(80)
    result = evaluate_entry_indicators(candles, _entry_cfg())
    assert result["checks"].get("rsi") is False


def test_volume_check_with_rising_candles():
    candles = make_rising_candles(80)
    result = evaluate_entry_indicators(candles, _entry_cfg())
    assert "volume_vs_ema" in result["checks"]


def test_empty_candles_safe():
    result = evaluate_entry_indicators([], _entry_cfg())
    assert result["ok"] is False
    assert "No candles" in result["reason"]


def test_insufficient_candles():
    candles = make_rising_candles(10)
    result = evaluate_entry_indicators(candles, _entry_cfg())
    assert result["ok"] is False
    assert "Insufficient" in result["reason"]


def test_all_disabled_returns_false():
    cfg = _entry_cfg()
    cfg["rsi"]["enabled"] = False
    cfg["volume_vs_ema"]["enabled"] = False
    candles = make_rising_candles(80)
    result = evaluate_entry_indicators(candles, cfg)
    assert result["ok"] is False


def test_macd_removed_not_in_checks():
    """MACD was removed from indicator evaluation — should not appear in checks."""
    cfg = _entry_cfg()
    cfg["macd"] = {"enabled": True, "fast_period": 12, "slow_period": 26, "signal_period": 9, "min_histogram": 0.0}
    candles = make_rising_candles(80)
    result = evaluate_entry_indicators(candles, cfg)
    assert "macd" not in result["checks"]


def test_adx_enabled_adds_check():
    cfg = _entry_cfg()
    cfg["adx"] = {"enabled": True, "period": 14, "threshold": 20.0}
    candles = make_rising_candles(80)
    result = evaluate_entry_indicators(candles, cfg)
    assert "adx" in result["checks"]
