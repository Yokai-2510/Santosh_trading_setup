"""
Sample option universe for tests.
"""

from __future__ import annotations

from typing import Any, Dict


def make_nifty_universe(spot: float = 22450.0, expiry: str = "2025-07-03") -> Dict[str, Any]:
    """Minimal NIFTY universe with strikes 22000-22900 in 50pt steps."""
    ce_options = {}
    pe_options = {}
    for strike in range(22000, 22950, 50):
        base = {
            "instrument_key": f"NSE_FO|NIFTY{expiry.replace('-', '')}C{strike}" if True else "",
            "exchange_token": str(strike),
            "trading_symbol": f"NIFTY {expiry} {strike} CE",
            "strike": float(strike),
            "lot_size": 50,
            "tick_size": 0.05,
            "expiry": expiry,
            "option_type": "CE",
            "underlying": "NIFTY",
        }
        ce_options[str(strike)] = base

        pe = dict(base)
        pe["instrument_key"] = f"NSE_FO|NIFTY{expiry.replace('-', '')}P{strike}"
        pe["trading_symbol"] = f"NIFTY {expiry} {strike} PE"
        pe["option_type"] = "PE"
        pe_options[str(strike)] = pe

    return {
        "generated_at_ist": "2025-07-01 09:00:00",
        "expiry_choice": "current",
        "indices": {
            "NIFTY": {
                "underlying": "NIFTY",
                "spot_instrument_key": "NSE_INDEX|Nifty 50",
                "expiry": expiry,
                "options": {"CE": ce_options, "PE": pe_options},
            }
        },
    }
