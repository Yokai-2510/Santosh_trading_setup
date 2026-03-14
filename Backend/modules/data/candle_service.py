"""
candle_service — maintains rolling candle cache from Upstox Historical V3.

When a LiveCandleBuilder is attached (via set_live_builder), live WebSocket
candles are merged on top of the historical REST data so that volume fields
contain real values for NSE_INDEX instruments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from brokers.upstox.historical_v3 import fetch_historical_candles_v3

if TYPE_CHECKING:
    from modules.data.live_candle_builder import LiveCandleBuilder


@dataclass
class CandleCacheItem:
    candles: List[dict] = field(default_factory=list)
    last_refresh: float = 0.0


class CandleService:
    def __init__(self, headers: Dict[str, str], timeout_seconds: int = 20) -> None:
        self.headers = headers
        self.timeout_seconds = timeout_seconds
        self._cache: Dict[str, CandleCacheItem] = {}
        self._live_builder: Optional["LiveCandleBuilder"] = None

    def set_live_builder(self, builder: "LiveCandleBuilder") -> None:
        """Attach a LiveCandleBuilder so live WebSocket volume overlays REST data."""
        self._live_builder = builder

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
        """
        Return candles for the given instrument and timeframe.

        Live WebSocket candles (with real volume) are merged on top of the
        historical REST baseline whenever the LiveCandleBuilder has data.
        """
        key = self._cache_key(instrument_key, timeframe_minutes)
        if key not in self._cache:
            historical = self.bootstrap_one_month(instrument_key, timeframe_minutes)
        else:
            historical = self.refresh_recent(instrument_key, timeframe_minutes)

        if self._live_builder:
            live = self._live_builder.get_candles(instrument_key, timeframe_minutes)
            if live:
                historical = self._merge_candles(historical, live)

        return historical

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
