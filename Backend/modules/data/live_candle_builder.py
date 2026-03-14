"""
live_candle_builder — accumulates real-time OHLCV ticks from the Upstox v3
WebSocket into rolling candle lists with actual volume data.

Design
------
* `on_feed(instrument_key, feed_data)` — wired directly as the WebSocket
  on_feed callback.  Thread-safe; may be called from any thread.
* Completed 1-minute candles are archived when the candle timestamp (`ts`)
  changes between successive ticks.
* `get_candles(instrument_key, timeframe_minutes)` — returns 1-minute candles
  aggregated into N-minute bars, suitable as a drop-in replacement for the
  historical REST candle list.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Interval names Upstox uses in the full-feed OHLC list for 1-minute bars.
# The SDK may use any of these; we match all of them.
_ONE_MIN_INTERVALS = {"1minute", "I1", "1min", "1m", "minute"}

_MAX_1M_CANDLES = 600   # ~10 hours of 1-min history


class LiveCandleBuilder:
    """
    Builds rolling OHLCV candle lists from WebSocket ticks.

    Thread-safe — `on_feed` is called from the WebSocket receive thread;
    `get_candles` is called from the engine/indicator thread.
    """

    def __init__(self, max_1m_candles: int = _MAX_1M_CANDLES) -> None:
        self._max = max_1m_candles
        # Archived completed 1-min candles: instrument → {ts_str: candle_dict}
        self._archive: Dict[str, Dict[str, dict]] = {}
        # Latest in-progress snapshot per instrument and interval name
        self._current: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    # ── WebSocket callback ────────────────────────────────────────────────────

    def on_feed(self, instrument_key: str, feed_data: Dict[str, Any]) -> None:
        """Called by UpstoxMarketFeedV3 on every decoded message."""
        ohlc_list: List[Dict[str, Any]] = feed_data.get("ohlc", [])
        if not ohlc_list:
            return

        with self._lock:
            if instrument_key not in self._current:
                self._current[instrument_key] = {}

            for ohlc in ohlc_list:
                interval = str(ohlc.get("interval", "")).lower()
                ts = str(ohlc.get("ts", ""))
                if not ts:
                    continue

                prev = self._current[instrument_key].get(interval)

                # Candle closed → archive it when the timestamp rolls over
                if prev and prev.get("ts") != ts and _is_one_minute(interval):
                    self._archive_1m(instrument_key, prev)

                # Always keep the latest snapshot
                self._current[instrument_key][interval] = ohlc

    # ── Query interface ───────────────────────────────────────────────────────

    def get_candles(
        self,
        instrument_key: str,
        timeframe_minutes: int,
    ) -> List[dict]:
        """
        Return completed N-minute candles (with real volume) for the given
        instrument.  Also appends the current in-progress candle so callers
        always see the freshest data.
        """
        candles_1m = self._get_1m_with_current(instrument_key)
        if not candles_1m:
            return []
        if timeframe_minutes == 1:
            return candles_1m
        return _aggregate(candles_1m, timeframe_minutes)

    def count_candles(self, instrument_key: str, timeframe_minutes: int) -> int:
        return len(self.get_candles(instrument_key, timeframe_minutes))

    def has_enough(
        self,
        instrument_key: str,
        timeframe_minutes: int,
        min_count: int,
    ) -> bool:
        return self.count_candles(instrument_key, timeframe_minutes) >= min_count

    def get_current_volume(self, instrument_key: str) -> Optional[float]:
        """Return the current candle volume (any interval that has data)."""
        with self._lock:
            per_interval = self._current.get(instrument_key, {})
        for ohlc in per_interval.values():
            vol = ohlc.get("volume")
            if vol is not None and float(vol) > 0:
                return float(vol)
        return None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _archive_1m(self, instrument_key: str, ohlc: Dict[str, Any]) -> None:
        ts = str(ohlc.get("ts", ""))
        if not ts:
            return
        if instrument_key not in self._archive:
            self._archive[instrument_key] = {}
        self._archive[instrument_key][ts] = _ohlc_to_candle(ohlc)

        # Trim oldest candles to keep memory bounded
        store = self._archive[instrument_key]
        if len(store) > self._max:
            keys_sorted = sorted(store.keys())
            for old_key in keys_sorted[: len(store) - self._max]:
                del store[old_key]

    def _get_1m_with_current(self, instrument_key: str) -> List[dict]:
        with self._lock:
            archived = dict(self._archive.get(instrument_key, {}))
            per_interval = dict(self._current.get(instrument_key, {}))

        candles = sorted(archived.values(), key=lambda c: c["timestamp"])

        # Find and append the in-progress 1-min candle
        current_1m = _find_one_min_ohlc(per_interval)
        if current_1m:
            current_candle = _ohlc_to_candle(current_1m)
            if candles and candles[-1]["timestamp"] == current_candle["timestamp"]:
                candles[-1] = current_candle   # update in place
            else:
                candles.append(current_candle)

        return candles


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_one_minute(interval: str) -> bool:
    return interval in _ONE_MIN_INTERVALS


def _find_one_min_ohlc(per_interval: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for interval_name, ohlc in per_interval.items():
        if _is_one_minute(interval_name.lower()):
            return ohlc
    return None


def _ohlc_to_candle(ohlc: Dict[str, Any]) -> dict:
    return {
        "timestamp":      str(ohlc.get("ts", "")),
        "open":           float(ohlc.get("open", 0)),
        "high":           float(ohlc.get("high", 0)),
        "low":            float(ohlc.get("low", 0)),
        "close":          float(ohlc.get("close", 0)),
        "volume":         float(ohlc.get("volume", 0)),
        "open_interest":  0.0,
    }


def _aggregate(candles_1m: List[dict], timeframe_minutes: int) -> List[dict]:
    """Aggregate a list of 1-minute candles into N-minute bars."""
    result: List[dict] = []
    current_bar: Optional[dict] = None
    current_bar_epoch: Optional[int] = None
    n_secs = timeframe_minutes * 60

    for c in candles_1m:
        ts_str = c.get("timestamp", "")
        try:
            ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            continue

        epoch = int(ts_dt.timestamp())
        bar_epoch = (epoch // n_secs) * n_secs

        if bar_epoch != current_bar_epoch:
            if current_bar is not None:
                result.append(current_bar)
            current_bar_epoch = bar_epoch
            bar_ts = datetime.fromtimestamp(bar_epoch, tz=timezone.utc).isoformat()
            current_bar = {
                "timestamp":     bar_ts,
                "open":          c["open"],
                "high":          c["high"],
                "low":           c["low"],
                "close":         c["close"],
                "volume":        c["volume"],
                "open_interest": 0.0,
            }
        else:
            assert current_bar is not None
            current_bar["high"] = max(current_bar["high"], c["high"])
            current_bar["low"]  = min(current_bar["low"],  c["low"])
            current_bar["close"]  = c["close"]
            current_bar["volume"] += c["volume"]

    if current_bar is not None:
        result.append(current_bar)

    return result
