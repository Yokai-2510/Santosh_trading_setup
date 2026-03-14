"""
market_hours — market session helpers.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Any, Dict


def is_market_active(market_cfg: Dict[str, Any], ignore: bool = False) -> bool:
    if ignore:
        return True
    open_str = market_cfg.get("open", "09:15:00")
    close_str = market_cfg.get("close", "15:30:00")
    now = datetime.now().time()
    return _parse_time(open_str) <= now <= _parse_time(close_str)


def _parse_time(time_str: str) -> dt_time:
    parts = [int(x) for x in time_str.split(":")]
    return dt_time(
        hour=parts[0],
        minute=parts[1] if len(parts) > 1 else 0,
        second=parts[2] if len(parts) > 2 else 0,
    )
