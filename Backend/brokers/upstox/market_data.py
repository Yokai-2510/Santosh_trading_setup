"""
brokers.upstox.market_data — LTP market quote calls.
"""

from __future__ import annotations

from typing import Dict, List

import requests

_LTP_URL = "https://api.upstox.com/v3/market-quote/ltp"


def get_ltp(headers: Dict[str, str], instrument_keys: List[str], timeout: int = 10, url: str = _LTP_URL) -> Dict[str, float]:
    if not instrument_keys:
        return {}
    params = {"instrument_key": ",".join(instrument_keys)}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        data = response.json()
        if response.status_code != 200 or data.get("status") != "success":
            return {}

        output: Dict[str, float] = {}
        for key, info in data.get("data", {}).items():
            ltp = info.get("last_price")
            if ltp is None:
                continue
            output[key] = float(ltp)
        return output
    except Exception:
        return {}
