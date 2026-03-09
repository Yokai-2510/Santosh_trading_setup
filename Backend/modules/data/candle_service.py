"""
candle_service — maintains rolling candle cache from Upstox Historical V3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List

from brokers.upstox.historical_v3 import fetch_historical_candles_v3


@dataclass
class CandleCacheItem:
    candles: List[dict] = field(default_factory=list)
    last_refresh: float = 0.0


class CandleService:
    def __init__(self, headers: Dict[str, str], timeout_seconds: int = 20) -> None:
        self.headers = headers
        self.timeout_seconds = timeout_seconds
        self._cache: Dict[str, CandleCacheItem] = {}

    def bootstrap_one_month(self, instrument_key: str, timeframe_minutes: int) -> List[dict]:
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=31)
        result = fetch_historical_candles_v3(
            headers=self.headers,
            instrument_key=instrument_key,
            unit="minutes",
            interval=int(timeframe_minutes),
            to_date=to_date.strftime("%Y-%m-%d"),
            from_date=from_date.strftime("%Y-%m-%d"),
            timeout=self.timeout_seconds,
        )
        candles = result.get("candles", []) if result.get("success") else []
        key = self._cache_key(instrument_key, timeframe_minutes)
        self._cache[key] = CandleCacheItem(candles=candles, last_refresh=datetime.now().timestamp())
        return candles

    def refresh_recent(self, instrument_key: str, timeframe_minutes: int) -> List[dict]:
        key = self._cache_key(instrument_key, timeframe_minutes)
        if key not in self._cache:
            return self.bootstrap_one_month(instrument_key, timeframe_minutes)

        cached = self._cache[key]
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=2)
        result = fetch_historical_candles_v3(
            headers=self.headers,
            instrument_key=instrument_key,
            unit="minutes",
            interval=int(timeframe_minutes),
            to_date=to_date.strftime("%Y-%m-%d"),
            from_date=from_date.strftime("%Y-%m-%d"),
            timeout=self.timeout_seconds,
        )
        if result.get("success"):
            cached.candles = self._merge_candles(cached.candles, result.get("candles", []))
            cached.last_refresh = datetime.now().timestamp()
        return cached.candles

    def get_candles(self, instrument_key: str, timeframe_minutes: int) -> List[dict]:
        key = self._cache_key(instrument_key, timeframe_minutes)
        if key not in self._cache:
            return self.bootstrap_one_month(instrument_key, timeframe_minutes)
        return self.refresh_recent(instrument_key, timeframe_minutes)

    @staticmethod
    def _cache_key(instrument_key: str, timeframe_minutes: int) -> str:
        return f"{instrument_key}|{timeframe_minutes}"

    @staticmethod
    def _merge_candles(existing: List[dict], incoming: List[dict]) -> List[dict]:
        mapping = {row["timestamp"]: row for row in existing if "timestamp" in row}
        for row in incoming:
            ts = row.get("timestamp")
            if ts:
                mapping[ts] = row
        merged = list(mapping.values())
        merged.sort(key=lambda x: x.get("timestamp", ""))
        return merged
