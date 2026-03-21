"""exit_conditions — evaluate whether the active position should be exited.

Pure functions — no broker calls. Reusable by backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dt_time
from typing import Any, Dict, Optional


@dataclass
class ExitSignal:
    trigger: str       # SL | TARGET | TRAILING_SL | TIME
    reason: str
    exit_price: float
    order_type: str    # MARKET | SL-M | LIMIT


def evaluate_exit(
    entry_price: float,
    current_ltp: float,
    peak_ltp: float,
    exit_cfg: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Optional[ExitSignal]:
    """
    Evaluate exit conditions in priority order:
      1. Time-based exit
      2. Trailing SL
      3. Hard SL
      4. Target
    """
    if now is None:
        now = datetime.now()
    if entry_price <= 0 or current_ltp <= 0:
        return None

    signal = _check_time_exit(exit_cfg, now, current_ltp)
    if signal:
        return signal

    signal = _check_trailing_sl(exit_cfg, entry_price, current_ltp, peak_ltp)
    if signal:
        return signal

    signal = _check_stoploss(exit_cfg, entry_price, current_ltp)
    if signal:
        return signal

    signal = _check_target(exit_cfg, entry_price, current_ltp)
    if signal:
        return signal

    return None


# ---------------------------------------------------------------------------
# Individual exit checks
# ---------------------------------------------------------------------------

def _check_time_exit(
    exit_cfg: Dict[str, Any], now: datetime, current_ltp: float
) -> Optional[ExitSignal]:
    cfg = exit_cfg.get("time_based_exit", {})
    if not cfg.get("enabled", False):
        return None
    exit_time_str = cfg.get("exit_at_time", "15:15:00")
    parts = [int(x) for x in exit_time_str.split(":")]
    exit_time = dt_time(
        hour=parts[0],
        minute=parts[1] if len(parts) > 1 else 0,
        second=parts[2] if len(parts) > 2 else 0,
    )
    if now.time() >= exit_time:
        return ExitSignal(
            trigger="TIME",
            reason=f"Time exit at {exit_time_str}",
            exit_price=current_ltp,
            order_type="MARKET",
        )
    return None


def _check_trailing_sl(
    exit_cfg: Dict[str, Any],
    entry_price: float,
    current_ltp: float,
    peak_ltp: float,
) -> Optional[ExitSignal]:
    cfg = exit_cfg.get("trailing_sl", {})
    if not cfg.get("enabled", False):
        return None
    activate_pct = float(cfg.get("activate_at_percent", 20.0))
    trail_pct = float(cfg.get("trail_by_percent", 10.0))
    activate_price = entry_price * (1 + activate_pct / 100.0)
    if peak_ltp < activate_price:
        return None
    trail_price = peak_ltp * (1 - trail_pct / 100.0)
    if current_ltp <= trail_price:
        return ExitSignal(
            trigger="TRAILING_SL",
            reason=f"Trailing SL: peak={peak_ltp:.2f} trail={trail_price:.2f} ltp={current_ltp:.2f}",
            exit_price=current_ltp,
            order_type="MARKET",
        )
    return None


def _check_stoploss(
    exit_cfg: Dict[str, Any], entry_price: float, current_ltp: float
) -> Optional[ExitSignal]:
    cfg = exit_cfg.get("stoploss", {})
    if not cfg.get("enabled", False):
        return None
    sl_type = cfg.get("type", "percent")
    sl_value = float(cfg.get("value", 30.0))
    sl_order_type = cfg.get("order_type", "SL-M")

    if sl_type == "percent":
        sl_price = entry_price * (1 - sl_value / 100.0)
    elif sl_type == "points":
        sl_price = entry_price - sl_value
    else:
        sl_price = sl_value

    if current_ltp <= sl_price:
        return ExitSignal(
            trigger="SL",
            reason=f"SL hit: entry={entry_price:.2f} sl={sl_price:.2f} ltp={current_ltp:.2f}",
            exit_price=current_ltp,
            order_type=sl_order_type,
        )
    return None


def _check_target(
    exit_cfg: Dict[str, Any], entry_price: float, current_ltp: float
) -> Optional[ExitSignal]:
    cfg = exit_cfg.get("target", {})
    if not cfg.get("enabled", False):
        return None
    target_type = cfg.get("type", "percent")
    target_value = float(cfg.get("value", 50.0))
    target_order_type = cfg.get("order_type", "LIMIT")

    if target_type == "percent":
        target_price = entry_price * (1 + target_value / 100.0)
    else:
        target_price = entry_price + target_value

    if current_ltp >= target_price:
        return ExitSignal(
            trigger="TARGET",
            reason=f"Target hit: entry={entry_price:.2f} target={target_price:.2f} ltp={current_ltp:.2f}",
            exit_price=current_ltp,
            order_type=target_order_type,
        )
    return None
