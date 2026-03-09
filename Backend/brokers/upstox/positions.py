"""
brokers.upstox.positions — short-term positions polling.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import requests

_POSITIONS_URL = "https://api.upstox.com/v2/portfolio/short-term-positions"


def get_positions(headers: Dict[str, str], timeout: int = 10, url: str = _POSITIONS_URL) -> Optional[List[dict]]:
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        data = response.json()
        if response.status_code == 200 and data.get("status") == "success":
            return data.get("data", [])
        return None
    except Exception:
        return None
