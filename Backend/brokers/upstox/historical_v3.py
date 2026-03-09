"""
brokers.upstox.historical_v3 — Historical Candle Data API V3 wrapper.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

_BASE_URL = "https://api.upstox.com/v3/historical-candle"


def fetch_historical_candles_v3(
    headers: Dict[str, str],
    instrument_key: str,
    unit: str,
    interval: int,
    to_date: str,
    from_date: Optional[str] = None,
    timeout: int = 20,
    base_url: str = _BASE_URL,
) -> Dict[str, object]:
    encoded_key = quote(instrument_key, safe="")
    interval_str = str(interval)

    if from_date:
        url = f"{base_url}/{encoded_key}/{unit}/{interval_str}/{to_date}/{from_date}"
    else:
        url = f"{base_url}/{encoded_key}/{unit}/{interval_str}/{to_date}"

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        data = response.json()
        ok = response.status_code == 200 and data.get("status") == "success"

        candles: List[dict] = []
        if ok:
            raw_candles = data.get("data", {}).get("candles", [])
            candles = _normalize_candles(raw_candles)

        return {
            "success": ok,
            "status_code": response.status_code,
            "response": data,
            "candles": candles,
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "response": {"error": str(exc)},
            "candles": [],
        }


def _normalize_candles(raw_candles: List[list]) -> List[dict]:
    output: List[dict] = []
    for row in raw_candles:
        if not isinstance(row, list) or len(row) < 7:
            continue
        output.append(
            {
                "timestamp": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "open_interest": float(row[6]),
            }
        )
    output.sort(key=lambda x: _timestamp_sort_key(x["timestamp"]))
    return output


def _timestamp_sort_key(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.min
