"""
brokers.upstox.instruments — master contract download/decompression.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Optional

import requests

_MASTER_CONTRACT_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


def download_master_contract(
    cache_dir: Path,
    headers: dict,
    timeout: int = 60,
    gz_filename: str = "master.json.gz",
    json_filename: str = "master.json",
    url: Optional[str] = None,
) -> bool:
    fetch_url = url or _MASTER_CONTRACT_URL
    gz_path = cache_dir / gz_filename
    json_path = cache_dir / json_filename

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        response = requests.get(fetch_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        with open(gz_path, "wb") as file:
            file.write(response.content)

        with gzip.open(gz_path, "rt", encoding="utf-8") as gz_file:
            data = json.load(gz_file)

        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(data, file)
        return True
    except Exception:
        return False
