"""data_loader — load historical data for backtesting.

Supports:
  - Upstox historical candle API (via broker module)
  - CSV files (local)
  - yfinance (optional, for volume data)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from data.indicators import build_dataframe


def load_from_csv(file_path: Path, date_col: str = "timestamp") -> List[dict]:
    """
    Load OHLCV candles from a CSV file.

    Expected columns: timestamp, open, high, low, close, volume
    Optional: open_interest
    """
    df = pd.read_csv(file_path)
    if date_col in df.columns:
        df = df.sort_values(date_col).reset_index(drop=True)

    candles = []
    for _, row in df.iterrows():
        candles.append({
            "timestamp": str(row.get(date_col, "")),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": float(row.get("volume", 0)),
            "open_interest": float(row.get("open_interest", 0)),
        })
    return candles


def load_from_upstox(
    headers: Dict[str, str],
    instrument_key: str,
    from_date: str,
    to_date: str,
    timeframe_minutes: int = 3,
    timeout: int = 20,
) -> List[dict]:
    """Load historical candles from Upstox API."""
    from brokers.upstox.historical_v3 import fetch_historical_candles_v3

    result = fetch_historical_candles_v3(
        headers=headers,
        instrument_key=instrument_key,
        unit="minutes",
        interval=timeframe_minutes,
        to_date=to_date,
        from_date=from_date,
        timeout=timeout,
    )
    if result.get("success"):
        return result.get("candles", [])
    return []


def load_from_yfinance(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "5m",
) -> List[dict]:
    """
    Load historical candles from yfinance.

    Args:
        symbol: yfinance symbol (e.g., "^NSEI" for Nifty 50)
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
        interval: "1m", "2m", "5m", "15m", "30m", "1h", "1d"
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance is required for this data source. Install with: pip install yfinance")

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date, interval=interval)

    if df.empty:
        return []

    candles = []
    for ts, row in df.iterrows():
        candles.append({
            "timestamp": str(ts),
            "open": float(row.get("Open", 0)),
            "high": float(row.get("High", 0)),
            "low": float(row.get("Low", 0)),
            "close": float(row.get("Close", 0)),
            "volume": float(row.get("Volume", 0)),
            "open_interest": 0.0,
        })
    return candles


def merge_volume_sources(
    base_candles: List[dict],
    volume_candles: List[dict],
) -> List[dict]:
    """
    Merge volume data from a secondary source into base candles.

    Useful when base data (e.g., Upstox index) has zero volume,
    and volume comes from another source (e.g., yfinance or WebSocket).
    """
    vol_map = {}
    for c in volume_candles:
        ts = c.get("timestamp", "")
        vol = c.get("volume", 0)
        if ts and vol > 0:
            vol_map[ts] = vol

    merged = []
    for c in base_candles:
        candle = dict(c)
        ts = candle.get("timestamp", "")
        if ts in vol_map and float(candle.get("volume", 0)) == 0:
            candle["volume"] = vol_map[ts]
        merged.append(candle)
    return merged
