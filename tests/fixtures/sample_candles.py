"""
Sample candle data for tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List


def make_rising_candles(n: int = 80, base_price: float = 22000.0) -> List[dict]:
    """Rising price series with high volume — RSI will exceed 60."""
    candles = []
    price = base_price
    t = datetime(2025, 6, 1, 9, 15, 0)
    for i in range(n):
        # Strong upward bias: ~80% candles rise, ~20% small dips
        if i % 5 == 4:
            price -= 2.0
        else:
            price += 10.0 + (i % 4)
        candles.append({
            "timestamp": t.isoformat(),
            "open": price - 3,
            "high": price + 5,
            "low": price - 5,
            "close": price,
            "volume": 80000 + i * 500,
            "open_interest": 0,
        })
        t += timedelta(minutes=3)
    return candles


def make_flat_candles(n: int = 80, price: float = 22000.0) -> List[dict]:
    """Flat price — RSI near 50, volume low."""
    candles = []
    t = datetime(2025, 6, 1, 9, 15, 0)
    for i in range(n):
        delta = 1 if i % 2 == 0 else -1
        candles.append({
            "timestamp": t.isoformat(),
            "open": price,
            "high": price + 2,
            "low": price - 2,
            "close": price + delta,
            "volume": 1000,
            "open_interest": 0,
        })
        t += timedelta(minutes=3)
    return candles


def make_dropping_candles(n: int = 80, base_price: float = 22000.0) -> List[dict]:
    """Falling price — RSI below 40."""
    candles = []
    price = base_price
    t = datetime(2025, 6, 1, 9, 15, 0)
    for i in range(n):
        price -= 5.0 + (i % 3)
        candles.append({
            "timestamp": t.isoformat(),
            "open": price + 2,
            "high": price + 4,
            "low": price - 3,
            "close": price,
            "volume": 50000 + i * 200,
            "open_interest": 0,
        })
        t += timedelta(minutes=3)
    return candles
