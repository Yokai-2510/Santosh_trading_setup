"""instrument_selection — choose option contract from filtered expiry chain.

Pure function — no broker calls. Reusable by backtesting.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from data.instrument_filter import resolve_option_contract


def select_entry_contract(
    universe: Dict[str, Any],
    strategy_cfg: Dict[str, Any],
    spot_ltp: float,
) -> Optional[Dict[str, Any]]:
    """
    Resolve the option contract to trade based on:
      - underlying (NIFTY / BANKNIFTY)
      - option_type (CE / PE)
      - strike_mode (ATM / ITM / OTM) + offset
      - spot LTP for ATM determination

    Returns dict with keys: underlying, expiry, spot_instrument_key, contract
    or None if no contract could be resolved.
    """
    instrument_cfg = strategy_cfg.get("instrument_selection", {})
    underlying = str(instrument_cfg.get("underlying", "NIFTY")).upper()
    index_map = universe.get("indices", {})
    underlying_data = index_map.get(underlying)
    if not underlying_data:
        return None

    contract = resolve_option_contract(
        underlying_data=underlying_data,
        option_type=str(instrument_cfg.get("option_type", "CE")).upper(),
        strike_mode=str(instrument_cfg.get("strike_mode", "ATM")).upper(),
        strike_offset=int(instrument_cfg.get("strike_offset", 0)),
        spot_price=float(spot_ltp),
    )
    if not contract:
        return None

    return {
        "underlying": underlying,
        "expiry": underlying_data.get("expiry"),
        "spot_instrument_key": underlying_data.get("spot_instrument_key"),
        "contract": contract,
    }
