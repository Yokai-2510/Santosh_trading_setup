"""order_builder — order preparation: quantity, price, tick rounding.

Pure functions — no broker calls. Reusable by backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class OrderParams:
    """Fully prepared order ready for execution."""
    instrument_token: str
    trading_symbol: str
    underlying: str
    expiry: str
    option_type: str
    strike: float
    lot_size: int

    transaction_type: str   # BUY or SELL
    quantity: int
    price: Optional[float]  # None for MARKET orders
    order_type: str         # LIMIT, MARKET, SL-M
    product: str            # D, I, CO, OCO
    validity: str           # DAY, IOC
    trigger_price: float
    disclosed_quantity: int
    is_amo: bool
    tick_size: float


def prepare_entry_order(
    contract_selection: Dict[str, Any],
    option_ltp: float,
    strategy_cfg: Dict[str, Any],
) -> Optional[OrderParams]:
    """
    Build entry order parameters from contract selection and strategy config.

    Steps:
      1. Extract instrument details from contract
      2. Calculate quantity (lots * lot_size or raw qty)
      3. Calculate entry price (round to tick)
      4. Build complete OrderParams
    """
    contract = contract_selection.get("contract")
    if not contract:
        return None

    instrument_cfg = strategy_cfg.get("instrument_selection", {})
    order_cfg = strategy_cfg.get("order_execution", {})

    # Quantity calculation
    quantity = calculate_quantity(contract, instrument_cfg)

    # Price calculation
    order_type = str(order_cfg.get("order_type", "LIMIT")).upper()
    tick_size = float(contract.get("tick_size", order_cfg.get("tick_size", 0.05)))
    price = round_to_tick(option_ltp, tick_size) if order_type != "MARKET" else None

    return OrderParams(
        instrument_token=contract["instrument_key"],
        trading_symbol=contract.get("trading_symbol", ""),
        underlying=contract_selection.get("underlying", ""),
        expiry=contract_selection.get("expiry", ""),
        option_type=contract.get("option_type", ""),
        strike=float(contract.get("strike", 0.0)),
        lot_size=int(contract.get("lot_size", 1)),
        transaction_type="BUY",
        quantity=quantity,
        price=price,
        order_type=order_type,
        product=str(order_cfg.get("product", "D")),
        validity=str(order_cfg.get("validity", "DAY")),
        trigger_price=float(order_cfg.get("trigger_price", 0.0)),
        disclosed_quantity=int(order_cfg.get("disclosed_quantity", 0)),
        is_amo=bool(order_cfg.get("is_amo", False)),
        tick_size=tick_size,
    )


def prepare_exit_order(
    instrument_token: str,
    trading_symbol: str,
    quantity: int,
    exit_price: float,
    exit_order_type: str,
    strategy_cfg: Dict[str, Any],
    tick_size: float = 0.05,
) -> OrderParams:
    """Build exit (SELL) order parameters."""
    order_cfg = strategy_cfg.get("order_execution", {})

    price = None
    if exit_order_type == "LIMIT":
        price = round_to_tick(exit_price, tick_size)

    return OrderParams(
        instrument_token=instrument_token,
        trading_symbol=trading_symbol,
        underlying="",
        expiry="",
        option_type="",
        strike=0.0,
        lot_size=0,
        transaction_type="SELL",
        quantity=quantity,
        price=price,
        order_type=exit_order_type,
        product=str(order_cfg.get("product", "D")),
        validity=str(order_cfg.get("validity", "DAY")),
        trigger_price=0.0,
        disclosed_quantity=int(order_cfg.get("disclosed_quantity", 0)),
        is_amo=False,
        tick_size=tick_size,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def calculate_quantity(contract: Dict[str, Any], instrument_cfg: Dict[str, Any]) -> int:
    """Calculate order quantity from lots or raw qty config."""
    mode = str(instrument_cfg.get("quantity_mode", "lots")).lower()
    if mode == "qty":
        return max(1, int(instrument_cfg.get("quantity", 1)))
    lots = max(1, int(instrument_cfg.get("lots", 1)))
    lot_size = max(1, int(contract.get("lot_size", 1)))
    return lots * lot_size


def round_to_tick(price: float, tick_size: float = 0.05) -> float:
    """Round price to nearest tick size."""
    if tick_size <= 0:
        return round(float(price), 2)
    return round(round(float(price) / tick_size) * tick_size, 2)
