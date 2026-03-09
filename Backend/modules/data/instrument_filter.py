"""
instrument_filter — download and filter Upstox master contract for NIFTY/BANKNIFTY.

Only one expiry choice is allowed at runtime: "current" or "next".
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from brokers.upstox.instruments import download_master_contract

SUPPORTED_UNDERLYINGS = ("NIFTY", "BANKNIFTY")


def build_index_option_universe(
    headers: Dict[str, str],
    cache_dir: Path,
    expiry_choice: str,
    timeout_seconds: int = 60,
    force_download: bool = False,
) -> Dict[str, Any]:
    """
    Build filtered option chain universe for current or next expiry only.
    """
    expiry_choice = str(expiry_choice).lower()
    if expiry_choice not in {"current", "next"}:
        raise ValueError("expiry_choice must be 'current' or 'next'")

    cache_dir.mkdir(parents=True, exist_ok=True)
    master_path = cache_dir / "master.json"

    if force_download or not master_path.exists():
        ok = download_master_contract(
            cache_dir=cache_dir,
            headers=headers,
            timeout=timeout_seconds,
            gz_filename="master.json.gz",
            json_filename="master.json",
        )
        if not ok:
            raise RuntimeError("Failed to download Upstox master contract")

    with open(master_path, "r", encoding="utf-8") as file:
        raw = json.load(file)

    df = pd.DataFrame(raw)
    if df.empty:
        raise RuntimeError("Master contract is empty")

    universe = {
        "generated_at_ist": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_choice": expiry_choice,
        "indices": {},
    }

    for underlying in SUPPORTED_UNDERLYINGS:
        data = _build_underlying_universe(df, underlying, expiry_choice)
        if data is not None:
            universe["indices"][underlying] = data

    out_path = cache_dir / "index_option_universe.json"
    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(universe, file, indent=2)
    return universe


def load_cached_universe(universe_path: Path) -> Optional[Dict[str, Any]]:
    if not universe_path.exists():
        return None
    try:
        with open(universe_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def resolve_option_contract(
    underlying_data: Dict[str, Any],
    option_type: str,
    strike_mode: str,
    strike_offset: int,
    spot_price: float,
) -> Optional[Dict[str, Any]]:
    """
    Resolve one contract by ATM/ITM/OTM + offset for CE/PE.
    """
    option_type = str(option_type).upper()
    strike_mode = str(strike_mode).upper()
    if option_type not in {"CE", "PE"}:
        return None
    if strike_mode not in {"ATM", "ITM", "OTM"}:
        strike_mode = "ATM"

    contracts_by_type = underlying_data.get("options", {}).get(option_type, {})
    strikes = sorted(float(x) for x in contracts_by_type.keys())
    if not strikes:
        return None

    atm_index = min(range(len(strikes)), key=lambda idx: abs(strikes[idx] - float(spot_price)))
    target_index = atm_index
    offset = max(0, int(strike_offset))

    if strike_mode != "ATM":
        step = offset
        if strike_mode == "OTM":
            if option_type == "CE":
                target_index = atm_index + step
            else:  # PE OTM is lower strike
                target_index = atm_index - step
        else:  # ITM
            if option_type == "CE":
                target_index = atm_index - step
            else:
                target_index = atm_index + step

    target_index = min(max(target_index, 0), len(strikes) - 1)
    strike = strikes[target_index]
    key = _strike_key(strike)
    return contracts_by_type.get(key)


def _build_underlying_universe(df: pd.DataFrame, underlying: str, expiry_choice: str) -> Optional[Dict[str, Any]]:
    required = {"segment", "instrument_type", "underlying_symbol", "asset_symbol", "expiry"}
    if not required.issubset(set(df.columns)):
        return None

    opt_df = df[
        (df.get("segment") == "NSE_FO")
        & (df.get("instrument_type").isin(["CE", "PE"]))
        & (
            (df.get("underlying_symbol") == underlying)
            | (df.get("asset_symbol") == underlying)
        )
    ].copy()
    if opt_df.empty:
        return None

    opt_df["expiry_dt"] = pd.to_datetime(opt_df["expiry"], unit="ms", errors="coerce").dt.normalize()
    today = pd.Timestamp.now().normalize()
    opt_df = opt_df[opt_df["expiry_dt"] >= today]
    if opt_df.empty:
        return None

    unique_expiries = sorted(d for d in opt_df["expiry_dt"].dropna().unique())
    if not unique_expiries:
        return None

    expiry_idx = 0 if expiry_choice == "current" else 1
    if expiry_idx >= len(unique_expiries):
        return None

    selected_expiry = unique_expiries[expiry_idx]
    exp_df = opt_df[opt_df["expiry_dt"] == selected_expiry].copy()
    if exp_df.empty:
        return None

    options = {"CE": {}, "PE": {}}
    for _, row in exp_df.iterrows():
        option_type = str(row.get("instrument_type", "")).upper()
        strike = float(row.get("strike_price", 0.0))
        if option_type not in options or strike <= 0:
            continue
        payload = {
            "instrument_key": row.get("instrument_key"),
            "exchange_token": str(row.get("exchange_token", "")),
            "trading_symbol": row.get("trading_symbol", ""),
            "strike": strike,
            "lot_size": int(row.get("lot_size", 1)),
            "tick_size": float(row.get("tick_size", 0.05)),
            "expiry": str(pd.Timestamp(selected_expiry).date()),
            "option_type": option_type,
            "underlying": underlying,
        }
        options[option_type][_strike_key(strike)] = payload

    if not options["CE"] and not options["PE"]:
        return None

    return {
        "underlying": underlying,
        "spot_instrument_key": _spot_instrument_key(underlying),
        "expiry": str(pd.Timestamp(selected_expiry).date()),
        "options": options,
    }


def _spot_instrument_key(underlying: str) -> str:
    if underlying == "BANKNIFTY":
        return "NSE_INDEX|Nifty Bank"
    return "NSE_INDEX|Nifty 50"


def _strike_key(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"
