"""
brokers.upstox.order_modify_v3 — Modify Order API V3 wrapper.
"""

from __future__ import annotations

from typing import Any, Dict

import requests

_MODIFY_URL = "https://api-hft.upstox.com/v3/order/modify"


def modify_order_v3(
    headers: Dict[str, str],
    order_id: str,
    order_type: str,
    price: float,
    validity: str,
    trigger_price: float = 0.0,
    quantity: int | None = None,
    disclosed_quantity: int = 0,
    timeout: int = 10,
    url: str = _MODIFY_URL,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "order_id": order_id,
        "order_type": order_type,
        "price": float(price),
        "validity": validity,
        "trigger_price": float(trigger_price),
        "disclosed_quantity": int(disclosed_quantity),
    }
    if quantity is not None:
        payload["quantity"] = int(quantity)

    try:
        response = requests.put(url, headers=headers, json=payload, timeout=timeout)
        data = response.json()
        return {
            "success": response.status_code == 200 and data.get("status") == "success",
            "status_code": response.status_code,
            "response": data,
            "order_id": data.get("data", {}).get("order_id"),
            "latency_ms": data.get("metadata", {}).get("latency"),
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "response": {"error": str(exc)},
            "order_id": None,
            "latency_ms": None,
        }
