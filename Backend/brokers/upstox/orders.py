"""
brokers.upstox.orders — order placement and status lookup.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

_ORDER_PLACE_URL = "https://api-hft.upstox.com/v3/order/place"
_ORDER_DETAILS_URL = "https://api.upstox.com/v2/order/details"
_ORDER_CANCEL_URL = "https://api-hft.upstox.com/v3/order/cancel"


def place_order(
    headers: Dict[str, str],
    instrument_token: str,
    quantity: int,
    transaction_type: str,
    order_cfg: Dict[str, Any],
    price: Optional[float] = None,
    timeout: int = 10,
    url: str = _ORDER_PLACE_URL,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "instrument_token": instrument_token,
        "quantity": int(quantity),
        "product": order_cfg.get("product", "D"),
        "validity": order_cfg.get("validity", "DAY"),
        "order_type": order_cfg.get("order_type", "LIMIT"),
        "transaction_type": transaction_type,
        "disclosed_quantity": int(order_cfg.get("disclosed_quantity", 0)),
        "trigger_price": float(order_cfg.get("trigger_price", 0.0)),
        "is_amo": bool(order_cfg.get("is_amo", False)),
        "slice": True,
    }

    if price is not None:
        payload["price"] = float(price)

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        data = response.json()
        ok = response.status_code == 200 and data.get("status") == "success"
        order_ids = data.get("data", {}).get("order_ids", [])
        return {
            "success": ok,
            "status_code": response.status_code,
            "response": data,
            "order_id": order_ids[0] if order_ids else None,
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "response": {"error": str(exc)},
            "order_id": None,
        }


def get_order_status(
    headers: Dict[str, str],
    order_id: str,
    timeout: int = 10,
    url: str = _ORDER_DETAILS_URL,
) -> Dict[str, Any]:
    try:
        response = requests.get(url, headers=headers, params={"order_id": order_id}, timeout=timeout)
        data = response.json()
        order_data = data.get("data")

        # Upstox may return an object or list depending on endpoint evolution.
        if isinstance(order_data, list) and order_data:
            order_data = order_data[0]

        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": data,
            "data": order_data if isinstance(order_data, dict) else {},
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "response": {"error": str(exc)},
            "data": {},
        }


def cancel_order(
    headers: Dict[str, str],
    order_id: str,
    timeout: int = 10,
    url: str = _ORDER_CANCEL_URL,
) -> Dict[str, Any]:
    try:
        response = requests.delete(url, headers=headers, json={"order_id": order_id}, timeout=timeout)
        data = response.json()
        return {
            "success": response.status_code == 200 and data.get("status") == "success",
            "status_code": response.status_code,
            "response": data,
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": 0,
            "response": {"error": str(exc)},
        }
